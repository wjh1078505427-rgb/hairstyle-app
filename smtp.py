"""QQ邮箱 SMTP 发送 — 验证码邮件"""
import smtplib
import os
from email.mime.text import MIMEText

from dotenv import load_dotenv
load_dotenv()

SMTP_SERVER = "smtp.qq.com"
SMTP_PORT = 465  # SSL
SENDER_EMAIL = os.getenv("QQ_EMAIL", "")
SENDER_PASSWORD = os.getenv("QQ_SMTP_PASSWORD", "")


def send_verification_code(to_email: str, code: str) -> dict:
    """发送验证码邮件，返回 {"success": bool, "error": str}"""

    if not SENDER_EMAIL or not SENDER_PASSWORD:
        return {"success": False, "error": "SMTP 未配置，请设置 QQ_EMAIL 和 QQ_SMTP_PASSWORD"}

    subject = "AI换发型 - 登录验证码"
    body = f"""你的验证码是：{code}

5 分钟内有效，请勿泄露。

——
AI换发型 · 上传照片一键换发型"""

    msg = MIMEText(body, "plain", "utf-8")
    msg["From"] = SENDER_EMAIL
    msg["To"] = to_email
    msg["Subject"] = subject

    try:
        server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, timeout=10)
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, [to_email], msg.as_string())
        server.quit()
        return {"success": True, "error": ""}
    except smtplib.SMTPAuthenticationError:
        return {"success": False, "error": "SMTP 认证失败，请检查授权码是否正确"}
    except smtplib.SMTPException as e:
        return {"success": False, "error": f"邮件发送失败: {e}"}
    except Exception as e:
        return {"success": False, "error": f"未知错误: {e}"}
