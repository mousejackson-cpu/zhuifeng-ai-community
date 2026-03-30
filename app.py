import os
import io
import json
import time
import uuid
import base64
import zipfile
import logging
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, send_file, send_from_directory
from PIL import Image
from werkzeug.utils import secure_filename

load_dotenv()

# ===================== 基础配置 =====================
class Config:
    BASE_DIR = Path(__file__).resolve().parent
    TEMPLATE_DIR = BASE_DIR / "templates"
    DATA_DIR = BASE_DIR / "data"
    UPLOAD_DIR = BASE_DIR / "uploads"
    GENERATED_DIR = BASE_DIR / "generated"
    TEMP_DIR = BASE_DIR / "temp"
    HISTORY_FILE = DATA_DIR / "history.json"
    STATS_FILE = DATA_DIR / "stats.json"
    GALLERY_FILE = DATA_DIR / "gallery.sample.json"

    HOST = os.getenv("FLASK_HOST", "0.0.0.0")
    PORT = int(os.getenv("FLASK_PORT", "5000"))
    DEBUG = os.getenv("FLASK_DEBUG", "false").lower() == "true"
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024

    APP_NAME = os.getenv("APP_NAME", "追风AI Community Edition")
    PRO_BASE_URL = os.getenv("PRO_BASE_URL", "https://www.zhuifengai.hk/")
    GITHUB_URL = os.getenv("GITHUB_URL", "https://github.com/yourname/zhuifeng-ai-community")

    ARK_API_KEY = os.getenv("ARK_API_KEY", "")
    ARK_IMAGE_MODEL_ID = os.getenv("ARK_IMAGE_MODEL_ID", "")
    ARK_ANALYSIS_MODEL_ID = os.getenv("ARK_ANALYSIS_MODEL_ID", "")
    ARK_IMAGE_API = os.getenv("ARK_IMAGE_API", "https://ark.cn-beijing.volces.com/api/v3/images/generations")
    ARK_CHAT_API = os.getenv("ARK_CHAT_API", "https://ark.cn-beijing.volces.com/api/v3/chat/completions")

    QWEN_API_KEY = os.getenv("QWEN_API_KEY", "")
    QWEN_IMAGE_MODEL_ID = os.getenv("QWEN_IMAGE_MODEL_ID", "qwen-image")
    QWEN_IMAGE_API = os.getenv(
        "QWEN_IMAGE_API",
        "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation",
    )

    VIDEO_API_KEY = os.getenv("VIDEO_API_KEY", "")
    VIDEO_MODEL_ID = os.getenv("VIDEO_MODEL_ID", "")
    VIDEO_TASK_API = os.getenv("VIDEO_TASK_API", "https://ark.cn-beijing.volces.com/api/v3/contents/generations/tasks")

    SUPPORTED_IMG_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
    TARGET_SIZES = {
        "16:9": (1280, 720),
        "16:9-HD": (2560, 1440),
        "9:16": (1080, 1920),
        "3:4": (1242, 1660),
        "1:1": (1080, 1080),
    }


config = Config()

for path in [config.DATA_DIR, config.UPLOAD_DIR, config.GENERATED_DIR, config.TEMP_DIR]:
    path.mkdir(parents=True, exist_ok=True)

if not config.HISTORY_FILE.exists():
    config.HISTORY_FILE.write_text("[]", encoding="utf-8")

if not config.STATS_FILE.exists():
    config.STATS_FILE.write_text(
        json.dumps(
            {
                "success_count": 0,
                "fail_count": 0,
                "total_generated": 0,
                "total_videos": 0,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

if not config.GALLERY_FILE.exists():
    sample = [
        {
            "id": "sample-1",
            "title": "电商主图示例",
            "category": "ecommerce",
            "prompt": "高级感护肤品主图，白底棚拍，玻璃质感，柔和高光，电商广告，高清细节",
            "image": "/static/gallery-placeholder-1.svg",
        },
        {
            "id": "sample-2",
            "title": "小红书封面示例",
            "category": "social",
            "prompt": "小红书风格封面，明亮清爽，极简排版，生活方式摄影，适合种草分享",
            "image": "/static/gallery-placeholder-2.svg",
        },
        {
            "id": "sample-3",
            "title": "信息流投放示例",
            "category": "ads",
            "prompt": "高转化广告素材，强对比色块，突出卖点，品牌产品居中，商业投放风格",
            "image": "/static/gallery-placeholder-3.svg",
        },
    ]
    config.GALLERY_FILE.write_text(json.dumps(sample, ensure_ascii=False, indent=2), encoding="utf-8")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("zhuifeng_ai_community")

app = Flask(__name__, template_folder=str(config.TEMPLATE_DIR))
app.config["MAX_CONTENT_LENGTH"] = config.MAX_CONTENT_LENGTH
app.config["JSON_AS_ASCII"] = False


# ===================== 工具函数 =====================
def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def read_json(path: Path, default: Any):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def record_history(record: Dict[str, Any]) -> None:
    history = read_json(config.HISTORY_FILE, [])
    history.insert(0, record)
    write_json(config.HISTORY_FILE, history[:200])


def update_stats(success: bool, is_video: bool = False) -> None:
    stats = read_json(config.STATS_FILE, {})
    stats.setdefault("success_count", 0)
    stats.setdefault("fail_count", 0)
    stats.setdefault("total_generated", 0)
    stats.setdefault("total_videos", 0)

    if success:
        stats["success_count"] += 1
        if is_video:
            stats["total_videos"] += 1
        else:
            stats["total_generated"] += 1
    else:
        stats["fail_count"] += 1

    write_json(config.STATS_FILE, stats)


def allowed_image(filename: str) -> bool:
    return Path(filename).suffix.lower() in config.SUPPORTED_IMG_EXT


def save_uploaded_file(file_storage) -> Dict[str, str]:
    filename = secure_filename(file_storage.filename or f"upload-{uuid.uuid4().hex}.png")
    ext = Path(filename).suffix.lower()
    if ext not in config.SUPPORTED_IMG_EXT:
        raise ValueError("仅支持 jpg、jpeg、png、webp、bmp")
    final_name = f"{uuid.uuid4().hex}{ext}"
    final_path = config.UPLOAD_DIR / final_name
    file_storage.save(final_path)
    return {"filename": final_name, "url": f"/uploads/{final_name}", "path": str(final_path)}


def image_to_base64(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("utf-8")


def ratio_to_size(ratio: str) -> str:
    w, h = config.TARGET_SIZES.get(ratio, config.TARGET_SIZES["16:9"])
    return f"{w}x{h}"


def download_remote_file(url: str, dest: Path) -> None:
    resp = requests.get(url, timeout=120)
    resp.raise_for_status()
    dest.write_bytes(resp.content)


def create_placeholder_image(prompt: str, ratio: str) -> str:
    w, h = config.TARGET_SIZES.get(ratio, config.TARGET_SIZES["16:9"])
    img = Image.new("RGB", (w, h), color=(241, 245, 249))
    filename = f"placeholder_{uuid.uuid4().hex[:12]}.png"
    path = config.GENERATED_DIR / filename
    img.save(path)
    return filename


# ===================== 模型调用 =====================
def call_ark_image_generation(prompt: str, ratio: str, image_count: int = 1) -> List[str]:
    if not config.ARK_API_KEY or not config.ARK_IMAGE_MODEL_ID:
        raise RuntimeError("ARK 图片模型未配置")

    payload = {
        "model": config.ARK_IMAGE_MODEL_ID,
        "prompt": prompt,
        "size": ratio_to_size(ratio),
        "n": image_count,
        "response_format": "url",
    }
    headers = {
        "Authorization": f"Bearer {config.ARK_API_KEY}",
        "Content-Type": "application/json",
    }
    resp = requests.post(config.ARK_IMAGE_API, headers=headers, json=payload, timeout=240)
    resp.raise_for_status()
    data = resp.json()
    items = data.get("data") or []
    urls = [item.get("url") for item in items if item.get("url")]
    if not urls:
        raise RuntimeError(data.get("error", {}).get("message") or "图片生成失败")
    return urls


def call_qwen_image_generation(prompt: str, ratio: str, image_count: int = 1) -> List[str]:
    if not config.QWEN_API_KEY:
        raise RuntimeError("Qwen 图片模型未配置")

    size = ratio_to_size(ratio)
    payload = {
        "model": config.QWEN_IMAGE_MODEL_ID,
        "input": {
            "prompt": prompt,
            "size": size,
            "n": image_count,
        },
        "parameters": {
            "size": size,
        },
    }
    headers = {
        "Authorization": f"Bearer {config.QWEN_API_KEY}",
        "Content-Type": "application/json",
    }
    resp = requests.post(config.QWEN_IMAGE_API, headers=headers, json=payload, timeout=240)
    resp.raise_for_status()
    data = resp.json()

    urls: List[str] = []
    output = data.get("output") or {}
    for item in output.get("results", []) or []:
        if item.get("url"):
            urls.append(item["url"])
    if not urls:
        raise RuntimeError(data.get("message") or "Qwen 图片生成失败")
    return urls


def analyze_image_with_ark(image_path: Path, user_prompt: str = "") -> str:
    if not config.ARK_API_KEY or not config.ARK_ANALYSIS_MODEL_ID:
        return "请根据参考图提炼主体、构图、材质、光线、场景与广告风格，生成可直接用于图片创作的详细提示词。"

    image_b64 = image_to_base64(image_path)
    mime = "image/png" if image_path.suffix.lower() == ".png" else "image/jpeg"
    prompt = user_prompt.strip() or "请分析这张参考图，并输出一段适合 AI 图片生成的中文提示词，包含主体、风格、镜头、光线、构图、材质和商业用途。"
    payload = {
        "model": config.ARK_ANALYSIS_MODEL_ID,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{image_b64}"}},
                ],
            }
        ],
        "temperature": 0.2,
    }
    headers = {
        "Authorization": f"Bearer {config.ARK_API_KEY}",
        "Content-Type": "application/json",
    }
    resp = requests.post(config.ARK_CHAT_API, headers=headers, json=payload, timeout=180)
    resp.raise_for_status()
    data = resp.json()
    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError("图像分析失败")
    return choices[0].get("message", {}).get("content", "").strip() or "图像分析完成，但未返回可用内容。"


def generate_video_task(image_url: str, prompt: str, duration: int = 5) -> Dict[str, Any]:
    if not config.VIDEO_API_KEY or not config.VIDEO_MODEL_ID:
        raise RuntimeError("视频模型未配置。社区版默认关闭视频生成功能，请在 .env 中填写 VIDEO_API_KEY / VIDEO_MODEL_ID。")

    payload = {
        "model": config.VIDEO_MODEL_ID,
        "content": [
            {
                "type": "image_url",
                "image_url": image_url,
            },
            {
                "type": "text",
                "text": prompt or "根据参考图生成一段自然、稳定、适合广告展示的短视频",
            },
        ],
        "duration": duration,
    }
    headers = {
        "Authorization": f"Bearer {config.VIDEO_API_KEY}",
        "Content-Type": "application/json",
    }
    resp = requests.post(config.VIDEO_TASK_API, headers=headers, json=payload, timeout=180)
    resp.raise_for_status()
    data = resp.json()
    task_id = data.get("id") or data.get("task_id")
    if not task_id:
        raise RuntimeError(data.get("message") or "视频任务创建失败")
    return {"task_id": task_id, "raw": data}


# ===================== 页面路由 =====================
@app.route("/")
def index():
    return render_template(
        "index.html",
        app_name=config.APP_NAME,
        pro_base_url=config.PRO_BASE_URL,
        github_url=config.GITHUB_URL,
    )


@app.route("/health", methods=["GET"])
def health():
    return jsonify(
        {
            "code": 0,
            "msg": "ok",
            "data": {
                "app": config.APP_NAME,
                "provider": {
                    "ark_image": bool(config.ARK_API_KEY and config.ARK_IMAGE_MODEL_ID),
                    "ark_analysis": bool(config.ARK_API_KEY and config.ARK_ANALYSIS_MODEL_ID),
                    "qwen_image": bool(config.QWEN_API_KEY),
                    "video_enabled": bool(config.VIDEO_API_KEY and config.VIDEO_MODEL_ID),
                },
            },
        }
    )


@app.route("/generated/<path:filename>")
def serve_generated(filename: str):
    return send_from_directory(config.GENERATED_DIR, filename)


@app.route("/uploads/<path:filename>")
def serve_uploads(filename: str):
    return send_from_directory(config.UPLOAD_DIR, filename)


# ===================== API =====================
@app.route("/api/upload_img", methods=["POST"])
def api_upload_img():
    if "file" not in request.files:
        return jsonify({"code": -2, "msg": "请选择要上传的图片"}), 400

    try:
        meta = save_uploaded_file(request.files["file"])
        return jsonify({"code": 0, "msg": "上传成功", "data": meta})
    except Exception as e:
        return jsonify({"code": -1, "msg": f"上传失败：{e}"}), 400


@app.route("/api/upload_multiple_images", methods=["POST"])
def api_upload_multiple_images():
    files = request.files.getlist("files")
    if not files:
        return jsonify({"code": -2, "msg": "请选择要上传的图片"}), 400

    results = []
    try:
        for file_storage in files:
            results.append(save_uploaded_file(file_storage))
        return jsonify({"code": 0, "msg": "上传成功", "data": results})
    except Exception as e:
        return jsonify({"code": -1, "msg": f"批量上传失败：{e}"}), 400


@app.route("/api/analyze_image", methods=["POST"])
def api_analyze_image():
    try:
        image_path: Optional[Path] = None
        if "file" in request.files and request.files["file"].filename:
            meta = save_uploaded_file(request.files["file"])
            image_path = Path(meta["path"])
        else:
            data = request.get_json(silent=True) or {}
            upload_url = data.get("image_url", "")
            if upload_url.startswith("/uploads/"):
                image_path = config.UPLOAD_DIR / Path(upload_url).name

        if not image_path or not image_path.exists():
            return jsonify({"code": -2, "msg": "请先上传参考图"}), 400

        prompt = request.form.get("prompt") if request.form else ""
        if not prompt:
            prompt = (request.get_json(silent=True) or {}).get("prompt", "")
        extracted = analyze_image_with_ark(image_path, prompt)
        return jsonify({"code": 0, "msg": "分析成功", "data": {"prompt": extracted}})
    except Exception as e:
        logger.exception("analyze_image failed")
        return jsonify({"code": -1, "msg": f"分析失败：{e}"}), 500


@app.route("/api/generate", methods=["POST"])
def api_generate():
    data = request.get_json(silent=True) or request.form.to_dict() or {}
    prompt = (data.get("prompt") or "").strip()
    ratio = data.get("ratio", "16:9")
    provider = data.get("provider", "ark")
    image_count = int(data.get("image_count", 1))

    if not prompt:
        return jsonify({"code": -2, "msg": "提示词不能为空"}), 400

    image_count = max(1, min(image_count, 4))

    try:
        if provider == "qwen":
            remote_urls = call_qwen_image_generation(prompt, ratio, image_count)
        else:
            remote_urls = call_ark_image_generation(prompt, ratio, image_count)

        files = []
        for url in remote_urls:
            filename = f"img_{uuid.uuid4().hex[:12]}.png"
            save_path = config.GENERATED_DIR / filename
            download_remote_file(url, save_path)
            files.append({"filename": filename, "url": f"/generated/{filename}"})

        record = {
            "id": uuid.uuid4().hex,
            "type": "image",
            "prompt": prompt,
            "ratio": ratio,
            "provider": provider,
            "created_at": now_str(),
            "files": files,
        }
        record_history(record)
        update_stats(True, is_video=False)
        return jsonify({"code": 0, "msg": "生成成功", "data": record})
    except Exception as e:
        logger.exception("generate failed")
        update_stats(False, is_video=False)
        placeholder = create_placeholder_image(prompt, ratio)
        record = {
            "id": uuid.uuid4().hex,
            "type": "image",
            "prompt": prompt,
            "ratio": ratio,
            "provider": provider,
            "created_at": now_str(),
            "files": [{"filename": placeholder, "url": f"/generated/{placeholder}"}],
            "fallback": True,
            "error": str(e),
        }
        record_history(record)
        return jsonify(
            {
                "code": 0,
                "msg": "当前环境未能调用远程模型，已返回占位图用于本地调试。请检查 .env 中的模型配置。",
                "data": record,
            }
        )


@app.route("/api/generate_video", methods=["POST"])
def api_generate_video():
    data = request.get_json(silent=True) or request.form.to_dict() or {}
    prompt = (data.get("prompt") or "").strip()
    duration = int(data.get("duration", 5))
    image_url = data.get("image_url", "")

    if not image_url:
        return jsonify({"code": -2, "msg": "请先提供参考图 image_url"}), 400

    try:
        task = generate_video_task(image_url=image_url, prompt=prompt, duration=duration)
        record = {
            "id": task["task_id"],
            "type": "video",
            "prompt": prompt,
            "image_url": image_url,
            "duration": duration,
            "created_at": now_str(),
            "status": "submitted",
        }
        record_history(record)
        return jsonify({"code": 0, "msg": "视频任务已提交", "data": record})
    except Exception as e:
        return jsonify({"code": -1, "msg": str(e)}), 400


@app.route("/api/video/status/<task_id>", methods=["GET"])
def api_video_status(task_id: str):
    if not config.VIDEO_API_KEY:
        return jsonify({"code": -1, "msg": "视频能力未启用"}), 400

    headers = {"Authorization": f"Bearer {config.VIDEO_API_KEY}"}
    try:
        resp = requests.get(f"{config.VIDEO_TASK_API}/{task_id}", headers=headers, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        return jsonify({"code": 0, "msg": "ok", "data": data})
    except Exception as e:
        return jsonify({"code": -1, "msg": f"查询视频状态失败：{e}"}), 500


@app.route("/api/history", methods=["GET"])
def api_history():
    history = read_json(config.HISTORY_FILE, [])
    return jsonify({"code": 0, "msg": "ok", "data": history})


@app.route("/api/stats", methods=["GET"])
def api_stats():
    stats = read_json(config.STATS_FILE, {})
    return jsonify({"code": 0, "msg": "ok", "data": stats})


@app.route("/api/gallery", methods=["GET"])
def api_gallery():
    gallery = read_json(config.GALLERY_FILE, [])
    category = request.args.get("category", "all")
    if category != "all":
        gallery = [item for item in gallery if item.get("category") == category]
    return jsonify({"code": 0, "msg": "ok", "data": gallery})


@app.route("/api/download/batch", methods=["POST"])
def api_download_batch():
    data = request.get_json(silent=True) or {}
    urls = data.get("urls") or []
    if not urls:
        return jsonify({"code": -2, "msg": "请选择要下载的文件"}), 400

    zip_name = f"zhuifeng_batch_{int(time.time())}.zip"
    zip_path = config.TEMP_DIR / zip_name
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for index, item in enumerate(urls, start=1):
            path = None
            if isinstance(item, dict):
                url = item.get("url") or ""
            else:
                url = str(item)
            if url.startswith("/generated/"):
                path = config.GENERATED_DIR / Path(url).name
            elif url.startswith("/uploads/"):
                path = config.UPLOAD_DIR / Path(url).name
            if path and path.exists():
                zf.write(path, arcname=f"{index:02d}_{path.name}")

    return send_file(zip_path, as_attachment=True, download_name=zip_name)


if __name__ == "__main__":
    app.run(host=config.HOST, port=config.PORT, debug=config.DEBUG)
