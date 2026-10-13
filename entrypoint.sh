#!/bin/bash

# ============ GENERATE RANDOM USERNAME ============
if [ ! -z "${SSH_USERNAME}" ]; then
    USERNAME="${SSH_USERNAME}"
else
    USERNAME="user"
fi

# Create user dynamically
useradd -m -s /bin/bash -d /home/${USERNAME} ${USERNAME} 2>/dev/null || true

# Set password using chpasswd
echo "${USERNAME}:${ROOT_PASSWORD}" | chpasswd 2>/dev/null || true

# Also set via usermod as fallback
echo -e "${ROOT_PASSWORD}\n${ROOT_PASSWORD}" | passwd ${USERNAME} 2>/dev/null || true

# Setup bashrc with custom prompt + PATH
cat /etc/skel/.bashrc_custom >> /home/${USERNAME}/.bashrc 2>/dev/null || true
cp /etc/skel/.bashrc_custom /root/.bashrc 2>/dev/null || true
chown -R ${USERNAME}:${USERNAME} /home/${USERNAME}

# Copy neofetch config
cp -r /etc/skel/.config /home/${USERNAME}/ 2>/dev/null || true
chown -R ${USERNAME}:${USERNAME} /home/${USERNAME}/.config 2>/dev/null || true

# ============ ROOT ACCESS (only if whitelisted) ============
if [ "${ROOT_ACCESS}" = "true" ]; then
    echo "root:${ROOT_PASSWORD}" | chpasswd
    passwd -u root 2>/dev/null
    sed -i 's/PermitRootLogin no/PermitRootLogin yes/' /etc/ssh/sshd_config
    usermod -aG sudo ${USERNAME} 2>/dev/null
    echo "${USERNAME} ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/${USERNAME}
    chmod 440 /etc/sudoers.d/${USERNAME}
fi

# ============ CUSTOM HOSTNAME ============
# Hostname is already set by Docker --hostname flag
# Just update /etc/hosts for resolution
if [ ! -z "${VPS_USER_ID}" ]; then
    echo "127.0.1.1 cloud-${VPS_USER_ID}" >> /etc/hosts 2>/dev/null || true
fi

# ============ DYNAMIC MOTD ============
cat > /etc/profile.d/motd.sh << 'MOTD'
echo ""
echo -e "\033[1;36m╔═══════════════════════════════════════════════╗"
echo -e "║          ☁️  V I S H A L  C L O U D  ☁️           ║"
echo -e "╠═══════════════════════════════════════════════╣"
echo -e "║                                               ║"
echo -e "║  \033[1;32m▸ ᴡᴇʟᴄᴏᴍᴇ ᴛᴏ ʏᴏᴜʀ ᴘʀɪᴠᴀᴛᴇ ᴠᴘs\033[1;36m             ║"
echo -e "║  \033[1;33m▸ ʜᴏsᴛ: $(hostname)\033[1;36m"
echo -e "║  \033[1;33m▸ ᴜᴘᴛɪᴍᴇ: $(uptime -p 2>/dev/null || echo 'N/A')\033[1;36m"
echo -e "║  \033[1;33m▸ ᴍᴇᴍᴏʀʏ: $(free -h 2>/dev/null | awk '/Mem:/{print $3"/"$2}' || echo 'N/A')\033[1;36m"
echo -e "║  \033[1;33m▸ ᴀᴄᴄᴇss: $(if groups | grep -q sudo; then echo 'ROOT'; else echo 'USER'; fi)\033[1;36m"
echo -e "║                                               ║"
echo -e "║  \033[1;31m⚠ ᴍɪɴɪɴɢ/ʜᴀᴄᴋɪɴɢ = ɪɴsᴛᴀɴᴛ ʙᴀɴ\033[1;36m           ║"
echo -e "║  \033[1;31m⚠ ᴛʜɪs sᴇssɪᴏɴ ɪs ᴍᴏɴɪᴛᴏʀᴇᴅ\033[1;36m              ║"
echo -e "║                                               ║"
echo -e "╚═══════════════════════════════════════════════╝\033[0m"
echo ""
MOTD
chmod +x /etc/profile.d/motd.sh

# ============ DATA ISOLATION ============
chmod 700 /root
chmod 750 /home/${USERNAME}
chown -R ${USERNAME}:${USERNAME} /home/${USERNAME}

# Remove sensitive env vars
unset ROOT_PASSWORD
unset VPS_USER_ID
unset ROOT_ACCESS

# Hide processes
mount -o remount,hidepid=2 /proc 2>/dev/null || true

# ============ NETWORK FIREWALL ============
/usr/local/bin/firewall.sh 2>/dev/null || true

# ============ FAIL2BAN ============
service fail2ban start 2>/dev/null || true

# ============ ANTI-MINER DAEMON ============
(while true; do /usr/local/bin/antiminer.sh; sleep 30; done) &

# ============ CONNECTION LOGGER ============
(tail -f /var/log/auth.log 2>/dev/null | while read line; do
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $line" >> /var/log/ssh_audit.log
done) &

# ============ RESOURCE MONITOR ============
(while true; do
    sleep 120
    ps aux --sort=-%cpu | awk 'NR>1 && $3 > 90.0 {print $2}' | head -5 | while read pid; do
        if [ -f "/proc/$pid/stat" ]; then
            starttime=$(awk '{print $22}' /proc/$pid/stat 2>/dev/null)
            uptime_s=$(cat /proc/uptime | awk '{print $1}')
            if [ ! -z "$starttime" ] && [ ! -z "$uptime_s" ]; then
                runtime=$(echo "$uptime_s - ($starttime / 100)" | bc 2>/dev/null || echo "0")
                if [ "${runtime%.*}" -gt 120 ] 2>/dev/null; then
                    kill -9 $pid 2>/dev/null
                    echo "[$(date)] Killed PID $pid (high CPU)" >> /var/log/security.log
                fi
            fi
        fi
    done
done) &

# ============ START SSH ============
exec /usr/sbin/sshd -D -e
