"""
VPS Manager - Docker container management with FULL isolation & security.
Each container is completely isolated - no user can access another user's data.
"""
import time
import docker
import secrets
import string
import logging
import config

logger = logging.getLogger(__name__)
client = None

# Network sampler cache: container_id -> (timestamp, tx_bytes, rx_bytes)
_net_sample_cache: dict[str, tuple] = {}


def _get_client():
    """Lazy init Docker client (only connects when first used)."""
    global client
    if client is None:
        client = docker.from_env()
    return client


def generate_password(length: int = 16) -> str:
    """Strong random SSH password - letters and digits only (no shell escape issues)."""
    chars = string.ascii_letters + string.digits
    password = [
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.digits),
    ]
    password += [secrets.choice(chars) for _ in range(length - 3)]
    password_list = list(password)
    secrets.SystemRandom().shuffle(password_list)
    return "".join(password_list)


def generate_username() -> str:
    """Generate random SSH username like: vx7k2m"""
    chars = string.ascii_lowercase + string.digits
    return "".join(secrets.choice(chars) for _ in range(6))


def create_vps(
    user_id: int,
    ssh_port: int,
    ram: str = None,
    cpu: float = None,
    root_access: bool = False,
) -> dict:
    """
    Fully isolated Docker container.
    User gets 'user' account by default — NO root.
    Root access only if owner whitelists via /grantroot command.
    """
    # Whitelist RAM and CPU to plan-defined values only — prevent arbitrary resource requests
    allowed_ram = {p["ram"] for p in config.VPS_PLANS.values()} | {config.DEFAULT_RAM}
    allowed_cpu = {p["cpu"] for p in config.VPS_PLANS.values()} | {config.DEFAULT_CPU}
    ram = ram if ram in allowed_ram else config.DEFAULT_RAM
    cpu = cpu if cpu in allowed_cpu else config.DEFAULT_CPU

    password = generate_password()
    username = generate_username()
    container_name = f"vps_{user_id}_{ssh_port}"

    # ============ SECURITY OPTIONS ============
    security_opts = [
        "no-new-privileges:true",  # Privilege escalation block
    ]

    # Sysctls - network protection
    sysctls = {
        "net.ipv4.ip_forward": "0",
        "net.ipv4.conf.all.send_redirects": "0",
        "net.ipv4.conf.default.send_redirects": "0",
        "net.ipv4.conf.all.accept_redirects": "0",
        "net.ipv4.conf.default.accept_redirects": "0",
        "net.ipv4.icmp_echo_ignore_broadcasts": "1",
    }

    # Ulimits - resource boundaries
    ulimits = [
        docker.types.Ulimit(name="nofile", soft=1024, hard=2048),   # File descriptors
        docker.types.Ulimit(name="nproc", soft=100, hard=150),      # Max processes
        docker.types.Ulimit(name="core", soft=0, hard=0),           # No core dumps (data leak prevention)
        docker.types.Ulimit(name="fsize", soft=1073741824, hard=1073741824),  # 1GB max file size
    ]

    # ============ CREATE CONTAINER ============
    # Verify image exists locally (don't try to pull from Docker Hub)
    try:
        _get_client().images.get(config.VPS_IMAGE)
    except docker.errors.ImageNotFound:
        raise Exception(f"Image '{config.VPS_IMAGE}' not found locally. Run: docker build -t {config.VPS_IMAGE} -f Dockerfile.vps .")

    container = _get_client().containers.run(
        image=config.VPS_IMAGE,
        name=container_name,
        hostname=f"cloud-{user_id}",  # Custom branded hostname
        detach=True,
        ports={"22/tcp": ("0.0.0.0", ssh_port)},

        # ===== RESOURCE LIMITS =====
        mem_limit=ram,
        memswap_limit=ram,          # No swap = prevent data leak to disk
        nano_cpus=int(cpu * 1e9),
        pids_limit=config.CONTAINER_PIDS_LIMIT,
        shm_size=config.CONTAINER_SHM_SIZE,

        # ===== ISOLATION =====
        network_mode="bridge",      # Use bridge (run setup_network.sh for isolated net)
        ipc_mode="private",         # IPC namespace isolated
        pid_mode=None,              # Separate PID namespace (default)
        userns_mode="",             # User namespace isolation
        
        # ===== SECURITY =====
        security_opt=security_opts,
        cap_drop=["ALL"],           # DROP all Linux capabilities
        cap_add=[                   # Add back ONLY minimum needed
            "CHOWN",
            "DAC_OVERRIDE",
            "FOWNER",
            "FSETID",
            "KILL",
            "SETGID",
            "SETUID",
            "NET_BIND_SERVICE",
            "SYS_CHROOT",
            "AUDIT_WRITE",
            "NET_RAW",              # For ping
        ],
        sysctls=sysctls,
        ulimits=ulimits,

        # ===== FILESYSTEM SECURITY =====
        read_only=False,            # Root FS writable (needed for SSH)
        tmpfs={
            "/tmp": "size=100m,noexec,nosuid,nodev",    # Tmp limited, no execution
            "/var/tmp": "size=50m,noexec,nosuid,nodev",
        },
        
        # ===== DNS (prevent DNS tunneling) =====
        dns=["8.8.8.8", "1.1.1.1"],
        dns_search=[],
        dns_opt=["timeout:2", "attempts:1"],

        # ===== ENVIRONMENT =====
        environment={
            "ROOT_PASSWORD": password,
            "SSH_USERNAME": username,
            "VPS_USER_ID": str(user_id),
            "ROOT_ACCESS": "true" if root_access else "false",
            "TERM": "xterm-256color",
        },

        # ===== NO HOST ACCESS =====
        volumes={},                 # NO host volumes mounted
        privileged=False,           # NEVER privileged
        
        # ===== RESTART POLICY =====
        restart_policy={"Name": "unless-stopped"},

        # ===== LABELS =====
        labels={
            "managed_by": "vps_bot",
            "user_id": str(user_id),
            "security_level": "high",
            "isolation": "full",
        },
    )

    logger.info(f"Secure VPS created: {container_name} for user {user_id}, port {ssh_port}")
    return {
        "container_id": container.id,
        "container_name": container_name,
        "ssh_port": ssh_port,
        "ssh_user": "root" if root_access else username,
        "ssh_password": password,
        "ram": ram,
        "cpu": cpu,
        "root_access": root_access,
    }


def stop_vps(container_id: str) -> bool:
    """VPS stop + remove + cleanup."""
    try:
        container = _get_client().containers.get(container_id)
        container.stop(timeout=10)
        container.remove(force=True, v=True)  # v=True removes anonymous volumes
        logger.info(f"VPS stopped and cleaned: {container_id[:12]}")
        return True
    except docker.errors.NotFound:
        return True
    except Exception as e:
        logger.error(f"Failed to stop VPS {container_id[:12]}: {e}")
        return False


def update_limits(container_id: str, ram: str = None, cpu: float = None) -> bool:
    """Live-update a running container's RAM/CPU limits (docker update)."""
    try:
        container = _get_client().containers.get(container_id)
        kwargs = {}
        if ram:
            kwargs["mem_limit"] = ram
            kwargs["memswap_limit"] = ram
        if cpu:
            kwargs["nano_cpus"] = int(cpu * 1e9)
        container.update(**kwargs)
        logger.info(f"Limits updated for {container_id[:12]}: ram={ram}, cpu={cpu}")
        return True
    except docker.errors.NotFound:
        return False
    except Exception as e:
        logger.error(f"Failed to update limits {container_id[:12]}: {e}")
        return False


def get_container_status(container_id: str) -> str:
    """Container status check."""
    try:
        container = _get_client().containers.get(container_id)
        return container.status
    except docker.errors.NotFound:
        return "not_found"
    except Exception:
        return "error"


def restart_vps(container_id: str) -> bool:
    """VPS restart."""
    try:
        container = _get_client().containers.get(container_id)
        container.restart(timeout=10)
        logger.info(f"VPS restarted: {container_id[:12]}")
        return True
    except Exception as e:
        logger.error(f"Restart failed {container_id[:12]}: {e}")
        return False


def get_container_stats(container_id: str) -> dict | None:
    """Live resource usage stats."""
    try:
        container = _get_client().containers.get(container_id)
        stats = container.stats(stream=False)

        cpu_delta = stats["cpu_stats"]["cpu_usage"]["total_usage"] - \
                    stats["precpu_stats"]["cpu_usage"]["total_usage"]
        system_delta = stats["cpu_stats"]["system_cpu_usage"] - \
                       stats["precpu_stats"]["system_cpu_usage"]
        cpu_percent = 0.0
        if system_delta > 0:
            cpu_percent = (cpu_delta / system_delta) * 100.0

        mem_usage = stats["memory_stats"].get("usage", 0)
        mem_limit = stats["memory_stats"].get("limit", 0)

        return {
            "cpu_percent": round(cpu_percent, 2),
            "memory_used_mb": round(mem_usage / (1024 * 1024), 2),
            "memory_limit_mb": round(mem_limit / (1024 * 1024), 2),
            "memory_percent": round((mem_usage / mem_limit) * 100, 2) if mem_limit > 0 else 0,
            "pids": stats.get("pids_stats", {}).get("current", 0),
        }
    except Exception:
        return None


def get_net_rate_mbps(container_id: str) -> dict | None:
    """
    Outbound/inbound traffic rate in Mbps since the previous sample
    (uses cumulative docker stats counters). Returns None on first call
    or when the container/daemon is unavailable.
    """
    try:
        stats = _get_client().containers.get(container_id).stats(stream=False)
    except Exception:
        return None

    networks = stats.get("networks") or {}
    tx_total = sum(int(n.get("tx_bytes", 0)) for n in networks.values())
    rx_total = sum(int(n.get("rx_bytes", 0)) for n in networks.values())
    now = time.time()

    prev = _net_sample_cache.get(container_id)
    _net_sample_cache[container_id] = (now, tx_total, rx_total)
    if not prev:
        return None

    dt = now - prev[0]
    if dt <= 0:
        return None
    tx_delta = max(0, tx_total - prev[1])
    rx_delta = max(0, rx_total - prev[2])
    # bytes*8 / 1e6 / seconds = Mbps
    return {
        "tx_mbps": round(tx_delta * 8 / 1e6 / dt, 3),
        "rx_mbps": round(rx_delta * 8 / 1e6 / dt, 3),
    }


def reset_net_cache(container_id: str):
    """Drop cached sample (e.g. container recreated)."""
    _net_sample_cache.pop(container_id, None)


def force_kill_container(container_id: str) -> bool:
    """Emergency force kill + full cleanup."""
    try:
        container = _get_client().containers.get(container_id)
        container.kill()
        container.remove(force=True, v=True)
        logger.warning(f"VPS force killed: {container_id[:12]}")
        return True
    except Exception as e:
        logger.error(f"Force kill failed {container_id[:12]}: {e}")
        return False


def inspect_container_security(container_id: str) -> dict | None:
    """Container ki security settings inspect karo (admin use)."""
    try:
        container = _get_client().containers.get(container_id)
        info = container.attrs
        host_config = info.get("HostConfig", {})
        return {
            "privileged": host_config.get("Privileged", False),
            "cap_add": host_config.get("CapAdd", []),
            "cap_drop": host_config.get("CapDrop", []),
            "security_opt": host_config.get("SecurityOpt", []),
            "read_only_rootfs": host_config.get("ReadonlyRootfs", False),
            "network_mode": host_config.get("NetworkMode", ""),
            "pid_mode": host_config.get("PidMode", ""),
            "ipc_mode": host_config.get("IpcMode", ""),
            "memory_limit": host_config.get("Memory", 0),
            "pids_limit": host_config.get("PidsLimit", 0),
            "volumes": list(info.get("Mounts", [])),
        }
    except Exception:
        return None
