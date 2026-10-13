"""
Security module - Rate limiting, anti-abuse, ban system (MongoDB).
"""
import time
import logging
from collections import defaultdict
from datetime import datetime, timedelta

import config

logger = logging.getLogger(__name__)

# In-memory rate limiter
_command_timestamps: dict[int, list[float]] = defaultdict(list)
_create_timestamps: dict[int, float] = {}

# Force join cache: {user_id: (passed: bool, timestamp: float)}
_force_join_cache: dict[int, tuple[bool, float]] = {}
FORCE_JOIN_CACHE_TTL = 300  # 5 minutes

# MongoDB reference (set after init)
db = None


# ============ Init ============

async def init_security_db():
    """Setup security collections and indexes."""
    global db
    from database import db as mongo_db
    db = mongo_db
    await db.banned_users.create_index("user_id", unique=True)
    await db.security_logs.create_index("created_at")
    await db.abuse_reports.create_index("user_id")


# ============ Rate Limiting ============

def check_rate_limit(user_id: int) -> bool:
    now = time.time()
    window = config.RATE_LIMIT_WINDOW
    recent = [ts for ts in _command_timestamps[user_id] if now - ts < window]
    # Prune empty entries to prevent memory leak
    if not recent:
        _command_timestamps.pop(user_id, None)
    else:
        _command_timestamps[user_id] = recent
    if len(recent) >= config.RATE_LIMIT_COMMANDS:
        return False
    _command_timestamps[user_id].append(now)
    return True


def get_force_join_cache(user_id: int) -> bool | None:
    """Return cached join result or None if expired/missing."""
    entry = _force_join_cache.get(user_id)
    if entry and (time.time() - entry[1]) < FORCE_JOIN_CACHE_TTL:
        return entry[0]
    return None


def set_force_join_cache(user_id: int, passed: bool):
    """Cache join check result for TTL seconds."""
    _force_join_cache[user_id] = (passed, time.time())


def clear_force_join_cache(user_id: int):
    """Invalidate cache entry (called after /addchannel or /removechannel)."""
    _force_join_cache.pop(user_id, None)


def check_create_cooldown(user_id: int) -> tuple[bool, int]:
    now = time.time()
    last_create = _create_timestamps.get(user_id, 0)
    elapsed = now - last_create
    if elapsed < config.CREATE_COOLDOWN:
        return False, int(config.CREATE_COOLDOWN - elapsed)
    return True, 0


def record_create(user_id: int):
    _create_timestamps[user_id] = time.time()


# ============ Ban System ============

async def is_user_banned(user_id: int) -> tuple[bool, str]:
    doc = await db.banned_users.find_one({"user_id": user_id})
    if doc:
        expires_at = doc.get("expires_at")
        if expires_at and datetime.now() > expires_at:
            await db.banned_users.delete_one({"user_id": user_id})
            return False, ""
        return True, doc.get("reason", "Policy violation")
    return False, ""


async def ban_user(user_id: int, reason: str, hours: int = None, banned_by: int = None):
    expires_at = None
    if hours:
        expires_at = datetime.now() + timedelta(hours=hours)
    await db.banned_users.update_one(
        {"user_id": user_id},
        {"$set": {
            "user_id": user_id,
            "reason": reason,
            "expires_at": expires_at,
            "banned_by": banned_by,
            "banned_at": datetime.now(),
        }},
        upsert=True,
    )
    await log_security_event(user_id, "BAN", f"Reason: {reason}, Duration: {hours}h")


async def unban_user(user_id: int):
    await db.banned_users.delete_one({"user_id": user_id})
    # Clear in-memory rate limit so user isn't still throttled after unban
    _command_timestamps.pop(user_id, None)
    _create_timestamps.pop(user_id, None)


async def get_banned_users() -> list:
    cursor = db.banned_users.find({})
    return await cursor.to_list(length=None)


# ============ Security Logging ============

async def log_security_event(user_id: int, action: str, details: str = "", ip: str = ""):
    await db.security_logs.insert_one({
        "user_id": user_id,
        "action": action,
        "details": details,
        "ip_address": ip,
        "created_at": datetime.now(),
    })
    logger.info(f"SECURITY [{action}] User {user_id}: {details}")


# ============ Abuse Detection ============

async def report_abuse(user_id: int, container_id: str, abuse_type: str, details: str, auto: bool = False) -> bool:
    """Record an abuse report. Returns True if it triggered an automatic strike-ban."""
    await db.abuse_reports.insert_one({
        "user_id": user_id,
        "container_id": container_id,
        "abuse_type": abuse_type,
        "details": details,
        "auto_detected": auto,
        "resolved": False,
        "created_at": datetime.now(),
    })
    await log_security_event(user_id, "ABUSE_REPORT", f"{abuse_type}: {details}")

    # Strike escalation: ABUSE_STRIKE_LIMIT unresolved reports -> escalating auto-ban
    limit = config.ABUSE_STRIKE_LIMIT
    strikes = await db.abuse_reports.count_documents({"user_id": user_id, "resolved": False})
    if strikes >= limit:
        banned, _ = await is_user_banned(user_id)
        if not banned:
            hours = 24 if strikes < limit * 2 else (168 if strikes < limit * 3 else None)
            reason = f"AUTO-BAN: {strikes} unresolved abuse report(s)"
            await ban_user(user_id, reason, hours=hours)
            await resolve_all_abuse(user_id)
            await log_security_event(user_id, "STRIKE_BAN", f"Strikes: {strikes}, Duration: {hours or 'permanent'}h")
            return True
    return False


async def resolve_all_abuse(user_id: int):
    """Mark all open abuse reports of a user as resolved (called when banned)."""
    await db.abuse_reports.update_many(
        {"user_id": user_id, "resolved": False},
        {"$set": {"resolved": True, "resolved_at": datetime.now()}},
    )


async def get_unresolved_abuse(user_id: int = None) -> int:
    """Count unresolved abuse reports (optionally per user)."""
    q = {"resolved": False}
    if user_id is not None:
        q["user_id"] = user_id
    return await db.abuse_reports.count_documents(q)


async def check_daily_invite_limit(user_id: int) -> bool:
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    count = await db.invites.count_documents({
        "inviter_id": user_id,
        "created_at": {"$gte": today_start},
    })
    return count < config.MAX_INVITES_PER_DAY


async def get_security_logs(limit: int = 50) -> list:
    cursor = db.security_logs.find({}).sort("created_at", -1).limit(limit)
    return await cursor.to_list(length=None)
