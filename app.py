"""AI 图片风格迁移 — 免费1次/天，¥0.8/次"""
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
from config import DEFAULT_PROVIDER, FREE_TRIAL_LIMIT, PRICING, PROVIDERS, TRANSFER_MODES
from db import (
    add_balance, check_can_generate, create_user, deduct_balance,
    get_or_create_device, get_stats, get_user, link_device_to_user,
    record_usage, set_premium,
)

ADMIN_PASSWORD = "admin888"  # 后台管理密码，生产环境请修改

# ── 页面配置 ─────────────────────────────────────────────
st.set_page_config(
    page_title="AI 图片风格迁移",
    page_icon="🎨",
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
</style>
""", unsafe_allow_html=True)

# ── 设备追踪（无 JS，纯 HTTP 指纹 + 会话） ────────────────
# 优先级：query param > HTTP 指纹 > 随机生成

def _get_fingerprint() -> str:
    """从 HTTP 请求头生成设备指纹"""
    try:
        headers = st.context.headers
        ip = (
            headers.get("X-Forwarded-For", "").split(",")[0].strip()
            or headers.get("X-Real-IP", "")
            or headers.get("Host", "")
        )
        ua = headers.get("User-Agent", "")
        raw = f"{ip}|{ua}"
        if raw.strip() == "|":
            return ""
        return "dev_" + hashlib.md5(raw.encode()).hexdigest()[:12]
    except Exception:
        return ""


if "device_id" not in st.session_state:
    # 1. 优先从 URL 参数读取（用户可分享带 did 的链接）
    try:
        params = st.query_params
        if "did" in params and params["did"]:
            st.session_state.device_id = params["did"]
    except Exception:
        pass

if "device_id" not in st.session_state:
    # 2. 尝试 HTTP 指纹
    fp = _get_fingerprint()
    if fp:
        st.session_state.device_id = fp
    else:
        # 3. 降级：随机 ID（每次会话不同）
        st.session_state.device_id = "dev_" + uuid.uuid4().hex[:12]

did = st.session_state.device_id

# ── 会话状态 ─────────────────────────────────────────────
device = get_or_create_device(did)
check = check_can_generate(did, FREE_TRIAL_LIMIT)

if "generated_images" not in st.session_state:
    st.session_state.generated_images = []
if "provider" not in st.session_state:
    st.session_state.provider = DEFAULT_PROVIDER
if "user_id" not in st.session_state:
    st.session_state.user_id = device.get("linked_user")
if "show_register" not in st.session_state:
    st.session_state.show_register = False
if "show_admin" not in st.session_state:
    st.session_state.show_admin = False


def _check_api_key(provider: str) -> bool:
    key_map = {"google": "GOOGLE_API_KEY", "laozhang": "LAOZHANG_API_KEY", "grsai": "GRSAI_API_KEY"}
    return bool(os.getenv(key_map.get(provider, ""), ""))


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
        st.success(f"👤 {user['username']}")
        st.metric("💰 余额", f"¥{user['balance']:.2f}")
        st.metric("📊 已用", f"{user['total_used']} 次")
        if st.button("🚪 退出", use_container_width=True):
            st.session_state.user_id = None
            st.rerun()
    else:
        today_used = device.get("today_used", 0)
        remaining = max(0, FREE_TRIAL_LIMIT - today_used)
        if device.get("premium"):
            st.success("⭐ 付费会员")
        elif remaining > 0:
            st.info(f"🎁 今日免费：{remaining}/{FREE_TRIAL_LIMIT} 次")
        else:
            st.warning("⚠️ 今日免费已用完")

        st.caption(f"🖥️ 设备: ...{did[-8:]}")

        # 登录/注册
        st.divider()
        if not st.session_state.show_register:
            login_name = st.text_input("用户名", key="ln", placeholder="输入用户名登录")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("登录", use_container_width=True) and login_name:
                    uid = f"user_{login_name}"
                    u = get_user(uid)
                    if u:
                        st.session_state.user_id = uid
                        link_device_to_user(did, uid)
                        st.rerun()
                    else:
                        st.error("用户不存在")
            with c2:
                if st.button("注册", use_container_width=True):
                    st.session_state.show_register = True
                    st.rerun()
        else:
            reg_name = st.text_input("设置用户名", key="rn", placeholder="字母或中文")
            c1, c2 = st.columns(2)
            with c1:
                if st.button("确认注册", use_container_width=True) and reg_name:
                    uid = create_user(reg_name)
                    link_device_to_user(did, uid)
                    st.session_state.user_id = uid
                    st.session_state.show_register = False
                    st.success("注册成功！")
                    st.rerun()
            with c2:
                if st.button("← 返回", use_container_width=True):
                    st.session_state.show_register = False
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
    <div class="price-card"><strong>🎁 免费</strong><br><small>每设备 {FREE_TRIAL_LIMIT}次/天</small></div>
    <div class="price-card rec"><strong>⭐ 按次</strong><br><span class="price">¥0.8/次</span><br><small>注册充值</small></div>
    """, unsafe_allow_html=True)

    # 充值
    if user:
        st.divider()
        st.markdown("### 💳 充值")
        code = st.text_input("充值码", placeholder="输入充值码")
        if code and st.button("兑换", use_container_width=True):
            if code.startswith("ADMIN"):
                amt = float(re.search(r'(\d+)', code).group(1)) if re.search(r'(\d+)', code) else 10
                add_balance(user_id, amt, f"充值码: {code}")
                st.success(f"充值 ¥{amt} 成功！")
                st.rerun()
            else:
                st.error("无效充值码")
        st.caption("客服微信: SodaCao")

    st.divider()
    st.caption(f"成本 ¥0.02/次 · 售价 ¥0.80/次 · 毛利 ¥0.78/次")

    # ── 后台管理入口 ──
    with st.expander("🔧 后台管理"):
        admin_pw = st.text_input("管理密码", type="password", key="admin_pw")
        if st.button("进入后台") and admin_pw == ADMIN_PASSWORD:
            st.session_state.show_admin = True
            st.rerun()

# ── 后台管理页面 ──────────────────────────────────────────
if st.session_state.show_admin:
    st.markdown("## 🔧 后台管理")
    stats = get_stats()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("总设备", stats["total_devices"])
    with col2:
        st.metric("总使用", stats["total_usage"])
    with col3:
        st.metric("今日使用", stats["today_usage"])
    with col4:
        st.metric("总收入", f"¥{stats['total_revenue']:.2f}")

    st.divider()

    tab1, tab2, tab3 = st.tabs(["👥 用户管理", "📱 设备管理", "💳 充值操作"])

    with tab1:
        from db import _read_db
        db = _read_db()
        users = db.get("users", {})
        if users:
            for uid, u in users.items():
                with st.expander(f"{u['username']} | 余额 ¥{u['balance']:.2f} | {u['total_used']}次"):
                    st.write(f"注册时间: {u.get('registered', '?')}")
                    st.write(f"绑定设备: {u.get('device_ids', [])}")
                    st.write(f"累计消费: ¥{u.get('total_spent', 0):.2f}")
        else:
            st.info("暂无用户")

    with tab2:
        devices = db.get("devices", {})
        if devices:
            for did_key, d in list(devices.items())[:50]:
                premium_badge = "⭐" if d.get("premium") else ""
                today = __import__('datetime').date.today().isoformat()
                tu = d.get("daily_usage", {}).get(today, 0)
                st.write(f"{premium_badge} `...{did_key[-12:]}` | 今日{tu}次 | 累计{d.get('total_usage',0)}次")

    with tab3:
        target_user = st.text_input("目标用户名", key="admin_target")
        recharge_amount = st.number_input("充值金额", min_value=1.0, max_value=1000.0, value=10.0, step=10.0)
        note = st.text_input("备注", value="管理员充值")
        if st.button("确认充值", type="primary") and target_user:
            result = add_balance(f"user_{target_user}", recharge_amount, note)
            if result["success"]:
                st.success(f"已为 {target_user} 充值 ¥{recharge_amount}，当前余额 ¥{result['balance']:.2f}")
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

    st.stop()  # 在后台页面时不显示主界面

# ── 主界面 ───────────────────────────────────────────────
st.markdown(
    """<div class="main-header">
    <h1>🎨 AI 图片风格迁移</h1>
    <p>上传你的照片 + 参考图片 → AI 自动融合</p>
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
    st.markdown("### 🖼️ 参考图片")
    st.caption("任何照片，AI 自动提取特征")
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

    elif not can_gen["allowed"] and not user:
        st.markdown(f"""
        <div class="limit-warn">
        <h4>🔒 今日免费 {FREE_TRIAL_LIMIT} 次已用完</h4>
        <p>注册充值 ¥0.80/次 继续使用，或明天再来免费</p>
        </div>""", unsafe_allow_html=True)
        if st.button("📝 免费注册", use_container_width=True, type="primary"):
            st.session_state.show_register = True
            st.rerun()

    elif can_gen["reason"] == "balance" and user:
        st.info(f"💰 扣 ¥0.80（余额 ¥{user['balance']:.2f}）")

    elif not can_gen["allowed"] and user:
        st.error(f"💰 余额不足（¥{user['balance']:.2f}），请充值")

    can_click = (has_key and has_photos and can_gen["allowed"]
                 and not (selected_mode == "custom" and not custom_prompt))

    btn_label = "✨ 开始生成" if can_gen["allowed"] else "🔒 免费已用完"
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
        if gen_check["reason"] == "balance" and user:
            result = deduct_balance(st.session_state.user_id, 0.80)
            if not result["success"]:
                st.error(result["error"])
                st.stop()
            cost_note = f"已扣 ¥0.80，余额 ¥{result['balance']:.2f}"
            refund_needed = True

        with st.spinner("🪄 AI 处理中（30-60秒）..."):
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
            if new_check["remaining_free"] > 0:
                st.info(f"💡 今日还剩 {new_check['remaining_free']} 次免费")
            elif not user:
                st.warning("⚠️ 免费次数用完，注册 ¥0.80/次 继续")
        else:
            if refund_needed:
                add_balance(st.session_state.user_id, 0.80, "失败退款")
                st.warning("生成失败，已退款 ¥0.80")
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
    API成本 ¥{pc:.3f}/次 · 售价 ¥0.80/次 · 免费 {FREE_TRIAL_LIMIT}次/天/设备
    </div>""",
    unsafe_allow_html=True,
)
