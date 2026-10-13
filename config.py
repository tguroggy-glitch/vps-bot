import os
from dotenv import load_dotenv

load_dotenv()

# Telegram
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

# Developer info (welcome message mein dikhega)
DEVELOPER_USERNAME = os.getenv("DEVELOPER_USERNAME", "developer")
DEVELOPER_ID = int(os.getenv("DEVELOPER_ID", os.getenv("ADMIN_ID", "0")))

# Force Join Channels (comma separated channel usernames or IDs)
# Example: "@vishalcloud,@vishalupdates" or "-1001234567890"
FORCE_JOIN_CHANNELS = [ch.strip() for ch in os.getenv("FORCE_JOIN_CHANNELS", "").split(",") if ch.strip()]

# Payment QR (UPI) image URL/file_id — paid plan select karne par user ko bheja jayega.
# Admin /setqr <url|file_id> se bhi change ho sakta hai (DB mein save).
PAYMENT_QR_URL = os.getenv("PAYMENT_QR_URL", "")

# VPS Limits
MAX_VPS_PER_USER = 1
DEFAULT_RAM = os.getenv("DEFAULT_RAM", "512m")
DEFAULT_CPU = float(os.getenv("DEFAULT_CPU", "0.5"))
DEFAULT_STORAGE = os.getenv("DEFAULT_STORAGE", "5g")

# VPS Plans
VPS_PLANS = {
    "free": {
        "name": "ғʀᴇᴇ",
        "ram": "512m",
        "cpu": 0.5,
        "time_seconds": 2 * 24 * 3600,
        "price": 0,
    },
    "pro": {
        "name": "ᴘʀᴏ",
        "ram": "1g",
        "cpu": 1.0,
        "time_seconds": 7 * 24 * 3600,
        "price": 49,
    },
    "ultra": {
        "name": "ᴜʟᴛʀᴀ",
        "ram": "2g",
        "cpu": 2.0,
        "time_seconds": 15 * 24 * 3600,
        "price": 99,
    },
    "deal30": {
        "name": "ᴍᴏɴᴛʜʟʏ ᴅᴇᴀʟ",
        "ram": "2g",
        "cpu": 2.0,
        "time_seconds": 30 * 24 * 3600,
        "price": 189,
    },
}

# VPS Duration (default free plan)
VPS_DURATION_DAYS = 2
VPS_DURATION_SECONDS = 2 * 24 * 3600
INVITE_BONUS_DAYS = 1
INVITE_BONUS_SECONDS = 1 * 24 * 3600

# SSH Port Range
SSH_PORT_START = int(os.getenv("SSH_PORT_START", "2222"))
SSH_PORT_END = int(os.getenv("SSH_PORT_END", "2300"))

# Container Image
VPS_IMAGE = os.getenv("VPS_IMAGE", "vps-ssh-secure")

# Server IP
SERVER_IP = os.getenv("SERVER_IP", "YOUR_SERVER_IP")

# MongoDB
MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "vishal_vps")

# Database (legacy, not used)
DB_PATH = "vps_bot.db"

# ============ SECURITY SETTINGS ============

# Rate Limiting
RATE_LIMIT_COMMANDS = 5  # Max commands per minute per user
RATE_LIMIT_WINDOW = 60  # Window in seconds
CREATE_COOLDOWN = 300  # 5 min cooldown between VPS creates

# Anti-Abuse
MAX_FAILED_ATTEMPTS = 5  # Max failed SSH attempts before ban
BAN_DURATION_HOURS = 24  # Ban duration in hours
MAX_INVITES_PER_DAY = 10  # Max invites credited per day

# Abuse strikes: N unresolved reports = auto-ban (escalating: 24h -> 7d -> permanent)
ABUSE_STRIKE_LIMIT = int(os.getenv("ABUSE_STRIKE_LIMIT", "3"))

# New-user approval gate (APPROVAL_REQUIRED=1 in .env to enable)
# When ON: naya user /create tabhi kar sakta hai jab admin /approve kare
APPROVAL_REQUIRED = os.getenv("APPROVAL_REQUIRED", "0") == "1"

# Container Security & Isolation
CONTAINER_PIDS_LIMIT = 100           # Max processes inside container
CONTAINER_NETWORK_MODE = "vps_isolated_net"    # Isolated network (run setup_network.sh first)
CONTAINER_SHM_SIZE = "64m"          # Shared memory limit

# Data Isolation
# - NO host volumes mounted to containers
# - Each container has own isolated filesystem
# - v=True on remove to cleanup anonymous volumes
# - Private IPC namespace (no shared memory between containers)
# - Separate PID namespace (can't see other container processes)
# - No swap (prevents data leaking to disk)

# ============ MONITORING SETTINGS ============

# Bandwidth limits
BANDWIDTH_LIMIT_MB = 500  # Max outbound MB per day per container
BANDWIDTH_CHECK_INTERVAL = 120  # Seconds between bandwidth checks

# ===== DDoS OUTBOUND FLOOD PROTECTION =====
# Agar kisi container ka OUTBOUND traffic isse zyada ho (2 consecutive checks)
# -> container force-kill + user auto-ban (traffic turant band).
OUTBOUND_LIMIT_MBPS = float(os.getenv("OUTBOUND_LIMIT_MBPS", "20"))
OUTBOUND_CHECK_INTERVAL = int(os.getenv("OUTBOUND_CHECK_INTERVAL", "60"))  # seconds

# Expiry reminders
REMINDER_6H = True  # Send reminder 6 hours before expiry
REMINDER_1H = True  # Send reminder 1 hour before expiry

# File scanning
SCAN_INTERVAL = 300  # Seconds between filesystem scans inside containers
SUSPICIOUS_PATHS = ["/tmp", "/dev/shm", "/var/tmp", "/root", "/home/user"]
SUSPICIOUS_EXTENSIONS = [".sh", ".elf", ""]  # empty = no extension (common miner)

# DDoS detection
DDOS_SYN_THRESHOLD = 100  # SYN packets per second = DDoS
DDOS_CONN_THRESHOLD = 200  # Total outbound connections = suspicious
