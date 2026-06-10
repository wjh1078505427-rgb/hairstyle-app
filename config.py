"""配置管理 — 多 API 提供商"""
import os
from dotenv import load_dotenv

load_dotenv()

# ── API 提供商配置 ──────────────────────────────────────
# 按优先级排序，第一个有 key 的会被默认选中

PROVIDERS = {
    "grsai": {
        "name": "🚌 GrsAI（gpt-image-2，推荐）",
        "base_url": "https://grsai.dakka.com.cn",
        "model": "gpt-image-2",
        "model_pro": "nano-banana-fast",
        "cost_per_call": 0.02,
        "free_daily": "注册送 1000 积分 + 兑换码送 10 万积分",
        "setup_url": "https://grsai.com",
        "note": "国内直连，微信/支付宝充值，端点 /v1/draw/completions",
    },
    "google": {
        "name": "🎌 Google AI Studio（免费）",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/models",
        "model": "gemini-2.5-flash-image",
        "model_pro": "gemini-3-pro-image-preview",
        "auth_header": False,
        "auth_param": "key",
        "cost_per_call": 0,
        "free_daily": "500+ 张/天（新用户 AQ key 可能配额为 1）",
        "setup_url": "https://aistudio.google.com/apikey",
        "note": "Google 账号登录获取，新用户 AQ 格式 key 有配额 bug",
    },
    "laozhang": {
        "name": "💵 laozhang.ai（Nano Banana Pro）",
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

DEFAULT_PROVIDER = "google"

# ── 转换模式 ────────────────────────────────────────────

TRANSFER_MODES = {
    "hairstyle": {
        "label": "💇 换发型",
        "icon": "💇",
        "prompt_template": (
            "Generate a completely new, photorealistic portrait. "
            "The person is the same individual as in Image 1 — same identity, facial features, expression, skin tone, and clothing. "
            "However, their hairstyle has been professionally changed to match the hairstyle from Image 2. "
            "Carefully analyze Image 2: replicate its haircut shape, hair color, length, texture, curl pattern, bangs/fringe style, part line, and volume. "
            "Naturally adapt this hairstyle to the head shape and face framing of the person in Image 1. "
            "The hair must blend seamlessly with the scalp — render realistic hair roots, natural shadows at the hairline, and consistent lighting that matches Image 1's original light direction. "
            "Do NOT simply paste or overlay hair. Render the entire image as one unified photograph: "
            "hair, face, background, clothing, and lighting all belong to the same scene. "
            "The result should look like a genuine before-and-after photo from a high-end hair salon — "
            "same person, same setting, new hairstyle. "
            "Output: a single realistic photograph, no text overlay, no split-screen, no collage."
        ),
    },
    "outfit": {
        "label": "👗 换穿搭",
        "icon": "👗",
        "prompt_template": (
            "Generate a completely new, photorealistic full-body or portrait shot. "
            "The person is the same individual as in Image 1 — same identity, facial features, skin tone, and pose. "
            "However, their outfit has been professionally changed to match the clothing style from Image 2. "
            "Carefully analyze Image 2: replicate its garment type, color palette, patterns, cut, layering, fabric drape, and accessories. "
            "Dress the person in Image 1 with this outfit. The clothing must drape naturally over their body shape, "
            "with realistic fabric folds, shadows, and interaction with the pose and lighting from Image 1. "
            "Do NOT simply paste or overlay clothing. Render the entire image as one unified photograph: "
            "the outfit, body, face, background, and lighting all belong to the same scene. "
            "Keep the person's hairstyle, makeup, and expression consistent with Image 1. "
            "Output: a single realistic photograph, no text overlay, no split-screen, no collage."
        ),
    },
    "style": {
        "label": "🎨 风格迁移",
        "icon": "🎨",
        "prompt_template": (
            "Generate a completely new image. Take the subject and composition from Image 1 "
            "and re-render it entirely in the visual style from Image 2. "
            "Analyze Image 2 for: color palette, lighting mood, texture quality, depth of field, contrast, saturation, "
            "and overall aesthetic (e.g. film photography, oil painting, anime, editorial fashion, vintage). "
            "Apply this style to Image 1 as if the same scene were shot or painted in that style from the start — "
            "not as a filter overlay, but as a genuine re-rendering where every pixel naturally belongs to the target style. "
            "Preserve the core subject, pose, and composition from Image 1. "
            "Output: a single cohesive image, no text overlay, no split-screen, no collage."
        ),
    },
    "custom": {
        "label": "✏️ 自由描述",
        "icon": "✏️",
        "prompt_template": None,
    },
}

# ── 定价方案（对应前端展示） ─────────────────────────────

PRICING = {
    "free_trial": {"uses": 5, "price": 0, "label": "免费试用"},
    "standard": {"uses": 10, "price": 9.9, "label": "标准包"},
    "unlimited": {"uses": -1, "price": 19.9, "label": "30天无限包"},
    "consult": {"uses": 1, "price": 29.9, "label": "AI 形象咨询"},
}

FREE_TRIAL_LIMIT = 5

