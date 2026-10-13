"""
Advanced Monitoring Module:
- Resource usage dashboard (CPU/RAM/Bandwidth)
- Bandwidth monitoring + auto-kill on limit
- Auto-renewal reminders (6h, 1h before expiry)
- Network traffic analysis (DDoS detection)
- Filesystem scanning for miners
"""
import logging
import asyncio
from datetime import datetime

import docker
from telegram.constants import ParseMode

import config
import database as db
import vps_manager
import security

logger = logging.getLogger(__name__)


_docker_client = None

def _get_client():
    """Reuse single Docker client — no reconnect on every call."""
    global _docker_client
    if _docker_client is None:
        _docker_client = docker.from_env()
    return _docker_client


# ============ 4. RESOURCE USAGE DASHBOARD ============

async def get_usage_report(user_id: int) -> str | None:
    """Generate detailed resource usage report for a user's VPS."""
    vps = await db.get_user_vps(user_id)
    if not vps:
        return None

    stats = vps_manager.get_container_stats(vps["container_id"])
    if not stats:
        return None

    # Get bandwidth
    bandwidth = get_container_bandwidth(vps["container_id"])

    # Calculate time used
    started_at = datetime.fromisoformat(vps["started_at"])
    uptime_seconds = int((datetime.now() - started_at).total_seconds())
    uptime_h = uptime_seconds // 3600
    uptime_m = (uptime_seconds % 3600) // 60

    remaining = await db.get_remaining_seconds(user_id)
    time_left = max(0, remaining - uptime_seconds)

    # CPU bar
    cpu_bar = _progress_bar(stats["cpu_percent"], 100)
    # RAM bar
    ram_bar = _progress_bar(stats["memory_percent"], 100)
    # Time bar
    time_percent = ((remaining - time_left) / remaining * 100) if remaining > 0 else 100
    time_bar = _progress_bar(time_percent, 100)
    # Bandwidth bar
    bw_percent = (bandwidth["tx_mb"] / config.BANDWIDTH_LIMIT_MB * 100) if config.BANDWIDTH_LIMIT_MB > 0 else 0
    bw_bar = _progress_bar(min(bw_percent, 100), 100)

    report = (
        f"⟐ <b>ʀᴇsᴏᴜʀᴄᴇ ᴅᴀsʜʙᴏᴀʀᴅ</b>\n\n"
        f"◈ {vps['container_name']}\n"
        f"⏱️ ᴜᴘᴛɪᴍᴇ: {uptime_h}ʜ {uptime_m}ᴍ\n\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"⟐ <b>ᴄᴘᴜ:</b> {stats['cpu_percent']}%\n"
        f"{cpu_bar}\n\n"
        f"⟐ <b>ʀᴀᴍ:</b> {stats['memory_used_mb']}ᴍʙ / {stats['memory_limit_mb']}ᴍʙ\n"
        f"{ram_bar}\n\n"
        f"⟐ <b>ʙᴀɴᴅᴡɪᴅᴛʜ:</b> ↑{bandwidth['tx_mb']}ᴍʙ / {config.BANDWIDTH_LIMIT_MB}ᴍʙ\n"
        f"{bw_bar}\n\n"
        f"⟐ <b>ᴛɪᴍᴇ ᴜsᴇᴅ:</b>\n"
        f"{time_bar}\n\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"⟐ ᴘʀᴏᴄᴇssᴇs: {stats['pids']}/{config.CONTAINER_PIDS_LIMIT}\n"
        f"↓ ʀx: {bandwidth['rx_mb']}ᴍʙ | ↑ ᴛx: {bandwidth['tx_mb']}ᴍʙ\n"
        f"◔ ᴛɪᴍᴇ ʟᴇғᴛ: <b>{_format_seconds(time_left)}</b>"
    )
    return report


def _progress_bar(percent: float, max_val: float, length: int = 15) -> str:
    """Generate text progress bar."""
    filled = int(percent / max_val * length) if max_val > 0 else 0
    filled = min(filled, length)
    bar = "█" * filled + "░" * (length - filled)
    if percent > 80:
        return f"[{bar}] △ {percent:.0f}%"
    return f"[{bar}] {percent:.0f}%"


def _format_seconds(seconds: int) -> str:
    if seconds <= 0:
        return "0s"
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    mins = (seconds % 3600) // 60
    if days > 0:
        return f"{days}ᴅ {hours}ʜ {mins}ᴍ"
    elif hours > 0:
        return f"{hours}ʜ {mins}ᴍ"
    return f"{mins}ᴍ"


# ============ 8. BANDWIDTH MONITORING ============

def get_container_bandwidth(container_id: str) -> dict:
    """Get container's network usage in MB."""
    try:
        container = _get_client().containers.get(container_id)
        stats = container.stats(stream=False)
        networks = stats.get("networks", {})
        rx_bytes = 0
        tx_bytes = 0
        for iface in networks.values():
            rx_bytes += iface.get("rx_bytes", 0)
            tx_bytes += iface.get("tx_bytes", 0)
        return {
            "rx_mb": round(rx_bytes / (1024 * 1024), 2),
            "tx_mb": round(tx_bytes / (1024 * 1024), 2),
            "rx_bytes": rx_bytes,
            "tx_bytes": tx_bytes,
        }
    except Exception:
        return {"rx_mb": 0, "tx_mb": 0, "rx_bytes": 0, "tx_bytes": 0}


async def check_bandwidth_limits(app):
    """Check all containers for bandwidth abuse. Auto-kill on exceed."""
    while True:
        try:
            all_vps = await db.get_all_running_vps()
            for vps in all_vps:
                bw = get_container_bandwidth(vps["container_id"])
                if bw["tx_mb"] > config.BANDWIDTH_LIMIT_MB:
                    user_id = vps["user_id"]

                    # Kill VPS
                    vps_manager.force_kill_container(vps["container_id"])
                    await db.remove_vps_instance(vps["container_id"])

                    # Ban user
                    await security.ban_user(
                        user_id,
                        f"ᴀᴜᴛᴏ-ʙᴀɴ: ʙᴀɴᴅᴡɪᴅᴛʜ ᴇxᴄᴇᴇᴅᴇᴅ ({bw['tx_mb']}ᴍʙ)",
                        hours=config.BAN_DURATION_HOURS,
                    )

                    # Notify user
                    try:
                        await app.bot.send_message(
                            chat_id=user_id,
                            text=(
                                "⊘ <b>ʙᴀɴɴᴇᴅ: ʙᴀɴᴅᴡɪᴅᴛʜ ᴇxᴄᴇᴇᴅᴇᴅ</b>\n\n"
                                f"ʏᴏᴜ ᴜsᴇᴅ {bw['tx_mb']}ᴍʙ (ʟɪᴍɪᴛ: {config.BANDWIDTH_LIMIT_MB}ᴍʙ)\n"
                                f"ᴠᴘs ᴛᴇʀᴍɪɴᴀᴛᴇᴅ. ʙᴀɴ: {config.BAN_DURATION_HOURS}ʜ"
                            ),
                            parse_mode=ParseMode.HTML,
                        )
                    except Exception:
                        pass

                    # Notify admin
                    try:
                        await app.bot.send_message(
                            chat_id=config.ADMIN_ID,
                            text=(
                                f"● <b>ʙᴀɴᴅᴡɪᴅᴛʜ ᴀʙᴜsᴇ</b>\n"
                                f"ᴜsᴇʀ: <code>{user_id}</code>\n"
                                f"ᴛx: {bw['tx_mb']}ᴍʙ / {config.BANDWIDTH_LIMIT_MB}ᴍʙ\n"
                                f"ᴀᴜᴛᴏ-ʙᴀɴɴᴇᴅ + ᴠᴘs ᴋɪʟʟᴇᴅ\n"
                                f"/unban {user_id}"
                            ),
                            parse_mode=ParseMode.HTML,
                        )
                    except Exception:
                        pass

                    logger.warning(f"BANDWIDTH BAN: User {user_id} - TX: {bw['tx_mb']}MB")

        except Exception as e:
            logger.error(f"Bandwidth check error: {e}")

        await asyncio.sleep(config.BANDWIDTH_CHECK_INTERVAL)


# ============ 9. AUTO-RENEWAL REMINDERS ============

async def expiry_reminders(app):
    """Send reminders at 6h and 1h before VPS expiry."""
    reminded_6h: set[int] = set()
    reminded_1h: set[int] = set()

    while True:
        try:
            all_vps = await db.get_all_running_vps()
            for vps in all_vps:
                user_id = vps["user_id"]
                remaining = await db.get_remaining_seconds(user_id)
                started_at = datetime.fromisoformat(vps["started_at"])
                used = int((datetime.now() - started_at).total_seconds())
                time_left = max(0, remaining - used)

                # 6 hour reminder
                if config.REMINDER_6H and 0 < time_left <= 21600 and user_id not in reminded_6h:
                    reminded_6h.add(user_id)
                    import bot as _bot_module
                    invite_link = f"https://t.me/{_bot_module._bot_username}?start=invite_{user_id}"
                    try:
                        await app.bot.send_message(
                            chat_id=user_id,
                            text=(
                                f"△ <b>6 ʜᴏᴜʀs ʟᴇғᴛ!</b>\n\n"
                                f"ʏᴏᴜʀ ᴠᴘs ᴡɪʟʟ ᴇxᴘɪʀᴇ ɪɴ ~{_format_seconds(time_left)}.\n\n"
                                f"⟡ ɪɴᴠɪᴛᴇ ғʀɪᴇɴᴅs ᴛᴏ ᴇxᴛᴇɴᴅ:\n"
                                f"<code>{invite_link}</code>\n\n"
                                f"ᴇᴀᴄʜ ɪɴᴠɪᴛᴇ = +1 ᴅᴀʏ ᴀᴅᴅᴇᴅ!"
                            ),
                            parse_mode=ParseMode.HTML,
                        )
                    except Exception:
                        pass

                # 1 hour reminder
                elif config.REMINDER_1H and 0 < time_left <= 3600 and user_id not in reminded_1h:
                    reminded_1h.add(user_id)
                    import bot as _bot_module
                    invite_link = f"https://t.me/{_bot_module._bot_username}?start=invite_{user_id}"
                    try:
                        await app.bot.send_message(
                            chat_id=user_id,
                            text=(
                                f"△ <b>1 ʜᴏᴜʀ ʟᴇғᴛ!</b>\n\n"
                                f"◔ ʏᴏᴜʀ ᴠᴘs ᴡɪʟʟ ʙᴇ <b>ᴅᴇʟᴇᴛᴇᴅ</b> ɪɴ ~{time_left // 60} ᴍɪɴᴜᴛᴇs!\n\n"
                                f"⟡ ǫᴜɪᴄᴋ — sʜᴀʀᴇ ᴛʜɪs ʟɪɴᴋ ɴᴏᴡ:\n"
                                f"<code>{invite_link}</code>\n\n"
                                f"↯ 1 ɪɴᴠɪᴛᴇ = +1 ᴅᴀʏ sᴀᴠᴇᴅ!"
                            ),
                            parse_mode=ParseMode.HTML,
                        )
                    except Exception:
                        pass

                # Reset if time was extended
                if time_left > 21600:
                    reminded_6h.discard(user_id)
                    reminded_1h.discard(user_id)
                elif time_left > 3600:
                    reminded_1h.discard(user_id)

        except Exception as e:
            logger.error(f"Reminder error: {e}")

        await asyncio.sleep(300)  # Check every 5 min


# ============ 10. ADMIN ANALYTICS ============

async def get_analytics() -> str:
    """Generate admin analytics report."""
    all_users = await db.get_all_users()
    all_running = await db.get_all_running_vps()
    banned = await security.get_banned_users()

    total_users = len(all_users)
    active_vps = len(all_running)
    banned_count = len(banned)

    # Total time served
    total_uptime = 0
    for vps in all_running:
        started_at = datetime.fromisoformat(vps["started_at"])
        total_uptime += int((datetime.now() - started_at).total_seconds())

    # Total bandwidth
    total_tx = 0
    total_rx = 0
    for vps in all_running:
        bw = get_container_bandwidth(vps["container_id"])
        total_tx += bw["tx_mb"]
        total_rx += bw["rx_mb"]

    # Users joined today
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    new_today = sum(1 for u in all_users if u.get("created_at") and u["created_at"] >= today_start)

    report = (
        f"⟐ <b>ᴀɴᴀʟʏᴛɪᴄs ᴅᴀsʜʙᴏᴀʀᴅ</b>\n\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"◈ <b>ᴜsᴇʀs:</b>\n"
        f"  • ᴛᴏᴛᴀʟ: {total_users}\n"
        f"  • ɴᴇᴡ ᴛᴏᴅᴀʏ: {new_today}\n"
        f"  • ʙᴀɴɴᴇᴅ: {banned_count}\n\n"
        f"◈ <b>ᴠᴘs:</b>\n"
        f"  • ᴀᴄᴛɪᴠᴇ: {active_vps}\n"
        f"  • ᴛᴏᴛᴀʟ ᴜᴘᴛɪᴍᴇ: {_format_seconds(total_uptime)}\n\n"
        f"🌐 <b>ɴᴇᴛᴡᴏʀᴋ:</b>\n"
        f"  • ᴛᴏᴛᴀʟ ᴛx: {total_tx:.1f}ᴍʙ\n"
        f"  • ᴛᴏᴛᴀʟ ʀx: {total_rx:.1f}ᴍʙ\n"
        f"━━━━━━━━━━━━━━━━━━"
    )
    return report


# ============ 12. NETWORK TRAFFIC ANALYSIS (DDoS) ============

async def ddos_detection(app):
    """Detect DDoS patterns: TCP flood + UDP flood attempts."""
    while True:
        try:
            all_vps = await db.get_all_running_vps()
            for vps in all_vps:
                user_id = vps["user_id"]
                container_id = vps["container_id"]

                # Check TCP connections
                tcp_count = _get_outbound_connections(container_id)
                # Check UDP send attempts (blocked by iptables, but logged)
                udp_attempts = _get_udp_attempts(container_id)

                abuse_type = None
                details = ""

                if tcp_count > config.DDOS_CONN_THRESHOLD:
                    abuse_type = "ᴛᴄᴘ ғʟᴏᴏᴅ"
                    details = f"ᴛᴄᴘ ᴄᴏɴɴᴇᴄᴛɪᴏɴs: {tcp_count}"
                elif udp_attempts > 50:
                    abuse_type = "ᴜᴅᴘ ғʟᴏᴏᴅ ᴀᴛᴛᴇᴍᴘᴛ"
                    details = f"ᴜᴅᴘ ᴘᴀᴄᴋᴇᴛs ʙʟᴏᴄᴋᴇᴅ: {udp_attempts}"

                if abuse_type:
                    # Kill + Ban
                    vps_manager.force_kill_container(container_id)
                    await db.remove_vps_instance(container_id)
                    await security.ban_user(
                        user_id,
                        f"ᴀᴜᴛᴏ-ʙᴀɴ: {abuse_type} ({details})",
                        hours=config.BAN_DURATION_HOURS,
                    )

                    # Notify user
                    try:
                        await app.bot.send_message(
                            chat_id=user_id,
                            text=(
                                f"⊘ <b>ʙᴀɴɴᴇᴅ: {abuse_type}</b>\n\n"
                                f"{details}\n"
                                f"ᴠᴘs ᴛᴇʀᴍɪɴᴀᴛᴇᴅ. ʙᴀɴ: {config.BAN_DURATION_HOURS}ʜ\n\n"
                                "ᴅᴅᴏs / ᴜᴅᴘ ғʟᴏᴏᴅ / ɴᴇᴛᴡᴏʀᴋ ᴀʙᴜsᴇ ɪs\n"
                                "sᴛʀɪᴄᴛʟʏ ᴘʀᴏʜɪʙɪᴛᴇᴅ."
                            ),
                            parse_mode=ParseMode.HTML,
                        )
                    except Exception:
                        pass

                    # Notify admin
                    try:
                        await app.bot.send_message(
                            chat_id=config.ADMIN_ID,
                            text=(
                                f"● <b>ᴅᴅᴏs: {abuse_type}</b>\n"
                                f"ᴜsᴇʀ: <code>{user_id}</code>\n"
                                f"{details}\n"
                                f"ᴀᴜᴛᴏ-ʙᴀɴɴᴇᴅ + ᴠᴘs ᴋɪʟʟᴇᴅ\n"
                                f"/unban {user_id}"
                            ),
                            parse_mode=ParseMode.HTML,
                        )
                    except Exception:
                        pass

                    logger.warning(f"DDOS BAN: User {user_id} - {abuse_type}: {details}")

        except Exception as e:
            logger.error(f"DDoS detection error: {e}")

        await asyncio.sleep(60)


def _get_outbound_connections(container_id: str) -> int:
    """Count outbound TCP connections."""
    try:
        container = _get_client().containers.get(container_id)
        result = container.exec_run("ss -tn state established", demux=True)
        if result.exit_code == 0 and result.output[0]:
            lines = result.output[0].decode().strip().split("\n")
            return max(0, len(lines) - 1)
    except Exception:
        pass
    return 0


def _get_udp_attempts(container_id: str) -> int:
    """Check blocked UDP packets (iptables DROP counter)."""
    try:
        container = _get_client().containers.get(container_id)
        # Check iptables counters for dropped UDP
        result = container.exec_run(
            "iptables -L OUTPUT -v -n 2>/dev/null | grep 'udp.*DROP' | awk '{print $1}'",
            demux=True,
        )
        if result.exit_code == 0 and result.output[0]:
            count_str = result.output[0].decode().strip()
            if count_str:
                # Parse packet count (could be like "1234" or "1.2K")
                count_str = count_str.split("\n")[0].strip()
                if "K" in count_str:
                    return int(float(count_str.replace("K", "")) * 1000)
                elif "M" in count_str:
                    return int(float(count_str.replace("M", "")) * 1000000)
                elif count_str.isdigit():
                    return int(count_str)
    except Exception:
        pass
    return 0


# ============ 13. FILESYSTEM SCANNING ============

async def filesystem_scanner(app):
    """Scan containers for suspicious files (miners, exploits)."""
    while True:
        try:
            all_vps = await db.get_all_running_vps()
            for vps in all_vps:
                user_id = vps["user_id"]
                threats = _scan_container(vps["container_id"])

                if threats:
                    threat_list = "\n".join(f"  • {t}" for t in threats[:10])

                    # Notify admin
                    try:
                        await app.bot.send_message(
                            chat_id=config.ADMIN_ID,
                            text=(
                                f"◈ <b>sᴜsᴘɪᴄɪᴏᴜs ғɪʟᴇs ᴅᴇᴛᴇᴄᴛᴇᴅ</b>\n\n"
                                f"ᴜsᴇʀ: <code>{user_id}</code>\n"
                                f"ᴠᴘs: {vps['container_name']}\n\n"
                                f"<b>ᴛʜʀᴇᴀᴛs:</b>\n{threat_list}\n\n"
                                f"/forcekill {vps['container_id'][:12]}\n"
                                f"/ban {user_id} Suspicious files detected"
                            ),
                            parse_mode=ParseMode.HTML,
                        )
                    except Exception:
                        pass

                    await security.report_abuse(
                        user_id, vps["container_id"],
                        "SUSPICIOUS_FILES", f"Found: {len(threats)} threats", auto=True,
                    )

        except Exception as e:
            logger.error(f"Filesystem scan error: {e}")

        await asyncio.sleep(config.SCAN_INTERVAL)


def _scan_container(container_id: str) -> list[str]:
    """Scan container filesystem for miner binaries and suspicious files."""
    threats = []
    try:
        container = _get_client().containers.get(container_id)

        # Check for known miner binaries
        miner_names = [
            "xmrig", "minerd", "cpuminer", "bfgminer", "cgminer",
            "ethminer", "nbminer", "t-rex", "phoenixminer", "lolminer",
            "ccminer", "nanominer", "gminer", "teamredminer",
        ]

        for path in config.SUSPICIOUS_PATHS:
            # Find executable files in suspicious paths
            cmd = f"find {path} -type f -executable 2>/dev/null | head -20"
            result = container.exec_run(cmd, demux=True)
            if result.exit_code == 0 and result.output[0]:
                files = result.output[0].decode().strip().split("\n")
                for f in files:
                    if not f:
                        continue
                    fname = f.split("/")[-1].lower()
                    # Check against known miner names
                    for miner in miner_names:
                        if miner in fname:
                            threats.append(f"● ᴍɪɴᴇʀ: {f}")
                            break
                    # Check for suspicious: no extension, recently created
                    if "." not in fname and len(fname) <= 5:
                        threats.append(f"△ sᴜsᴘᴇᴄᴛ: {f}")

        # Check for stratum connections in running processes
        cmd = "ps aux 2>/dev/null | grep -i 'stratum\\|pool\\|miner' | grep -v grep"
        result = container.exec_run(cmd, demux=True)
        if result.exit_code == 0 and result.output[0]:
            procs = result.output[0].decode().strip().split("\n")
            for proc in procs[:5]:
                if proc.strip():
                    threats.append(f"● ᴘʀᴏᴄᴇss: {proc[:60]}")

        # Check for crypto wallet addresses in files
        cmd = "grep -rl '4[0-9A-Za-z]\\{94\\}\\|0x[0-9a-fA-F]\\{40\\}' /tmp /dev/shm 2>/dev/null | head -5"
        result = container.exec_run(cmd, demux=True)
        if result.exit_code == 0 and result.output[0]:
            wallet_files = result.output[0].decode().strip().split("\n")
            for wf in wallet_files:
                if wf.strip():
                    threats.append(f"◇ ᴡᴀʟʟᴇᴛ ɪɴ: {wf}")

    except Exception:
        pass

    return threats
