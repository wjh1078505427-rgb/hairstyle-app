"""多提供商 AI 图片生成客户端"""
import base64
import io
import os
import time
from pathlib import Path

import httpx
from PIL import Image

from config import PROVIDERS, TRANSFER_MODES


# ── 工具函数 ─────────────────────────────────────────────

def image_to_base64(image_path: str | Path) -> tuple[str, str]:
    """图片文件 → (mime_type, base64_data)"""
    path = Path(image_path)
    ext = path.suffix.lower()
    mime_map = {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".png": "image/png", ".webp": "image/webp",
        ".gif": "image/gif",
    }
    mime_type = mime_map.get(ext, "image/jpeg")
    with open(path, "rb") as f:
        data = base64.b64encode(f.read()).decode("utf-8")
    return mime_type, data


def image_to_data_uri(image_path: str | Path) -> str:
    """图片文件 → data: URI 字符串"""
    mime, b64 = image_to_base64(image_path)
    return f"data:{mime};base64,{b64}"


def _build_prompt(mode: str, custom_prompt: str | None = None) -> str:
    """获取对应模式的提示词"""
    if mode == "custom" and custom_prompt:
        return custom_prompt
    mode_cfg = TRANSFER_MODES.get(mode, TRANSFER_MODES["hairstyle"])
    return mode_cfg.get("prompt_template", "") or custom_prompt or ""


# ── Gemini 兼容 API（Google / laozhang / felo）───────────

def _call_gemini_api(
    user_photo_path: str | Path,
    reference_photo_path: str | Path,
    prompt: str,
    provider: dict,
    api_key: str,
) -> dict:
    """调用 Gemini 兼容 API"""
    user_mime, user_b64 = image_to_base64(user_photo_path)
    ref_mime, ref_b64 = image_to_base64(reference_photo_path)

    endpoint = f"{provider['base_url']}/{provider['model']}:generateContent"
    if provider.get("auth_param"):
        endpoint += f"?{provider['auth_param']}={api_key}"

    request_body = {
        "contents": [{
            "parts": [
                {"text": prompt},
                {"inlineData": {"mimeType": user_mime, "data": user_b64}},
                {"inlineData": {"mimeType": ref_mime, "data": ref_b64}},
            ]
        }],
        "generationConfig": {"responseModalities": ["IMAGE", "TEXT"]},
    }

    headers = {"Content-Type": "application/json"}
    if provider.get("auth_header"):
        headers["x-goog-api-key"] = api_key

    with httpx.Client(timeout=120.0) as client:
        response = client.post(endpoint, json=request_body, headers=headers)
        response.raise_for_status()
        result = response.json()

    candidates = result.get("candidates", [])
    if not candidates:
        finish = result.get("promptFeedback", {}).get("blockReason", "未知")
        return {"success": False, "image_base64": None, "text": None,
                "error": f"API 未生成内容（可能被拦截: {finish}）"}

    parts = candidates[0].get("content", {}).get("parts", [])
    image_b64 = None
    text_output = None

    for part in parts:
        if "inlineData" in part:
            image_b64 = part["inlineData"].get("data")
        if "text" in part:
            text_output = part["text"]

    if not image_b64:
        return {"success": False, "image_base64": None, "text": text_output,
                "error": f"模型未生成图片，文字回复: {(text_output or '无')[:200]}"}

    return {"success": True, "image_base64": image_b64,
            "text": text_output, "error": None}


# ── GrsAI API（异步任务模式）─────────────────────────────

def _call_grsai_api(
    user_photo_path: str | Path,
    reference_photo_path: str | Path,
    prompt: str,
    provider: dict,
    api_key: str,
) -> dict:
    """调用 GrsAI API — 创建异步任务 + 轮询结果"""
    user_data_uri = image_to_data_uri(user_photo_path)
    ref_data_uri = image_to_data_uri(reference_photo_path)

    base_url = provider["base_url"]

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    with httpx.Client(timeout=900.0) as client:
        # 1. 创建任务 — 使用 Nano Banana 专用端点
        create_resp = client.post(
            f"{base_url}/v1/draw/nano-banana",
            headers=headers,
            json={
                "model": provider["model"],
                "prompt": prompt,
                "aspectRatio": "auto",
                "imageSize": "1K",
                "urls": [user_data_uri, ref_data_uri],
                "webHook": "-1",
                "shutProgress": True,
            },
        )
        create_resp.raise_for_status()
        create_data = create_resp.json()

        if create_data.get("code") != 0:
            return {"success": False, "image_base64": None, "text": None,
                    "error": f"GrsAI 创建任务失败: {create_data.get('msg', '未知')}"}

        task_id = create_data["data"]["id"]

        # 2. 轮询结果（最多等 600 秒 = 10 分钟）
        for attempt in range(200):
            time.sleep(3)
            poll_resp = client.post(
                f"{base_url}/v1/draw/result",
                headers=headers,
                json={"id": task_id},
            )
            poll_resp.raise_for_status()
            poll_data = poll_resp.json()
            status = poll_data.get("data", {}).get("status")

            if status == "succeeded":
                results = poll_data["data"].get("results", [])
                if not results:
                    return {"success": False, "image_base64": None, "text": None,
                            "error": "GrsAI 任务完成但无图片"}

                image_url = results[0].get("url", "")
                if not image_url:
                    return {"success": False, "image_base64": None, "text": None,
                            "error": "GrsAI 任务完成但图片 URL 为空"}

                # 3. 下载图片
                img_resp = client.get(image_url)
                img_resp.raise_for_status()
                img_b64 = base64.b64encode(img_resp.content).decode("utf-8")

                return {"success": True, "image_base64": img_b64,
                        "text": None, "error": None}

            elif status == "failed":
                fail_reason = poll_data.get("data", {}).get("fail_reason", "未知原因")
                return {"success": False, "image_base64": None, "text": None,
                        "error": f"GrsAI 生成失败: {fail_reason}"}

        return {"success": False, "image_base64": None, "text": None,
                "error": "GrsAI 任务超时（900秒），请重试"}


# ── 统一入口 ─────────────────────────────────────────────

# 提供商 API 类型映射
PROVIDER_API_TYPES = {
    "google": "gemini",
    "laozhang": "gemini",
    "felo": "gemini",
    "grsai": "grsai",
}


def call_image_api(
    user_photo_path: str | Path,
    reference_photo_path: str | Path,
    mode: str = "hairstyle",
    custom_prompt: str | None = None,
    provider_key: str = "grsai",
) -> dict:
    """统一入口：调用 AI 图片生成

    Returns:
        {"success": bool, "image_base64": str|None, "text": str|None, "error": str|None}
    """
    provider = PROVIDERS.get(provider_key)
    if not provider:
        return {"success": False, "image_base64": None, "text": None,
                "error": f"未知提供商: {provider_key}"}

    # 动态读取 API Key
    env_key_map = {
        "google": "GOOGLE_API_KEY",
        "laozhang": "LAOZHANG_API_KEY",
        "felo": "FELO_API_KEY",
        "grsai": "GRSAI_API_KEY",
    }
    key_name = env_key_map.get(provider_key, "")

    # 优先从 Streamlit secrets 读取（云端），fallback 到环境变量（本地）
    api_key = ""
    try:
        import streamlit as st
        api_key = st.secrets.get(key_name, "")
    except Exception:
        pass
    if not api_key:
        api_key = os.getenv(key_name, "")

    if not api_key:
        return {"success": False, "image_base64": None, "text": None,
                "error": f"请先设置 {key_name}"}

    # 构建提示词
    prompt = _build_prompt(mode, custom_prompt)

    # 根据 API 类型分发
    api_type = PROVIDER_API_TYPES.get(provider_key, "gemini")

    try:
        if api_type == "grsai":
            return _call_grsai_api(user_photo_path, reference_photo_path,
                                   prompt, provider, api_key)
        else:
            return _call_gemini_api(user_photo_path, reference_photo_path,
                                    prompt, provider, api_key)

    except httpx.HTTPStatusError as e:
        return {"success": False, "image_base64": None, "text": None,
                "error": f"API 请求失败 ({e.response.status_code}): {e.response.text[:500]}"}
    except httpx.TimeoutException:
        return {"success": False, "image_base64": None, "text": None,
                "error": "API 请求超时，请重试"}
    except Exception as e:
        return {"success": False, "image_base64": None, "text": None,
                "error": f"未知错误: {str(e)}"}
