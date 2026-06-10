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
            "Task: Give the person in Image 1 the hairstyle from Image 2. "
            "CRITICAL — Head pose & angle adaptation: "
            "Image 1 and Image 2 may have different head angles, tilts, or camera positions. "
            "You MUST first detect the exact head orientation, camera angle, and face direction in Image 1. "
            "Then mentally rotate and adjust the hairstyle from Image 2 to fit Image 1's angle. "
            "The hairstyle should look like it naturally exists on Image 1's head at THAT angle — "
            "not pasted from a different perspective. Hair volume, part line placement, and fringe shape "
            "must all respect the 3D orientation of Image 1's head. "
            "Lighting & shadow: "
            "Analyze the light source direction, intensity, and color temperature in Image 1. "
            "Re-light the new hairstyle to match exactly — natural scalp shadows at the hairline, "
            "consistent highlight placement, same ambient occlusion. "
            "Hair physics & scale: "
            "Measure the head size in Image 1. Scale the hairstyle from Image 2 proportionally. "
            "Do NOT copy hair volume literally — adapt it to the actual head dimensions in Image 1. "
            "If Image 2 shows long hair, render it falling naturally with gravity relative to Image 1's head tilt. "
            "Identity preservation: "
            "Keep the person's face, facial features, expression, skin tone, and clothing identical to Image 1. "
            "Only the hair changes. "
            "Output: a SINGLE realistic photograph — same person, same background, same lighting, new hairstyle. "
            "No text, no watermark, no split-screen, no before/after collage."
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

