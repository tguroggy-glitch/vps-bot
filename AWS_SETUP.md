# 🚀 VishalCloud — AWS Ubuntu VPS Setup Guide (Step by Step)

> Har command ek ek karke run karo. Error aaye to wahi output copy karke help lo.

---

## STEP 1 — System update
```bash
sudo apt update && sudo apt upgrade -y
```

## STEP 2 — Docker install
```bash
curl -fsSL https://get.docker.com | sudo sh
```

## STEP 3 — Docker group (optional — bina sudo chalane ke liye)
```bash
sudo usermod -aG docker $USER
```
> ⚠️ Iske baad **logout/login karo** (ya next commands `sudo` ke saath chalao).

## STEP 4 — Docker verify + autostart enable
```bash
docker --version && sudo systemctl enable --now docker
```

## STEP 5 — Code download (repo private hai — token mange to daal do)
```bash
cd ~ && git clone https://github.com/ItsMeVishal0/VishalCloud.git && cd VishalCloud
```

## STEP 6 — .env banao aur fill karo
```bash
cp .env.example .env && nano .env
```
`nano` mein ye set karo:
```
BOT_TOKEN=<BotFather se token>
ADMIN_ID=8477195695
DEVELOPER_USERNAME=UROGGY
DEVELOPER_ID=8477195695
SERVER_IP=13.54.191.110
PAYMENT_QR_URL=https://files.catbox.moe/qdb4yk.jpg
MONGO_URL=mongodb+srv://zz3921657_db_user:zz3921657_db_user@cluster0.dvdlgol.mongodb
```
Save: `Ctrl+O` → Enter → `Ctrl+X`

## STEP 7 — docker-compose.yml update (MongoDB add) — poori file overwrite
```bash
cat > docker-compose.yml <<'YAML'
version: "3.8"

services:
  mongo:
    image: mongo:7
    container_name: vps_mongo
    restart: unless-stopped
    volumes:
      - mongo_data:/data/db
    healthcheck:
      test: ["CMD", "mongosh", "--quiet", "--eval", "db.runCommand({ping:1}).ok"]
      interval: 10s
      timeout: 5s
      retries: 5

  build-vps-image:
    image: docker:24-cli
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - .:/workspace
    command: docker build -t vps-ssh-secure -f /workspace/Dockerfile.vps /workspace
    restart: "no"
    depends_on:
      mongo:
        condition: service_healthy

  vps-bot:
    build: .
    container_name: vps_bot
    restart: unless-stopped
    env_file: .env
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - ./vps_bot.db:/app/vps_bot.db
    working_dir: /app
    command: python bot.py
    depends_on:
      mongo:
        condition: service_healthy
      build-vps-image:
        condition: service_completed_successfully

volumes:
  mongo_data:
YAML
```

## STEP 8 — Start sab kuch (pehli baar 2–5 min lagega)
```bash
docker compose up -d --build
```

## STEP 9 — Logs check
```bash
docker compose logs -f vps-bot
```
> `Application started` dikhe = bot online ✅ — `Ctrl+C` se sirf log band hoga, bot nahi rukta.

## STEP 10 — Verify
```bash
docker ps
```
> `vps_bot` + `vps_mongo` dono **Up** hone chahiye. (`vishalcloud-build-vps-image-1` exited = normal — woh sirf image banata hai.)

---

## ⚠️ AWS Security Group (zaroori!)
AWS Console → EC2 → Instance → **Security Groups → Inbound rules**:
- `TCP 22` (SSH)
- `TCP 2222–2300` (users ke VPS SSH ports)

## 🧹 Purane VPS containers hatao (agar port 2222–2238 occupied hain)
```bash
docker rm -f $(docker ps -aq --filter "name=vps_")
```
```bash
ss -tlnp | grep -E ":222[2-9]|:223[0-8]" || echo "PORTS FREE ✅"
```

## 🧪 Telegram test
1. Bot ko `/start` bhejo
2. `/security` → admin hub
3. `/create` → real VPS banega (30–60s)
4. Server pe:
```bash
docker ps | grep vps_
docker inspect $(docker ps -q --filter "name=vps_" | head -1) | grep -iE "memory|nanocpus"
```
> Memory `536870912` (512MB) + NanoCpus `500000000` (0.5 core) = limits apply ✅

---

## 🕐 24/7 kaise chalega?
- Bot **Docker container** hai — laptop/SSH band karo to koi asar nahi
- Server **reboot** par bot + mongo auto-start (`restart: unless-stopped`)
- Server **stop** karoge to bot band — start karte hi wapas aa jayega
- 💡 **Elastic IP** allocate karo (AWS Console) — warna IP badle par users connect nahi kar payenge. IP badle to:
```bash
nano .env   # SERVER_IP update
docker compose up -d --force-recreate vps-bot
```

## 🛠 Useful commands
```bash
docker compose logs -f vps-bot    # live logs
docker compose down && docker compose up -d   # restart sab
docker logs vps_bot --tail 50     # last 50 lines
docker ps                         # running containers
```
