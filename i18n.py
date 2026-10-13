"""
i18n module - bilingual UI layer (English + Hindi) for VishalCloud bot.

Usage:
    import i18n as ui
    ui.lbl(lang, "create")      -> button/label text
    ui.msg(lang, "welcome", name=..., time=...)   -> message template

`lang` is a 2-letter code: "en" (default, decorative caps style) or "hi" (हिंदी).
All placeholders are passed as keyword args to msg(); templates use {name} style.
"""

# ============ Supported languages ============
LANGS = ("en", "hi")

LANG_NAMES = {
    "en": "English 🇬🇧",
    "hi": "हिंदी 🇮🇳",
}

# ============ BUTTONS / SHORT LABELS ============
LBL = {
    "en": {
        "create": "☁️ ᴄʀᴇᴀᴛᴇ ᴠᴘs",
        "myvps": "🖥 ᴍʏ ᴠᴘs",
        "dashboard": "📊 ᴅᴀsʜʙᴏᴀʀᴅ",
        "invite": "🟡 ɪɴᴠɪᴛᴇ",
        "plans": "💎 ᴘʟᴀɴs",
        "help": "❓ ʜᴇʟᴘ",
        "admin": "👑 ᴀᴅᴍɪɴ",
        "analytics": "📈 ᴀɴᴀʟʏᴛɪᴄs",
        "language": "🌐 ʟᴀɴɢᴜᴀɢᴇ",
        "back": "🔙 ᴍᴇɴᴜ",
        "live_stats": "📊 ʟɪᴠᴇ sᴛᴀᴛs",
        "restart": "🔄 ʀᴇsᴛᴀʀᴛ",
        "delete": "🗑 ᴅᴇʟᴇᴛᴇ",
        "confirm_yes": "✅ ʏᴇs, ᴅᴇʟᴇᴛᴇ",
        "cancel": "❌ ᴄᴀɴᴄᴇʟ",
        "share": "✦ 📤 sʜᴀʀᴇ ɪɴᴠɪᴛᴇ ʟɪɴᴋ ✦",
        "create_go": "✦ ᴄʀᴇᴀᴛᴇ ᴠᴘs ✦",
        "invite_friends": "🟡 ɪɴᴠɪᴛᴇ ғʀɪᴇɴᴅs",
        "view_plans": "💎 ᴠɪᴇᴡ ᴘʟᴀɴs",
        "prev": "◀️ ᴘʀᴇᴠ",
        "next": "ɴᴇxᴛ ▶️",
        "ram": "💾 ʀᴀᴍ",
        "cpu": "⚡ ᴄᴘᴜ",
        "cpu_core": "ᴄᴏʀᴇ",
        "time": "⏳ ᴛɪᴍᴇ",
        "user": "👤 ᴜsᴇʀ",
        "pass": "🔐 ᴘᴀss",
        "ip": "🌐 ɪᴘ",
        "port": "🔌 ᴘᴏʀᴛ",
        "invites": "🎁 ɪɴᴠɪᴛᴇs",
        "total": "ᴛᴏᴛᴀʟ",
        "pids": "🔧 ᴘɪᴅs",
        "status": "📡 sᴛᴀᴛᴜs",
        "running": "ʀᴜɴɴɪɴɢ",
        "stopped": "sᴛᴏᴘᴘᴇᴅ",
        "free": "ғʀᴇᴇ",
        "days": "ᴅᴀʏs",
        "price": "💰 ᴘʀɪᴄᴇ",
        "current": "◂ ᴄᴜʀʀᴇɴᴛ",
    },
    "hi": {
        "create": "☁️ वीपीएस बनाएं",
        "myvps": "🖥 मेरा वीपीएस",
        "dashboard": "📊 डैशबोर्ड",
        "invite": "🟡 इनवाइट",
        "plans": "💎 प्लान्स",
        "help": "❓ मदद",
        "admin": "👑 एडमिन",
        "analytics": "📈 एनालिटिक्स",
        "language": "🌐 भाषा",
        "back": "🔙 मेन्यू",
        "live_stats": "📊 लाइव स्टैट्स",
        "restart": "🔄 रीस्टार्ट",
        "delete": "🗑 डिलीट",
        "confirm_yes": "✅ हाँ, डिलीट करें",
        "cancel": "❌ कैंसल",
        "share": "✦ 📤 लिंक शेयर करें ✦",
        "create_go": "✦ वीपीएस बनाएं ✦",
        "invite_friends": "🟡 दोस्तों को बुलाओ",
        "view_plans": "💎 प्लान्स देखें",
        "prev": "◀️ पिछला",
        "next": "अगला ▶️",
        "ram": "💾 रैम",
        "cpu": "⚡ सीपीयू",
        "cpu_core": "कोर",
        "time": "⏳ समय",
        "user": "👤 यूज़र",
        "pass": "🔐 पासवर्ड",
        "ip": "🌐 आईपी",
        "port": "🔌 पोर्ट",
        "invites": "🎁 इनवाइट्स",
        "total": "कुल",
        "pids": "🔧 पीआईडी",
        "status": "📡 स्टेटस",
        "running": "चालू",
        "stopped": "बंद",
        "free": "फ्री",
        "days": "दिन",
        "price": "💰 कीमत",
        "current": "◂ वर्तमान",
    },
}

# ============ MESSAGE TEMPLATES ============
MSG = {
    "en": {
        # home hub header shown on every main menu
        "home": "⟡ <b>ᴍᴀɪɴ ᴍᴇɴᴜ</b>\n\n⏳ ᴛɪᴍᴇ ʟᴇғᴛ: <b>{time}</b>\n👤 ɪᴅ: <code>{uid}</code>",
        # /start welcome (photo caption)
        "welcome": (
            "✧ ʜᴇʏ <b>{name}</b>! ❤️\n\n"
            "☁️ ɪ'ᴍ <b>ᴠɪsʜᴀʟ ᴄʟᴏᴜᴅ</b> — ʏᴏᴜʀ ᴘʀᴇᴍɪᴜᴍ ᴠᴘs ᴘʀᴏᴠɪᴅᴇʀ ☁️\n\n"
            "┌─────────────────────\n"
            "│ ☁️ ɪɴsᴛᴀɴᴛ ssʜ ᴠᴘs\n"
            "│ ⚡ ʟɪɢʜᴛɴɪɴɢ ғᴀsᴛ ᴅᴇᴘʟᴏʏ\n"
            "│ 🔒 ғᴜʟʟ ɪsᴏʟᴀᴛɪᴏɴ & sᴇᴄᴜʀɪᴛʏ\n"
            "│ 🎁 ɪɴᴠɪᴛᴇ ᴛᴏ ᴇᴀʀɴ ᴍᴏʀᴇ ᴛɪᴍᴇ\n"
            "└─────────────────────\n\n"
            "⏳ ᴛɪᴍᴇ ʙᴀʟᴀɴᴄᴇ: <b>{time}</b>\n"
            "👤 ɪᴅ: <code>{uid}</code>\n\n"
            "✦ ᴅᴇᴠᴇʟᴏᴘᴇʀ : <a href=\"https://t.me/{dev}\">❏ @{dev} ❏</a> ✦"
        ),
        "cooldown": (
            "⏳ <b>ᴄᴏᴏʟᴅᴏᴡɴ ᴀᴄᴛɪᴠᴇ!</b>\n\n"
            "┌─────────────────────\n"
            "│ ⟳ ᴘʟᴇᴀsᴇ ᴡᴀɪᴛ <b>{sec}s</b>\n"
            "└─────────────────────\n\n"
            "ᴛʀʏ ᴀɢᴀɪɴ ɪɴ ᴀ ᴍᴏᴍᴇɴᴛ."
        ),
        "already_active_title": (
            "⚠️ <b>ʏᴏᴜ ᴀʟʀᴇᴀᴅʏ ʜᴀᴠᴇ ᴀɴ ᴀᴄᴛɪᴠᴇ ᴠᴘs</b>\n"
            "─────────────────────\n"
        ),
        "nobal": (
            "⊘ <b>ɴᴏ ᴛɪᴍᴇ ʙᴀʟᴀɴᴄᴇ!</b>\n\n"
            "┌─────────────────────\n"
            "│ 🎁 ɪɴᴠɪᴛᴇ ғʀɪᴇɴᴅs = +1 ᴅᴀʏ ᴇᴀᴄʜ\n"
            "│ 💎 ᴜᴘɢʀᴀᴅᴇ ᴘʟᴀɴ ғᴏʀ ᴍᴏʀᴇ ᴛɪᴍᴇ\n"
            "└─────────────────────"
        ),
        "noports": "⊘ <b>ɴᴏ ᴘᴏʀᴛs ᴀᴠᴀɪʟᴀʙʟᴇ!</b>\n\nᴘʟᴇᴀsᴇ ᴛʀʏ ᴀɢᴀɪɴ ʟᴀᴛᴇʀ.",
        "deploying": (
            "⟳ <b>ᴅᴇᴘʟᴏʏɪɴɢ ʏᴏᴜʀ ᴠᴘs...</b>\n\n"
            "┌─────────────────────\n"
            "│ ☁️ sᴇᴛᴛɪɴɢ ᴜᴘ ɪsᴏʟᴀᴛᴇᴅ ᴇɴᴠɪʀᴏɴᴍᴇɴᴛ\n"
            "│ 🔒 ᴀᴘᴘʟʏɪɴɢ sᴇᴄᴜʀɪᴛʏ ᴘᴏʟɪᴄɪᴇs\n"
            "│ ⚡ sᴛᴀʀᴛɪɴɢ ssʜ sᴇʀᴠɪᴄᴇ\n"
            "└─────────────────────\n\n"
            "⏳ ᴘʟᴇᴀsᴇ ᴡᴀɪᴛ <b>30-60s</b>..."
        ),
        "deploy_success": (
            "✅ <b>ᴠᴘs ᴅᴇᴘʟᴏʏᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ!</b>\n\n"
            "┌ 🖥 <b>ᴄᴏɴɴᴇᴄᴛɪᴏɴ</b>\n"
            "│ <code>ssh {user}@{ip} -p {port}</code>\n"
            "│\n"
            "│ 👤 ᴜsᴇʀ : <code>{user}</code>\n"
            "│ 🔐 ᴘᴀss : <code>{password}</code>\n"
            "│ 🌐 ɪᴘ   : <code>{ip}</code>\n"
            "│ 🔌 ᴘᴏʀᴛ : <code>{port}</code>\n"
            "└─────────────────────\n\n"
            "┌ ⚙️ <b>sᴘᴇᴄs</b>\n"
            "│ 💾 ʀᴀᴍ  : {ram}\n"
            "│ ⚡ ᴄᴘᴜ  : {cpu} ᴄᴏʀᴇ\n"
            "│ ⏳ ᴛɪᴍᴇ : <b>{time}</b>\n"
            "└─────────────────────\n\n"
            "🎁 <a href=\"{link}\">sʜᴀʀᴇ ɪɴᴠɪᴛᴇ ʟɪɴᴋ</a> → +1 ᴅᴀʏ ғʀᴇᴇ!\n\n"
            "⚠️ ɴᴏ ᴍɪɴɪɴɢ • ɴᴏ ᴅᴅᴏs • ɴᴏ ᴀʙᴜsᴇ"
        ),
        "deploy_fail": "❌ <b>ᴅᴇᴘʟᴏʏ ғᴀɪʟᴇᴅ!</b>\n\n<code>{err}</code>",
        "deploy_no_docker": (
            "⊘ <b>ᴅᴏᴄᴋᴇʀ ᴜɴʀᴇᴀᴄʜᴀʙʟᴇ!</b>\n\n"
            "ᴛʜᴇ ʙᴏᴛ ᴄᴀɴ'ᴛ ᴄᴏɴɴᴇᴄᴛ ᴛᴏ ᴛʜᴇ ᴅᴏᴄᴋᴇʀ ᴇɴɢɪɴᴇ.\n\n"
            "ᴛʜɪs ᴜsᴜᴀʟʟʏ ᴍᴇᴀɴs ᴛʜᴇ ʙᴏᴛ ɪs ʀᴜɴɴɪɴɢ ᴏɴ ᴀ sᴇʀᴠᴇʀ\n"
            "ᴡɪᴛʜᴏᴜᴛ ᴅᴏᴄᴋᴇʀ ɪɴsᴛᴀʟʟᴇᴅ/ʀᴜɴɴɪɴɢ.\n\n"
            "👉 ᴀᴅᴍɪɴ sᴇ ᴄᴏɴᴛᴀᴄᴛ ᴋᴀʀᴏ."
        ),
        "approval_pending": (
            "⏳ <b>ᴀᴘᴘʀᴏᴠᴀʟ ᴘᴇɴᴅɪɴɢ</b>\n\n"
            "ʏᴏᴜʀ ᴀᴄᴄᴏᴜɴᴛ ɴᴇᴇᴅs ᴀᴅᴍɪɴ ᴀᴘᴘʀᴏᴠᴀʟ.\n\n"
            "ᴏɴᴄᴇ ᴀᴘᴘʀᴏᴠᴇᴅ, ʏᴏᴜ ᴄᴀɴ ᴄʀᴇᴀᴛᴇ ʏᴏᴜʀ ᴠᴘs."
        ),
        "approved_notify": (
            "✅ <b>ᴀᴄᴄᴏᴜɴᴛ ᴀᴘᴘʀᴏᴠᴇᴅ!</b>\n\n"
            "ʏᴏᴜ ᴄᴀɴ ɴᴏᴡ ᴄʀᴇᴀᴛᴇ ʏᴏᴜʀ ᴠᴘs → /create"
        ),
        "rejected_notify": (
            "⊘ <b>ᴀᴄᴄᴏᴜɴᴛ ʀᴇᴊᴇᴄᴛᴇᴅ</b>\n\n"
            "ʏᴏᴜ ᴄᴀɴ'ᴛ ᴜsᴇ ᴛʜɪs ʙᴏᴛ. ᴄᴏɴᴛᴀᴄᴛ ᴀᴅᴍɪɴ ɪғ ᴛʜɪs ɪs ᴀ ᴍɪsᴛᴀᴋᴇ."
        ),
        "time_added_admin": (
            "🎁 <b>ᴛɪᴍᴇ ᴀᴅᴅᴇᴅ ʙʏ ᴀᴅᴍɪɴ!</b>\n\n"
            "┌─────────────────────\n"
            "│ ⊕ +<b>{days} ᴅᴀʏs</b>\n"
            "│ ⏳ ɴᴇᴡ ʙᴀʟᴀɴᴄᴇ: <b>{balance}</b>\n"
            "└─────────────────────"
        ),
        "time_removed_admin": (
            "⊘ <b>ᴛɪᴍᴇ ʀᴇᴅᴜᴄᴇᴅ ʙʏ ᴀᴅᴍɪɴ</b>\n\n"
            "┌─────────────────────\n"
            "│ ⊖ −<b>{days} ᴅᴀʏs</b>\n"
            "│ ⏳ ɴᴇᴡ ʙᴀʟᴀɴᴄᴇ: <b>{balance}</b>\n"
            "└─────────────────────"
        ),

        "pay_btn": "✅ ᴘᴀʏᴍᴇɴᴛ ᴋɪʏᴀ — sᴄʀᴇᴇɴsʜᴏᴛ ʙʜᴇᴊᴏ",
        "pay_qr_caption": (
            "💳 <b>ᴘᴀʏ ғᴏʀ: {plan}</b>\n\n"
            "💰 ᴀᴍᴏᴜɴᴛ: <b>₹{price}</b>\n"
            "▹ {days} ᴅᴀʏs | {ram} ʀᴀᴍ | {cpu} ᴄᴏʀᴇ\n\n"
            "📸 QR scan karke payment karo.\n"
            "Phir neeche button dabao aur screenshot bhejo."
        ),
        "pay_screenshot_now": (
            "📤 <b>ᴀʙ ᴘᴀʏᴍᴇɴᴛ sᴄʀᴇᴇɴsʜᴏᴛ ʙʜᴇᴊᴏ</b>\n\n"
            "Photo (screenshot) bhej do — admin verify karke\nplan activate karega.\n\n"
            "↩ cancel: /cancel_pay"
        ),
        "pay_sent": (
            "✅ <b>ʀᴇǫᴜᴇsᴛ ʙʜᴇᴊ ᴅɪʏᴀ!</b>\n\n"
            "Screenshot + details admin ke paas gayi hain.\n"
            "Approve hote hi notification milega — thodi der wait karo."
        ),
        "pay_rejected": (
            "⊘ <b>ᴘᴀʏᴍᴇɴᴛ ʀᴇǫᴜᴇsᴛ ʀᴇᴊᴇᴄᴛᴇᴅ</b>\n\n"
            "Screenshot verify nahi hua ya amount galat tha.\nAdmin se contact karo."
        ),
        "pay_no_qr": "⚠️ ᴘᴀʏᴍᴇɴᴛ QR abhi set nahi hai — admin se link lo.",
        "pay_approved": (
            "✅ <b>ᴘᴀʏᴍᴇɴᴛ ᴠᴇʀɪғɪᴇᴅ — ᴘʟᴀɴ ᴀᴄᴛɪᴠᴇ!</b>\n\n"
            "💎 {plan}\n⏳ +{days} ᴅᴀʏs ᴀᴅᴅᴇᴅ\n🖥 VPS banane ke liye /create dabao"
        ),


        "lockdown_user": (
            "🔒 <b>ᴍᴀɪɴᴛᴇɴᴀɴᴄᴇ</b>\n\n"
            "ᴠᴘs ᴄʀᴇᴀᴛɪᴏɴ ɪs ᴛᴇᴍᴘᴏʀᴀʀɪʟʏ ᴅɪsᴀʙʟᴇᴅ.\n\n"
            "ᴛʀʏ ᴀɢᴀɪɴ ʟᴀᴛᴇʀ."
        ),
        "approval_admin_hint": "\n\n⚠️ ᴀᴘᴘʀᴏᴠᴀʟ ʀᴇǫᴜɪʀᴇᴅ → /approve {uid}",
        "warn_notify": (
            "⊘ <b>ᴡᴀʀɴɪɴɢ</b>  ({strikes}/{limit})\n\n"
            "ʀᴇᴀsᴏɴ: {reason}\n\n"
            "⊘ {strikes} sᴛʀɪᴋᴇs = ᴀᴜᴛᴏ-ʙᴀɴ"
        ),
        "myvps_none": (
            "⊡ <b>ɴᴏ ᴀᴄᴛɪᴠᴇ ᴠᴘs ғᴏᴜɴᴅ</b>\n\n"
            "┌─────────────────────\n"
            "│ ⏳ ᴛɪᴍᴇ ʙᴀʟᴀɴᴄᴇ: <b>{time}</b>\n"
            "└─────────────────────\n\n"
            "ᴘʀᴇss ☁️ ᴄʀᴇᴀᴛᴇ ᴠᴘs ᴛᴏ ɢᴇᴛ sᴛᴀʀᴛᴇᴅ!"
        ),
        "del_confirm": (
            "🗑 <b>ᴄᴏɴғɪʀᴍ ᴅᴇʟᴇᴛɪᴏɴ?</b>\n\n"
            "┌─────────────────────\n"
            "│ 🖥 ᴠᴘs  : <code>{name}</code>\n"
            "│ ⏱ ᴜsᴇᴅ : {used}\n"
            "│ ⏳ sᴀᴠᴇᴅ: <b>{left}</b>\n"
            "└─────────────────────\n\n"
            "⚠️ <b>ᴀʟʟ ᴅᴀᴛᴀ ᴡɪʟʟ ʙᴇ ʟᴏsᴛ!</b>"
        ),
        "vps_deleted": (
            "✅ <b>ᴠᴘs ᴅᴇʟᴇᴛᴇᴅ!</b>\n\n"
            "◔ ᴛɪᴍᴇ ʙᴀʟᴀɴᴄᴇ: <b>{time}</b>\n\n"
            "ᴜsᴇ ☁️ ᴄʀᴇᴀᴛᴇ ᴠᴘs ᴛᴏ ᴅᴇᴘʟᴏʏ ᴀ ɴᴇᴡ ᴏɴᴇ."
        ),
        "restart_ok": "✅ <b>ᴠᴘs ʀᴇsᴛᴀʀᴛᴇᴅ!</b>\n\n🖥 <code>{name}</code>\n🟢 sᴛᴀᴛᴜs: ʀᴜɴɴɪɴɢ",
        "restart_fail": "⊘ <b>ʀᴇsᴛᴀʀᴛ ғᴀɪʟᴇᴅ!</b>\n\nᴘʟᴇᴀsᴇ ᴛʀʏ ᴀɢᴀɪɴ.",
        "cancel_done": "👍 ᴄᴀɴᴄᴇʟʟᴇᴅ.",
        "no_vps_short": "⊡ <b>ɴᴏ ᴀᴄᴛɪᴠᴇ ᴠᴘs ғᴏᴜɴᴅ</b>",
        "invite": (
            "🟡 <b>ɪɴᴠɪᴛᴇ & ᴇᴀʀɴ</b>\n\n"
            "┌─────────────────────\n"
            "│ 🔗 ʏᴏᴜʀ ʟɪɴᴋ:\n"
            "│ <code>{link}</code>\n"
            "└─────────────────────\n\n"
            "┌ 🎁 <b>ʀᴇᴡᴀʀᴅs</b>\n"
            "│ ⊕ +1 ᴅᴀʏ ᴘᴇʀ ɪɴᴠɪᴛᴇ\n"
            "│ ▹ ᴍᴀx {max_inv} ɪɴᴠɪᴛᴇs/ᴅᴀʏ\n"
            "└─────────────────────\n\n"
            "┌ 📊 <b>ʏᴏᴜʀ sᴛᴀᴛs</b>\n"
            "│ 👥 ɪɴᴠɪᴛᴇᴅ : <b>{count}</b> ᴜsᴇʀs\n"
            "│ 🎁 ᴇᴀʀɴᴇᴅ  : <b>+{count} ᴅᴀʏs</b>\n"
            "│ ⏳ ʙᴀʟᴀɴᴄᴇ : <b>{balance}</b>\n"
            "└─────────────────────"
        ),
        "plans_hdr": "💎 <b>ᴠᴘs ᴘʟᴀɴs</b>",
        "plan_active": "  ◂ <b>ᴀᴄᴛɪᴠᴇ</b>",
        "plan_upgrade": "↗ ᴜᴘɢʀᴀᴅᴇ: ᴄᴏɴᴛᴀᴄᴛ ᴀᴅᴍɪɴ",
        "help_title": "❓ <b>ᴠɪsʜᴀʟ ᴄʟᴏᴜᴅ — ᴄᴏᴍᴍᴀɴᴅs</b>",
        "help_user_hdr": "┌ 👤 <b>ᴜsᴇʀ ᴄᴏᴍᴍᴀɴᴅs</b>",
        "help_free_hdr": "┌ ⚙️ <b>ғʀᴇᴇ ᴘʟᴀɴ</b>",
        "help_rules_hdr": "┌ ⚠️ <b>ʀᴜʟᴇs</b>",
        "help_admin_hdr": "┌ 👑 <b>ᴀᴅᴍɪɴ ᴄᴏᴍᴍᴀɴᴅs</b>",
        "lang_title": "🌐 <b>ʟᴀɴɢᴜᴀɢᴇ / भाषा</b>\n\nᴄʜᴏᴏsᴇ ʏᴏᴜʀ ʟᴀɴɢᴜᴀɢᴇ:\nअपनी भाषा चुनें:",
        "lang_done": "🌐 ʟᴀɴɢᴜᴀɢᴇ sᴇᴛ ᴛᴏ {name}",
        "expiry_notice": (
            "◔ <b>ᴠᴘs ᴇxᴘɪʀᴇᴅ &amp; ᴅᴇʟᴇᴛᴇᴅ</b>\n\n"
            "ʏᴏᴜʀ ᴛɪᴍᴇ ʙᴀʟᴀɴᴄᴇ ʜᴀs ʀᴜɴ ᴏᴜᴛ.\n\n"
            "⟡ ɪɴᴠɪᴛᴇ ғʀɪᴇɴᴅs ᴛᴏ ᴇᴀʀɴ ᴍᴏʀᴇ ᴛɪᴍᴇ: /invite"
        ),
        "invite_bonus": (
            "✦ <b>+{days} ᴅᴀʏ ᴀᴅᴅᴇᴅ!</b>\n\n"
            "@{name} ᴊᴏɪɴᴇᴅ ᴠɪᴀ ʏᴏᴜʀ ʟɪɴᴋ.\n"
            "ᴛɪᴍᴇ ʙᴀʟᴀɴᴄᴇ: <b>{balance}</b>"
        ),
        "down_owner": (
            "🔴 <b>ʏᴏᴜʀ ᴠᴘs ᴡᴇɴᴛ ᴅᴏᴡɴ!</b>\n\n"
            "🖥 <code>{name}</code>\n\n"
            "ᴛʜᴇ ᴄᴏɴᴛᴀɪɴᴇʀ ɪs ɴᴏᴛ ʀᴜɴɴɪɴɢ ᴀɴʏᴍᴏʀᴇ.\n"
            "ᴛʀʏ 🔄 ʀᴇsᴛᴀʀᴛ ғʀᴏᴍ /myvps ᴏʀ ᴄᴏɴᴛᴀᴄᴛ ᴀᴅᴍɪɴ."
        ),
        "down_admin": (
            "🔴 <b>ᴠᴘs ᴅᴏᴡɴ ᴀʟᴇʀᴛ</b>\n\n"
            "👤 ᴜsᴇʀ: <code>{uid}</code>\n"
            "🖥 ᴠᴘs : {name}\n"
            "🔌 ᴘᴏʀᴛ: {port}\n\n"
            "⛑ ᴄᴏɴᴛᴀɪɴᴇʀ ɪs ɴᴏᴛ ʀᴜɴɴɪɴɢ — /forcekill ᴏʀ /delvps {uid}"
        ),
        "new_user_admin": (
            "👤 <b>ɴᴇᴡ ᴜsᴇʀ ᴊᴏɪɴᴇᴅ</b>\n\n"
            "ɪᴅ   : <code>{uid}</code>\n"
            "ɴᴀᴍᴇ : {name}\n"
            "ʟɪɴᴋ : {link}\n\n"
            "🕒 {when}"
        ),
        "stats_live": "📊 <b>ʟɪᴠᴇ sᴛᴀᴛs</b>",
        "myvps_page_hdr": "🖥 <b>ʏᴏᴜʀ ᴠᴘs</b>  <i>({cur}/{total})</i>",
        "banned": "⊘ ʙᴀɴɴᴇᴅ: {reason}",
    },
    "hi": {
        "home": "⟡ <b>मुख्य मेन्यू</b>\n\n⏳ बचा समय: <b>{time}</b>\n👤 आईडी: <code>{uid}</code>",
        "welcome": (
            "✧ नमस्ते <b>{name}</b>! ❤️\n\n"
            "☁️ मैं <b>विशाल क्लाउड</b> हूँ — आपका प्रीमियम वीपीएस प्रोवाइडर ☁️\n\n"
            "┌─────────────────────\n"
            "│ ☁️ इंस्टेंट SSH वीपीएस\n"
            "│ ⚡ बिजली जैसी तेज़ डिप्लॉय\n"
            "│ 🔒 पूरा आइसोलेशन और सुरक्षा\n"
            "│ 🎁 दोस्त बुलाओ, ज़्यादा समय कमाओ\n"
            "└─────────────────────\n\n"
            "⏳ समय बैलेंस: <b>{time}</b>\n"
            "👤 आईडी: <code>{uid}</code>\n\n"
            "✦ डेवलपर : <a href=\"https://t.me/{dev}\">❏ @{dev} ❏</a> ✦"
        ),
        "cooldown": (
            "⏳ <b>कूलडाउन चालू है!</b>\n\n"
            "┌─────────────────────\n"
            "│ ⟳ कृपया <b>{sec} सेकंड</b> रुकें\n"
            "└─────────────────────\n\n"
            "थोड़ी देर बाद दोबारा कोशिश करें।"
        ),
        "already_active_title": (
            "⚠️ <b>आपका वीपीएस पहले से एक्टिव है</b>\n"
            "─────────────────────\n"
        ),
        "nobal": (
            "⊘ <b>समय बैलेंस नहीं!</b>\n\n"
            "┌─────────────────────\n"
            "│ 🎁 दोस्त बुलाओ = हर एक पर +1 दिन\n"
            "│ 💎 ज़्यादा समय के लिए प्लान अपग्रेड करो\n"
            "└─────────────────────"
        ),
        "noports": "⊘ <b>कोई पोर्ट उपलब्ध नहीं!</b>\n\nकृपया थोड़ी देर बाद कोशिश करें।",
        "deploying": (
            "⟳ <b>आपका वीपीएस डिप्लॉय हो रहा है...</b>\n\n"
            "┌─────────────────────\n"
            "│ ☁️ आइसोलेटेड वातावरण बनाया जा रहा है\n"
            "│ 🔒 सुरक्षा नीतियाँ लागू हो रही हैं\n"
            "│ ⚡ SSH सर्विस शुरू हो रही है\n"
            "└─────────────────────\n\n"
            "⏳ कृपया <b>30-60 सेकंड</b> इंतज़ार करें..."
        ),
        "deploy_success": (
            "✅ <b>वीपीएस सफलतापूर्वक डिप्लॉय हुआ!</b>\n\n"
            "┌ 🖥 <b>कनेक्शन</b>\n"
            "│ <code>ssh {user}@{ip} -p {port}</code>\n"
            "│\n"
            "│ 👤 यूज़र : <code>{user}</code>\n"
            "│ 🔐 पास   : <code>{password}</code>\n"
            "│ 🌐 आईपी  : <code>{ip}</code>\n"
            "│ 🔌 पोर्ट : <code>{port}</code>\n"
            "└─────────────────────\n\n"
            "┌ ⚙️ <b>स्पेक्स</b>\n"
            "│ 💾 रैम  : {ram}\n"
            "│ ⚡ सीपीयू: {cpu} कोर\n"
            "│ ⏳ समय  : <b>{time}</b>\n"
            "└─────────────────────\n\n"
            "🎁 <a href=\"{link}\">इनवाइट लिंक शेयर करें</a> → +1 दिन फ्री!\n\n"
            "⚠️ कोई माइनिंग नहीं • DDOS नहीं • दुरुपयोग नहीं"
        ),
        "deploy_fail": "❌ <b>डिप्लॉय फेल!</b>\n\n<code>{err}</code>",
        "deploy_no_docker": (
            "⊘ <b>Docker उपलब्ध नहीं!</b>\n\n"
            "बॉट Docker इंजन से कनेक्ट नहीं कर पा रहा।\n\n"
            "इसका मतलब बॉट ऐसी सर्वर पर चल रहा है\n"
            "जहाँ Docker इंस्टॉल/चालू नहीं है।\n\n"
            "👉 एडमिन से संपर्क करें।"
        ),
        "approval_pending": (
            "⏳ <b>अप्रूवल पेंडिंग</b>\n\n"
            "आपका अकाउंट एडमिन की मंज़ूरी के लिए है।\n\n"
            "मंज़ूरी मिलते ही आप वीपीएस बना पाओगे।"
        ),
        "approved_notify": (
            "✅ <b>अकाउंट अप्रूव हो गया!</b>\n\n"
            "अब आप वीपीएस बना सकते हो → /create"
        ),
        "rejected_notify": (
            "⊘ <b>अकाउंट रिजेक्ट हो गया</b>\n\n"
            "आप यह बॉट इस्तेमाल नहीं कर सकते। गलती हो तो एडमिन से संपर्क करें।"
        ),
        "time_added_admin": (
            "🎁 <b>एडमिन ने समय जोड़ा!</b>\n\n"
            "┌─────────────────────\n"
            "│ ⊕ +<b>{days} दिन</b>\n"
            "│ ⏳ नया बैलेंस: <b>{balance}</b>\n"
            "└─────────────────────"
        ),
        "time_removed_admin": (
            "⊘ <b>एडमिन ने समय घटाया</b>\n\n"
            "┌─────────────────────\n"
            "│ ⊖ −<b>{days} दिन</b>\n"
            "│ ⏳ नया बैलेंस: <b>{balance}</b>\n"
            "└─────────────────────"
        ),

        "pay_btn": "✅ पेमेंट किया — स्क्रीनशॉट भेजो",
        "pay_qr_caption": (
            "💳 <b>पेमेंट करो: {plan}</b>\n\n"
            "💰 राशि: <b>₹{price}</b>\n"
            "▹ {days} दिन | {ram} रैम | {cpu} कोर\n\n"
            "📸 QR स्कैन करके पेमेंट करो。\n"
            "फिर नीचे बटन दबाकर स्क्रीनशॉट भेजो।"
        ),
        "pay_screenshot_now": (
            "📤 <b>अब पेमेंट स्क्रीनशॉट भेजो</b>\n\n"
            "फोटो (स्क्रीनशॉट) भेज दो — एडमिन वेरिफाई करके\nप्लान एक्टिवेट करेगा।\n\n"
            "↩ कैंसल: /cancel_pay"
        ),
        "pay_sent": (
            "✅ <b>रिक्वेस्ट भेज दी!</b>\n\n"
            "स्क्रीनशॉट + डिटेल्स एडमिन के पास गईं।\n"
            "अप्रूव होते ही नोटिफिकेशन मिलेगा — थोड़ी देर इंतज़ार करो।"
        ),
        "pay_rejected": (
            "⊘ <b>पेमेंट रिक्वेस्ट रिजेक्ट</b>\n\n"
            "स्क्रीनशॉट वेरिफाई नहीं हुआ या राशि गलत थी।\nएडमिन से संपर्क करो।"
        ),
        "pay_no_qr": "⚠️ पेमेंट QR अभी सेट नहीं है — एडमिन से लिंक लो।",
        "pay_approved": (
            "✅ <b>पेमेंट वेरिफाइड — प्लान एक्टिव!</b>\n\n"
            "💎 {plan}\n⏳ +{days} दिन जुड़े\n🖥 वीपीएस बनाने के लिए /create दबाओ"
        ),
        "lockdown_user": (
            "🔒 <b>मेंटेनेंस</b>\n\n"
            "वीपीएस बनाना अस्थायी रूप से बंद है।\n\n"
            "थोड़ी देर बाद कोशिश करें।"
        ),
        "approval_admin_hint": "\n\n⚠️ मंज़ूरी ज़रूरी है → /approve {uid}",
        "warn_notify": (
            "⊘ <b>चेतावनी</b>  ({strikes}/{limit})\n\n"
            "कारण: {reason}\n\n"
            "⊘ {strikes} स्ट्राइक = ऑटो-बैन"
        ),
        "myvps_none": (
            "⊡ <b>कोई एक्टिव वीपीएस नहीं मिला</b>\n\n"
            "┌─────────────────────\n"
            "│ ⏳ समय बैलेंस: <b>{time}</b>\n"
            "└─────────────────────\n\n"
            "शुरू करने के लिए ☁️ वीपीएस बनाएं दबाएं!"
        ),
        "del_confirm": (
            "🗑 <b>डिलीट कन्फर्म करें?</b>\n\n"
            "┌─────────────────────\n"
            "│ 🖥 वीपीएस : <code>{name}</code>\n"
            "│ ⏱ इस्तेमाल : {used}\n"
            "│ ⏳ बचेगा: <b>{left}</b>\n"
            "└─────────────────────\n\n"
            "⚠️ <b>सारा डेटा हमेशा के लिए खो जाएगा!</b>"
        ),
        "vps_deleted": (
            "✅ <b>वीपीएस डिलीट हो गया!</b>\n\n"
            "◔ समय बैलेंस: <b>{time}</b>\n\n"
            "नया डिप्लॉय करने के लिए ☁️ वीपीएस बनाएं दबाएं।"
        ),
        "restart_ok": "✅ <b>वीपीएस रीस्टार्ट हो गया!</b>\n\n🖥 <code>{name}</code>\n🟢 स्टेटस: चालू",
        "restart_fail": "⊘ <b>रीस्टार्ट फेल!</b>\n\nकृपया दोबारा कोशिश करें।",
        "cancel_done": "👍 रद्द कर दिया गया।",
        "no_vps_short": "⊡ <b>कोई एक्टिव वीपीएस नहीं मिला</b>",
        "invite": (
            "🟡 <b>इनवाइट और कमाओ</b>\n\n"
            "┌─────────────────────\n"
            "│ 🔗 आपका लिंक:\n"
            "│ <code>{link}</code>\n"
            "└─────────────────────\n\n"
            "┌ 🎁 <b>इनाम</b>\n"
            "│ ⊕ हर इनवाइट पर +1 दिन\n"
            "│ ▹ अधिकतम {max_inv} इनवाइट/दिन\n"
            "└─────────────────────\n\n"
            "┌ 📊 <b>आपके आँकड़े</b>\n"
            "│ 👥 इनवाइट किए : <b>{count}</b> यूज़र\n"
            "│ 🎁 कमाए       : <b>+{count} दिन</b>\n"
            "│ ⏳ बैलेंस     : <b>{balance}</b>\n"
            "└─────────────────────"
        ),
        "plans_hdr": "💎 <b>वीपीएस प्लान्स</b>",
        "plan_active": "  ◂ <b>एक्टिव</b>",
        "plan_upgrade": "↗ अपग्रेड के लिए एडमिन से संपर्क करें",
        "help_title": "❓ <b>विशाल क्लाउड — कमांड्स</b>",
        "help_user_hdr": "┌ 👤 <b>यूज़र कमांड्स</b>",
        "help_free_hdr": "┌ ⚙️ <b>फ्री प्लान</b>",
        "help_rules_hdr": "┌ ⚠️ <b>नियम</b>",
        "help_admin_hdr": "┌ 👑 <b>एडमिन कमांड्स</b>",
        "lang_title": "🌐 <b>भाषा चुनें</b>\n\nChoose your language / अपनी भाषा चुनें:",
        "lang_done": "🌐 भाषा बदल दी गई: {name}",
        "expiry_notice": (
            "◔ <b>वीपीएस एक्सपायर होकर डिलीट हो गया</b>\n\n"
            "आपका समय बैलेंस खत्म हो गया।\n\n"
            "⟡ दोस्त बुलाकर और समय कमाएं: /invite"
        ),
        "invite_bonus": (
            "✦ <b>+{days} दिन जुड़ गए!</b>\n\n"
            "@{name} आपके लिंक से जुड़ा।\n"
            "समय बैलेंस: <b>{balance}</b>"
        ),
        "down_owner": (
            "🔴 <b>आपका वीपीएस बंद हो गया!</b>\n\n"
            "🖥 <code>{name}</code>\n\n"
            "कंटेनर अब चालू नहीं है।\n"
            "/myvps से 🔄 रीस्टार्ट करें या एडमिन से संपर्क करें।"
        ),
        "down_admin": (
            "🔴 <b>वीपीएस डाउन अलर्ट</b>\n\n"
            "👤 यूज़र: <code>{uid}</code>\n"
            "🖥 वीपीएस : {name}\n"
            "🔌 पोर्ट: {port}\n\n"
            "⛑ कंटेनर चालू नहीं — /forcekill या /delvps {uid}"
        ),
        "new_user_admin": (
            "👤 <b>नया यूज़र जुड़ा</b>\n\n"
            "आईडी   : <code>{uid}</code>\n"
            "नाम    : {name}\n"
            "लिंक   : {link}\n\n"
            "🕒 {when}"
        ),
        "stats_live": "📊 <b>लाइव स्टैट्स</b>",
        "myvps_page_hdr": "🖥 <b>आपका वीपीएस</b>  <i>({cur}/{total})</i>",
        "banned": "⊘ प्रतिबंधित: {reason}",
    },
}

# ============ HELP COMMAND LISTS (per language) ============
HELP_USER = {
    "en": (
        "\n│ /start     — ᴘʀᴏғɪʟᴇ & ᴍᴇɴᴜ\n"
        "│ /create    — ᴄʀᴇᴀᴛᴇ ɴᴇᴡ ᴠᴘs\n"
        "│ /myvps     — ssʜ ᴅᴇᴛᴀɪʟs + sᴛᴀᴛs\n"
        "│ /dashboard — ʟɪᴠᴇ ᴄᴘᴜ/ʀᴀᴍ\n"
        "│ /restart   — ʀᴇsᴛᴀʀᴛ ᴠᴘs\n"
        "│ /delete    — ᴅᴇʟᴇᴛᴇ ᴠᴘs\n"
        "│ /invite    — ɢᴇᴛ ɪɴᴠɪᴛᴇ ʟɪɴᴋ\n"
        "│ /plans     — ᴠɪᴇᴡ ᴘʟᴀɴs\n"
        "│ /language  — ᴄʜᴀɴɢᴇ ʟᴀɴɢᴜᴀɢᴇ\n"
        "└─────────────────────"
    ),
    "hi": (
        "\n│ /start     — प्रोफाइल और मेन्यू\n"
        "│ /create    — नया वीपीएस बनाएं\n"
        "│ /myvps     — SSH डिटेल्स + स्टैट्स\n"
        "│ /dashboard — लाइव CPU/RAM\n"
        "│ /restart   — वीपीएस रीस्टार्ट\n"
        "│ /delete    — वीपीएस डिलीट\n"
        "│ /invite    — इनवाइट लिंक पाएं\n"
        "│ /plans     — प्लान्स देखें\n"
        "│ /language  — भाषा बदलें\n"
        "└─────────────────────"
    ),
}

HELP_FREE = {
    "en": (
        "\n│ 💾 ʀᴀᴍ : {ram}\n"
        "│ ⚡ ᴄᴘᴜ : {cpu} ᴄᴏʀᴇ\n"
        "│ ⏳ ᴛɪᴍᴇ: {days} ᴅᴀʏs\n"
        "│ 🌐 ʙᴡ  : {bw}ᴍʙ/ᴅᴀʏ\n"
        "└─────────────────────"
    ),
    "hi": (
        "\n│ 💾 रैम : {ram}\n"
        "│ ⚡ सीपीयू: {cpu} कोर\n"
        "│ ⏳ समय: {days} दिन\n"
        "│ 🌐 बैंडविड्थ: {bw}MB/दिन\n"
        "└─────────────────────"
    ),
}

HELP_RULES = {
    "en": (
        "\n│ ⊘ ɴᴏ ᴍɪɴɪɴɢ / ʜᴀᴄᴋɪɴɢ / ᴅᴅᴏs\n"
        "│ ⊘ ɴᴏ ʙᴀɴᴅᴡɪᴅᴛʜ ᴀʙᴜsᴇ\n"
        "│ ⊘ 1 ᴠᴘs ᴘᴇʀ ᴘᴇʀsᴏɴ\n"
        "└─────────────────────"
    ),
    "hi": (
        "\n│ ⊘ माइनिंग / हैकिंग / DDOS नहीं\n"
        "│ ⊘ बैंडविड्थ का दुरुपयोग नहीं\n"
        "│ ⊘ हर व्यक्ति पर 1 वीपीएस\n"
        "└─────────────────────"
    ),
}

# Admin section is intentionally English (operator-facing).
HELP_ADMIN = (
    "\n\n┌ 👑 <b>ᴀᴅᴍɪɴ ᴄᴏᴍᴍᴀɴᴅs</b>\n"
    "│ /admin      — ᴀᴅᴍɪɴ ᴘᴀɴᴇʟ\n"
    "│ /users      — ʟɪsᴛ ᴜsᴇʀs\n"
    "│ /ban        — ʙᴀɴ ᴜsᴇʀ\n"
    "│ /unban      — ᴜɴʙᴀɴ ᴜsᴇʀ\n"
    "│ /addtime    — ᴀᴅᴅ ᴛɪᴍᴇ\n"
    "│ /removetime — ᴛɪᴍᴇ ᴋᴀᴍ ᴋᴀʀᴏ\n"
    "│ /forcekill  — ᴋɪʟʟ ᴄᴏɴᴛᴀɪɴᴇʀ\n"
    "│ /delvps     — ᴅᴇʟᴇᴛᴇ ᴜsᴇʀ ᴠᴘs\n"
    "│ /setplan    — sᴇᴛ ᴜsᴇʀ ᴘʟᴀɴ\n"
    "│ /grantroot  — ɢɪᴠᴇ ʀᴏᴏᴛ\n"
    "│ /revokeroot — ʀᴇᴠᴏᴋᴇ ʀᴏᴏᴛ\n"
    "│ /broadcast  — sᴇɴᴅ ᴛᴏ ᴀʟʟ\n"
    "│ /analytics  — ᴀɴᴀʟʏᴛɪᴄs\n"
    "│ /logs       — sᴇᴄᴜʀɪᴛʏ ʟᴏɢs\n"
    "│ /stats      — ᴜsᴇʀ ᴠᴘs sᴛᴀᴛs\n"
    "│ /addchannel — ᴀᴅᴅ ғᴏʀᴄᴇ ᴊᴏɪɴ\n"
    "│ /removechannel — ʀᴇᴍᴏᴠᴇ ᴄʜᴀɴɴᴇʟ\n"
    "│ /approve    — ᴀᴘᴘʀᴏᴠᴇ ɴᴇᴡ ᴜsᴇʀ\n"
    "│ /approveall — ᴀᴘᴘʀᴏᴠᴇ sᴀʙ ᴘᴇɴᴅɪɴɢ\n"
    "│ /reject     — ʀᴇᴊᴇᴄᴛ ᴜsᴇʀ\n"
    "│ /pending    — ᴘᴇɴᴅɪɴɢ ᴀᴘᴘʀᴏᴠᴀʟs\n"
    "│ /warn       — ᴡᴀʀɴ + sᴛʀɪᴋᴇ\n"
    "│ /lockdown   — ᴏɴ/ᴏғғ ᴄʀᴇᴀᴛᴇ\n"
    "│ /security   — sᴇᴄᴜʀɪᴛʏ ʜᴜʙ\n"
    "│ /manage     — ᴀʟʟ ᴜsᴇʀs → ᴛᴀᴘ = ssʜ/ʀᴇsᴛᴀʀᴛ/ᴅᴇʟ/+ᴛɪᴍᴇ\n"
    "└─────────────────────"
)


# ============ ACCESSORS ============

def _norm(lang: str) -> str:
    return lang if lang in LANGS else "en"


def lbl(lang: str, key: str) -> str:
    """Short label / button text."""
    return LBL[_norm(lang)].get(key, LBL["en"].get(key, key))


def msg(lang: str, key: str, **kwargs) -> str:
    """Message template with {placeholders} filled from kwargs."""
    template = MSG[_norm(lang)].get(key) or MSG["en"].get(key, key)
    try:
        return template.format(**kwargs)
    except (KeyError, IndexError, ValueError):
        return template
