"""AI换发型 — QQ邮箱登录 + 积分制 · 1次/天/设备免费"""
import base64
import hashlib
import os
import re
import tempfile
import uuid
from io import BytesIO
from pathlib import Path

import streamlit as st
from PIL import Image

from api_client import call_image_api
from auth import can_send_code, send_code, verify_code, clean_expired_codes
from config import (
    DEFAULT_PROVIDER, FREE_TRIAL_LIMIT, POINTS_PER_USE,
    POINTS_REGISTER_BONUS, POINTS_MONTHLY, POINTS_MONTHLY_PRICE,
    PRICING, PROVIDERS, TRANSFER_MODES,
)
from db import (
    add_points, create_user, deduct_points, get_or_create_device,
    get_stats, get_user, get_user_by_email, link_device_to_user,
    record_usage, set_premium, check_can_generate,
)

ADMIN_PASSWORD = "admin888"

# ── 页面配置 ─────────────────────────────────────────────
st.set_page_config(
    page_title="AI换发型",
    page_icon="💇",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ──────────────────────────────────────────────────
st.markdown("""
<style>
    .main-header { text-align: center; padding: 0.3rem 0 0 0; }
    .main-header h1 { font-size: 2rem; margin-bottom: 0.1rem; }
    .main-header p { color: #888; font-size: 0.95rem; }
    .price-card { border: 1px solid #ddd; border-radius: 12px; padding: 0.7rem;
                  margin: 0.4rem 0; text-align: center; }
    .price-card.rec { border: 2px solid #ff6b6b; background: #fff5f5; }
    .price-card .price { font-size: 1.5rem; font-weight: bold; color: #ff6b6b; }
    .cost-hint { color: #999; font-size: 0.75rem; text-align: center; padding: 0.8rem 0; }
    .limit-warn { background: #fff3cd; border: 1px solid #ffc107; border-radius: 8px;
                  padding: 0.8rem; text-align: center; margin: 0.8rem 0; }
    .login-box { background: #f0f8ff; border: 1px solid #b8daff; border-radius: 8px;
                 padding: 0.8rem; margin: 0.4rem 0; }
    .points-badge { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white; border-radius: 8px; padding: 0.6rem; text-align: center; }
    .email-tag { background: #e8f5e9; border-radius: 4px; padding: 0.15rem 0.4rem;
                 font-size: 0.8rem; color: #2e7d32; }
</style>
""", unsafe_allow_html=True)

# ── 设备追踪 ────────────────────────────────────────────

def _get_fingerprint() -> str:
    """HTTP 请求头生成设备指纹"""
    try:
        headers = st.context.headers
        ip = (
            headers.get("X-Forwarded-For", "").split(",")[0].strip()
            or headers.get("X-Real-IP", "")
            or headers.get("Host", "")
        )
        ua = headers.get("User-Agent", "")
        al = headers.get("Accept-Language", "")
        ae = headers.get("Accept-Encoding", "")
        raw = f"{ip}|{ua}|{al}|{ae}"
        if raw.strip() == "|||":
            return ""
        return "dev_" + hashlib.sha256(raw.encode()).hexdigest()[:16]
    except Exception:
        return ""


if "device_id" not in st.session_state:
    try:
        params = st.query_params
        if "did" in params and params["did"]:
            st.session_state.device_id = params["did"]
    except Exception:
        pass

if "device_id" not in st.session_state:
    fp = _get_fingerprint()
    st.session_state.device_id = fp if fp else "dev_" + uuid.uuid4().hex[:12]

did = st.session_state.device_id

# ── 会话状态初始化 ───────────────────────────────────────
device = get_or_create_device(did)
check = check_can_generate(did, FREE_TRIAL_LIMIT)

if "generated_images" not in st.session_state:
    st.session_state.generated_images = []
if "provider" not in st.session_state:
    st.session_state.provider = DEFAULT_PROVIDER
if "user_id" not in st.session_state:
    st.session_state.user_id = device.get("linked_user")
if "show_admin" not in st.session_state:
    st.session_state.show_admin = False
# 登录流程状态
if "login_step" not in st.session_state:
    st.session_state.login_step = "input_email"  # input_email | input_code
if "login_email" not in st.session_state:
    st.session_state.login_email = ""


def _check_api_key(provider: str) -> bool:
    key_map = {"google": "GOOGLE_API_KEY", "laozhang": "LAOZHANG_API_KEY", "grsai": "GRSAI_API_KEY"}
    return bool(os.getenv(key_map.get(provider, ""), ""))


def _get_client_ip() -> str:
    """获取客户端 IP"""
    try:
        headers = st.context.headers
        return (
            headers.get("X-Forwarded-For", "").split(",")[0].strip()
            or headers.get("X-Real-IP", "")
            or headers.get("Host", "")
            or "127.0.0.1"
        )
    except Exception:
        return "127.0.0.1"


def save_uploaded_file(uploaded_file) -> str:
    suffix = Path(uploaded_file.name).suffix or ".jpg"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    tmp.write(uploaded_file.getvalue())
    return tmp.name


# ── 侧边栏 ───────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 📱 我的账户")
    user_id = st.session_state.user_id
    user = get_user(user_id) if user_id else None

    if user:
        # ── 已登录 ─────────────────────────────────────
        st.success(f"📧 {user.get('email', '')}")
        st.markdown(f"""
        <div class="points-badge">
            <span style="font-size:1.5rem;font-weight:bold;">✨ {user['points']}</span> 积分<br>
            <small>= {user['points'] // POINTS_PER_USE} 次生成</small>
        </div>
        """, unsafe_allow_html=True)
        st.metric("📊 已用", f"{user.get('total_used', 0)} 次")

        # 充值入口
        with st.expander("💳 充值积分"):
            st.markdown(f"""
            <div class="price-card rec">
                <strong>⚡ 包月</strong><br>
                <span class="price">¥{POINTS_MONTHLY_PRICE}</span> = {POINTS_MONTHLY} 积分<br>
                <small>≈ {POINTS_MONTHLY // POINTS_PER_USE} 次</small>
            </div>
            """, unsafe_allow_html=True)
            qr_path = Path(__file__).parent / "static" / "qrcode.png"
            if qr_path.exists():
                st.image(str(qr_path), caption="微信赞赏码 ¥9.9", use_container_width=True)
            st.warning(f"⚠️ 付款后截图发给客服时，请备注你的邮箱：**{user['email']}**")
            st.info("📱 扫码赞赏 → 截图发客服 → 秒到账")
            st.caption("客服微信: SodaCao")

        if st.button("🚪 退出登录", use_container_width=True):
            st.session_state.user_id = None
            st.session_state.login_step = "input_email"
            st.session_state.login_email = ""
            st.rerun()

    else:
        # ── 未登录 ─────────────────────────────────────
        today_used = device.get("today_used", 0)
        remaining = max(0, FREE_TRIAL_LIMIT - today_used)
        if device.get("premium"):
            st.success("⭐ 付费会员")
        elif remaining > 0:
            st.info(f"🎁 今日免费：{remaining}/{FREE_TRIAL_LIMIT} 次")
        else:
            st.warning("⚠️ 今日免费已用完")

        st.caption(f"🖥️ 设备: ...{did[-8:]}")

        st.divider()

        # QQ邮箱登录
        st.markdown("### 📧 QQ邮箱登录")
        st.caption(f"注册即送 {POINTS_REGISTER_BONUS} 积分")

        if st.session_state.login_step == "input_email":
            email_input = st.text_input("QQ邮箱", key="login_email_input",
                                        placeholder="123456789@qq.com")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("📩 发送验证码", use_container_width=True, type="primary"):
                    email = email_input.strip() if email_input else ""
                    if not email or "@" not in email:
                        st.error("请输入正确的邮箱地址")
                    else:
                        ip = _get_client_ip()
                        result = send_code(email, ip)
                        if result["success"]:
                            st.session_state.login_email = email
                            st.session_state.login_step = "input_code"
                            st.success(result.get("message", "验证码已发送"))
                            st.rerun()
                        else:
                            st.error(result.get("error", "发送失败"))
            with c2:
                pass

        elif st.session_state.login_step == "input_code":
            st.info(f"验证码已发送至 **{st.session_state.login_email}**")
            code_input = st.text_input("6位验证码", key="code_input",
                                       placeholder="输入验证码", max_chars=6)
            c1, c2 = st.columns(2)
            with c1:
                if st.button("✅ 验证登录", use_container_width=True, type="primary"):
                    email = st.session_state.login_email
                    result = verify_code(email, code_input.strip() if code_input else "")
                    if result["success"]:
                        uid = create_user(email)
                        link_device_to_user(did, uid)
                        st.session_state.user_id = uid
                        st.session_state.login_step = "input_email"
                        st.success("登录成功！")
                        st.rerun()
                    else:
                        st.error(result.get("error", "验证失败"))
            with c2:
                if st.button("🔄 重发", use_container_width=True):
                    ip = _get_client_ip()
                    email = st.session_state.login_email
                    send_result = send_code(email, ip)
                    if send_result["success"]:
                        st.success("验证码已重新发送")
                        st.rerun()
                    else:
                        st.error(send_result.get("error", "重发失败"))

            if st.button("← 换邮箱", use_container_width=True):
                st.session_state.login_step = "input_email"
                st.session_state.login_email = ""
                st.rerun()

    st.divider()

    # ── API 配置 ──
    st.markdown("### ⚙️ API")
    provider_names = {k: v["name"] for k, v in PROVIDERS.items()}
    sp = st.selectbox("提供商", list(PROVIDERS.keys()),
                      format_func=lambda x: provider_names[x],
                      index=list(PROVIDERS.keys()).index(st.session_state.provider))
    if sp != st.session_state.provider:
        st.session_state.provider = sp
        st.rerun()

    if not _check_api_key(st.session_state.provider):
        key_map = {"google": "GOOGLE_API_KEY", "laozhang": "LAOZHANG_API_KEY", "grsai": "GRSAI_API_KEY"}
        api_key = st.text_input("API Key", type="password", placeholder="粘贴...")
        if api_key and st.button("💾 保存"):
            os.environ[key_map[st.session_state.provider]] = api_key
            env_path = Path(__file__).parent / ".env"
            e = env_path.read_text("utf-8") if env_path.exists() else ""
            ek = key_map[st.session_state.provider]
            if ek not in e:
                e += f"\n{ek}={api_key}\n"
            else:
                e = re.sub(f"{ek}=.*", f"{ek}={api_key}", e)
            env_path.write_text(e, "utf-8")
            st.success("已保存！")
            st.rerun()

    st.divider()

    # ── 定价 ──
    st.markdown("### 💰 定价")
    st.markdown(f"""
    <div class="price-card"><strong>🎁 免费</strong><br><small>每设备 {FREE_TRIAL_LIMIT} 次/天</small></div>
    <div class="price-card rec"><strong>⭐ 积分制</strong><br><span class="price">{POINTS_PER_USE}分/次</span><br><small>注册送{POINTS_REGISTER_BONUS}分</small></div>
    <div class="price-card"><strong>💎 包月</strong><br><span class="price">¥{POINTS_MONTHLY_PRICE}</span><br><small>{POINTS_MONTHLY}积分 ≈ {POINTS_MONTHLY // POINTS_PER_USE}次</small></div>
    """, unsafe_allow_html=True)

    if user:
        st.caption(f"💰 成本 ¥0.02/次 · 售价约 ¥0.88/次")

    st.divider()

    # ── 后台管理入口 ──
    with st.expander("🔧 后台管理"):
        admin_pw = st.text_input("管理密码", type="password", key="admin_pw")
        if st.button("进入后台") and admin_pw == ADMIN_PASSWORD:
            st.session_state.show_admin = True
            st.rerun()

# ── 后台管理页面 ──────────────────────────────────────────
if st.session_state.show_admin:
    st.markdown("## 🔧 后台管理")

    # 清理过期验证码
    cleaned = clean_expired_codes()
    if cleaned:
        st.caption(f"🧹 已清理 {cleaned} 条过期验证码")

    stats = get_stats()

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("总设备", stats["total_devices"])
    with col2:
        st.metric("总用户", stats["total_users"])
    with col3:
        st.metric("总使用", stats["total_usage"])
    with col4:
        st.metric("今日使用", stats["today_usage"])
    with col5:
        st.metric("总收入", f"¥{stats['total_revenue']:.2f}")

    st.divider()

    tab1, tab2, tab3 = st.tabs(["👥 用户管理", "📱 设备管理", "💳 充值积分"])

    with tab1:
        import json
        from pathlib import Path
        db_path = Path(__file__).parent / "data" / "db.json"
        db = json.loads(db_path.read_text(encoding="utf-8")) if db_path.exists() else {"users": {}, "devices": {}}
        users = db.get("users", {})
        if users:
            for uid, u in users.items():
                points = u.get("points", 0)
                with st.expander(f"{u.get('email', uid)} | ✨ {points}分 | {u.get('total_used', 0)}次"):
                    st.write(f"注册时间: {u.get('registered', '?')}")
                    st.write(f"绑定设备: {u.get('device_ids', [])}")
                    st.write(f"累计消耗积分: {u.get('total_spent_points', 0)}")
                    if u.get("recharge_log"):
                        st.write("充值记录:", u["recharge_log"])
        else:
            st.info("暂无用户")

    with tab2:
        devices = db.get("devices", {})
        if devices:
            for did_key, d in list(devices.items())[:50]:
                premium_badge = "⭐" if d.get("premium") else ""
                today = __import__('datetime').date.today().isoformat()
                tu = d.get("daily_usage", {}).get(today, 0)
                linked = d.get("linked_user", "")
                email = ""
                if linked:
                    u = get_user(linked)
                    email = u.get("email", "") if u else ""
                st.write(f"{premium_badge} `...{did_key[-12:]}` | 今日{tu}次 | 累计{d.get('total_usage',0)}次 | {email}")

    with tab3:
        st.markdown("#### 给用户充值积分")
        target_email = st.text_input("用户邮箱", key="admin_target")
        recharge_points = st.number_input("积分数量", min_value=888, max_value=100000,
                                          value=10000, step=1000)
        note = st.text_input("备注", value="赞赏码充值")
        if st.button("确认充值", type="primary") and target_email:
            uid = f"user_{target_email.strip()}"
            u = get_user(uid)
            if not u:
                # 用户不存在，先创建
                uid = create_user(target_email.strip())
            result = add_points(uid, int(recharge_points), note)
            if result["success"]:
                st.success(f"已为 {target_email} 充值 {recharge_points} 积分，当前 {result['points']} 分")
            else:
                st.error(result["error"])

        st.divider()
        st.markdown("#### 设置付费会员")
        premium_did = st.text_input("设备ID（完整）", key="premium_did")
        premium_days = st.number_input("天数", min_value=1, max_value=365, value=30)
        if st.button("设为付费") and premium_did:
            set_premium(premium_did, premium_days)
            st.success(f"设备 {premium_did} 已设为付费会员 {premium_days} 天")

    if st.button("← 返回主界面", use_container_width=True):
        st.session_state.show_admin = False
        st.rerun()

    st.stop()

# ── 主界面 ───────────────────────────────────────────────
st.markdown(
    """<div class="main-header">
    <h1>💇 AI 换发型</h1>
    <p>上传你的照片 + 参考发型 → AI 自动融合</p>
</div>""",
    unsafe_allow_html=True,
)

# 模式选择
st.markdown("### 🎯 选择模式")
mode_cols = st.columns(len(TRANSFER_MODES))
selected_mode = st.session_state.get("selected_mode", "hairstyle")
for i, (mk, mc) in enumerate(TRANSFER_MODES.items()):
    with mode_cols[i]:
        if st.button(mc["label"], key=f"m_{mk}", use_container_width=True,
                     type="primary" if selected_mode == mk else "secondary"):
            st.session_state.selected_mode = mk
            st.rerun()

st.divider()

# 上传区域
c1, c2 = st.columns(2)
with c1:
    st.markdown("### 📷 你的照片")
    st.caption("正面、光线好效果最佳")
    user_photo = st.file_uploader("选择照片", type=["jpg", "jpeg", "png", "webp"], key="up")
    if user_photo:
        st.image(user_photo, use_container_width=True)

with c2:
    st.markdown("### 🖼️ 参考发型")
    st.caption("任何照片，AI 自动提取发型")
    ref_photo = st.file_uploader("选择参考图", type=["jpg", "jpeg", "png", "webp"], key="rp")
    if ref_photo:
        st.image(ref_photo, use_container_width=True)

if selected_mode == "custom":
    custom_prompt = st.text_area("✍️ 描述效果", placeholder="把图1的人换成图2的发型...", height=80)
else:
    custom_prompt = None

st.divider()

# ── 生成按钮 ──────────────────────────────────────────────
gc1, gc2, gc3 = st.columns([1, 2, 1])
with gc2:
    has_key = _check_api_key(st.session_state.provider)
    has_photos = user_photo and ref_photo
    can_gen = check_can_generate(did, FREE_TRIAL_LIMIT)

    if not has_key:
        st.warning("⚠️ 请先在左侧配置 API Key")
    elif not has_photos:
        st.info("👆 上传两张照片即可开始")

    elif not can_gen["allowed"] and not user and can_gen["reason"] == "daily_limit":
        st.markdown(f"""
        <div class="limit-warn">
        <h4>🔒 今日免费 {FREE_TRIAL_LIMIT} 次已用完</h4>
        <p>QQ邮箱登录送 {POINTS_REGISTER_BONUS} 积分（可生成 {POINTS_REGISTER_BONUS // POINTS_PER_USE} 次）</p>
        </div>""", unsafe_allow_html=True)
        if st.button("📧 QQ邮箱登录（送888积分）", use_container_width=True, type="primary"):
            st.session_state.login_step = "input_email"
            st.rerun()

    elif not can_gen["allowed"] and user and can_gen["reason"] == "no_points":
        st.markdown(f"""
        <div class="limit-warn">
        <h4>🔒 积分不足</h4>
        <p>当前 {user['points']} 积分，每次需要 {POINTS_PER_USE} 积分</p>
        <p>充值 ¥{POINTS_MONTHLY_PRICE} 得 {POINTS_MONTHLY} 积分</p>
        </div>""", unsafe_allow_html=True)
        with st.expander("💳 充值（微信赞赏码）"):
            st.info("📱 微信扫码赞赏 ¥9.9 → 截图发客服微信 SodaCao → 秒到账")

    elif can_gen["reason"] == "points" and user:
        st.info(f"✨ 扣 {POINTS_PER_USE} 积分（余额 {user['points']} 分）")

    elif can_gen["reason"] == "free" and not user:
        remaining_after = can_gen.get("remaining_free", 0)
        st.info(f"🎁 今日免费还剩 {remaining_after + 1} 次")

    can_click = (has_key and has_photos and can_gen["allowed"]
                 and not (selected_mode == "custom" and not custom_prompt))

    if can_gen["allowed"]:
        if can_gen["reason"] == "free":
            btn_label = f"🎁 免费生成（今日剩{can_gen.get('remaining_free', 0) + 1}次）"
        elif can_gen["reason"] == "points":
            btn_label = f"✨ 生成（-{POINTS_PER_USE}积分）"
        else:
            btn_label = "✨ 开始生成"
    else:
        btn_label = "🔒 不可用"

    generate_clicked = st.button(btn_label, type="primary", use_container_width=True,
                                 disabled=not can_click)

# ── 生成 ──────────────────────────────────────────────────
if generate_clicked and can_click:
    user_path = save_uploaded_file(user_photo)
    ref_path = save_uploaded_file(ref_photo)

    try:
        gen_check = check_can_generate(did, FREE_TRIAL_LIMIT)
        if not gen_check["allowed"]:
            st.error("权限不足，请刷新")
            st.stop()

        cost_note = ""
        refund_needed = False

        # 积分扣费
        if gen_check["reason"] == "points" and user:
            result = deduct_points(st.session_state.user_id, POINTS_PER_USE)
            if not result["success"]:
                st.error(result["error"])
                st.stop()
            cost_note = f"已扣 {POINTS_PER_USE} 积分，余额 {result['points']} 分"
            refund_needed = True

        with st.spinner("🪄 AI 处理中（约 1-2 分钟）..."):
            api_result = call_image_api(
                user_path, ref_path, mode=selected_mode,
                custom_prompt=custom_prompt, provider_key=st.session_state.provider,
            )

        if api_result["success"]:
            record_usage(did)
            img_bytes = base64.b64decode(api_result["image_base64"])
            img = Image.open(BytesIO(img_bytes))
            st.session_state.generated_images.append({
                "user": user_photo.name, "ref": ref_photo.name, "image": img_bytes,
            })

            st.success(f"✅ 生成成功！{cost_note}")
            st.divider()
            st.markdown("### 🎨 效果")
            r1, r2, r3 = st.columns([1, 0.05, 1])
            with r1:
                st.image(user_photo, use_container_width=True, caption="原图")
            with r2:
                st.markdown("<br><br><h2>→</h2>", unsafe_allow_html=True)
            with r3:
                st.image(img, use_container_width=True, caption="结果")

            st.download_button("📥 下载", img_bytes, "result.jpg", "image/jpeg", use_container_width=True)

            new_check = check_can_generate(did, FREE_TRIAL_LIMIT)
            if new_check["reason"] == "free":
                remaining_after = new_check.get("remaining_free", 0)
                if remaining_after > 0:
                    st.info(f"💡 今日还剩 {remaining_after} 次免费")
                else:
                    st.warning("⚠️ 今日免费用完，QQ邮箱登录继续")
            elif new_check["reason"] == "points" and user:
                st.info(f"💡 积分余额 {user['points']} 分，还可生成 {user['points'] // POINTS_PER_USE} 次")
        else:
            if refund_needed and user:
                add_points(st.session_state.user_id, POINTS_PER_USE, "失败退款")
                st.warning(f"生成失败，已退还 {POINTS_PER_USE} 积分")
            st.error(f"❌ {api_result['error']}")
    finally:
        try:
            os.unlink(user_path)
            os.unlink(ref_path)
        except OSError:
            pass

# ── 历史 ──────────────────────────────────────────────────
if st.session_state.generated_images:
    st.divider()
    st.markdown("### 📋 历史")
    n = len(st.session_state.generated_images)
    hc = st.columns(min(n, 4))
    for i, item in enumerate(st.session_state.generated_images):
        with hc[i % 4]:
            st.image(item["image"], caption=f"#{i+1}", use_container_width=True)

# ── 底部 ──────────────────────────────────────────────────
st.divider()
pc = PROVIDERS[st.session_state.provider]["cost_per_call"]
st.markdown(
    f"""<div class="cost-hint">
    API成本 ¥{pc:.3f}/次 · 积分 {POINTS_PER_USE}分/次 · 免费 {FREE_TRIAL_LIMIT}次/天/设备
    </div>""",
    unsafe_allow_html=True,
)
