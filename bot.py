"""
Telegram VPS Manager Bot — VishalCloud UI/UX Edition.

Features added on top of the original engine:
  • Bilingual UI (English decorative style + हिंदी) with /language switcher
  • Real "Home" hub with time balance + full inline navigation everywhere
  • Paginated My-VPS cards (multi-VPS ready), per-VPS action keys
  • Step progress during deploy (non-blocking async executor)
  • Alerts: new-user admin alert, container-down watchdog (owner + admin)
  • Localized expiry / invite / action feedback messages
"""
import logging
import asyncio
import html
import random
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from telegram.constants import ParseMode

import config
import database as db
import vps_manager
import security
import monitor
import colored_buttons as cb
import i18n as ui

# ============ Global cache ============
_bot_username: str = None  # cached once in post_init
# watchdog state: container_id -> [consecutive down checks, notified flag]
_down_state: dict[str, list] = {}
# users with a deploy currently in progress (double-tap guard)
_creating: set = set()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ============ Helpers ============

def is_admin(user_id: int) -> bool:
    return user_id == config.ADMIN_ID


def get_invite_link(user_id: int) -> str:
    return f"https://t.me/{_bot_username}?start=invite_{user_id}"


def esc(value) -> str:
    """HTML-escape a display value."""
    return html.escape(str(value), quote=False)


def format_time(seconds: int) -> str:
    if seconds <= 0:
        return "0s"
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    mins = (seconds % 3600) // 60
    if days > 0:
        return f"{days}ᴅ {hours}ʜ {mins}ᴍ"
    elif hours > 0:
        return f"{hours}ʜ {mins}ᴍ"
    else:
        return f"{mins}ᴍ"


def _bar(percent: float, length: int = 10) -> str:
    """Small text progress bar: ▰▰▱▱… (clamped 0-100)."""
    if percent is None:
        return "▱" * length
    percent = max(0.0, min(100.0, float(percent)))
    filled = int(round(percent / 100.0 * length))
    return "▰" * filled + "▱" * (length - filled)


def _page_of(context: ContextTypes.DEFAULT_TYPE, default: int = 0) -> int:
    return int(context.user_data.get("vps_page", default) or default)


def _set_page(context: ContextTypes.DEFAULT_TYPE, page: int):
    context.user_data["vps_page"] = max(0, page)


# ============ Inline Keyboard Builders (bilingual) ============

def _main_kb(lang: str, user_id: int) -> list:
    """Full home-hub keyboard — success=green actions, primary=blue nav, danger=red admin."""
    keyboard = [
        [
            cb.styled_button(ui.lbl(lang, "create"), callback_data="menu_create", style="success"),
            cb.styled_button(ui.lbl(lang, "myvps"), callback_data="menu_myvps", style="primary"),
        ],
        [
            cb.styled_button(ui.lbl(lang, "dashboard"), callback_data="menu_dashboard", style="primary"),
            cb.styled_button(ui.lbl(lang, "invite"), callback_data="menu_invite", style="success"),
        ],
        [
            cb.styled_button(ui.lbl(lang, "plans"), callback_data="menu_plans", style="primary"),
            cb.styled_button(ui.lbl(lang, "help"), callback_data="menu_help", style="primary"),
        ],
    ]
    if is_admin(user_id):
        keyboard.append([
            cb.styled_button(ui.lbl(lang, "admin"), callback_data="menu_admin", style="danger"),
            cb.styled_button(ui.lbl(lang, "analytics"), callback_data="menu_analytics", style="primary"),
        ])
    keyboard.append([cb.styled_button(ui.lbl(lang, "language"), callback_data="menu_language", style="primary")])
    return keyboard


def _vps_kb(lang: str, short_id: str, page: int, total: int, sid: str = None) -> list:
    """Per-VPS action keyboard: stats=blue, restart=green, delete=red, back=grey."""
    sid = sid or short_id
    keyboard = [
        [
            cb.styled_button(ui.lbl(lang, "live_stats"), callback_data=f"action_stats_{sid}", style="primary"),
            cb.styled_button(ui.lbl(lang, "restart"), callback_data=f"action_restart_{sid}", style="success"),
        ],
        [
            cb.styled_button(ui.lbl(lang, "delete"), callback_data=f"action_del_{sid}", style="danger"),
            cb.styled_button(ui.lbl(lang, "back"), callback_data="menu_back"),
        ],
    ]
    if total > 1:
        keyboard.insert(0, [
            cb.styled_button(ui.lbl(lang, "prev"), callback_data="myvps_prev", style="primary"),
            cb.styled_button(f"{page + 1}/{total}", callback_data="noop", style="primary"),
            cb.styled_button(ui.lbl(lang, "next"), callback_data="myvps_next", style="primary"),
        ])
    return keyboard


def _lang_kb(lang: str) -> list:
    keyboard = [
        [
            cb.styled_button(f"🇬🇧 English{'  ✓' if lang == 'en' else ''}", callback_data="lang_set_en",
                             style="success" if lang == "en" else "primary"),
            cb.styled_button(f"🇮🇳 हिंदी{'  ✓' if lang == 'hi' else ''}", callback_data="lang_set_hi",
                             style="success" if lang == "hi" else "primary"),
        ],
        [cb.styled_button(ui.lbl(lang, "back"), callback_data="menu_back")],
    ]
    return keyboard


def _back_kb(lang: str) -> list:
    # neutral grey "back" — colored styles reserved for real actions
    return [[cb.styled_button(ui.lbl(lang, "back"), callback_data="menu_back")]]


async def _emit(chat_id, message_id, text, kb, edit=True, send_fallback=True):
    """Try to edit `message_id`; else send a fresh message. Returns final message_id or None."""
    if edit and message_id:
        ok = await cb.edit_message_colored(chat_id, message_id, text=text, reply_markup=kb)
        if ok:
            return message_id
        if not send_fallback:
            return None
    sent = await cb.send_message_colored(chat_id, text=text, reply_markup=kb)
    if sent:
        return sent.get("message_id")
    return None


# ============ Private Chat Only + Force Join ============

async def private_only(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Block bot from responding in groups. Only private DM."""
    if update.effective_chat.type != "private":
        return False
    return True


async def check_force_join(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Check if user has joined all required channels. Result cached 5 min."""
    if not config.FORCE_JOIN_CHANNELS:
        return True

    user_id = update.effective_user.id
    if is_admin(user_id):
        return True

    # Check cache first
    cached = security.get_force_join_cache(user_id)
    if cached is True:
        return True

    not_joined = []
    for channel in config.FORCE_JOIN_CHANNELS:
        try:
            member = await context.bot.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status in ["left", "kicked"]:
                not_joined.append(channel)
        except Exception:
            not_joined.append(channel)

    if not_joined:
        security.set_force_join_cache(user_id, False)
        buttons = []
        for ch in not_joined:
            ch_name = ch.replace("@", "")
            buttons.append([InlineKeyboardButton(f"ᴊᴏɪɴ {ch}", url=f"https://t.me/{ch_name}")])
        buttons.append([InlineKeyboardButton("✓ ᴅᴏɴᴇ — ᴄʜᴇᴄᴋ ᴀɢᴀɪɴ", callback_data="check_join")])
        await update.message.reply_text(
            "◈ <b>ᴊᴏɪɴ ʀᴇǫᴜɪʀᴇᴅ!</b>\n\n"
            "ʏᴏᴜ ᴍᴜsᴛ ᴊᴏɪɴ ᴏᴜʀ ᴄʜᴀɴɴᴇʟ(s) ᴛᴏ ᴜsᴇ ᴛʜɪs ʙᴏᴛ:\n",
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=ParseMode.HTML,
        )
        return False

    security.set_force_join_cache(user_id, True)
    return True


# ============ Security Middleware ============

async def security_check(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    # Private chat only
    if not await private_only(update, context):
        return False
    # Force join check
    if not await check_force_join(update, context):
        return False

    user_id = update.effective_user.id
    if is_admin(user_id):
        return True
    is_banned, reason = await security.is_user_banned(user_id)
    if is_banned:
        await update.message.reply_text(
            f"⊘ <b>ʏᴏᴜ ᴀʀᴇ ʙᴀɴɴᴇᴅ!</b>\nʀᴇᴀsᴏɴ: {esc(reason)}",
            parse_mode=ParseMode.HTML,
        )
        return False
    if not security.check_rate_limit(user_id):
        await update.message.reply_text("△ ᴛᴏᴏ ᴍᴀɴʏ ʀᴇǫᴜᴇsᴛs. ᴡᴀɪᴛ 1 ᴍɪɴᴜᴛᴇ.")
        await security.log_security_event(user_id, "RATE_LIMIT", "Rate limit hit")
        return False
    return True


# ============ Background Tasks ============

async def auto_delete_expired_vps(app: Application):
    while True:
        try:
            expired_list = await db.get_expired_vps()
            for vps in expired_list:
                vps_manager.stop_vps(vps["container_id"])
                await db.remove_vps_instance(vps["container_id"])
                await security.log_security_event(
                    vps["user_id"], "VPS_EXPIRED", f"Auto-deleted: {vps['container_name']}"
                )
                try:
                    owner_lang = await db.get_user_lang(vps["user_id"])
                    await app.bot.send_message(
                        chat_id=vps["user_id"],
                        text=ui.msg(owner_lang, "expiry_notice"),
                        parse_mode=ParseMode.HTML,
                    )
                except Exception:
                    pass
                logger.info(f"Expired VPS deleted: {vps['container_name']}")
        except Exception as e:
            logger.error(f"Auto-delete error: {e}")
        await asyncio.sleep(300)


async def container_watchdog(app: Application):
    """
    Advanced uptime alert: if a container that DB says is 'running' is
    actually not running, notify the owner (localized) + admin after
    2 consecutive checks. Re-alerts on a fresh outage episode.
    """
    await asyncio.sleep(random.uniform(0, 60))  # stagger vs other loops
    while True:
        try:
            running = await db.get_all_running_vps()
            live_ids = set()
            for vps in running:
                sid = vps["container_id"]
                live_ids.add(sid)
                try:
                    status = vps_manager.get_container_status(sid)
                except Exception:
                    status = "unknown"

                if status == "running":
                    _down_state.pop(sid, None)
                    continue

                strikes, notified = _down_state.get(sid, [0, False])
                strikes += 1
                if strikes >= 2 and not notified:
                    _down_state[sid] = [strikes, True]
                    uid = vps["user_id"]
                    # Owner alert (localized)
                    try:
                        owner_lang = await db.get_user_lang(uid)
                        await app.bot.send_message(
                            chat_id=uid,
                            text=ui.msg(owner_lang, "down_owner", name=esc(vps["container_name"])),
                            parse_mode=ParseMode.HTML,
                        )
                    except Exception:
                        pass
                    # Admin alert
                    try:
                        await app.bot.send_message(
                            chat_id=config.ADMIN_ID,
                            text=ui.msg(
                                "en", "down_admin",
                                uid=esc(uid),
                                name=esc(vps["container_name"]),
                                port=vps.get("ssh_port", "?"),
                            ),
                            parse_mode=ParseMode.HTML,
                        )
                    except Exception:
                        pass
                    await security.log_security_event(uid, "VPS_DOWN", vps["container_name"])
                    logger.warning(f"VPS down alert: {vps['container_name']} (user {uid})")
                else:
                    _down_state[sid] = [strikes, notified]

            # Forget containers that no longer exist in DB
            for sid in [s for s in _down_state if s not in live_ids]:
                _down_state.pop(sid, None)
        except Exception as e:
            logger.error(f"Watchdog error: {e}")
        await asyncio.sleep(120)


async def monitor_containers(app: Application):
    """Monitor containers every 5 min. Auto-ban mining. Notify owner on ban."""
    # Track consecutive high CPU hits per user (need 2 hits = confirmed mining)
    cpu_strikes: dict[int, int] = {}

    await asyncio.sleep(random.uniform(0, 60))  # stagger vs other loops
    while True:
        try:
            all_vps = await db.get_all_running_vps()
            for vps in all_vps:
                user_id = vps["user_id"]
                stats = vps_manager.get_container_stats(vps["container_id"])
                if not stats:
                    continue

                # ===== MINING DETECTION =====
                # High CPU (>85%) for 2 consecutive checks = auto ban
                if stats["cpu_percent"] > 85:
                    cpu_strikes[user_id] = cpu_strikes.get(user_id, 0) + 1

                    if cpu_strikes[user_id] == 1:
                        # First strike: warn admin
                        try:
                            await app.bot.send_message(
                                chat_id=config.ADMIN_ID,
                                text=(
                                    f"△ <b>ʜɪɢʜ ᴄᴘᴜ ᴡᴀʀɴɪɴɢ</b>\n\n"
                                    f"ᴜsᴇʀ: <code>{user_id}</code>\n"
                                    f"ᴠᴘs: {vps['container_name']}\n"
                                    f"ᴄᴘᴜ: {stats['cpu_percent']}%\n"
                                    f"ᴘɪᴅs: {stats['pids']}\n\n"
                                    f"◌ ɴᴇxᴛ ʜɪᴛ = ᴀᴜᴛᴏ-ʙᴀɴ"
                                ),
                                parse_mode=ParseMode.HTML,
                            )
                        except Exception:
                            pass

                    elif cpu_strikes[user_id] >= 2:
                        # Second strike: AUTO BAN + kill VPS + notify
                        await security.report_abuse(
                            user_id, vps["container_id"],
                            "MINING_DETECTED", f"CPU: {stats['cpu_percent']}% (2 strikes)", auto=True,
                        )

                        # Kill VPS
                        vps_manager.force_kill_container(vps["container_id"])
                        await db.remove_vps_instance(vps["container_id"])

                        # Ban user
                        await security.ban_user(user_id, "ᴀᴜᴛᴏ-ʙᴀɴ: ᴄʀʏᴘᴛᴏ ᴍɪɴɪɴɢ ᴅᴇᴛᴇᴄᴛᴇᴅ", hours=config.BAN_DURATION_HOURS)

                        # Notify user (banned)
                        try:
                            await app.bot.send_message(
                                chat_id=user_id,
                                text=(
                                    "⊘ <b>ʏᴏᴜ ʜᴀᴠᴇ ʙᴇᴇɴ ʙᴀɴɴᴇᴅ!</b>\n\n"
                                    "⊘ ʀᴇᴀsᴏɴ: ᴄʀʏᴘᴛᴏ ᴍɪɴɪɴɢ ᴅᴇᴛᴇᴄᴛᴇᴅ\n"
                                    f"◔ ᴅᴜʀᴀᴛɪᴏɴ: {config.BAN_DURATION_HOURS} ʜᴏᴜʀs\n"
                                    "⊘ ʏᴏᴜʀ ᴠᴘs ʜᴀs ʙᴇᴇɴ ᴛᴇʀᴍɪɴᴀᴛᴇᴅ.\n\n"
                                    "ᴍɪɴɪɴɢ ɪs sᴛʀɪᴄᴛʟʏ ᴘʀᴏʜɪʙɪᴛᴇᴅ."
                                ),
                                parse_mode=ParseMode.HTML,
                            )
                        except Exception:
                            pass

                        # Notify admin (confirmed ban)
                        try:
                            await app.bot.send_message(
                                chat_id=config.ADMIN_ID,
                                text=(
                                    f"● <b>ᴀᴜᴛᴏ-ʙᴀɴ ᴇxᴇᴄᴜᴛᴇᴅ</b>\n\n"
                                    f"ᴜsᴇʀ: <code>{user_id}</code>\n"
                                    f"ᴠᴘs: {vps['container_name']}\n"
                                    f"ᴄᴘᴜ: {stats['cpu_percent']}%\n"
                                    f"ʀᴇᴀsᴏɴ: ᴄʀʏᴘᴛᴏ ᴍɪɴɪɴɢ (2 sᴛʀɪᴋᴇs)\n\n"
                                    f"ᴠᴘs ᴛᴇʀᴍɪɴᴀᴛᴇᴅ + ᴜsᴇʀ ʙᴀɴɴᴇᴅ {config.BAN_DURATION_HOURS}ʜ\n"
                                    f"/unban {user_id}"
                                ),
                                parse_mode=ParseMode.HTML,
                            )
                        except Exception:
                            pass

                        # Reset strikes
                        cpu_strikes.pop(user_id, None)
                        logger.warning(f"AUTO-BAN: User {user_id} - Mining detected")

                else:
                    # CPU normal, reset strikes
                    cpu_strikes.pop(user_id, None)

                # ===== PROCESS BOMB DETECTION =====
                if stats["pids"] > 90:
                    vps_manager.force_kill_container(vps["container_id"])
                    await db.remove_vps_instance(vps["container_id"])
                    await security.ban_user(user_id, "ᴀᴜᴛᴏ-ʙᴀɴ: ᴘʀᴏᴄᴇss ʙᴏᴍʙ ᴅᴇᴛᴇᴄᴛᴇᴅ", hours=config.BAN_DURATION_HOURS)

                    try:
                        await app.bot.send_message(
                            chat_id=user_id,
                            text=(
                                "⊘ <b>ʏᴏᴜ ʜᴀᴠᴇ ʙᴇᴇɴ ʙᴀɴɴᴇᴅ!</b>\n\n"
                                "⊘ ʀᴇᴀsᴏɴ: ᴘʀᴏᴄᴇss ʙᴏᴍʙ / ғᴏʀᴋ ʙᴏᴍʙ\n"
                                f"◔ ᴅᴜʀᴀᴛɪᴏɴ: {config.BAN_DURATION_HOURS} ʜᴏᴜʀs\n"
                                "⊘ ᴠᴘs ᴛᴇʀᴍɪɴᴀᴛᴇᴅ."
                            ),
                            parse_mode=ParseMode.HTML,
                        )
                    except Exception:
                        pass

                    try:
                        await app.bot.send_message(
                            chat_id=config.ADMIN_ID,
                            text=(
                                f"● <b>ᴀᴜᴛᴏ-ʙᴀɴ: ғᴏʀᴋ ʙᴏᴍʙ</b>\n"
                                f"ᴜsᴇʀ: <code>{user_id}</code>\n"
                                f"ᴘɪᴅs: {stats['pids']}\n"
                                f"/unban {user_id}"
                            ),
                            parse_mode=ParseMode.HTML,
                        )
                    except Exception:
                        pass

        except Exception as e:
            logger.error(f"Monitor error: {e}")
        await asyncio.sleep(300)  # Check every 5 minutes


async def ddos_outbound_watchdog(app: Application):
    """
    DDoS OUTBOUND FLOOD protection:
      • Har container ka outbound rate sample hota hai (default 60s).
      • OUTBOUND_LIMIT_MBPS se zyada (2 consecutive checks) =
        container force-kill + user auto-ban  => traffic turant band.
      • 1st hit = warning admin + owner; 2nd hit = block.
    """
    strikes: dict[int, int] = {}
    await asyncio.sleep(random.uniform(0, 60))  # stagger vs other loops
    while True:
        try:
            all_vps = await db.get_all_running_vps()
            for vps in all_vps:
                user_id = vps["user_id"]
                rate = vps_manager.get_net_rate_mbps(vps["container_id"])
                if not rate:
                    continue
                tx = rate["tx_mbps"]
                limit = config.OUTBOUND_LIMIT_MBPS

                if tx > limit:
                    strikes[user_id] = strikes.get(user_id, 0) + 1
                    if strikes[user_id] == 1:
                        # First hit: warn admin + owner
                        try:
                            await app.bot.send_message(
                                chat_id=config.ADMIN_ID,
                                text=(
                                    f"△ <b>ʜɪɢʜ ᴏᴜᴛʙᴏᴜɴᴅ ᴛʀᴀғғɪᴄ ᴡᴀʀɴɪɴɢ</b>\n\n"
                                    f"ᴜsᴇʀ: <code>{user_id}</code>\n"
                                    f"ᴠᴘs: {vps['container_name']}\n"
                                    f"ᴏᴜᴛʙᴏᴜɴᴅ: {tx} ᴍʙᴘs (ʟɪᴍɪᴛ {limit})\n\n"
                                    f"◌ ɴᴇxᴛ ʜɪᴛ = ᴀᴜᴛᴏ-ʙʟᴏᴄᴋ + ʙᴀɴ"
                                ),
                                parse_mode=ParseMode.HTML,
                            )
                        except Exception:
                            pass
                        try:
                            await app.bot.send_message(
                                chat_id=user_id,
                                text=(
                                    f"△ <b>ʜɪɢʜ ᴏᴜᴛʙᴏᴜɴᴅ ᴛʀᴀғғɪᴄ!</b>\n\n"
                                    f"ʏᴏᴜʀ ᴠᴘs: {vps['container_name']}\n"
                                    f"ᴏᴜᴛ: {tx} ᴍʙᴘs / ʟɪᴍɪᴛ: {limit} ᴍʙᴘs\n\n"
                                    f"◌ ᴅᴅᴏs/ᴀʙᴜsᴇ ᴅᴇᴛᴇᴄᴛ ʜᴜᴀ ᴛᴏ ᴠᴘs ʙʟᴏᴄᴋ + ʙᴀɴ. ʙᴀɴᴅᴡɪᴅᴛʜ ᴋᴀᴍ ᴋᴀʀᴏ."
                                ),
                                parse_mode=ParseMode.HTML,
                            )
                        except Exception:
                            pass
                        await security.log_security_event(user_id, "OUTBOUND_WARN", f"{tx} Mbps")
                    elif strikes[user_id] >= 2:
                        # Second consecutive hit: BLOCK traffic + BAN user
                        vps_manager.force_kill_container(vps["container_id"])
                        vps_manager.reset_net_cache(vps["container_id"])
                        await db.remove_vps_instance(vps["container_id"])
                        await security.ban_user(
                            user_id,
                            f"AUTO-BAN: outbound flood {tx} Mbps (limit {limit})",
                            hours=config.BAN_DURATION_HOURS,
                        )
                        try:
                            await app.bot.send_message(
                                chat_id=user_id,
                                text=(
                                    "⊘ <b>ʏᴏᴜ ʜᴀᴠᴇ ʙᴇᴇɴ ʙᴀɴɴᴇᴅ!</b>\n\n"
                                    "⊘ ʀᴇᴀsᴏɴ: ᴅᴅᴏs / ᴏᴜᴛʙᴏᴜɴᴅ ғʟᴏᴏᴅ ᴅᴇᴛᴇᴄᴛᴇᴅ\n"
                                    f"◔ ᴅᴜʀᴀᴛɪᴏɴ: {config.BAN_DURATION_HOURS} ʜᴏᴜʀs\n"
                                    "⊘ ʏᴏᴜʀ ᴠᴘs ᴛᴇʀᴍɪɴᴀᴛᴇᴅ."
                                ),
                                parse_mode=ParseMode.HTML,
                            )
                        except Exception:
                            pass
                        try:
                            await app.bot.send_message(
                                chat_id=config.ADMIN_ID,
                                text=(
                                    f"● <b>ᴀᴜᴛᴏ-ʙʟᴏᴄᴋ: ᴏᴜᴛʙᴏᴜɴᴅ ғʟᴏᴏᴅ</b>\n\n"
                                    f"ᴜsᴇʀ: <code>{user_id}</code>\n"
                                    f"ᴠᴘs: {vps['container_name']}\n"
                                    f"ᴏᴜᴛ: {tx} ᴍʙᴘs (ʟɪᴍɪᴛ {limit})\n\n"
                                    f"ᴠᴘs ᴋɪʟʟᴇᴅ + ʙᴀɴɴᴇᴅ {config.BAN_DURATION_HOURS}ʜ\n"
                                    f"/unban {user_id}"
                                ),
                                parse_mode=ParseMode.HTML,
                            )
                        except Exception:
                            pass
                        await security.log_security_event(user_id, "OUTBOUND_BLOCK",
                                                          f"{tx} Mbps flood")
                        strikes.pop(user_id, None)
                        logger.warning(f"AUTO-BLOCK: User {user_id} outbound flood {tx} Mbps")
                else:
                    # Under the limit -> reset strikes
                    strikes.pop(user_id, None)
        except Exception as e:
            logger.error(f"Outbound watchdog error: {e}")
        await asyncio.sleep(config.OUTBOUND_CHECK_INTERVAL)


# ============ Screen Builders (single source of truth for UI) ============

async def _card_text(vps: dict, user_id: int, lang: str, page: int, total: int) -> str:
    """Full VPS card message: status, credentials, specs, live bars, invites."""
    sid = vps["container_id"]
    status = vps_manager.get_container_status(sid)
    status_emoji = "🟢" if status == "running" else "🔴"
    status_label = ui.lbl(lang, "running") if status == "running" else ui.lbl(lang, "stopped")

    remaining = await db.get_remaining_seconds(user_id)
    started_at = datetime.fromisoformat(vps["started_at"])
    used = int((datetime.now() - started_at).total_seconds())
    time_left = max(0, remaining - used)
    invite_count = await db.get_invite_count(user_id)
    server_ip = config.SERVER_IP

    lines = []
    if total > 1:
        lines.append(ui.msg(lang, "myvps_page_hdr", cur=page + 1, total=total))
    else:
        lines.append("🖥 <b>" + (ui.lbl(lang, "myvps")).split(" ", 1)[-1].upper() + "</b>")
        lines.append("─────────────────────")
    lines.append("")
    lines.append(f"{status_emoji} <code>{esc(vps['container_name'])}</code>  •  {status_label}")
    lines.append("")
    lines.append("┌ 🔌 <b>ᴄᴏɴɴᴇᴄᴛɪᴏɴ</b>")
    lines.append(f"│ <code>ssh {esc(vps.get('ssh_user', 'user'))}@{server_ip} -p {vps['ssh_port']}</code>")
    lines.append(f"│ {ui.lbl(lang, 'user')} : <code>{esc(vps.get('ssh_user', 'user'))}</code>")
    lines.append(f"│ {ui.lbl(lang, 'pass')} : <code>{esc(vps['ssh_password'])}</code>")
    lines.append(f"│ {ui.lbl(lang, 'ip')}   : <code>{server_ip}</code>")
    lines.append(f"│ {ui.lbl(lang, 'port')} : <code>{vps['ssh_port']}</code>")
    lines.append("└─────────────────────")
    lines.append("")
    lines.append("┌ ⚙️ <b>sᴘᴇᴄs</b>")
    lines.append(f"│ {ui.lbl(lang, 'ram')}  : {vps['ram']}")
    lines.append(f"│ {ui.lbl(lang, 'cpu')}  : {vps['cpu']} {ui.lbl(lang, 'cpu_core')}")
    lines.append(f"│ {ui.lbl(lang, 'time')} : <b>{format_time(time_left)}</b>")

    try:
        stats = vps_manager.get_container_stats(sid)
    except Exception:
        stats = None
    if stats:
        ram_pct = (stats["memory_used_mb"] / stats["memory_limit_mb"] * 100) if stats.get("memory_limit_mb") else 0
        lines.append("│")
        lines.append(f"│ ⚡ CPU: {stats['cpu_percent']}%  {_bar(stats['cpu_percent'])}")
        lines.append(f"│ 💾 RAM: {stats['memory_used_mb']}/{stats['memory_limit_mb']}MB  {_bar(ram_pct)}")
        lines.append(f"│ {ui.lbl(lang, 'pids')} : {stats['pids']}")
    lines.append("└─────────────────────")
    lines.append("")
    lines.append("┌ <b>" + ui.lbl(lang, "invites") + "</b>")
    lines.append(f"│ {ui.lbl(lang, 'total')} : {invite_count}  (+{invite_count} " + (ui.lbl(lang, "days")).lower() + ")")
    lines.append("└─────────────────────")
    return "\n".join(lines)


async def show_home(chat_id, message_id, user_id, lang, edit=True):
    remaining = await db.get_remaining_seconds(user_id)
    text = ui.msg(lang, "home", time=format_time(remaining), uid=user_id)
    await _emit(chat_id, message_id, text, _main_kb(lang, user_id), edit=edit)


async def show_language(chat_id, message_id, user_id, lang, edit=True):
    text = ui.msg(lang, "lang_title")
    await _emit(chat_id, message_id, text, _lang_kb(lang), edit=edit)


async def show_myvps(chat_id, message_id, user_id, lang, page=0, edit=True, context=None):
    vps_list = await db.get_all_user_vps(user_id)
    if not vps_list:
        remaining = await db.get_remaining_seconds(user_id)
        text = ui.msg(lang, "myvps_none", time=format_time(remaining))
        kb = [
            [cb.styled_button(ui.lbl(lang, "create_go"), callback_data="menu_create", style="success")],
            [cb.styled_button(ui.lbl(lang, "back"), callback_data="menu_back", style="primary")],
        ]
        await _emit(chat_id, message_id, text, kb, edit=edit)
        return
    total = len(vps_list)
    page = max(0, min(page, total - 1))
    if context:
        _set_page(context, page)
    vps = vps_list[page]
    text = await _card_text(vps, user_id, lang, page, total)
    short = vps["container_id"][:12]
    kb = _vps_kb(lang, short, page, total)
    await _emit(chat_id, message_id, text, kb, edit=edit)


async def show_invite(chat_id, message_id, user_id, lang, edit=True):
    invite_count, remaining = await asyncio.gather(
        db.get_invite_count(user_id),
        db.get_remaining_seconds(user_id),
    )
    invite_link = get_invite_link(user_id)
    text = ui.msg(
        lang, "invite",
        link=invite_link,
        max_inv=config.MAX_INVITES_PER_DAY,
        count=invite_count,
        balance=format_time(remaining),
    )
    kb = [
        [cb.styled_button(ui.lbl(lang, "share"),
                          url=f"https://t.me/share/url?url={invite_link}&text=Get+Free+VPS!",
                          style="success")],
        [cb.styled_button(ui.lbl(lang, "back"), callback_data="menu_back", style="primary")],
    ]
    await _emit(chat_id, message_id, text, kb, edit=edit)


async def show_plans(chat_id, message_id, user_id, lang, edit=True):
    current_plan = await db.get_user_plan(user_id)
    text = ui.msg(lang, "plans_hdr") + "\n\n"
    for key, plan in config.VPS_PLANS.items():
        active = ui.msg(lang, "plan_active") if key == current_plan else ""
        price = ui.lbl(lang, "free") if plan["price"] == 0 else f"₹{plan['price']}"
        days = plan["time_seconds"] // 86400
        icon = "🟢" if key == current_plan else "⚪"
        text += (
            f"{icon} <b>{esc(plan['name'])}</b>{active}\n"
            f"┌─────────────────────\n"
            f"│ {ui.lbl(lang, 'ram')}  : {plan['ram']}\n"
            f"│ {ui.lbl(lang, 'cpu')}  : {plan['cpu']} {ui.lbl(lang, 'cpu_core')}\n"
            f"│ {ui.lbl(lang, 'time')} : {days} {ui.lbl(lang, 'days')}\n"
            f"│ {ui.lbl(lang, 'price')}: {price}\n"
            f"└─────────────────────\n\n"
        )
    text += ui.msg(lang, "plan_upgrade")

    # Paid plans ke liye buy buttons — tap = QR payment flow
    kb = []
    for key, plan in config.VPS_PLANS.items():
        if plan["price"] > 0 and key != current_plan:
            kb.append([cb.styled_button(
                f"💳 ʙᴜʏ {esc(plan['name'])} — ₹{plan['price']}",
                callback_data=f"pay_buy_{key}", style="success")])
    kb.append([cb.styled_button(ui.lbl(lang, "back"), callback_data="menu_back")])
    await _emit(chat_id, message_id, text, kb, edit=edit)


async def show_dashboard(chat_id, message_id, user_id, lang, edit=True):
    report = await monitor.get_usage_report(user_id)
    if report:
        await _emit(chat_id, message_id, report, _back_kb(lang), edit=edit)
    else:
        remaining = await db.get_remaining_seconds(user_id)
        text = ui.msg(lang, "myvps_none", time=format_time(remaining))
        kb = [[cb.styled_button(ui.lbl(lang, "create_go"), callback_data="menu_create", style="success")],
              _back_kb(lang)[0]]
        await _emit(chat_id, message_id, text, kb, edit=edit)


async def show_help(chat_id, message_id, user_id, lang, edit=True):
    text = ui.msg(lang, "help_title") + "\n\n"
    text += ui.msg(lang, "help_user_hdr") + ui.HELP_USER[lang] + "\n\n"
    text += ui.msg(lang, "help_free_hdr") + ui.HELP_FREE[lang].format(
        ram=config.DEFAULT_RAM, cpu=config.DEFAULT_CPU,
        days=config.VPS_DURATION_DAYS, bw=config.BANDWIDTH_LIMIT_MB,
    ) + "\n\n"
    text += ui.msg(lang, "help_rules_hdr") + ui.HELP_RULES[lang]
    if is_admin(user_id):
        text += ui.HELP_ADMIN
    kb = [
        [cb.styled_button(ui.lbl(lang, "create"), callback_data="menu_create", style="success"),
         cb.styled_button(ui.lbl(lang, "myvps"), callback_data="menu_myvps", style="primary")],
        [cb.styled_button(ui.lbl(lang, "language"), callback_data="menu_language", style="primary")],
        _back_kb(lang)[0],
    ]
    await _emit(chat_id, message_id, text, kb, edit=edit)


async def show_vps_stats(chat_id, message_id, user_id, lang, short_id, edit=True):
    vps_list = await db.get_all_user_vps(user_id)
    vps = next((v for v in vps_list if v["container_id"].startswith(short_id)), None)
    if not vps:
        await _emit(chat_id, message_id, ui.msg(lang, "no_vps_short"), _back_kb(lang), edit=edit)
        return
    stats = vps_manager.get_container_stats(vps["container_id"])
    remaining = await db.get_remaining_seconds(user_id)
    started_at = datetime.fromisoformat(vps["started_at"])
    used = int((datetime.now() - started_at).total_seconds())
    time_left = max(0, remaining - used)
    lines = [ui.msg(lang, "stats_live"), "─────────────────────", ""]
    if stats:
        ram_pct = (stats["memory_used_mb"] / stats["memory_limit_mb"] * 100) if stats.get("memory_limit_mb") else 0
        lines.append(f"⚡ CPU: {stats['cpu_percent']}%")
        lines.append(f"   {_bar(stats['cpu_percent'])}")
        lines.append(f"💾 RAM: {stats['memory_used_mb']}MB / {stats['memory_limit_mb']}MB")
        lines.append(f"   {_bar(ram_pct)}")
        lines.append(f"🔧 PIDs: {stats['pids']}")
    else:
        lines.append("⊘ stats ᴜɴᴀᴠᴀɪʟᴀʙʟᴇ")
    lines.append("")
    lines.append(f"{ui.lbl(lang, 'time')}: <b>{format_time(time_left)}</b>")
    text = "\n".join(lines)
    kb = [
        [cb.styled_button(ui.lbl(lang, "back"), callback_data="menu_myvps"),
         cb.styled_button(ui.lbl(lang, "restart"), callback_data=f"action_restart_{short_id}", style="success")],
    ]
    await _emit(chat_id, message_id, text, kb, edit=edit)


async def ask_delete(chat_id, message_id, user_id, lang, short_id=None, edit=True):
    vps_list = await db.get_all_user_vps(user_id)
    if not vps_list:
        await _emit(chat_id, message_id, ui.msg(lang, "no_vps_short"), _back_kb(lang), edit=edit)
        return
    vps = vps_list[0] if short_id is None else next(
        (v for v in vps_list if v["container_id"].startswith(short_id)), vps_list[0]
    )
    remaining = await db.get_remaining_seconds(user_id)
    started_at = datetime.fromisoformat(vps["started_at"])
    used = int((datetime.now() - started_at).total_seconds())
    will_remain = max(0, remaining - used)
    sid = vps["container_id"][:12]
    text = ui.msg(lang, "del_confirm", name=esc(vps["container_name"]),
                  used=format_time(used), left=format_time(will_remain))
    kb = [
        [cb.styled_button(ui.lbl(lang, "confirm_yes"), callback_data=f"do_delete_{sid}", style="danger"),
         cb.styled_button(ui.lbl(lang, "cancel"), callback_data="menu_myvps")],
    ]
    await _emit(chat_id, message_id, text, kb, edit=edit)


def _deleted_screen(lang: str, remaining: int) -> tuple:
    text = ui.msg(lang, "vps_deleted", time=format_time(remaining))
    kb = [
        [cb.styled_button(ui.lbl(lang, "create_go"), callback_data="menu_create", style="success")],
        _back_kb(lang)[0],
    ]
    return text, kb


# ============ Create flow (shared by /create + menu button) ============

async def _perform_create(chat_id: int, message_id, user_id: int, lang: str, context, edit: bool):
    """Full guarded deploy flow. Returns final message_id (if any)."""
    # 1) banned / limit guard (lightweight, no message context needed)
    is_banned, reason = await security.is_user_banned(user_id)
    if is_banned:
        text = ui.msg(lang, "banned", reason=esc(reason))
        return await _emit(chat_id, message_id, text, None, edit=edit)

    # 1b) lockdown mode — creation disabled by admin
    if await db.get_lockdown():
        text = ui.msg(lang, "lockdown_user")
        return await _emit(chat_id, message_id, text, _back_kb(lang), edit=edit)

    # 1c) approval gate — sirf PAID plans ke liye; FREE plan sab auto-approve
    if config.APPROVAL_REQUIRED and not await db.is_user_approved(user_id):
        user_plan = await db.get_user_plan(user_id)
        if user_plan != "free":  # free users kabhi block nahi hote approval se
            text = ui.msg(lang, "approval_pending")
            return await _emit(chat_id, message_id, text, _back_kb(lang), edit=edit)

    # 2) existing VPS guard (multi-VPS ready: compare against MAX_VPS_PER_USER)
    active = await db.get_active_vps_count(user_id)
    if active >= config.MAX_VPS_PER_USER:
        return await show_myvps(chat_id, message_id, user_id, lang, page=0, edit=edit, context=context)

    # 3) cooldown
    allowed, cooldown_remaining = security.check_create_cooldown(user_id)
    if not allowed:
        text = ui.msg(lang, "cooldown", sec=cooldown_remaining)
        return await _emit(chat_id, message_id, text, _back_kb(lang), edit=edit)

    # 4) time balance
    remaining = await db.get_remaining_seconds(user_id)
    if remaining <= 0:
        text = ui.msg(lang, "nobal")
        kb = [
            [cb.styled_button(ui.lbl(lang, "invite_friends"), callback_data="menu_invite", style="primary")],
            [cb.styled_button(ui.lbl(lang, "view_plans"), callback_data="menu_plans", style="primary")],
            _back_kb(lang)[0],
        ]
        return await _emit(chat_id, message_id, text, kb, edit=edit)

    # 5) free port
    ssh_port = await db.get_next_available_port()
    if ssh_port == -1:
        text = ui.msg(lang, "noports")
        return await _emit(chat_id, message_id, text, _back_kb(lang), edit=edit)

    # 5b) already deploying? (double-tap protection)
    if user_id in _creating:
        text = ui.msg(lang, "deploying") + "\n\n⊘ ᴅᴇᴘʟᴏʏ ᴀʟʀᴇᴀᴅʏ ɪɴ ᴘʀᴏɢʀᴇss..."
        return await _emit(chat_id, message_id, text, None, edit=edit)

    # 6) mark in-progress first, then show progress message
    _creating.add(user_id)
    try:
        cur_id = await _emit(chat_id, message_id, ui.msg(lang, "deploying"), None, edit=edit)
        user_plan = await db.get_user_plan(user_id)
        plan_config = config.VPS_PLANS.get(user_plan, config.VPS_PLANS["free"])
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            vps_manager.create_vps,
            user_id, ssh_port, plan_config["ram"], plan_config["cpu"],
        )
        await db.add_vps_instance(
            user_id=user_id,
            container_id=result["container_id"],
            container_name=result["container_name"],
            ssh_port=result["ssh_port"],
            ssh_password=result["ssh_password"],
            ssh_user=result["ssh_user"],
            ram=result["ram"], cpu=result["cpu"],
            storage=config.DEFAULT_STORAGE,
        )
        security.record_create(user_id)  # cooldown only on success (original behaviour)
        await security.log_security_event(user_id, "VPS_CREATE", f"Port: {ssh_port}")

        server_ip = config.SERVER_IP
        time_display = format_time(remaining)
        text = ui.msg(
            lang, "deploy_success",
            user=esc(result["ssh_user"]),
            ip=server_ip,
            port=result["ssh_port"],
            password=esc(result["ssh_password"]),
            ram=result["ram"],
            cpu=result["cpu"],
            time=time_display,
            link=get_invite_link(user_id),
        )
        short = result["container_id"][:12]
        kb = _vps_kb(lang, short, 0, 1)
        return await _emit(chat_id, cur_id, text, kb, edit=True)

    except Exception as e:
        logger.error(f"VPS creation failed for {user_id}: {e}")
        err_text = str(e)
        # Friendly hint when the Docker daemon itself is unreachable
        if any(k in err_text for k in ("Connection aborted", "No such file or directory",
                                       "docker", "docker.errors", "Cannot connect")):
            text = ui.msg(lang, "deploy_no_docker")
        else:
            text = ui.msg(lang, "deploy_fail", err=esc(err_text[:150]))
        return await _emit(chat_id, cur_id, text, _back_kb(lang), edit=True)
    finally:
        _creating.discard(user_id)


# ============ User Commands ============

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Private only
    if update.effective_chat.type != "private":
        return
    # Force join check
    if not await check_force_join(update, context):
        return

    user = update.effective_user
    is_banned, reason = await security.is_user_banned(user.id)
    if is_banned:
        await update.message.reply_text(f"⊘ ʙᴀɴɴᴇᴅ: {esc(reason)}", parse_mode=ParseMode.HTML)
        return

    # Silently remove any old reply keyboard
    try:
        removal_msg = await update.message.reply_text(".", reply_markup=ReplyKeyboardRemove())
        await removal_msg.delete()
    except Exception:
        pass

    is_new = not await db.user_exists(user.id)

    inviter_id = None
    if context.args and context.args[0].startswith("invite_"):
        try:
            inviter_id = int(context.args[0].replace("invite_", ""))
            if inviter_id == user.id:
                inviter_id = None
            # Validate inviter exists
            elif not await db.user_exists(inviter_id):
                inviter_id = None
        except ValueError:
            inviter_id = None

    await db.add_user(user.id, user.username or user.first_name, invited_by=inviter_id)
    await security.log_security_event(user.id, "START", f"New: {is_new}, Inviter: {inviter_id}")

    # Invite reward for the inviter (localized)
    if is_new and inviter_id:
        if await security.check_daily_invite_limit(inviter_id):
            await db.record_invite(inviter_id, user.id)
            await db.add_time(inviter_id, config.INVITE_BONUS_SECONDS)
            remaining = await db.get_remaining_seconds(inviter_id)
            inviter_lang = await db.get_user_lang(inviter_id)
            try:
                await context.bot.send_message(
                    chat_id=inviter_id,
                    text=ui.msg(
                        inviter_lang, "invite_bonus",
                        days=config.INVITE_BONUS_DAYS,
                        name=esc(user.username or user.first_name),
                        balance=format_time(remaining),
                    ),
                    parse_mode=ParseMode.HTML,
                )
            except Exception:
                pass

    # New-user alert to admin (localized for admin) + approval hint when gate is ON
    if is_new:
        try:
            admin_lang = await db.get_user_lang(config.ADMIN_ID)
            alert = ui.msg(
                admin_lang, "new_user_admin",
                uid=esc(user.id),
                name=esc(user.first_name),
                link=get_invite_link(user.id),
                when=datetime.now().strftime("%Y-%m-%d %H:%M"),
            )
            if config.APPROVAL_REQUIRED:
                alert += ui.msg(admin_lang, "approval_admin_hint", uid=esc(user.id))
            await context.bot.send_message(chat_id=config.ADMIN_ID, text=alert, parse_mode=ParseMode.HTML)
        except Exception:
            pass

    # Parallel fetch: remaining time + profile photo
    remaining, photo_result = await asyncio.gather(
        db.get_remaining_seconds(user.id),
        context.bot.get_user_profile_photos(user.id, limit=1),
        return_exceptions=True,
    )
    lang = await db.get_user_lang(user.id)

    photo_file_id = None
    if not isinstance(photo_result, Exception) and photo_result.total_count > 0:
        photo_file_id = photo_result.photos[0][0].file_id

    caption = ui.msg(
        lang, "welcome",
        name=esc(user.first_name),
        time=format_time(remaining),
        uid=user.id,
        dev=config.DEVELOPER_USERNAME,
    )
    kb = _main_kb(lang, user.id)

    if photo_file_id:
        result = await cb.send_photo_colored(
            chat_id=user.id, photo=photo_file_id, caption=caption, reply_markup=kb,
        )
        if not result:
            await cb.send_message_colored(chat_id=user.id, text=caption, reply_markup=kb)
    else:
        await cb.send_message_colored(chat_id=user.id, text=caption, reply_markup=kb)


async def create_vps_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await security_check(update, context):
        return
    user_id = update.effective_user.id
    lang = await db.get_user_lang(user_id)
    await _perform_create(user_id, None, user_id, lang, context, edit=False)


async def my_vps(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await security_check(update, context):
        return
    user_id = update.effective_user.id
    lang = await db.get_user_lang(user_id)
    _set_page(context, 0)
    await show_myvps(user_id, None, user_id, lang, page=0, edit=False, context=context)


async def invite_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await security_check(update, context):
        return
    user_id = update.effective_user.id
    lang = await db.get_user_lang(user_id)
    await show_invite(user_id, None, user_id, lang, edit=False)


async def delete_vps_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await security_check(update, context):
        return
    user_id = update.effective_user.id
    lang = await db.get_user_lang(user_id)
    await ask_delete(user_id, None, user_id, lang, short_id=None, edit=False)


async def restart_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await security_check(update, context):
        return
    user_id = update.effective_user.id
    lang = await db.get_user_lang(user_id)
    vps_list = await db.get_all_user_vps(user_id)
    if not vps_list:
        await cb.send_message_colored(
            chat_id=user_id,
            text=ui.msg(lang, "no_vps_short"),
            reply_markup=[[cb.styled_button(ui.lbl(lang, "create_go"), callback_data="menu_create", style="success")]],
        )
        return
    vps = vps_list[0]
    success = vps_manager.restart_vps(vps["container_id"])
    if success:
        await security.log_security_event(user_id, "VPS_RESTART", vps["container_name"])
    # Always show the fresh card afterwards
    await show_myvps(user_id, None, user_id, lang, page=0, edit=False, context=context)


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = await db.get_user_lang(user_id)
    await show_help(user_id, None, user_id, lang, edit=False)


async def dashboard_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await security_check(update, context):
        return
    user_id = update.effective_user.id
    lang = await db.get_user_lang(user_id)
    await show_dashboard(user_id, None, user_id, lang, edit=False)


async def plans_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await security_check(update, context):
        return
    user_id = update.effective_user.id
    lang = await db.get_user_lang(user_id)
    await show_plans(user_id, None, user_id, lang, edit=False)


async def language_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        return
    user_id = update.effective_user.id
    lang = await db.get_user_lang(user_id)
    await show_language(user_id, None, user_id, lang, edit=False)


# ============ Admin Commands ============

async def admin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    # Parallel fetch all stats
    users, expired, banned, all_vps = await asyncio.gather(
        db.get_all_users(),
        db.get_expired_vps(),
        security.get_banned_users(),
        db.get_all_running_vps(),
    )
    text = (
        f"👑 <b>ᴀᴅᴍɪɴ ᴘᴀɴᴇʟ</b>\n\n"
        f"┌ 📊 <b>sᴛᴀᴛs</b>\n"
        f"│ 👥 ᴜsᴇʀs   : {len(users)}\n"
        f"│ 🟢 ʀᴜɴɴɪɴɢ : {len(all_vps)}\n"
        f"│ ⏰ ᴇxᴘɪʀᴇᴅ : {len(expired)}\n"
        f"│ ⊘ ʙᴀɴɴᴇᴅ  : {len(banned)}\n"
        f"└─────────────────────\n\n"
        f"┌ 🔧 <b>ᴄᴏᴍᴍᴀɴᴅs</b>\n"
        f"│ /users • /ban • /unban\n"
        f"│ /forcekill • /stats\n"
        f"│ /setplan • /grantroot\n"
        f"│ /broadcast • /analytics\n"
        f"└─────────────────────"
    )
    await cb.send_message_colored(
        chat_id=update.effective_user.id,
        text=text,
        reply_markup=[
            [cb.styled_button("👥 ᴜsᴇʀs", callback_data="menu_analytics", style="primary"),
             cb.styled_button("📋 ʟᴏɢs", callback_data="menu_analytics", style="primary")],
            [cb.styled_button("✦ 📈 ᴀɴᴀʟʏᴛɪᴄs ✦", callback_data="menu_analytics", style="primary")],
            [cb.styled_button("🔙 ᴍᴇɴᴜ", callback_data="menu_back", style="primary")],
        ],
    )


async def users_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    users = await db.get_all_users()
    if not users:
        await update.message.reply_text("No users.")
        return
    text = "◈ <b>Users:</b>\n\n"
    for user in users[:50]:
        bal = format_time(user.get('remaining_seconds', 0))
        text += f"• <code>{user['user_id']}</code> - {esc(user.get('username', ''))} [{bal}]\n"
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def ban_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /ban user_id reason")
        return
    try:
        target_id = int(context.args[0])
        reason = " ".join(context.args[1:])
        # Confirm step
        await cb.send_message_colored(
            chat_id=update.effective_user.id,
            text=(
                f"⚠️ <b>ᴄᴏɴғɪʀᴍ ʙᴀɴ?</b>\n\n"
                f"┌─────────────────────\n"
                f"│ 👤 ᴜsᴇʀ ɪᴅ : <code>{target_id}</code>\n"
                f"│ ⊘ ʀᴇᴀsᴏɴ  : {esc(reason)}\n"
                f"│ ⏱ ᴅᴜʀᴀᴛɪᴏɴ: {config.BAN_DURATION_HOURS}ʜ\n"
                f"└─────────────────────"
            ),
            reply_markup=[[
                cb.styled_button("✅ ᴄᴏɴғɪʀᴍ", callback_data=f"admin_ban_{target_id}_{reason[:30]}", style="danger"),
                cb.styled_button("❌ ᴄᴀɴᴄᴇʟ", callback_data="cancel"),
            ]],
        )
    except ValueError:
        await update.message.reply_text("✗ Invalid ID.")


async def unban_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text("Usage: /unban user_id")
        return
    try:
        target_id = int(context.args[0])
        await security.unban_user(target_id)
        await update.message.reply_text(f"✓ Unbanned <code>{target_id}</code>", parse_mode=ParseMode.HTML)
    except ValueError:
        await update.message.reply_text("✗ Invalid ID.")


async def forcekill_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text("Usage: /forcekill short_id")
        return
    short_id = context.args[0]
    all_vps = await db.get_all_running_vps()
    target = next((v for v in all_vps if v["container_id"].startswith(short_id)), None)
    if not target:
        await update.message.reply_text("✗ Not found.")
        return
    success = vps_manager.force_kill_container(target["container_id"])
    if success:
        await db.remove_vps_instance(target["container_id"])
        await security.log_security_event(target["user_id"], "FORCE_KILL", target['container_name'])
        await update.message.reply_text(f"⊘ Killed: {target['container_name']}")
    else:
        await update.message.reply_text("✗ Failed.")


async def delvps_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/delvps <user_id> — Admin: specific user ka VPS delete karo with confirm."""
    if not is_admin(update.effective_user.id):
        return

    # No args — list all running VPS
    if not context.args:
        all_vps = await db.get_all_running_vps()
        if not all_vps:
            await update.message.reply_text("⊡ ᴄᴜʀʀᴇɴᴛʟʏ ɴᴏ ᴠᴘs ʀᴜɴɴɪɴɢ.")
            return
        text = "🖥 <b>ʀᴜɴɴɪɴɢ ᴠᴘs ʟɪsᴛ</b>\n\n"
        for vps in all_vps:
            started_at = vps.get("started_at", "")
            text += (
                f"┌ ᴜsᴇʀ: <code>{vps['user_id']}</code>\n"
                f"│ ɴᴀᴍᴇ: <code>{vps['container_name']}</code>\n"
                f"│ ᴘᴏʀᴛ: {vps['ssh_port']}\n"
                f"│ sᴛᴀʀᴛᴇᴅ: {started_at[:16]}\n"
                f"└─────────────────────\n\n"
            )
        text += "ᴜsᴇ: /delvps &lt;user_id&gt;"
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)
        return

    # With user_id arg — show confirm buttons
    try:
        target_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("✗ ɪɴᴠᴀʟɪᴅ ᴜsᴇʀ ɪᴅ.")
        return

    vps = await db.get_user_vps(target_id)
    if not vps:
        await update.message.reply_text(
            f"⊡ ᴜsᴇʀ <code>{target_id}</code> ʜᴀs ɴᴏ ᴀᴄᴛɪᴠᴇ ᴠᴘs.",
            parse_mode=ParseMode.HTML,
        )
        return

    started_at = vps.get("started_at", "")
    stats = vps_manager.get_container_stats(vps["container_id"])
    stats_text = ""
    if stats:
        stats_text = (
            f"│ ⚡ ᴄᴘᴜ  : {stats['cpu_percent']}%\n"
            f"│ 💾 ʀᴀᴍ  : {stats['memory_used_mb']}MB\n"
            f"│ 🔧 ᴘɪᴅs : {stats['pids']}\n"
        )

    await cb.send_message_colored(
        chat_id=update.effective_user.id,
        text=(
            f"🗑 <b>ᴄᴏɴғɪʀᴍ ᴅᴇʟᴇᴛᴇ?</b>\n\n"
            f"┌ 👤 <b>ᴜsᴇʀ</b>\n"
            f"│ ɪᴅ    : <code>{target_id}</code>\n"
            f"└─────────────────────\n\n"
            f"┌ 🖥 <b>ᴠᴘs</b>\n"
            f"│ ɴᴀᴍᴇ  : <code>{vps['container_name']}</code>\n"
            f"│ ᴘᴏʀᴛ  : {vps['ssh_port']}\n"
            f"│ ʀᴀᴍ   : {vps['ram']} | ᴄᴘᴜ: {vps['cpu']}\n"
            f"│ sᴛᴀʀᴛ : {started_at[:16]}\n"
            f"{stats_text}"
            f"└─────────────────────\n\n"
            f"⚠️ ᴛʜɪs ᴡɪʟʟ ᴘᴇʀᴍᴀɴᴇɴᴛʟʏ ᴅᴇsᴛʀᴏʏ ᴛʜᴇ ᴄᴏɴᴛᴀɪɴᴇʀ."
        ),
        reply_markup=[
            [
                cb.styled_button("✅ ʏᴇs, ᴅᴇʟᴇᴛᴇ", callback_data=f"admin_delvps_{target_id}", style="danger"),
                cb.styled_button("❌ ᴄᴀɴᴄᴇʟ", callback_data="cancel"),
            ]
        ],
    )


async def logs_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    logs = await security.get_security_logs(20)
    if not logs:
        await update.message.reply_text("No logs.")
        return
    text = "◇ <b>Logs:</b>\n\n"
    for log in logs:
        text += f"<code>{log['created_at'][:16]}</code> [{log['action']}] {log['user_id']} - {esc(log['details'])[:35]}\n"
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def stats_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text("Usage: /stats user_id")
        return
    try:
        target_id = int(context.args[0])
        vps = await db.get_user_vps(target_id)
        if not vps:
            await update.message.reply_text("No VPS.")
            return
        stats = vps_manager.get_container_stats(vps["container_id"])
        if stats:
            text = f"⟐ <b>{target_id}:</b>\nCPU: {stats['cpu_percent']}%\nRAM: {stats['memory_used_mb']}MB/{stats['memory_limit_mb']}MB\nPIDs: {stats['pids']}"
        else:
            text = "Stats unavailable."
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)
    except ValueError:
        await update.message.reply_text("✗ Invalid ID.")


async def broadcast_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text("Usage: /broadcast msg")
        return
    message = " ".join(context.args)
    users = await db.get_all_users()
    sent = 0
    status_msg = await update.message.reply_text(f"⟳ ʙʀᴏᴀᴅᴄᴀsᴛɪɴɢ ᴛᴏ {len(users)} ᴜsᴇʀs...")
    for i, user in enumerate(users):
        try:
            await context.bot.send_message(chat_id=user["user_id"], text=message)
            sent += 1
        except Exception:
            pass
        # Rate limit: max 20 msg/sec — update status every 50 users
        await asyncio.sleep(0.05)
        if (i + 1) % 50 == 0:
            try:
                await status_msg.edit_text(f"⟳ ᴘʀᴏɢʀᴇss: {i+1}/{len(users)}...")
            except Exception:
                pass
    await status_msg.edit_text(f"✅ ʙʀᴏᴀᴅᴄᴀsᴛ ᴅᴏɴᴇ\n\n📤 sᴇɴᴛ: {sent}/{len(users)}")


async def setplan_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/setplan <user_id> <plan> - Set user's plan (admin only)."""
    if not is_admin(update.effective_user.id):
        return
    if len(context.args) < 2:
        plans_list = ", ".join(config.VPS_PLANS.keys())
        await update.message.reply_text(f"Usage: /setplan user_id plan\nPlans: {plans_list}")
        return
    try:
        target_id = int(context.args[0])
        plan = context.args[1].lower()
        if plan not in config.VPS_PLANS:
            await update.message.reply_text(f"⊘ ɪɴᴠᴀʟɪᴅ ᴘʟᴀɴ. ᴏᴘᴛɪᴏɴs: {', '.join(config.VPS_PLANS.keys())}")
            return
        plan_data = config.VPS_PLANS[plan]
        await db.set_user_plan(target_id, plan, add_time=plan_data["time_seconds"])

        # FIX: plan change ab user ke RUNNING VPS par LIVE apply hota hai
        # (docker update RAM/CPU) — delete/recreate ki zaroorat nahi
        vps = await db.get_user_vps(target_id)
        live_note = ""
        live_applied = False
        if vps:
            live_applied = vps_manager.update_limits(
                vps["container_id"], ram=plan_data["ram"], cpu=plan_data["cpu"]
            )
            live_note = (
                "\n🟢 Running VPS live-updated."
                if live_applied
                else "\n⚠️ Docker se live update fail — user ko /delete + /create bolna padega."
            )
        await update.message.reply_text(
            f"✓ ᴜsᴇʀ <code>{target_id}</code> → <b>{esc(plan_data['name'])}</b>\n"
            f"▹ ʀᴀᴍ: {plan_data['ram']} | ᴄᴘᴜ: {plan_data['cpu']} ᴄᴏʀᴇ\n"
            f"▹ +{plan_data['time_seconds'] // 86400} ᴅᴀʏs ᴀᴅᴅᴇᴅ"
            f"{live_note}",
            parse_mode=ParseMode.HTML,
        )
        # Notify user (localized balance-style)
        try:
            remaining = format_time(await db.get_remaining_seconds(target_id))
            apply_line = (
                "🟢 ᴀᴀᴘᴋᴇ ʀᴜɴɴɪɴɢ ᴠᴘs ᴘᴀʀ ʟɪᴍɪᴛs ʟɪᴠᴇ ᴀᴘᴘʟʏ — ᴋᴜᴄʜ ɴᴀʜɪ ᴋᴀʀɴᴀ."
                if live_applied
                else "⊖ ɴᴀʏᴀ ʀᴀᴍ/ᴄᴘᴜ ʟᴀɢᴜ ᴋᴀʀɴᴇ ᴋᴇ ʟɪʏᴇ ᴠᴘs ᴅᴇʟᴇᴛᴇ ᴋᴀʀᴋᴇ /create ᴋᴀʀᴏ."
            )
            await context.bot.send_message(
                chat_id=target_id,
                text=(
                    f"✦ <b>ᴘʟᴀɴ ᴜᴘᴅᴀᴛᴇᴅ!</b>\n\n"
                    f"▹ ᴘʟᴀɴ: <b>{esc(plan_data['name'])}</b>\n"
                    f"▹ ʀᴀᴍ: {plan_data['ram']}\n"
                    f"▹ ᴄᴘᴜ: {plan_data['cpu']} ᴄᴏʀᴇ\n"
                    f"▹ +{plan_data['time_seconds'] // 86400} ᴅᴀʏs ᴀᴅᴅᴇᴅ\n"
                    f"⏳ ʙᴀʟᴀɴᴄᴇ: {remaining}\n\n"
                    f"{apply_line}"
                ),
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            pass
    except ValueError:
        await update.message.reply_text("⊘ ɪɴᴠᴀʟɪᴅ ᴜsᴇʀ ɪᴅ.")


async def addchannel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/addchannel @username - Add force join channel."""
    if not is_admin(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text("Usage: /addchannel @channelname")
        return
    channel = context.args[0]
    if not channel.startswith("@"):
        channel = "@" + channel
    if channel not in config.FORCE_JOIN_CHANNELS:
        config.FORCE_JOIN_CHANNELS.append(channel)
        # Save to DB for persistence
        await db.db.settings.update_one(
            {"key": "force_join_channels"},
            {"$set": {"channels": config.FORCE_JOIN_CHANNELS}},
            upsert=True,
        )
    await update.message.reply_text(
        f"✓ ᴄʜᴀɴɴᴇʟ ᴀᴅᴅᴇᴅ: {channel}\n\n"
        f"ᴄᴜʀʀᴇɴᴛ ʟɪsᴛ: {', '.join(config.FORCE_JOIN_CHANNELS)}",
    )


async def removechannel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/removechannel @username - Remove force join channel."""
    if not is_admin(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text("Usage: /removechannel @channelname")
        return
    channel = context.args[0]
    if not channel.startswith("@"):
        channel = "@" + channel
    if channel in config.FORCE_JOIN_CHANNELS:
        config.FORCE_JOIN_CHANNELS.remove(channel)
        await db.db.settings.update_one(
            {"key": "force_join_channels"},
            {"$set": {"channels": config.FORCE_JOIN_CHANNELS}},
            upsert=True,
        )
        await update.message.reply_text(f"✓ ʀᴇᴍᴏᴠᴇᴅ: {channel}")
    else:
        await update.message.reply_text(f"✗ {channel} ɴᴏᴛ ɪɴ ʟɪsᴛ.")


async def channels_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/channels - List all force join channels."""
    if not is_admin(update.effective_user.id):
        return
    if config.FORCE_JOIN_CHANNELS:
        text = "◇ <b>ғᴏʀᴄᴇ ᴊᴏɪɴ ᴄʜᴀɴɴᴇʟs:</b>\n\n"
        for i, ch in enumerate(config.FORCE_JOIN_CHANNELS, 1):
            text += f"{i}. {ch}\n"
        text += "\n/addchannel @name\n/removechannel @name"
    else:
        text = "◇ ɴᴏ ᴄʜᴀɴɴᴇʟs sᴇᴛ.\n\n/addchannel @name ᴛᴏ ᴀᴅᴅ."
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


# ============ User Manager Browser (/manage) ============

ADMIN_PAGE_SIZE = 10


async def _manage_list(chat_id, message_id, page: int = 0, edit=True):
    """All users ka paginated inline list — tap karo user detail ke liye."""
    users = list(await db.get_all_users())
    users.reverse()  # newest first
    total_pages = max(1, -(-len(users) // ADMIN_PAGE_SIZE))
    page = max(0, min(page, total_pages - 1))
    start = page * ADMIN_PAGE_SIZE
    chunk = users[start:start + ADMIN_PAGE_SIZE]

    text = f"👥 <b>ᴀʟʟ ᴜsᴇʀs ({len(users)})</b>\n📄 ᴘᴀɢᴇ {page + 1}/{total_pages}\n\n"
    for i, u in enumerate(chunk, start + 1):
        label = (u.get("username") or u.get("first_name") or u.get("user_id"))
        text += f"{i}. <b>{esc(str(label)[:20])}</b>  <code>{u['user_id']}</code>\n"
    text += "\n👇 ᴜsᴇʀ ᴘᴀʀ ᴛᴀᴘ ᴋᴀʀᴏ — ᴠᴘs + ssʜ ᴍᴀɴᴀɢᴇ ᴋʀᴏ."

    kb = []
    for j, u in enumerate(chunk, start + 1):
        label = (u.get("username") or u.get("first_name") or u.get("user_id"))
        kb.append([cb.styled_button(f"{j}. {str(label)[:30]}", callback_data=f"umgr_user_{u['user_id']}", style="primary")])
    if total_pages > 1:
        kb.append([
            cb.styled_button("◀️", callback_data=f"umgr_pg_{max(0, page - 1)}"),
            cb.styled_button(f"📄 {page + 1}/{total_pages}", callback_data="noop"),
            cb.styled_button("▶️", callback_data=f"umgr_pg_{min(total_pages - 1, page + 1)}"),
        ])
    kb.append([cb.styled_button("🔙 ᴍᴇɴᴜ", callback_data="menu_back")])
    await _emit(chat_id, message_id, text, kb, edit=edit)


async def _manage_detail(chat_id, message_id, uid: int, page: int, edit=True):
    """Ek user ka full card: profile + VPS + SSH credentials + actions."""
    u = await db.db.users.find_one({"user_id": uid})
    if not u:
        text = f"⊡ ᴜsᴇʀ <code>{uid}</code> ɴᴏᴛ ғᴏᴜɴᴅ."
        kb = [[cb.styled_button("🔙 ʟɪsᴛ", callback_data="umgr_pg_0")]]
        await _emit(chat_id, message_id, text, kb, edit=edit)
        return

    name = u.get("username") or u.get("first_name") or uid
    plan = await db.get_user_plan(uid)
    balance = format_time(await db.get_remaining_seconds(uid))
    invites = await db.get_invite_count(uid)
    vps = await db.get_user_vps(uid)

    text = (
        f"👤 <b>{esc(str(name)[:20])}</b>  <code>{uid}</code>\n"
        f"💎 {plan}   ⏳ {balance}   🎁 {invites}\n\n"
    )
    kb = []
    if vps:
        status = vps_manager.get_container_status(vps["container_id"])
        emoji = "🟢" if status == "running" else "🔴"
        ssh_user = vps.get("ssh_user", "user")
        text += (
            f"🖥 {emoji} <code>{esc(vps['container_name'])}</code>\n"
            f"🔌 ᴘᴏʀᴛ: <code>{vps['ssh_port']}</code>\n"
            f"👤 ssʜ: <code>{ssh_user}</code>\n"
            f"🔐 ᴘᴀss: <code>{vps.get('ssh_password', '?')}</code>\n"
            f"🌐 ssh {ssh_user}@{config.SERVER_IP} -p {vps['ssh_port']}\n"
            f"💾 {vps.get('ram')}   ⚡ {vps.get('cpu')} ᴄᴏʀᴇ\n"
        )
        kb.append([
            cb.styled_button("🔄 ʀᴇsᴛᴀʀᴛ", callback_data=f"umgr_restart_{uid}", style="primary"),
            cb.styled_button("🗑 ᴅᴇʟᴇᴛᴇ", callback_data=f"umgr_del_{uid}", style="danger"),
        ])
    else:
        text += "⊡ <b>ɴᴏ ᴀᴄᴛɪᴠᴇ ᴠᴘs</b>\n"
    kb.append([
        cb.styled_button("⏰ +1ᴅ", callback_data=f"umgr_ext_{uid}_1", style="primary"),
        cb.styled_button("⏰ +7ᴅ", callback_data=f"umgr_ext_{uid}_7", style="primary"),
    ])
    kb.append([
        cb.styled_button("⊖ −1ᴅ", callback_data=f"umgr_sub_{uid}_1", style="danger"),
        cb.styled_button("⊖ −7ᴅ", callback_data=f"umgr_sub_{uid}_7", style="danger"),
    ])
    kb.append([cb.styled_button("🔙 ʟɪsᴛ", callback_data=f"umgr_pg_{page}")])
    await _emit(chat_id, message_id, text, kb, edit=edit)


async def manage_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/manage [user_id] — All users ka interactive list; user tap = VPS+SSH manage."""
    if not is_admin(update.effective_user.id):
        return
    if context.args:
        try:
            uid = int(context.args[0])
        except ValueError:
            await update.message.reply_text("✗ Invalid user ID.")
            return
        await _manage_detail(update.effective_user.id, None, uid, 0, edit=False)
        return
    await _manage_list(update.effective_user.id, None, 0, edit=False)


async def _time_change(user_id: int, days: int, add: bool):
    """Time add/subtract karo (subtract 0 se neeche nahi jaata).
    Returns (new_balance_seconds, actual_days_str)."""
    secs = int(days * 86400)
    if add:
        await db.add_time(user_id, secs)
        actual = secs
    else:
        before = await db.get_remaining_seconds(user_id)
        new = await db.subtract_time(user_id, secs)
        actual = before - new
    balance = await db.get_remaining_seconds(user_id)
    actual_days = actual / 86400
    days_str = str(int(actual_days)) if float(actual_days).is_integer() else str(round(actual_days, 2))
    return balance, days_str


async def removetime_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/removetime <user_id> <days> - Admin: user ka time kam karo (0 se neeche nahi)."""
    if not is_admin(update.effective_user.id):
        return
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /removetime <user_id> <days>")
        return
    try:
        uid = int(context.args[0])
        days = int(context.args[1])
    except ValueError:
        await update.message.reply_text("✗ user_id aur days numbers hone chahiye.")
        return
    if days <= 0:
        await update.message.reply_text("✗ Days positive number do.")
        return
    balance, days_str = await _time_change(uid, days, add=False)
    await security.log_security_event(uid, "ADMIN_REMOVETIME", f"-{days}d by admin {update.effective_user.id}")
    try:
        lang = await db.get_user_lang(uid)
        await _bot_send(uid, ui.msg(lang, "time_removed_admin", days=days_str, balance=format_time(balance)))
    except Exception:
        pass
    await update.message.reply_text(
        f"⊖ User <code>{uid}</code> se {days_str} ᴅᴀʏs ʜᴀᴛᴀʏᴇ.\n"
        f"⏳ ɴᴇᴡ ʙᴀʟᴀɴᴄᴇ: {format_time(balance)}",
        parse_mode=ParseMode.HTML,
    )


async def analytics_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/analytics - Full admin analytics dashboard."""
    if not is_admin(update.effective_user.id):
        return
    report = await monitor.get_analytics()
    await update.message.reply_text(report, parse_mode=ParseMode.HTML)


async def grantroot_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/grantroot <user_id> - Grant root access to user's VPS (with confirm)."""
    if not is_admin(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text("Usage: /grantroot &lt;user_id&gt;", parse_mode=ParseMode.HTML)
        return
    try:
        target_id = int(context.args[0])
        vps = await db.get_user_vps(target_id)
        if not vps:
            await update.message.reply_text("✗ User has no active VPS.")
            return
        await cb.send_message_colored(
            chat_id=update.effective_user.id,
            text=(
                f"⚠️ <b>ɢʀᴀɴᴛ ʀᴏᴏᴛ?</b>\n\n"
                f"┌─────────────────────\n"
                f"│ 👤 ᴜsᴇʀ ɪᴅ : <code>{target_id}</code>\n"
                f"│ 🖥 ᴠᴘs    : <code>{vps['container_name']}</code>\n"
                f"└─────────────────────\n\n"
                f"△ ᴛʜɪs ᴡɪʟʟ ʀᴇsᴛᴀʀᴛ ᴛʜᴇ ᴠᴘs ᴡɪᴛʜ ʀᴏᴏᴛ ᴀᴄᴄᴇss."
            ),
            reply_markup=[[
                cb.styled_button("✅ ɢʀᴀɴᴛ", callback_data=f"admin_grantroot_{target_id}", style="danger"),
                cb.styled_button("❌ ᴄᴀɴᴄᴇʟ", callback_data="cancel"),
            ]],
        )
    except ValueError:
        await update.message.reply_text("✗ Invalid ID.")


async def _do_grantroot(context, target_id: int, chat_id: int):
    """Execute grantroot after admin confirmation."""
    vps = await db.get_user_vps(target_id)
    if not vps:
        await context.bot.send_message(chat_id=chat_id, text="✗ User has no active VPS.")
        return
    vps_manager.stop_vps(vps["container_id"])
    await db.remove_vps_instance(vps["container_id"])
    ssh_port = await db.get_next_available_port()
    # Use user's actual plan resources, not hardcoded defaults
    user_plan = await db.get_user_plan(target_id)
    plan_config = config.VPS_PLANS.get(user_plan, config.VPS_PLANS["free"])
    result = vps_manager.create_vps(
        user_id=target_id, ssh_port=ssh_port,
        ram=plan_config["ram"], cpu=plan_config["cpu"],
        root_access=True,
    )
    await db.add_vps_instance(
        user_id=target_id,
        container_id=result["container_id"],
        container_name=result["container_name"],
        ssh_port=result["ssh_port"],
        ssh_password=result["ssh_password"],
        ssh_user=result["ssh_user"],
        ram=result["ram"], cpu=result["cpu"],
        storage=config.DEFAULT_STORAGE,
    )
    await security.log_security_event(target_id, "ROOT_GRANTED", "By admin")
    server_ip = config.SERVER_IP
    try:
        await context.bot.send_message(
            chat_id=target_id,
            text=(
                f"◆ <b>ʀᴏᴏᴛ ᴀᴄᴄᴇss ɢʀᴀɴᴛᴇᴅ!</b>\n\n"
                f"⟡ <b>ssʜ:</b>\n"
                f"<code>ssh root@{server_ip} -p {result['ssh_port']}</code>\n\n"
                f"◇ <b>ᴘᴀssᴡᴏʀᴅ:</b>\n"
                f"<tg-spoiler>{result['ssh_password']}</tg-spoiler>\n\n"
                f"△ ᴅᴏ ɴᴏᴛ ᴀʙᴜsᴇ ʀᴏᴏᴛ ᴀᴄᴄᴇss."
            ),
            parse_mode=ParseMode.HTML,
        )
    except Exception:
        pass
    await context.bot.send_message(
        chat_id=chat_id,
        text=f"✅ ʀᴏᴏᴛ ɢʀᴀɴᴛᴇᴅ ᴛᴏ <code>{target_id}</code>. ᴘᴏʀᴛ: {result['ssh_port']}",
        parse_mode=ParseMode.HTML,
    )


async def revokeroot_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/revokeroot <user_id> - Revoke root, recreate with user-only access."""
    if not is_admin(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text("Usage: /revokeroot &lt;user_id&gt;", parse_mode=ParseMode.HTML)
        return
    try:
        target_id = int(context.args[0])
        vps = await db.get_user_vps(target_id)

        if not vps:
            await update.message.reply_text("✗ User has no active VPS.")
            return

        # Stop current VPS
        vps_manager.stop_vps(vps["container_id"])
        await db.remove_vps_instance(vps["container_id"])

        # Recreate WITHOUT root
        ssh_port = await db.get_next_available_port()
        result = vps_manager.create_vps(
            user_id=target_id, ssh_port=ssh_port,
            ram=config.DEFAULT_RAM, cpu=config.DEFAULT_CPU,
            root_access=False,
        )
        await db.add_vps_instance(
            user_id=target_id,
            container_id=result["container_id"],
            container_name=result["container_name"],
            ssh_port=result["ssh_port"],
            ssh_password=result["ssh_password"],
            ssh_user=result["ssh_user"],
            ram=result["ram"], cpu=result["cpu"],
            storage=config.DEFAULT_STORAGE,
        )

        await security.log_security_event(target_id, "ROOT_REVOKED", "By admin")

        try:
            await context.bot.send_message(
                chat_id=target_id,
                text=(
                    "△ <b>ʀᴏᴏᴛ ᴀᴄᴄᴇss ʀᴇᴠᴏᴋᴇᴅ</b>\n\n"
                    "ʏᴏᴜʀ ᴠᴘs ʜᴀs ʙᴇᴇɴ ʀᴇsᴇᴛ ᴛᴏ ᴜsᴇʀ-ᴏɴʟʏ ᴀᴄᴄᴇss.\n"
                    "ᴄʜᴇᴄᴋ /myvps ғᴏʀ ɴᴇᴡ ᴄʀᴇᴅᴇɴᴛɪᴀʟs."
                ),
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            pass

        await update.message.reply_text(
            f"✓ Root revoked for <code>{target_id}</code>.", parse_mode=ParseMode.HTML
        )
    except ValueError:
        await update.message.reply_text("✗ Invalid ID.")


async def addtime_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/addtime <user_id> <days> - Add time to user balance without changing plan."""
    if not is_admin(update.effective_user.id):
        return
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /addtime user_id days")
        return
    try:
        target_id = int(context.args[0])
        days = float(context.args[1])
        seconds = int(days * 86400)
        if seconds <= 0:
            await update.message.reply_text("✗ Days must be > 0")
            return
        await db.add_time(target_id, seconds)
        remaining = await db.get_remaining_seconds(target_id)
        await update.message.reply_text(
            f"✅ +{days}ᴅ ᴀᴅᴅᴇᴅ ᴛᴏ <code>{target_id}</code>\n"
            f"ɴᴇᴡ ʙᴀʟᴀɴᴄᴇ: <b>{format_time(remaining)}</b>",
            parse_mode=ParseMode.HTML,
        )
        try:
            await context.bot.send_message(
                chat_id=target_id,
                text=(
                    f"🎁 <b>ᴛɪᴍᴇ ᴀᴅᴅᴇᴅ ʙʏ ᴀᴅᴍɪɴ!</b>\n\n"
                    f"┌─────────────────────\n"
                    f"│ ⊕ +<b>{days} ᴅᴀʏs</b> ᴀᴅᴅᴇᴅ\n"
                    f"│ ⏳ ɴᴇᴡ ʙᴀʟᴀɴᴄᴇ: <b>{format_time(remaining)}</b>\n"
                    f"└─────────────────────"
                ),
                parse_mode=ParseMode.HTML,
            )
        except Exception:
            pass
    except ValueError:
        await update.message.reply_text("✗ Invalid user_id or days.")


# ============ Security Pack: approval gate / lockdown / strikes / hub ============

async def _security_hub(chat_id, message_id, edit=True):
    """Admin security dashboard screen."""
    users, banned, all_vps, pending, abuse_open, lockdown = await asyncio.gather(
        db.get_all_users(),
        security.get_banned_users(),
        db.get_all_running_vps(),
        db.get_pending_count(),
        security.get_unresolved_abuse(),
        db.get_lockdown(),
    )
    lockdown_txt = "🟢 ᴏɴ" if lockdown else "⚪ ᴏғғ"
    gate_txt = "🟢 ᴏɴ" if config.APPROVAL_REQUIRED else "⚪ ᴏғғ"
    text = (
        f"🛡 <b>sᴇᴄᴜʀɪᴛʏ ʜᴜʙ</b>\n\n"
        f"┌ 📊 <b>sᴛᴀᴛs</b>\n"
        f"│ 👥 ᴜsᴇʀs        : {len(users)}\n"
        f"│ 🟢 ʀᴜɴɴɪɴɢ ᴠᴘs  : {len(all_vps)}\n"
        f"│ ⊘ ʙᴀɴɴᴇᴅ       : {len(banned)}\n"
        f"│ ⏳ ᴘᴇɴᴅɪɴɢ       : {pending}\n"
        f"│ △ ᴀʙᴜsᴇ ʀᴇᴘᴏʀᴛs : {abuse_open}\n"
        f"└─────────────────────\n\n"
        f"┌ 🔐 <b>ᴄᴏɴᴛʀᴏʟs</b>\n"
        f"│ 🔒 ʟᴏᴄᴋᴅᴏᴡɴ      : {lockdown_txt}\n"
        f"│ ✅ ᴀᴘᴘʀᴏᴠᴀʟ ɢᴀᴛᴇ : {gate_txt} (ғʀᴇᴇ = ᴀᴜᴛᴏ)\n"
        f"└─────────────────────\n\n"
        f"⊘ {config.ABUSE_STRIKE_LIMIT} sᴛʀɪᴋᴇs = ᴀᴜᴛᴏ-ʙᴀɴ (24ʜ → 7ᴅ → ᴘᴇʀᴍᴀɴᴇɴᴛ)\n"
        f"△ ᴏᴜᴛʙᴏᴜɴᴅ >{config.OUTBOUND_LIMIT_MBPS} ᴍʙᴘs (2x) = ᴋɪʟʟ + ʙᴀɴ"
    )
    kb = [
        [
            cb.styled_button(f"🔒 ʟᴏᴄᴋᴅᴏᴡɴ: {'ᴏɴ' if lockdown else 'ᴏғғ'}",
                             callback_data="admin_lockdown",
                             style="danger" if lockdown else "success"),
            cb.styled_button(f"👥 ᴘᴇɴᴅɪɴɢ ({pending})",
                             callback_data="admin_pending_view", style="primary"),
        ],
        [cb.styled_button("🔙 ᴍᴇɴᴜ", callback_data="menu_back")],
    ]
    return await _emit(chat_id, message_id, text, kb, edit=edit)


async def _pending_view(chat_id, message_id, edit=True):
    """List of users waiting for approval, with Approve/Reject buttons."""
    pending = await db.get_pending_users()
    kb = []
    if not pending:
        text = "⊡ <b>ɴᴏ ᴘᴇɴᴅɪɴɢ ᴀᴘᴘʀᴏᴠᴀʟs</b> — sᴀʙ ᴄʟᴇᴀʀ ✅"
    else:
        text = f"⏳ <b>ᴘᴇɴᴅɪɴɢ ᴀᴘᴘʀᴏᴠᴀʟs:</b> {len(pending)}\n\n"
        for u in pending[:12]:
            name = esc(u.get("username") or u.get("user_id"))
            created = str(u.get("created_at", ""))[:16]
            text += f"• <code>{u['user_id']}</code> {name}  [{created}]\n"
            kb.append([
                cb.styled_button("✅ ᴀᴘᴘʀᴏᴠᴇ", callback_data=f"admin_approve_{u['user_id']}", style="success"),
                cb.styled_button("🗑 ʀᴇᴊᴇᴄᴛ", callback_data=f"admin_reject_{u['user_id']}", style="danger"),
            ])
    if pending:
        kb.append([cb.styled_button(f"✅ ᴀᴘᴘʀᴏᴠᴇ ᴀʟʟ ({len(pending)})",
                                    callback_data="admin_approve_all", style="success")])
    kb.append([
        cb.styled_button("🛡 sᴇᴄᴜʀɪᴛʏ ʜᴜʙ", callback_data="admin_security", style="primary"),
        cb.styled_button("🔙 ᴍᴇɴᴜ", callback_data="menu_back"),
    ])
    return await _emit(chat_id, message_id, text, kb, edit=edit)


async def _resolve_pending(user_id, approve: bool, admin_id: int, chat_id: int, message_id):
    """Apply approve/reject, notify the user, refresh the pending view (inline only)."""
    await db.set_user_approved(user_id, approve)
    await security.log_security_event(user_id, "APPROVED" if approve else "REJECTED", f"By admin {admin_id}")
    try:
        lang = await db.get_user_lang(user_id)
        key = "approved_notify" if approve else "rejected_notify"
        await _bot_send(user_id, ui.msg(lang, key))
    except Exception:
        pass
    if message_id:
        await _pending_view(chat_id, message_id, edit=True)


async def _bot_send(chat_id: int, text: str):
    """Fire-and-forget direct send used by background/admin notifiers."""
    await cb.send_message_colored(chat_id=chat_id, text=text)


async def _approve_all_users(admin_id: int) -> int:
    """Bulk-approve every pending user. Returns how many were approved."""
    pending = await db.get_pending_users()
    for u in pending:
        await db.set_user_approved(u["user_id"], True)
        try:
            lang = await db.get_user_lang(u["user_id"])
            await _bot_send(u["user_id"], ui.msg(lang, "approved_notify"))
        except Exception:
            pass
    if pending:
        await security.log_security_event(admin_id, "APPROVE_ALL", f"{len(pending)} users")
    return len(pending)


async def approveall_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/approveall — sab pending users ek click mein approve karo."""
    if not is_admin(update.effective_user.id):
        return
    count = await _approve_all_users(update.effective_user.id)
    await update.message.reply_text(f"✅ Approved all: <b>{count}</b> user(s)", parse_mode=ParseMode.HTML)


async def approve_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text("Usage: /approve <user_id>")
        return
    try:
        uid = int(context.args[0])
    except ValueError:
        await update.message.reply_text("✗ Invalid ID.")
        return
    if not await db.user_exists(uid):
        await update.message.reply_text("✗ User not found.")
        return
    await _resolve_pending(uid, True, update.effective_user.id, update.effective_user.id, None)
    await update.message.reply_text(f"✅ Approved <code>{uid}</code>", parse_mode=ParseMode.HTML)


async def reject_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text("Usage: /reject <user_id>")
        return
    try:
        uid = int(context.args[0])
    except ValueError:
        await update.message.reply_text("✗ Invalid ID.")
        return
    if not await db.user_exists(uid):
        await update.message.reply_text("✗ User not found.")
        return
    await _resolve_pending(uid, False, update.effective_user.id, update.effective_user.id, None)
    await update.message.reply_text(f"🗑 Rejected <code>{uid}</code>", parse_mode=ParseMode.HTML)


async def pending_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    await _pending_view(update.effective_user.id, None, edit=False)


async def lockdown_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    current = await db.get_lockdown()
    if context.args and context.args[0].lower() in ("on", "off"):
        new_state = context.args[0].lower() == "on"
    else:
        new_state = not current
    await db.set_lockdown(new_state)
    await security.log_security_event(update.effective_user.id, "LOCKDOWN",
                                      f"Set to {new_state} by admin")
    await update.message.reply_text(
        f"🔒 Lockdown {'ᴏɴ' if new_state else 'ᴏғғ'} — users {'CANNOT' if new_state else 'CAN'} create VPS now.",
        parse_mode=ParseMode.HTML,
    )


async def warn_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/warn <user_id> [reason] — manual abuse strike. N strikes = auto-ban."""
    if not is_admin(update.effective_user.id):
        return
    if len(context.args) < 1:
        await update.message.reply_text("Usage: /warn <user_id> [reason]")
        return
    try:
        uid = int(context.args[0])
    except ValueError:
        await update.message.reply_text("✗ Invalid ID.")
        return
    reason = " ".join(context.args[1:]) or "Manual warning"
    banned = await security.report_abuse(uid, "-", "MANUAL_WARN", reason, auto=False)
    strikes = await security.get_unresolved_abuse(uid)
    limit = config.ABUSE_STRIKE_LIMIT
    try:
        lang = await db.get_user_lang(uid)
        if banned:
            await _bot_send(uid, ui.msg(lang, "banned", reason=esc(f"{reason} (strike ban)")))
        else:
            await _bot_send(uid, ui.msg(lang, "warn_notify", strikes=strikes, limit=limit, reason=esc(reason)))
    except Exception:
        pass
    await update.message.reply_text(
        f"⊘ Warned <code>{uid}</code> — strike {strikes}/{limit}"
        + (" → AUTO-BANNED" if banned else ""),
        parse_mode=ParseMode.HTML,
    )


async def security_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    await _security_hub(update.effective_user.id, None, edit=False)


# ============ Payment Upgrade Flow (QR → screenshot → admin approve) ============

async def _pay_session(chat_id, user_id, lang, plan_key, context):
    """QR photo + instructions user ko bhejo; phir screenshot flow shuru."""
    plan = config.VPS_PLANS.get(plan_key)
    if not plan or plan["price"] <= 0:
        return
    qr = await db.get_payment_qr()
    if not qr:
        await _bot_send(chat_id, ui.msg(lang, "pay_no_qr"))
        return
    caption = ui.msg(
        lang, "pay_qr_caption",
        plan=esc(plan["name"]), price=plan["price"],
        days=plan["time_seconds"] // 86400, ram=plan["ram"], cpu=plan["cpu"],
    )
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton(ui.msg(lang, "pay_btn"), callback_data=f"pay_proof_{plan_key}"),
    ]])
    try:
        await context.bot.send_photo(
            chat_id=chat_id, photo=qr, caption=caption,
            parse_mode=ParseMode.HTML, reply_markup=kb,
        )
    except Exception:
        await _bot_send(chat_id, ui.msg(lang, "pay_no_qr"))


async def cancel_pay_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("pay_wait", None)
    await update.message.reply_text("✋ Payment flow cancel.")


async def setqr_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/setqr <url|file_id> (ya QR photo ka reply karke /setqr) — admin payment QR set karo."""
    if not is_admin(update.effective_user.id):
        return
    qr = None
    if context.args:
        qr = context.args[0]
    elif update.message.reply_to_message and update.message.reply_to_message.photo:
        qr = update.message.reply_to_message.photo[-1].file_id
    if not qr:
        await update.message.reply_text("Usage: /setqr https://image-link.jpg\nYa QR photo ka reply karke /setqr bhejo.")
        return
    await db.set_payment_qr(qr)
    config.PAYMENT_QR_URL = qr
    await update.message.reply_text("✅ Payment QR set ho gaya — ab paid plans par users ko ye QR milega.")


async def payment_screenshot_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Jab user payment screenshot bhejta hai (pay_wait state mein) → admin ko request."""
    if not update.message or not update.message.photo:
        return
    ud = context.user_data
    plan_key = ud.get("pay_wait")
    if not plan_key or plan_key not in config.VPS_PLANS:
        return  # koi pending payment flow nahi — photo ignore
    ud.pop("pay_wait", None)

    uid = update.effective_user.id
    plan = config.VPS_PLANS[plan_key]
    file_id = update.message.photo[-1].file_id
    await db.add_payment(uid, plan_key, plan["price"], file_id)

    user = update.effective_user
    uname = user.username or user.first_name or str(uid)
    caption = (
        f"💳 <b>ᴘᴀʏᴍᴇɴᴛ ʀᴇǫᴜᴇsᴛ</b>\n\n"
        f"👤 ᴜsᴇʀ: <code>{uid}</code> (@{esc(str(uname)[:20])})\n"
        f"💎 ᴘʟᴀɴ: <b>{esc(plan['name'])}</b>\n"
        f"💰 ᴀᴍᴏᴜɴᴛ: ₹{plan['price']}\n"
        f"🕒 {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
        f"Screenshot verify karke Approve dabao."
    )
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Approve", callback_data=f"admin_payok_{uid}_{plan_key}"),
        InlineKeyboardButton("❌ Reject", callback_data=f"admin_payno_{uid}_{plan_key}"),
    ]])
    try:
        await context.bot.send_photo(
            chat_id=config.ADMIN_ID, photo=file_id,
            caption=caption, parse_mode=ParseMode.HTML, reply_markup=kb,
        )
    except Exception:
        pass
    await update.message.reply_text(
        ui.msg(await db.get_user_lang(uid), "pay_sent"), parse_mode=ParseMode.HTML,
    )


# ============ Callback Handler ============

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    chat_id = query.message.chat_id
    message_id = query.message.message_id
    data = query.data
    lang = await db.get_user_lang(user_id)

    # ---- generic actions ----
    if data == "noop":
        return

    if data == "cancel":
        await cb.edit_message_colored(chat_id, message_id, text=ui.msg(lang, "cancel_done"), reply_markup=None)
        return

    if data == "check_join":
        # Re-verify channel join
        all_joined = True
        for channel in config.FORCE_JOIN_CHANNELS:
            try:
                member = await context.bot.get_chat_member(chat_id=channel, user_id=user_id)
                if member.status in ["left", "kicked"]:
                    all_joined = False
                    break
            except Exception:
                all_joined = False
                break
        if all_joined:
            await query.edit_message_text("✓ ᴠᴇʀɪғɪᴇᴅ! ɴᴏᴡ ᴜsᴇ /start ᴛᴏ ʙᴇɢɪɴ.")
        else:
            await query.answer("✗ ʏᴏᴜ ʜᴀᴠᴇɴ'ᴛ ᴊᴏɪɴᴇᴅ ᴀʟʟ ᴄʜᴀɴɴᴇʟs ʏᴇᴛ!", show_alert=True)
        return

    # ---- language switcher ----
    if data == "menu_language":
        await show_language(chat_id, message_id, user_id, lang)
        return

    if data in ("lang_set_en", "lang_set_hi"):
        new_lang = data.replace("lang_set_", "")
        await db.set_user_lang(user_id, new_lang)
        await show_home(chat_id, message_id, user_id, new_lang)
        return

    # ---- main menu hub ----
    if data == "menu_back":
        await show_home(chat_id, message_id, user_id, lang)
        return

    if data == "menu_create":
        await _perform_create(chat_id, message_id, user_id, lang, context, edit=True)
        return

    if data == "menu_myvps":
        page = _page_of(context)
        await show_myvps(chat_id, message_id, user_id, lang, page=page, edit=True, context=context)
        return

    if data in ("myvps_prev", "myvps_next"):
        total = len(await db.get_all_user_vps(user_id))
        page = _page_of(context)
        page = page - 1 if data == "myvps_prev" else page + 1
        if page < 0:
            page = max(0, total - 1)
        if total and page >= total:
            page = 0
        await show_myvps(chat_id, message_id, user_id, lang, page=page, edit=True, context=context)
        return

    if data == "menu_dashboard":
        await show_dashboard(chat_id, message_id, user_id, lang)
        return

    if data == "menu_invite":
        await show_invite(chat_id, message_id, user_id, lang)
        return

    if data == "menu_plans":
        await show_plans(chat_id, message_id, user_id, lang)
        return

    if data == "menu_help":
        await show_help(chat_id, message_id, user_id, lang)
        return

    # ---- legacy menu shortcuts (kept for compatibility) ----
    if data == "menu_restart":
        await restart_legacy_cb(chat_id, message_id, user_id, lang, None)
        return

    if data == "menu_delete":
        await ask_delete(chat_id, message_id, user_id, lang, short_id=None)
        return

    # ---- admin menu ----
    if data == "menu_admin":
        if not is_admin(user_id):
            return
        users = await db.get_all_users()
        banned = await security.get_banned_users()
        all_vps = await db.get_all_running_vps()
        text = (
            f"👑 <b>Admin Panel</b>\n\n"
            f"◈ Users: {len(users)}\n"
            f"◈ Running: {len(all_vps)}\n"
            f"⊘ Banned: {len(banned)}\n\n"
            f"/users • /ban • /unban\n"
            f"/forcekill • /logs • /stats\n"
            f"/broadcast"
        )
        await cb.edit_message_colored(chat_id, message_id, text=text,
                                      reply_markup=_back_kb(lang))
        return

    if data == "menu_analytics":
        if not is_admin(user_id):
            return
        report = await monitor.get_analytics()
        await cb.edit_message_colored(chat_id, message_id, text=report, reply_markup=_back_kb(lang))
        return

    # ===== SECURITY PACK ADMIN CALLBACKS =====
    if data == "admin_security":
        if not is_admin(user_id):
            return
        await _security_hub(chat_id, message_id, edit=True)
        return

    if data == "admin_pending_view":
        if not is_admin(user_id):
            return
        await _pending_view(chat_id, message_id, edit=True)
        return

    if data == "admin_lockdown":
        if not is_admin(user_id):
            return
        new_state = not await db.get_lockdown()
        await db.set_lockdown(new_state)
        await security.log_security_event(user_id, "LOCKDOWN", f"Toggled to {new_state}")
        await _security_hub(chat_id, message_id, edit=True)
        return

    if data == "admin_approve_all":
        if not is_admin(user_id):
            return
        await _approve_all_users(user_id)
        await _pending_view(chat_id, message_id, edit=True)
        return

    if data.startswith("admin_approve_") or data.startswith("admin_reject_"):
        if not is_admin(user_id):
            return
        try:
            approve = data.startswith("admin_approve_")
            target_id = int(data.replace("admin_approve_", "").replace("admin_reject_", ""))
        except ValueError:
            await query.edit_message_text("✗ Error.")
            return
        await _resolve_pending(target_id, approve, user_id, chat_id, message_id)
        return

    # ===== PAYMENT UPGRADE (pay_buy_ / pay_proof_ / admin_payok_ / admin_payno_) =====
    if data.startswith("pay_buy_"):
        plan_key = data.replace("pay_buy_", "")
        if plan_key not in config.VPS_PLANS or config.VPS_PLANS[plan_key]["price"] <= 0:
            return
        if await db.get_user_plan(user_id) == plan_key:
            await show_plans(chat_id, message_id, user_id, lang, edit=True)
            return
        await _pay_session(chat_id, user_id, lang, plan_key, context)
        return

    if data.startswith("pay_proof_"):
        plan_key = data.replace("pay_proof_", "")
        if plan_key not in config.VPS_PLANS:
            return
        context.user_data["pay_wait"] = plan_key
        await _bot_send(chat_id, ui.msg(lang, "pay_screenshot_now"))
        return

    if data.startswith("admin_payok_") or data.startswith("admin_payno_"):
        if not is_admin(user_id):
            return
        approve = data.startswith("admin_payok_")
        parts = data.split("_")[2:]          # [uid, plan_key]
        try:
            target_uid = int(parts[0])
        except (ValueError, IndexError):
            return
        plan_key = "_".join(parts[1:])
        if plan_key not in config.VPS_PLANS:
            return
        plan_data = config.VPS_PLANS[plan_key]

        if approve:
            await db.set_user_plan(target_uid, plan_key, add_time=plan_data["time_seconds"])
            vps = await db.get_user_vps(target_uid)
            if vps:
                try:
                    vps_manager.update_limits(vps["container_id"], ram=plan_data["ram"], cpu=plan_data["cpu"])
                except Exception:
                    pass
            await db.set_payment_status(target_uid, plan_key, "approved")
            await security.log_security_event(target_uid, "PAYMENT_APPROVED", f"{plan_key} by admin {user_id}")
            try:
                lang_t = await db.get_user_lang(target_uid)
                await _bot_send(target_uid, ui.msg(
                    lang_t, "pay_approved",
                    plan=esc(plan_data["name"]), days=plan_data["time_seconds"] // 86400,
                ))
            except Exception:
                pass
            await query.edit_message_caption(
                caption=f"✅ Approved: {esc(plan_data['name'])} for <code>{target_uid}</code>",
                parse_mode=ParseMode.HTML,
            )
        else:
            await db.set_payment_status(target_uid, plan_key, "rejected")
            await security.log_security_event(target_uid, "PAYMENT_REJECTED", f"{plan_key} by admin {user_id}")
            try:
                lang_t = await db.get_user_lang(target_uid)
                await _bot_send(target_uid, ui.msg(lang_t, "pay_rejected"))
            except Exception:
                pass
            await query.edit_message_caption(
                caption=f"❌ Rejected: {esc(plan_data['name'])} for <code>{target_uid}</code>",
                parse_mode=ParseMode.HTML,
            )
        return

    # ===== USER MANAGER BROWSER (umgr_*) =====
    if data.startswith("umgr_"):
        if not is_admin(user_id):
            return
        parts = data.replace("umgr_", "").split("_")

        if parts[0] == "pg":
            await _manage_list(chat_id, message_id, int(parts[1]), edit=True)
            return

        if parts[0] == "user":
            await _manage_detail(chat_id, message_id, int(parts[1]), 0, edit=True)
            return

        uid = int(parts[1])

        if parts[0] == "restart":
            vps = await db.get_user_vps(uid)
            if not vps:
                await _manage_detail(chat_id, message_id, uid, 0, edit=True)
                return
            ok = vps_manager.restart_vps(vps["container_id"])
            if ok:
                await security.log_security_event(uid, "VPS_RESTART", f"By admin {user_id}")
                await query.edit_message_text("🔄 ʀᴇsᴛᴀʀᴛɪɴɢ…")
                await _manage_detail(chat_id, message_id, uid, 0, edit=True)
            else:
                await query.edit_message_text("⊘ Restart fail (Docker?).")
            return

        if parts[0] == "del":
            vps = await db.get_user_vps(uid)
            if not vps:
                await _manage_detail(chat_id, message_id, uid, 0, edit=True)
                return
            await cb.edit_message_colored(
                chat_id,
                message_id,
                text=(
                    f"🗑 <b>Delete VPS?</b>\n\n"
                    f"🖥 <code>{esc(vps['container_name'])}</code>\n"
                    f"👤 ᴜsᴇʀ <code>{uid}</code>\n\n"
                    f"△ ᴜsᴇʀ ᴋᴀ ʙᴀʟᴀɴᴄᴇ ᴡᴀᴘs ᴍɪʟᴇɢᴀ (used time minus)."
                ),
                reply_markup=[[
                    cb.styled_button("✅ ʏᴇs, ᴅᴇʟᴇᴛᴇ", callback_data=f"umgr_delyes_{uid}", style="danger"),
                    cb.styled_button("❌ ᴄᴀɴᴄᴇʟ", callback_data=f"umgr_user_{uid}"),
                ]],
            )
            return

        if parts[0] == "delyes":
            vps = await db.get_user_vps(uid)
            if not vps:
                await _manage_detail(chat_id, message_id, uid, 0, edit=True)
                return
            ok = vps_manager.stop_vps(vps["container_id"])
            if ok:
                await db.remove_vps_instance(vps["container_id"])
                await security.log_security_event(uid, "ADMIN_DELVPS", f"By admin {user_id}")
                try:
                    await context.bot.send_message(
                        chat_id=uid,
                        text=f"🗑 ʏᴏᴜʀ ᴠᴘs ({vps['container_name']}) ᴅᴇʟᴇᴛᴇᴅ ʙʏ ᴀᴅᴍɪɴ.",
                    )
                except Exception:
                    pass
                await _manage_detail(chat_id, message_id, uid, 0, edit=True)
            else:
                await query.edit_message_text("✗ Delete fail (Docker?).")
            return

        if parts[0] in ("ext", "sub"):
            add = parts[0] == "ext"
            days = int(parts[2])
            balance, days_str = await _time_change(uid, days, add)
            await security.log_security_event(
                uid, "ADMIN_ADDTIME" if add else "ADMIN_REMOVETIME",
                f"{'+' if add else '-'}{days}d by admin {user_id}",
            )
            try:
                lang = await db.get_user_lang(uid)
                key = "time_added_admin" if add else "time_removed_admin"
                await _bot_send(uid, ui.msg(lang, key, days=days_str, balance=format_time(balance)))
            except Exception:
                pass
            await _manage_detail(chat_id, message_id, uid, 0, edit=True)
            return

    # ---- per-VPS action buttons ----
    if data.startswith("action_restart_"):
        short_id = data.replace("action_restart_", "")
        vps_list = await db.get_all_user_vps(user_id)
        vps = next((v for v in vps_list if v["container_id"].startswith(short_id)), None)
        if not vps:
            await cb.edit_message_colored(chat_id, message_id, text=ui.msg(lang, "no_vps_short"),
                                          reply_markup=_back_kb(lang))
            return
        success = vps_manager.restart_vps(vps["container_id"])
        if success:
            await security.log_security_event(user_id, "VPS_RESTART", vps["container_name"])
        page = _page_of(context)
        await show_myvps(chat_id, message_id, user_id, lang, page=page, edit=True, context=context)
        return

    if data.startswith("action_stats_"):
        short_id = data.replace("action_stats_", "")
        await show_vps_stats(chat_id, message_id, user_id, lang, short_id)
        return

    if data.startswith("action_del_"):
        short_id = data.replace("action_del_", "")
        await ask_delete(chat_id, message_id, user_id, lang, short_id=short_id)
        return

    # ---- confirmed delete (new flow) ----
    if data.startswith("do_delete_"):
        short_id = data.replace("do_delete_", "")
        vps_list = await db.get_all_user_vps(user_id)
        vps = next((v for v in vps_list if v["container_id"].startswith(short_id)), None)
        if not vps:
            await cb.edit_message_colored(chat_id, message_id, text=ui.msg(lang, "no_vps_short"),
                                          reply_markup=_back_kb(lang))
            return
        success = vps_manager.stop_vps(vps["container_id"])
        if success:
            await db.remove_vps_instance(vps["container_id"])
            await security.log_security_event(user_id, "VPS_DELETE", vps["container_name"])
            _set_page(context, 0)
            remaining = await db.get_remaining_seconds(user_id)
            text, kb = _deleted_screen(lang, remaining)
            await cb.edit_message_colored(chat_id, message_id, text=text, reply_markup=kb)
        else:
            await query.edit_message_text("✗ ᴅᴇʟᴇᴛᴇ ғᴀɪʟᴇᴅ.")
        return

    # ---- legacy direct delete (delete_<sid>) ----
    if data.startswith("delete_"):
        short_id = data.replace("delete_", "")
        vps_list = await db.get_all_user_vps(user_id)
        vps = next((v for v in vps_list if v["container_id"].startswith(short_id)), None)
        if not vps:
            await query.edit_message_text("✗ ᴠᴘs ɴᴏᴛ ғᴏᴜɴᴅ.")
            return
        success = vps_manager.stop_vps(vps["container_id"])
        if success:
            await db.remove_vps_instance(vps["container_id"])
            await security.log_security_event(user_id, "VPS_DELETE", vps["container_name"])
            _set_page(context, 0)
            remaining = await db.get_remaining_seconds(user_id)
            text, kb = _deleted_screen(lang, remaining)
            await cb.edit_message_colored(chat_id, message_id, text=text, reply_markup=kb)
        else:
            await query.edit_message_text("✗ ᴅᴇʟᴇᴛᴇ ғᴀɪʟᴇᴅ.")
        return

    # ===== ADMIN CONFIRM CALLBACKS =====
    if data.startswith("admin_delvps_"):
        if not is_admin(user_id):
            return
        try:
            target_id = int(data.replace("admin_delvps_", ""))
        except ValueError:
            await query.edit_message_text("✗ Error.")
            return

        vps = await db.get_user_vps(target_id)
        if not vps:
            await query.edit_message_text(
                f"⊡ ᴜsᴇʀ <code>{target_id}</code> ʜᴀs ɴᴏ ᴀᴄᴛɪᴠᴇ ᴠᴘs.",
                parse_mode="HTML",
            )
            return

        success = vps_manager.stop_vps(vps["container_id"])
        if success:
            await db.remove_vps_instance(vps["container_id"])
            await security.log_security_event(target_id, "ADMIN_DELVPS", f"By admin {user_id}")
            # Notify user
            try:
                target_lang = await db.get_user_lang(target_id)
                await context.bot.send_message(
                    chat_id=target_id,
                    text=ui.msg(target_lang, "vps_deleted", time=format_time(await db.get_remaining_seconds(target_id))),
                    parse_mode=ParseMode.HTML,
                )
            except Exception:
                pass
            await query.edit_message_text(
                f"✅ ᴠᴘs ᴅᴇʟᴇᴛᴇᴅ ғᴏʀ ᴜsᴇʀ <code>{target_id}</code>\n"
                f"ᴄᴏɴᴛᴀɪɴᴇʀ: <code>{vps['container_name']}</code>",
                parse_mode="HTML",
            )
        else:
            await query.edit_message_text("✗ ғᴀɪʟᴇᴅ ᴛᴏ ᴅᴇʟᴇᴛᴇ. ᴛʀʏ /forcekill")
        return

    if data.startswith("admin_ban_"):
        if not is_admin(user_id):
            return
        parts = data.replace("admin_ban_", "").split("_", 1)
        try:
            target_id = int(parts[0])
            reason = parts[1] if len(parts) > 1 else "Policy violation"
            vps = await db.get_user_vps(target_id)
            if vps:
                vps_manager.stop_vps(vps["container_id"])
                await db.remove_vps_instance(vps["container_id"])
            await security.ban_user(target_id, reason, hours=config.BAN_DURATION_HOURS, banned_by=user_id)
            try:
                await context.bot.send_message(chat_id=target_id, text=f"⊘ ʙᴀɴɴᴇᴅ: {reason}")
            except Exception:
                pass
            await query.edit_message_text(f"✅ ʙᴀɴɴᴇᴅ <code>{target_id}</code>", parse_mode="HTML")
        except (ValueError, IndexError):
            await query.edit_message_text("✗ Error.")
        return

    if data.startswith("admin_grantroot_"):
        if not is_admin(user_id):
            return
        try:
            target_id = int(data.replace("admin_grantroot_", ""))
            await query.edit_message_text("⟳ ɢʀᴀɴᴛɪɴɢ ʀᴏᴏᴛ...")
            await _do_grantroot(context, target_id, chat_id)
        except ValueError:
            await query.edit_message_text("✗ Error.")
        return

    logger.warning(f"Unhandled callback: {data}")


async def restart_legacy_cb(chat_id, message_id, user_id, lang, short_id):
    """Shared restart helper used by legacy menu_restart callback."""
    vps_list = await db.get_all_user_vps(user_id)
    vps = vps_list[0] if vps_list else None
    if not vps:
        await cb.edit_message_colored(chat_id, message_id, text=ui.msg(lang, "no_vps_short"),
                                      reply_markup=_back_kb(lang))
        return
    short = short_id or vps["container_id"][:12]
    vps = next((v for v in vps_list if v["container_id"].startswith(short)), vps)
    success = vps_manager.restart_vps(vps["container_id"])
    if success:
        await security.log_security_event(user_id, "VPS_RESTART", vps["container_name"])
    await show_myvps(chat_id, message_id, user_id, lang, page=0, edit=True, context=None)


# ============ Main ============

async def _task_wrapper(coro, name: str, app):
    """Wrap background task — log crash and notify admin."""
    try:
        await coro
    except Exception as e:
        logger.error(f"Background task '{name}' crashed: {e}", exc_info=True)
        try:
            await app.bot.send_message(
                chat_id=config.ADMIN_ID,
                text=(
                    f"🔴 <b>ʙᴀᴄᴋɢʀᴏᴜɴᴅ ᴛᴀsᴋ ᴄʀᴀsʜᴇᴅ!</b>\n\n"
                    f"ᴛᴀsᴋ: <code>{name}</code>\n"
                    f"ᴇʀʀᴏʀ: <code>{esc(str(e)[:200])}</code>\n\n"
                    f"⚠️ ʙᴏᴛ ᴍᴀʏ ɴᴏᴛ ʙᴇ ᴍᴏɴɪᴛᴏʀɪɴɢ ᴄᴏɴᴛᴀɪɴᴇʀs!"
                ),
                parse_mode="HTML",
            )
        except Exception:
            pass


async def post_init(application: Application):
    global _bot_username
    await db.init_db()
    await security.init_security_db()

    # Cache bot username globally — used in all invite links
    me = await application.bot.get_me()
    _bot_username = me.username

    # Load saved force join channels from DB — env + bot-added DONO merge
    # (env channels pehle, baad mein /addchannel se add kiye hue)
    saved = await db.db.settings.find_one({"key": "force_join_channels"})
    if saved and saved.get("channels"):
        merged = list(config.FORCE_JOIN_CHANNELS)
        for ch in saved["channels"]:
            if ch not in merged:
                merged.append(ch)
        config.FORCE_JOIN_CHANNELS = merged

    # Background tasks — wrapped with crash handler + admin alert
    asyncio.create_task(_task_wrapper(auto_delete_expired_vps(application), "auto_delete_expired_vps", application))
    asyncio.create_task(_task_wrapper(container_watchdog(application), "container_watchdog", application))
    asyncio.create_task(_task_wrapper(monitor_containers(application), "monitor_containers", application))
    asyncio.create_task(_task_wrapper(ddos_outbound_watchdog(application), "ddos_outbound_watchdog", application))
    asyncio.create_task(_task_wrapper(monitor.expiry_reminders(application), "expiry_reminders", application))
    asyncio.create_task(_task_wrapper(monitor.check_bandwidth_limits(application), "check_bandwidth_limits", application))
    asyncio.create_task(_task_wrapper(monitor.ddos_detection(application), "ddos_detection", application))
    asyncio.create_task(_task_wrapper(monitor.filesystem_scanner(application), "filesystem_scanner", application))
    logger.info(f"Bot initialized. Username: @{_bot_username}")


def main():
    if not config.BOT_TOKEN:
        print("✗ BOT_TOKEN not set!")
        return

    app = Application.builder().token(config.BOT_TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("create", create_vps_cmd))
    app.add_handler(CommandHandler("myvps", my_vps))
    app.add_handler(CommandHandler("delete", delete_vps_cmd))
    app.add_handler(CommandHandler("invite", invite_cmd))
    app.add_handler(CommandHandler("restart", restart_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("dashboard", dashboard_cmd))
    app.add_handler(CommandHandler("plans", plans_cmd))
    app.add_handler(CommandHandler("language", language_cmd))
    app.add_handler(CommandHandler("lang", language_cmd))

    app.add_handler(CommandHandler("admin", admin_cmd))
    app.add_handler(CommandHandler("analytics", analytics_cmd))
    app.add_handler(CommandHandler("addchannel", addchannel_cmd))
    app.add_handler(CommandHandler("removechannel", removechannel_cmd))
    app.add_handler(CommandHandler("channels", channels_cmd))
    app.add_handler(CommandHandler("manage", manage_cmd))
    app.add_handler(CommandHandler("um", manage_cmd))  # alias
    app.add_handler(CommandHandler("setplan", setplan_cmd))
    app.add_handler(CommandHandler("users", users_cmd))
    app.add_handler(CommandHandler("ban", ban_cmd))
    app.add_handler(CommandHandler("unban", unban_cmd))
    app.add_handler(CommandHandler("forcekill", forcekill_cmd))
    app.add_handler(CommandHandler("delvps", delvps_cmd))
    app.add_handler(CommandHandler("logs", logs_cmd))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(CommandHandler("broadcast", broadcast_cmd))
    app.add_handler(CommandHandler("grantroot", grantroot_cmd))
    app.add_handler(CommandHandler("revokeroot", revokeroot_cmd))
    app.add_handler(CommandHandler("addtime", addtime_cmd))
    app.add_handler(CommandHandler("removetime", removetime_cmd))
    app.add_handler(CommandHandler("deduct", removetime_cmd))  # alias

    # Security pack
    app.add_handler(CommandHandler("approveall", approveall_cmd))
    app.add_handler(CommandHandler("approve", approve_cmd))
    app.add_handler(CommandHandler("reject", reject_cmd))
    app.add_handler(CommandHandler("pending", pending_cmd))
    app.add_handler(CommandHandler("warn", warn_cmd))
    app.add_handler(CommandHandler("lockdown", lockdown_cmd))
    app.add_handler(CommandHandler("security", security_cmd))
    app.add_handler(CommandHandler("sec", security_cmd))

    # Payment upgrade flow
    app.add_handler(CommandHandler("cancel_pay", cancel_pay_cmd))
    app.add_handler(CommandHandler("setqr", setqr_cmd))
    app.add_handler(MessageHandler(filters.PHOTO, payment_screenshot_handler))

    app.add_handler(CallbackQueryHandler(button_callback))

    print("🤖 Bot started!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
