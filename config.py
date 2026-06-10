"""配置管理 — 多 API 提供商"""
import os
from dotenv import load_dotenv

load_dotenv()

# ── API 提供商配置 ──────────────────────────────────────
# 按优先级排序，第一个有 key 的会被默认选中

PROVIDERS = {
    "grsai": {
        "name": "🥇 GrsAI（gpt-image-2，推荐）",
        "base_url": "https://grsai.dakka.com.cn",  # 国内直连
        "model": "gpt-image-2",  # GPT-4o 生图，效果最好
        "model_pro": "nano-banana-fast",  # 备用
        "cost_per_call": 0.02,  # ¥0.02/张
        "free_daily": "注册送5000积分 + 兑换码送10万积分",
        "setup_url": "https://grsai.com",
        "note": "国内直连，微信/支付宝充值，端点 /v1/draw/completions",
    },
    "google": {
        "name": "🆓 Google AI Studio（免费）",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/models",
        "model": "gemini-2.5-flash-image",
        "model_pro": "gemini-3-pro-image-preview",
        "auth_header": False,
        "auth_param": "key",
        "cost_per_call": 0,
        "free_daily": "500+张/天（新用户 AQ key 可能配额为0）",
        "setup_url": "https://aistudio.google.com/apikey",
        "note": "Google 账号登录获取，新用户 AQ 格式 key 有配额 bug",
    },
    "laozhang": {
        "name": "💰 laozhang.ai（Nano Banana Pro）",
        "base_url": "https://api.laozhang.ai/v1beta/models",
        "model": "gemini-3-pro-image-preview",
        "model_pro": "gemini-3-pro-image-preview",
        "auth_header": True,
        "auth_param": None,
        "cost_per_call": 0.09,
        "free_daily": "无免费额度",
        "setup_url": "https://laozhang.ai",
        "note": "需充值，$0.09/次（¥0.65）",
    },
}

# 默认提供商
DEFAULT_PROVIDER = "grsai"

# ── 转换模式 ────────────────────────────────────────────
TRANSFER_MODES = {
    "hairstyle": {
        "label": "💇 换发型",
        "icon": "💇",
        "prompt_template": "生成一张新照片：图1中的人物，换成图2中的发型。保持图1人物的脸、五官、表情、肤色、头部形状完全不变。提取图2中的发型（包括发型的剪裁、颜色、长度、卷曲度、刘海、分缝），应用到图1人物的头上。背景、衣服、配饰保持图1不变。输出一张逼真的照片，就像真实的理发店效果图。",
    },
    "outfit": {
        "label": "👗 换穿搭",
        "icon": "👗",
        "prompt_template": "生成一张新照片：图1中的人物，穿上图2中的衣服/穿搭。保持图1人物的脸、身材、肤色、姿势、背景完全不变。提取图2中的服装风格（包括款式、颜色、图案、版型、层次、配饰），穿到图1人物身上。发型、妆容、表情保持图1不变。输出一张逼真的照片，衣服自然贴合。",
    },
    "style": {
        "label": "🎨 风格迁移",
        "icon": "🎨",
        "prompt_template": "生成一张新照片：将图1的内容用图2的视觉风格重新呈现。保持图1的主体、构图不变。应用图2的色彩风格、光线氛围、美学质感。输出一张自然的照片，不是滤镜叠加的效果。",
    },
    "custom": {
        "label": "✨ 自由描述",
        "icon": "✨",
        "prompt_template": None,  # 用户自己写 prompt
    },
}

# ── 定价方案（对应前端展示） ────────────────────────────
PRICING = {
    "free_trial": {"uses": 5, "price": 0, "label": "免费试用"},
    "standard": {"uses": 10, "price": 9.9, "label": "标准包"},
    "unlimited": {"uses": -1, "price": 19.9, "label": "30天无限包"},
    "consult": {"uses": 1, "price": 29.9, "label": "AI 形象咨询"},
}

# 免费试用次数
FREE_TRIAL_LIMIT = 5
