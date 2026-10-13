# 🖥️ Telegram VPS Manager Bot

Telegram bot jo SSH VPS create karta hai Docker containers ke through, limited resources ke saath.

## Features

- ✅ SSH VPS create/delete/restart
- ✅ Per-user resource limits (RAM, CPU, Storage)
- ✅ Admin approval system
- ✅ Multiple VPS per user (configurable)
- ✅ Auto SSH password generation
- ✅ Admin panel (users list, approve, set limits)
- ✅ **Bilingual UI — English 🇬🇧 / हिंदी 🇮🇳** (`/language` ya main menu se switch karo, per-user saved)
- ✅ **Full inline-keyboard navigation** — har screen se Home hub (time balance ke saath)
- ✅ **Paginated My-VPS cards** — live CPU/RAM progress bars, per-VPS buttons
- ✅ **Confirm-before-delete** — har destructive action par Yes/No dialog
- ✅ **Non-blocking deploy** — create Docker operation ab async executor mein chalta hai (event loop block nahi hota)
- ✅ **Container watchdog alerts** — VPS crash ho to owner (localized) + admin ko alert
- ✅ **New-user admin alerts** + localized expiry / invite-bonus notifications
- ✅ **Approval gate** (`APPROVAL_REQUIRED=1`) — sirf paid-plan users ke liye; **free plan = auto-approve** (kisi ko manually approve nahi karna)
- ✅ **DDoS outbound flood protection** — container ka outbound `OUTBOUND_LIMIT_MBPS` se zyada (2 checks) = force-kill + user auto-ban (`/unban` se wapas)
- ✅ **Lockdown mode** (`/lockdown on|off`) — emergency mein VPS creation turant band
- ✅ **Plan live-apply** — `/setplan` se user ka running VPS RAM/CPU turant update (delete/recreate nahi)
- ✅ **Strike auto-ban** — `ABUSE_STRIKE_LIMIT` unresolved reports = escalating ban (24h → 7d → permanent), `/warn` se manual strikes
- ✅ **Security Hub** (`/security`) — live counts + lockdown toggle + pending approvals with inline Approve/Reject buttons

## Requirements

- Python 3.10+
- Docker installed and running
- Telegram Bot Token (BotFather se)

## Setup

### 1. Docker Install karo (agar nahi hai)

```bash
curl -fsSL https://get.docker.com | sh
```

### 2. Custom VPS Image Build karo (Optional - faster startup)

```bash
docker build -t vps-ssh -f Dockerfile.vps .
```

Agar custom image use karna hai toh `.env` mein `VPS_IMAGE=vps-ssh` set karo.

### 3. Bot Setup

```bash
# Dependencies install karo
pip install -r requirements.txt

# .env file banao
cp .env.example .env

# .env file edit karo apne values ke saath
nano .env
```

### 4. .env Configuration

```env
BOT_TOKEN=your_telegram_bot_token_here
ADMIN_ID=your_telegram_user_id
MAX_VPS_PER_USER=2
DEFAULT_RAM=512m
DEFAULT_CPU=0.5
DEFAULT_STORAGE=5g
SSH_PORT_START=2222
SSH_PORT_END=2300
VPS_IMAGE=ubuntu:22.04
```

### 5. Bot Start karo

```bash
python bot.py
```

## Bot Commands

### User Commands
| Command | Description |
|---------|-------------|
| `/start` | Bot start karo |
| `/create` | Naya VPS banao |
| `/myvps` | Apne VPS dekho (cards + live bars) |
| `/delete` | VPS delete karo (confirm ke saath) |
| `/dashboard` | Live CPU/RAM usage |
| `/restart` | VPS restart karo |
| `/language` ya `/lang` | English / हिंदी switch karo |

### Admin Commands
| Command | Description |
|---------|-------------|
| `/approve <user_id>` | User ko approve karo |
| `/users` | Saare users list karo |
| `/setlimit <user_id> <max>` | User ka VPS limit set karo |

## Architecture

```
User → Telegram Bot → Docker API → Container (SSH Server)
                   ↕
            MongoDB (users, vps instances, lang)
```

## New UI Files

| File | Purpose |
|------|---------|
| `i18n.py` | Saare button labels + message templates (EN + HI). `ui.lbl()` / `ui.msg()` use karo naya text add karne ke liye |
| `bot.py` | Screen builders (Home / My VPS / Stats / Confirm / Help) — har screen ka ek single source |

## Multi-VPS Enable Karna

Default `MAX_VPS_PER_USER = 1` hai (time-balance model single VPS ke liye design kiya hai).
Zyada VPS chahiye toh `config.py` mein value badlo — UI already paginated cards support karta hai.
⚠️ Note: balance shared hai — multiple active VPS pe time har deletion pe deduct hota hai.

## Resource Limits

Default limits per VPS:
- **RAM:** 512MB
- **CPU:** 0.5 core
- **Storage:** 5GB (Docker default)
- **Max VPS per user:** 2

Admin `/setlimit` command se per-user limit change kar sakte ho.

## Security Notes

- Har VPS ka unique random password hota hai
- SSH root login enabled hai (container based hai toh safe hai)
- Resource limits Docker enforce karta hai
- Admin approval required hai VPS create karne se pehle
- Port range limited hai (2222-2300)

## Troubleshooting

**Docker permission error:**
```bash
sudo usermod -aG docker $USER
# Logout and login again
```

**Port already in use:**
- SSH_PORT_START/END range badhao `.env` mein

**Container start nahi ho raha:**
```bash
docker logs vps_<user_id>_<port>
```
