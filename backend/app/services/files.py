"""上传文件保存与 URL 生成。"""
import uuid
from pathlib import Path

from fastapi import UploadFile

ALLOWED_IMAGE = {"image/jpeg", "image/png", "image/gif", "image/webp"}
ALLOWED_CHAT_EXTRA = {
    "text/plain",
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_CHAT_FILE_BYTES = 10 * 1024 * 1024

_EXT_BY_TYPE = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "text/plain": ".txt",
    "application/pdf": ".pdf",
    "application/msword": ".doc",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
}


async def save_upload(upload_dir: Path, file: UploadFile, subfolder: str) -> str:
    """
    校验图片并保存到 uploads/{subfolder}，返回相对 URL 路径（/uploads/...）。
    """
    if file.content_type not in ALLOWED_IMAGE:
        raise ValueError("仅支持 jpeg/png/gif/webp 图片")
    content = await file.read()
    if len(content) > MAX_IMAGE_BYTES:
        raise ValueError("图片大小不能超过 5MB")

    ext = _EXT_BY_TYPE.get(file.content_type, ".bin")
    target_dir = upload_dir / subfolder
    target_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}{ext}"
    path = target_dir / filename
    path.write_bytes(content)
    return f"/uploads/{subfolder}/{filename}"


async def save_chat_attachment(
    upload_dir: Path, file: UploadFile
) -> tuple[str, str, str, str, bytes]:
    """
    保存聊天附件，返回 (url, kind, display_name, text_for_ai, raw_bytes)。
    kind 为 image 或 file。
    """
    content_type = file.content_type or "application/octet-stream"
    raw_name = (file.filename or "未命名文件").replace("\\", "/").split("/")[-1][:200]
    data = await file.read()
    if len(data) > MAX_CHAT_FILE_BYTES:
        raise ValueError("文件大小不能超过 10MB")

    if content_type in ALLOWED_IMAGE:
        kind = "image"
        ext = _EXT_BY_TYPE.get(content_type, ".bin")
        text_for_ai = f"用户发送了一张图片，文件名：{raw_name}。你无法直接查看图片内容，请用自然、简短的聊天口吻回应。"
    elif content_type in ALLOWED_CHAT_EXTRA or raw_name.lower().endswith((".txt", ".md", ".json")):
        kind = "file"
        ext = _EXT_BY_TYPE.get(content_type, Path(raw_name).suffix or ".bin")
        if content_type == "text/plain" or raw_name.lower().endswith((".txt", ".md", ".json")):
            try:
                snippet = data.decode("utf-8", errors="replace")[:8000]
                text_for_ai = f"用户发送了文本文件「{raw_name}」，内容如下：\n\n{snippet}"
            except OSError as exc:
                raise ValueError("无法读取文本文件") from exc
        else:
            text_for_ai = (
                f"用户发送了文件「{raw_name}」（类型 {content_type}）。"
                "你无法打开该文件，请用聊天口吻确认收到并询问是否需要文字说明。"
            )
    else:
        raise ValueError("不支持该文件类型，可发送图片或 txt/pdf/doc/docx")

    target_dir = upload_dir / "chat_files"
    target_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}{ext}"
    path = target_dir / filename
    path.write_bytes(data)
    url = f"/uploads/chat_files/{filename}"
    return url, kind, raw_name, text_for_ai, data
