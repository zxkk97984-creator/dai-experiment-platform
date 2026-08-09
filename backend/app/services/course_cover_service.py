"""课程封面的存储与校验服务。

沿用教师视频上传的“服务层校验 + staging 写入 + 原子移动”模式：
- 仅允许 JPEG、PNG、GIF、WebP，明确拒绝 SVG（脚本/外部资源风险）；
- 扩展名、声明 MIME 与文件魔数三者同时校验；
- 磁盘文件名使用 uuid4().hex，原文件名不进入磁盘路径；
- 文件先写入 .staging 目录，校验通过后 os.replace 原子移动到最终位置；
- 封面为公开展示资产，无签名播放逻辑（与视频不同）。
"""
from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from pathlib import Path

from fastapi import UploadFile

from app.config import Settings
from app.errors import api_error

# 扩展名 -> 标准 MIME 白名单（大小写不敏感）
ALLOWED_COVER_TYPES: dict[str, str] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
}

_CHUNK_SIZE = 1024 * 1024  # 流式读取块大小

# 封面存储 key 的逻辑前缀（数据库仅保存逻辑 key，不保存绝对路径）
COVER_KEY_PREFIX = "covers/"


@dataclass(frozen=True)
class StoredCover:
    storage_key: str
    content_type: str
    size: int


def _validate_filename(filename: str | None) -> str:
    """校验文件名本身是否安全（原文件名不落盘，仅用于推导扩展名）。"""
    if not filename:
        raise api_error(400, "COVER_FILE_EMPTY", "缺少文件名")
    if len(filename) > 255:
        raise api_error(400, "COVER_FILENAME_INVALID", "文件名长度不能超过 255 字符")
    # 拒绝 NUL 与全部控制字符
    for ch in filename:
        if ch == "\x00" or (ord(ch) < 0x20 and ch not in "\t\n\r"):
            raise api_error(400, "COVER_FILENAME_INVALID", "文件名包含非法控制字符")
    if "/" in filename or "\\" in filename:
        raise api_error(400, "COVER_FILENAME_INVALID", "文件名不能包含路径分隔符")
    # 拒绝 "." / ".." 路径片段（含任意位置的 ".." 组合）
    if filename in (".", "..") or ".." in filename:
        raise api_error(400, "COVER_FILENAME_INVALID", "文件名不能包含 .. 路径片段")
    return filename


def _check_magic_number(ext: str, head: bytes) -> bool:
    """校验文件头魔数是否与扩展名匹配。"""
    if ext in (".jpg", ".jpeg"):
        return head.startswith(b"\xff\xd8\xff")
    if ext == ".png":
        return head.startswith(b"\x89PNG\r\n\x1a\n")
    if ext == ".gif":
        return head.startswith((b"GIF87a", b"GIF89a"))
    if ext == ".webp":
        return len(head) >= 12 and head[:4] == b"RIFF" and head[8:12] == b"WEBP"
    return False


def _validate_upload(upload: UploadFile, settings: Settings) -> str:
    """校验文件名、MIME、扩展名与魔数，返回标准 MIME。"""
    filename = _validate_filename(upload.filename)

    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_COVER_TYPES:
        raise api_error(415, "COVER_TYPE_UNSUPPORTED", "仅支持 JPG / PNG / WebP / GIF 图片")

    declared_mime = (upload.content_type or "").split(";")[0].strip().lower()
    if declared_mime not in ALLOWED_COVER_TYPES.values():
        raise api_error(415, "COVER_TYPE_UNSUPPORTED", "图片 MIME 类型不受支持")

    expected_mime = ALLOWED_COVER_TYPES[ext]
    if declared_mime != expected_mime:
        raise api_error(415, "COVER_TYPE_UNSUPPORTED", "图片扩展名与 MIME 类型不匹配")

    # 读取文件头用于空文件与魔数校验（WebP 需要至少 12 字节）
    head = upload.file.read(16)
    upload.file.seek(0)
    if not head:
        raise api_error(400, "COVER_FILE_EMPTY", "图片文件为空")
    if not _check_magic_number(ext, head):
        raise api_error(415, "COVER_CONTENT_INVALID", "图片文件内容格式校验失败")

    return expected_mime


def _staging_path(settings: Settings) -> Path:
    """staging 目录：位于封面根目录内，上传时创建。"""
    path = settings.cover_storage_path / ".staging"
    path.mkdir(parents=True, exist_ok=True)
    return path


def resolve_storage_path(settings: Settings, storage_key: str | None) -> Path:
    """把存储 key 解析为磁盘路径；非 covers/ 前缀或越出封面根目录一律拒绝。

    先移除逻辑前缀再拼接，避免 key 内的 `../` 片段被 normalize 回根目录内
    而绕过 relative_to 校验。
    """
    if not storage_key or not storage_key.startswith(COVER_KEY_PREFIX):
        raise api_error(404, "COVER_NOT_FOUND", "封面文件不存在")
    root = settings.cover_storage_path
    relative = storage_key[len(COVER_KEY_PREFIX):]
    try:
        candidate = (root / relative).resolve()
        candidate.relative_to(root.resolve())
    except (ValueError, OSError):
        raise api_error(404, "COVER_NOT_FOUND", "封面文件不存在")
    return candidate


def remove_storage_key(settings: Settings, storage_key: str | None) -> None:
    """删除磁盘文件；文件不存在或删除失败只记录，不抛异常（生命周期尽力而为）。"""
    if not storage_key:
        return
    try:
        path = resolve_storage_path(settings, storage_key)
        if path.exists():
            path.unlink()
    except Exception:
        # 旧文件删除失败不能回滚已成功提交的新封面，只记录结构化错误
        import logging

        logging.getLogger("course_cover").error(
            "remove storage key failed: %s", storage_key, exc_info=True
        )


def content_type_for_storage_key(storage_key: str) -> str:
    """根据存储 key 的扩展名推断标准 MIME（公开读取端点使用）。"""
    return ALLOWED_COVER_TYPES.get(
        Path(storage_key).suffix.lower(), "application/octet-stream"
    )


async def store_upload(
    upload: UploadFile,
    course_id: int,
    settings: Settings,
) -> StoredCover:
    """校验并原子保存上传文件，返回元数据。任何失败都会清理 staging 文件。"""
    content_type = _validate_upload(upload, settings)

    ext = Path(upload.filename).suffix.lower()
    storage_key = f"{COVER_KEY_PREFIX}{course_id}/{uuid.uuid4().hex}{ext}"

    staging = _staging_path(settings)
    staging_file = staging / f"{uuid.uuid4().hex}.part"
    total = 0
    try:
        with staging_file.open("wb") as out:
            while True:
                chunk = await upload.read(_CHUNK_SIZE)
                if not chunk:
                    break
                total += len(chunk)
                if total > settings.cover_max_upload_bytes:
                    raise api_error(413, "COVER_TOO_LARGE", "封面文件超过 5 MB 大小限制")
                out.write(chunk)
        if total == 0:
            raise api_error(400, "COVER_FILE_EMPTY", "图片文件为空")

        # 原子移动到最终位置：key 移除逻辑前缀后的相对路径（磁盘上不再有
        # covers/ 目录层，与 resolve_storage_path 的解析规则保持一致）
        relative = storage_key[len(COVER_KEY_PREFIX):]
        final = settings.cover_storage_path / relative
        final.parent.mkdir(parents=True, exist_ok=True)
        os.replace(staging_file, final)
        return StoredCover(
            storage_key=storage_key,
            content_type=content_type,
            size=total,
        )
    finally:
        # 任何异常或客户端取消都清理 staging 文件
        if staging_file.exists():
            try:
                staging_file.unlink()
            except OSError:
                pass
