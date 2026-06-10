"""简易 JSON 数据库 — 设备追踪 + 用户管理 + 用量统计"""
import json
import os
from datetime import date, datetime
from pathlib import Path
from threading import Lock

DATA_DIR = Path(__file__).parent / "data"
DB_FILE = DATA_DIR / "db.json"
_lock = Lock()

# ── 初始化 ───────────────────────────────────────────────

def _init_db():
    """确保数据库文件存在"""
    if not DB_FILE.exists():
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        DB_FILE.write_text(json.dumps({"devices": {}, "users": {}}, ensure_ascii=False, indent=2))

def _read_db() -> dict:
    """读取数据库"""
    _init_db()
    with _lock:
        return json.loads(DB_FILE.read_text(encoding="utf-8"))

def _write_db(data: dict):
    """写入数据库"""
    with _lock:
        DB_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


# ── 设备管理 ─────────────────────────────────────────────

def get_or_create_device(device_id: str) -> dict:
    """获取或创建设备记录，返回设备信息"""
    db = _read_db()
    today = date.today().isoformat()

    if device_id not in db["devices"]:
        db["devices"][device_id] = {
            "created": today,
            "first_seen": datetime.now().isoformat(),
            "daily_usage": {},
            "total_usage": 0,
            "premium": False,
            "premium_until": None,
            "linked_user": None,
        }
        _write_db(db)

    device = db["devices"][device_id]
    device["today_used"] = device.get("daily_usage", {}).get(today, 0)
    return device


def record_usage(device_id: str) -> dict:
    """记录一次使用，返回更新后的状态"""
    db = _read_db()
    today = date.today().isoformat()

    device = db["devices"].setdefault(device_id, {
        "created": today,
        "first_seen": datetime.now().isoformat(),
        "daily_usage": {},
        "total_usage": 0,
        "premium": False,
        "premium_until": None,
        "linked_user": None,
    })

    # 更新日用量
    device["daily_usage"][today] = device.get("daily_usage", {}).get(today, 0) + 1
    device["total_usage"] = device.get("total_usage", 0) + 1
    _write_db(db)

    device["today_used"] = device["daily_usage"][today]
    return device


def check_can_generate(device_id: str, free_limit: int = 1) -> dict:
    """检查设备是否可以生成

    Returns:
        {"allowed": bool, "reason": str, "remaining_free": int, "is_premium": bool}
    """
    device = get_or_create_device(device_id)

    # 付费用户无限制
    if device.get("premium"):
        premium_until = device.get("premium_until")
        if premium_until:
            try:
                if datetime.fromisoformat(premium_until) > datetime.now():
                    return {"allowed": True, "reason": "premium", "remaining_free": -1, "is_premium": True}
            except (ValueError, TypeError):
                pass
        else:
            return {"allowed": True, "reason": "premium", "remaining_free": -1, "is_premium": True}

    # 检查余额制用户（通过 linked_user）
    user_id = device.get("linked_user")
    if user_id:
        user = get_user(user_id)
        if user and user.get("balance", 0) > 0:
            return {"allowed": True, "reason": "balance", "remaining_free": 0, "is_premium": False,
                    "balance": user["balance"]}

    # 免费用户检查日限额
    today = date.today().isoformat()
    today_used = device.get("daily_usage", {}).get(today, 0)
    remaining = max(0, free_limit - today_used)

    if remaining > 0:
        return {"allowed": True, "reason": "free", "remaining_free": remaining - 1, "is_premium": False}
    else:
        return {"allowed": False, "reason": "daily_limit", "remaining_free": 0, "is_premium": False}


# ── 用户管理 ─────────────────────────────────────────────

def create_user(username: str, initial_balance: float = 0) -> str:
    """创建用户，返回 user_id"""
    db = _read_db()
    user_id = f"user_{username}"
    if user_id in db["users"]:
        return user_id  # 已存在

    db["users"][user_id] = {
        "username": username,
        "balance": initial_balance,
        "total_used": 0,
        "total_spent": 0.0,
        "registered": datetime.now().isoformat(),
        "device_ids": [],
    }
    _write_db(db)
    return user_id


def get_user(user_id: str) -> dict | None:
    """获取用户信息"""
    db = _read_db()
    return db["users"].get(user_id)


def link_device_to_user(device_id: str, user_id: str) -> bool:
    """绑定设备到用户"""
    db = _read_db()
    if user_id not in db["users"]:
        return False

    db["devices"].setdefault(device_id, {
        "created": date.today().isoformat(),
        "daily_usage": {},
        "total_usage": 0,
        "premium": False,
        "premium_until": None,
        "linked_user": None,
    })

    db["devices"][device_id]["linked_user"] = user_id
    if device_id not in db["users"][user_id]["device_ids"]:
        db["users"][user_id]["device_ids"].append(device_id)
    _write_db(db)
    return True


def deduct_balance(user_id: str, amount: float) -> dict:
    """扣费，返回更新后的用户信息"""
    db = _read_db()
    user = db["users"].get(user_id)
    if not user:
        return {"success": False, "error": "用户不存在"}
    if user["balance"] < amount:
        return {"success": False, "error": f"余额不足（当前 ¥{user['balance']:.2f}，需要 ¥{amount:.2f}）"}

    user["balance"] = round(user["balance"] - amount, 2)
    user["total_used"] += 1
    user["total_spent"] = round(user["total_spent"] + amount, 2)
    _write_db(db)
    return {"success": True, "balance": user["balance"]}


def add_balance(user_id: str, amount: float, admin_note: str = "") -> dict:
    """充值（管理员操作）"""
    db = _read_db()
    user = db["users"].get(user_id)
    if not user:
        return {"success": False, "error": "用户不存在"}

    user["balance"] = round(user["balance"] + amount, 2)
    # 记录充值日志
    user.setdefault("recharge_log", []).append({
        "amount": amount,
        "time": datetime.now().isoformat(),
        "note": admin_note,
    })
    _write_db(db)
    return {"success": True, "balance": user["balance"]}


def set_premium(device_id: str, days: int = 30) -> dict:
    """设置设备为付费会员"""
    from datetime import timedelta
    db = _read_db()
    device = db["devices"].setdefault(device_id, {"daily_usage": {}, "total_usage": 0})
    device["premium"] = True
    device["premium_until"] = (datetime.now() + timedelta(days=days)).isoformat()
    _write_db(db)
    return device


# ── 统计 ─────────────────────────────────────────────────

def get_stats() -> dict:
    """获取全局统计"""
    db = _read_db()
    devices = db.get("devices", {})
    users = db.get("users", {})

    total_usage = sum(d.get("total_usage", 0) for d in devices.values())
    today = date.today().isoformat()
    today_usage = sum(d.get("daily_usage", {}).get(today, 0) for d in devices.values())
    total_users = len(users)
    total_revenue = sum(u.get("total_spent", 0) for u in users.values())

    return {
        "total_devices": len(devices),
        "total_usage": total_usage,
        "today_usage": today_usage,
        "total_users": total_users,
        "total_revenue": total_revenue,
    }
