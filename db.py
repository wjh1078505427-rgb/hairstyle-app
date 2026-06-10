"""简易 JSON 数据库 — 设备追踪 + 用户管理（积分制）+ 用量统计"""
import json
from datetime import date, datetime
from pathlib import Path
from threading import Lock

from config import POINTS_REGISTER_BONUS

DATA_DIR = Path(__file__).parent / "data"
DB_FILE = DATA_DIR / "db.json"
_lock = Lock()

# ── 初始化 ───────────────────────────────────────────────

def _init_db():
    """确保数据库文件存在"""
    if not DB_FILE.exists():
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        DB_FILE.write_text(json.dumps({
            "devices": {}, "users": {}, "verification_codes": {}, "ip_ratelimit": {}
        }, ensure_ascii=False, indent=2))


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
    """获取或创建设备记录"""
    db = _read_db()
    today = date.today().isoformat()

    if device_id not in db.setdefault("devices", {}):
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
    """记录一次使用（免费额度或积分扣费后调用）"""
    db = _read_db()
    today = date.today().isoformat()

    device = db.setdefault("devices", {}).setdefault(device_id, {
        "created": today,
        "first_seen": datetime.now().isoformat(),
        "daily_usage": {},
        "total_usage": 0,
        "premium": False,
        "premium_until": None,
        "linked_user": None,
    })

    device["daily_usage"][today] = device.get("daily_usage", {}).get(today, 0) + 1
    device["total_usage"] = device.get("total_usage", 0) + 1
    _write_db(db)

    device["today_used"] = device["daily_usage"][today]
    return device


def check_can_generate(device_id: str, free_limit: int = 1) -> dict:
    """检查设备是否可以生成

    Returns:
        {"allowed": bool, "reason": str, "remaining_free": int, "is_premium": bool}
        reason: "free" | "points" | "premium" | "daily_limit" | "no_points"
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

    # 检查登录用户积分
    user_id = device.get("linked_user")
    if user_id:
        user = get_user(user_id)
        if user and user.get("points", 0) >= 888:
            return {"allowed": True, "reason": "points", "remaining_free": 0, "is_premium": False,
                    "points": user["points"]}

    # 免费用户检查日限额
    today = date.today().isoformat()
    today_used = device.get("daily_usage", {}).get(today, 0)
    remaining = max(0, free_limit - today_used)

    if remaining > 0:
        return {"allowed": True, "reason": "free", "remaining_free": remaining - 1, "is_premium": False}
    else:
        # 免费次数用完
        if user_id:
            return {"allowed": False, "reason": "no_points", "remaining_free": 0, "is_premium": False}
        return {"allowed": False, "reason": "daily_limit", "remaining_free": 0, "is_premium": False}


# ── 用户管理（积分制）─────────────────────────────────────

def create_user(email: str) -> str:
    """创建用户（注册送积分），返回 user_id"""
    db = _read_db()
    user_id = f"user_{email}"
    if user_id in db.setdefault("users", {}):
        return user_id  # 已存在

    db["users"][user_id] = {
        "email": email,
        "points": POINTS_REGISTER_BONUS,
        "total_used": 0,
        "total_spent_points": 0,
        "registered": datetime.now().isoformat(),
        "device_ids": [],
        "recharge_log": [],
    }
    _write_db(db)
    return user_id


def get_user(user_id: str) -> dict | None:
    """获取用户信息"""
    db = _read_db()
    return db.get("users", {}).get(user_id)


def get_user_by_email(email: str) -> dict | None:
    """通过邮箱查找用户"""
    return get_user(f"user_{email}")


def link_device_to_user(device_id: str, user_id: str) -> bool:
    """绑定设备到用户"""
    db = _read_db()
    if user_id not in db.setdefault("users", {}):
        return False

    db.setdefault("devices", {}).setdefault(device_id, {
        "created": date.today().isoformat(),
        "daily_usage": {},
        "total_usage": 0,
        "premium": False,
        "premium_until": None,
        "linked_user": None,
    })

    db["devices"][device_id]["linked_user"] = user_id
    if device_id not in db["users"][user_id].setdefault("device_ids", []):
        db["users"][user_id]["device_ids"].append(device_id)
    _write_db(db)
    return True


def deduct_points(user_id: str, amount: int = 888) -> dict:
    """扣积分"""
    db = _read_db()
    user = db.get("users", {}).get(user_id)
    if not user:
        return {"success": False, "error": "用户不存在"}
    if user.get("points", 0) < amount:
        return {"success": False, "error": f"积分不足（当前 {user['points']}，需要 {amount}）"}

    user["points"] = user["points"] - amount
    user["total_used"] = user.get("total_used", 0) + 1
    user["total_spent_points"] = user.get("total_spent_points", 0) + amount
    _write_db(db)
    return {"success": True, "points": user["points"]}


def add_points(user_id: str, amount: int, note: str = "") -> dict:
    """充值积分（管理员操作）"""
    db = _read_db()
    user = db.get("users", {}).get(user_id)
    if not user:
        return {"success": False, "error": "用户不存在"}

    user["points"] = user.get("points", 0) + amount
    user.setdefault("recharge_log", []).append({
        "points": amount,
        "time": datetime.now().isoformat(),
        "note": note,
    })
    _write_db(db)
    return {"success": True, "points": user["points"]}


def set_premium(device_id: str, days: int = 30) -> dict:
    """设置设备为付费会员"""
    from datetime import timedelta
    db = _read_db()
    device = db.setdefault("devices", {}).setdefault(device_id, {
        "daily_usage": {}, "total_usage": 0
    })
    device["premium"] = True
    device["premium_until"] = (datetime.now() + timedelta(days=days)).isoformat()
    _write_db(db)
    return device


# ── 兼容旧接口（app.py 可能还在用）────────────────────────

def add_balance(user_id: str, amount: float, note: str = "") -> dict:
    """兼容旧充值接口 — 1元 = 100积分"""
    points = int(amount * 100)
    return add_points(user_id, points, note)


def deduct_balance(user_id: str, amount: float) -> dict:
    """兼容旧扣费接口"""
    points = int(amount * 100)
    result = deduct_points(user_id, points)
    if result["success"]:
        result["balance"] = result["points"] / 100
    return result


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
    total_revenue = sum(
        sum(r.get("amount", 0) for r in u.get("recharge_log", []))
        for u in users.values()
    )

    return {
        "total_devices": len(devices),
        "total_usage": total_usage,
        "today_usage": today_usage,
        "total_users": total_users,
        "total_revenue": total_revenue,
    }
