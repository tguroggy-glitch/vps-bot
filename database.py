"""
Database module - MongoDB with motor (async).
Collections: users, vps_instances, invites
"""
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
import config

# MongoDB client
client: AsyncIOMotorClient = None
db = None


async def init_db():
    """Connect to MongoDB and setup indexes."""
    global client, db
    client = AsyncIOMotorClient(config.MONGO_URL)
    db = client[config.MONGO_DB_NAME]

    # Create indexes
    await db.users.create_index("user_id", unique=True)
    await db.vps_instances.create_index("user_id")
    await db.vps_instances.create_index("container_id")
    await db.vps_instances.create_index("status")
    await db.invites.create_index("inviter_id")
    await db.invites.create_index("invited_id")


# ============ USERS ============

async def add_user(user_id: int, username: str, invited_by: int = None):
    await db.users.update_one(
        {"user_id": user_id},
        {"$setOnInsert": {
            "user_id": user_id,
            "username": username,
            "invited_by": invited_by,
            "remaining_seconds": config.VPS_DURATION_SECONDS,
            "plan": "free",
            "lang": "en",
            # Approval gate ON -> new users start unapproved, OFF -> pre-approved
            "approved": not config.APPROVAL_REQUIRED,
            "created_at": datetime.now(),
        }},
        upsert=True,
    )


# ============ APPROVAL GATE (optional, APPROVAL_REQUIRED=1) ============

async def is_user_approved(user_id: int) -> bool:
    """Approval status. Existing users without the field default to approved."""
    doc = await db.users.find_one({"user_id": user_id}, {"approved": 1})
    if not doc:
        return True
    return bool(doc.get("approved", True))


async def set_user_approved(user_id: int, approved: bool):
    await db.users.update_one(
        {"user_id": user_id},
        {"$set": {"approved": bool(approved), "approved_at": datetime.now()}},
        upsert=True,
    )


async def get_pending_users() -> list:
    """Users waiting for admin approval (only relevant when the gate is ON)."""
    cursor = db.users.find({"approved": False}).sort("created_at", 1).limit(50)
    return await cursor.to_list(length=None)


async def get_pending_count() -> int:
    return await db.users.count_documents({"approved": False})


# ============ LOCKDOWN MODE (admin toggle, persisted) ============

async def get_lockdown() -> bool:
    doc = await db.settings.find_one({"key": "lockdown"})
    return bool(doc and doc.get("enabled"))


async def set_lockdown(enabled: bool):
    await db.settings.update_one(
        {"key": "lockdown"},
        {"$set": {"enabled": bool(enabled), "updated_at": datetime.now()}},
        upsert=True,
    )


# ============ USER LANGUAGE (i18n) ============

async def get_user_lang(user_id: int) -> str:
    """Get user's UI language. Defaults to 'en'."""
    doc = await db.users.find_one({"user_id": user_id}, {"lang": 1})
    if doc and doc.get("lang") in ("en", "hi"):
        return doc["lang"]
    return "en"


async def set_user_lang(user_id: int, lang: str):
    """Persist the user's UI language choice."""
    if lang not in ("en", "hi"):
        lang = "en"
    await db.users.update_one(
        {"user_id": user_id},
        {"$set": {"lang": lang}},
        upsert=True,
    )


async def get_user_plan(user_id: int) -> str:
    doc = await db.users.find_one({"user_id": user_id})
    return doc.get("plan", "free") if doc else "free"


async def set_user_plan(user_id: int, plan: str, add_time: int = 0):
    update = {"$set": {"plan": plan}}
    if add_time > 0:
        update["$inc"] = {"remaining_seconds": add_time}
    await db.users.update_one({"user_id": user_id}, update)


async def user_exists(user_id: int) -> bool:
    doc = await db.users.find_one({"user_id": user_id})
    return doc is not None


async def get_remaining_seconds(user_id: int) -> int:
    doc = await db.users.find_one({"user_id": user_id})
    return doc.get("remaining_seconds", 0) if doc else 0


async def deduct_time(user_id: int, seconds: int):
    await db.users.update_one(
        {"user_id": user_id},
        {"$inc": {"remaining_seconds": -seconds}},
    )
    # Ensure not negative
    await db.users.update_one(
        {"user_id": user_id, "remaining_seconds": {"$lt": 0}},
        {"$set": {"remaining_seconds": 0}},
    )


async def add_time(user_id: int, seconds: int):
    await db.users.update_one(
        {"user_id": user_id},
        {"$inc": {"remaining_seconds": seconds}},
    )


# ============ PAYMENT SYSTEM ============

async def get_payment_qr() -> str:
    """Admin payment QR (image URL / file_id). DB se, warna config se."""
    doc = await db.settings.find_one({"key": "payment_qr"})
    if doc and doc.get("url"):
        return doc["url"]
    return config.PAYMENT_QR_URL


async def set_payment_qr(url_or_file_id: str):
    await db.settings.update_one(
        {"key": "payment_qr"},
        {"$set": {"url": url_or_file_id}},
        upsert=True,
    )


async def add_payment(user_id: int, plan: str, amount: int, file_id: str):
    await db.payments.insert_one({
        "user_id": user_id,
        "plan": plan,
        "amount": amount,
        "file_id": file_id,
        "status": "pending",
        "created_at": datetime.now(),
    })


async def set_payment_status(user_id: int, plan: str, status: str):
    await db.payments.update_many(
        {"user_id": user_id, "plan": plan, "status": "pending"},
        {"$set": {"status": status, "updated_at": datetime.now()}},
    )


async def get_all_users() -> list:
    cursor = db.users.find({})
    return await cursor.to_list(length=None)


# ============ VPS INSTANCES ============

async def get_user_vps(user_id: int) -> dict | None:
    doc = await db.vps_instances.find_one({"user_id": user_id, "status": "running"})
    return doc


async def get_all_user_vps(user_id: int) -> list:
    """All running VPS instances of one user (pagination / multi-VPS support)."""
    cursor = db.vps_instances.find({"user_id": user_id, "status": "running"}).sort("created_at", 1)
    return await cursor.to_list(length=None)


async def get_active_vps_count(user_id: int) -> int:
    return await db.vps_instances.count_documents({"user_id": user_id, "status": "running"})


async def subtract_time(user_id: int, seconds: int) -> int:
    """Time kam karo (0 se neeche nahi jaata). Returns new remaining seconds."""
    remaining = await get_remaining_seconds(user_id)
    new_remaining = max(0, remaining - int(seconds))
    await db.users.update_one(
        {"user_id": user_id},
        {"$set": {"remaining_seconds": new_remaining}},
    )
    return new_remaining


async def add_vps_instance(
    user_id: int,
    container_id: str,
    container_name: str,
    ssh_port: int,
    ssh_password: str,
    ssh_user: str,
    ram: str,
    cpu: float,
    storage: str,
):
    await db.vps_instances.insert_one({
        "user_id": user_id,
        "container_id": container_id,
        "container_name": container_name,
        "ssh_port": ssh_port,
        "ssh_password": ssh_password,
        "ssh_user": ssh_user,
        "ram": ram,
        "cpu": cpu,
        "storage": storage,
        "status": "running",
        "started_at": datetime.now().isoformat(),
        "created_at": datetime.now(),
    })


async def remove_vps_instance(container_id: str, user_id: int = None):
    """Stop VPS and deduct used time from user's balance."""
    doc = await db.vps_instances.find_one({"container_id": container_id, "status": "running"})
    if doc:
        uid = doc["user_id"]
        started_at = datetime.fromisoformat(doc["started_at"])
        used_seconds = int((datetime.now() - started_at).total_seconds())
        # Deduct used time
        await db.users.update_one(
            {"user_id": uid},
            {"$inc": {"remaining_seconds": -used_seconds}},
        )
        await db.users.update_one(
            {"user_id": uid, "remaining_seconds": {"$lt": 0}},
            {"$set": {"remaining_seconds": 0}},
        )

    await db.vps_instances.update_one(
        {"container_id": container_id},
        {"$set": {"status": "stopped", "stopped_at": datetime.now()}},
    )


async def get_expired_vps() -> list:
    """Get VPS where user's time balance has run out."""
    cursor = db.vps_instances.find({"status": "running"})
    all_running = await cursor.to_list(length=None)
    expired = []
    now = datetime.now()
    for vps in all_running:
        user = await db.users.find_one({"user_id": vps["user_id"]})
        if not user:
            expired.append(vps)
            continue
        started_at = datetime.fromisoformat(vps["started_at"])
        used_seconds = int((now - started_at).total_seconds())
        remaining = user.get("remaining_seconds", 0)
        if used_seconds >= remaining:
            expired.append(vps)
    return expired


async def get_all_running_vps() -> list:
    cursor = db.vps_instances.find({"status": "running"})
    return await cursor.to_list(length=None)


async def get_next_available_port() -> int:
    cursor = db.vps_instances.find({"status": "running"}, {"ssh_port": 1})
    docs = await cursor.to_list(length=None)
    used_ports = {doc["ssh_port"] for doc in docs}
    for port in range(config.SSH_PORT_START, config.SSH_PORT_END + 1):
        if port not in used_ports:
            return port
    return -1


# ============ INVITES ============

async def record_invite(inviter_id: int, invited_id: int):
    await db.invites.insert_one({
        "inviter_id": inviter_id,
        "invited_id": invited_id,
        "created_at": datetime.now(),
    })


async def get_invite_count(user_id: int) -> int:
    count = await db.invites.count_documents({"inviter_id": user_id})
    return count
