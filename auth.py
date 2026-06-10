"""验证码生成 / 发送 / 验证 — 带 IP 速率限制"""
import random
from datetime import datetime, timedelta

from config import (
    CODE_EXPIRE_MINUTES, CODE_LENGTH, CODE_MAX_ATTEMPTS,
    CODE_RESEND_SECONDS, IP_MAX_CODES_PER_DAY, IP_MAX_CODES_PER_HOUR,
)
from db import _read_db, _write_db
from smtp import send_verification_code


def _now() -> str:
    return datetime.now().isoformat()


def _generate_code() -> str:
    return "".join(random.choices("0123456789", k=CODE_LENGTH))


# ── IP 速率限制 ─────────────────────────────────────────────

def _check_ip_ratelimit(ip: str) -> dict:
    """检查 IP 是否超限，返回 {"allowed": bool, "reason": str}"""
    db = _read_db()
    rl = db.setdefault("ip_ratelimit", {})
    entry = rl.get(ip, {})

    now = datetime.now()
    today = now.date().isoformat()

    # 今天维度
    today_count = 0
    hour_count = 0
    last_send_str = entry.get("last_send", "")
    log = entry.get("log", [])

    for ts in log:
        try:
            t = datetime.fromisoformat(ts)
            if t.date().isoformat() == today:
                today_count += 1
                if (now - t).total_seconds() < 3600:
                    hour_count += 1
        except (ValueError, TypeError):
            pass

    if today_count >= IP_MAX_CODES_PER_DAY:
        return {"allowed": False, "reason": "该网络今日发送验证码已达上限，请明天再试"}

    if hour_count >= IP_MAX_CODES_PER_HOUR:
        return {"allowed": False, "reason": "发送太频繁，请 1 小时后再试"}

    # 重发间隔
    if last_send_str:
        try:
            last_send = datetime.fromisoformat(last_send_str)
            elapsed = (now - last_send).total_seconds()
            if elapsed < CODE_RESEND_SECONDS:
                wait = int(CODE_RESEND_SECONDS - elapsed)
                return {"allowed": False, "reason": f"请 {wait} 秒后再发送"}
        except (ValueError, TypeError):
            pass

    return {"allowed": True, "reason": ""}


def _record_ip_send(ip: str):
    """记录一次发送"""
    db = _read_db()
    rl = db.setdefault("ip_ratelimit", {})
    entry = rl.setdefault(ip, {})
    entry["last_send"] = _now()
    entry.setdefault("log", []).append(_now())
    # 只保留最近 50 条
    entry["log"] = entry["log"][-50:]
    _write_db(db)


# ── 验证码 ──────────────────────────────────────────────────

def can_send_code(email: str, ip: str) -> dict:
    """检查是否可以发送验证码"""
    # IP 限流
    ip_check = _check_ip_ratelimit(ip)
    if not ip_check["allowed"]:
        return ip_check

    # 邮箱重发间隔
    db = _read_db()
    codes = db.setdefault("verification_codes", {})
    existing = codes.get(email)
    if existing:
        try:
            last_send = datetime.fromisoformat(existing.get("sent_at", ""))
            elapsed = (datetime.now() - last_send).total_seconds()
            if elapsed < CODE_RESEND_SECONDS:
                wait = int(CODE_RESEND_SECONDS - elapsed)
                return {"allowed": False, "reason": f"请 {wait} 秒后再发送"}
        except (ValueError, TypeError):
            pass

    return {"allowed": True, "reason": ""}


def send_code(email: str, ip: str) -> dict:
    """生成验证码、发送邮件、存储"""
    # 先检查
    check = can_send_code(email, ip)
    if not check["allowed"]:
        return check

    code = _generate_code()
    result = send_verification_code(email, code)

    if not result["success"]:
        return result

    # 存储验证码
    db = _read_db()
    codes = db.setdefault("verification_codes", {})
    expires_at = (datetime.now() + timedelta(minutes=CODE_EXPIRE_MINUTES)).isoformat()
    codes[email] = {
        "code": code,
        "expires_at": expires_at,
        "attempts": 0,
        "sent_at": _now(),
    }
    _write_db(db)

    # 记录 IP 发送
    _record_ip_send(ip)

    return {"success": True, "error": "", "message": f"验证码已发送至 {email}"}


def verify_code(email: str, code: str) -> dict:
    """验证验证码，返回 {"success": bool, "error": str}"""
    db = _read_db()
    codes = db.setdefault("verification_codes", {})

    entry = codes.get(email)
    if not entry:
        return {"success": False, "error": "请先发送验证码"}

    # 检查过期
    try:
        expires_at = datetime.fromisoformat(entry["expires_at"])
        if datetime.now() > expires_at:
            del codes[email]
            _write_db(db)
            return {"success": False, "error": "验证码已过期，请重新发送"}
    except (ValueError, TypeError):
        del codes[email]
        _write_db(db)
        return {"success": False, "error": "验证码数据异常，请重新发送"}

    # 检查尝试次数
    entry["attempts"] = entry.get("attempts", 0) + 1
    if entry["attempts"] > CODE_MAX_ATTEMPTS:
        del codes[email]
        _write_db(db)
        return {"success": False, "error": "尝试次数过多，请重新发送验证码"}

    # 验证
    if entry["code"] != code.strip():
        _write_db(db)
        remaining = CODE_MAX_ATTEMPTS - entry["attempts"]
        return {"success": False, "error": f"验证码错误，还剩 {remaining} 次机会"}

    # 成功 → 删除验证码
    del codes[email]
    _write_db(db)
    return {"success": True, "error": ""}


def clean_expired_codes() -> int:
    """清理过期验证码，返回清理数量"""
    db = _read_db()
    codes = db.get("verification_codes", {})
    expired = []
    now = datetime.now()

    for email, entry in codes.items():
        try:
            expires_at = datetime.fromisoformat(entry["expires_at"])
            if now > expires_at:
                expired.append(email)
        except (ValueError, TypeError):
            expired.append(email)

    for email in expired:
        del codes[email]

    _write_db(db)
    return len(expired)
