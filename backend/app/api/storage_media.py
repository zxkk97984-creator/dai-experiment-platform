"""HTTP adaptation for reading objects from StorageService.

This module intentionally owns HTTP-only concerns such as Range parsing,
response headers and streaming response construction.  Storage backends only
provide object metadata and forward-only byte streams.
"""
from __future__ import annotations

import re
from email.utils import format_datetime
from secrets import token_hex
from urllib.parse import quote

from fastapi import Request
from fastapi.responses import PlainTextResponse, Response, StreamingResponse

from app.storage import StorageArea, StorageService, StorageReadStream


_CHUNK_SIZE = 1024 * 1024
_RANGE_PATTERN = re.compile(r"^\s*(\d*)-(\d*)\s*$")


class _MalformedRange(ValueError):
    pass


class _UnsatisfiableRange(ValueError):
    def __init__(self, size: int) -> None:
        self.size = size


def _parse_ranges(value: str | None, size: int) -> list[tuple[int, int]] | None:
    if value is None:
        return None
    try:
        units, raw_ranges = value.split("=", 1)
    except ValueError as exc:
        raise _MalformedRange("Range header is malformed") from exc
    if units.strip().lower() != "bytes":
        raise _MalformedRange("Only byte ranges are supported")

    ranges: list[tuple[int, int]] = []
    for raw_range in raw_ranges.split(","):
        match = _RANGE_PATTERN.fullmatch(raw_range)
        if not match or match.groups() == ("", ""):
            raise _MalformedRange("Range header must contain a byte range")
        start_text, end_text = match.groups()
        if not size:
            raise _UnsatisfiableRange(size)
        if not start_text:
            suffix_length = int(end_text)
            if suffix_length <= 0:
                raise _UnsatisfiableRange(size)
            start = max(0, size - suffix_length)
            end = size
        else:
            start = int(start_text)
            if start >= size:
                raise _UnsatisfiableRange(size)
            end = size if not end_text else min(size, int(end_text) + 1)
            if end <= start:
                raise _MalformedRange("Range start must be before range end")
        ranges.append((start, end))

    ranges.sort()
    merged: list[tuple[int, int]] = []
    for start, end in ranges:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def _set_header(headers: dict[str, str], name: str, value: str) -> None:
    for existing in list(headers):
        if existing.lower() == name.lower():
            del headers[existing]
    headers[name] = value


def _set_object_headers(headers: dict[str, str], metadata) -> None:
    if metadata.etag:
        _set_header(headers, "ETag", metadata.etag)
    if metadata.last_modified:
        _set_header(
            headers,
            "Last-Modified",
            format_datetime(metadata.last_modified, usegmt=True),
        )


def _content_disposition(
    filename: str,
    disposition_type: str,
) -> str:
    # Historical database values are treated as untrusted header input.
    safe_name = filename.replace("\r", "").replace("\n", "")
    safe_name = safe_name.replace("\\", "/").rsplit("/", 1)[-1] or "download"
    encoded = quote(safe_name, safe="")
    if encoded != safe_name:
        return f"{disposition_type}; filename*=utf-8''{encoded}"
    return f'{disposition_type}; filename="{safe_name}"'


def _iter_stream(stream: StorageReadStream):
    try:
        while True:
            chunk = stream.read(_CHUNK_SIZE)
            if not chunk:
                break
            yield chunk
    finally:
        stream.close()


def _iter_multipart(
    storage: StorageService,
    area: StorageArea,
    key: str,
    ranges: list[tuple[int, int]],
    boundary: str,
    media_type: str,
    size: int,
):
    for start, end in ranges:
        yield (
            f"--{boundary}\n"
            f"Content-Type: {media_type}\n"
            f"Content-Range: bytes {start}-{end - 1}/{size}\n"
            "\n"
        ).encode("latin-1")
        stream = storage.open_read(area, key, offset=start, length=end - start)
        yield from _iter_stream(stream)
        yield b"\n"
    yield f"\n--{boundary}--\n".encode("latin-1")


def storage_response(
    request: Request,
    storage: StorageService,
    area: StorageArea,
    key: str,
    *,
    media_type: str,
    filename: str | None = None,
    headers: dict[str, str] | None = None,
    content_disposition_type: str = "inline",
) -> Response:
    """Build an HTTP response while keeping HTTP concerns outside Storage."""
    metadata = storage.head(area, key)
    response_headers = dict(headers or {})
    _set_object_headers(response_headers, metadata)
    _set_header(response_headers, "Accept-Ranges", "bytes")
    if filename is not None:
        _set_header(
            response_headers,
            "Content-Disposition",
            _content_disposition(filename, content_disposition_type),
        )

    try:
        ranges = _parse_ranges(request.headers.get("range"), metadata.size)
    except _MalformedRange as exc:
        return PlainTextResponse(str(exc), status_code=400, headers=response_headers)
    except _UnsatisfiableRange as exc:
        _set_header(response_headers, "Content-Range", f"*/{exc.size}")
        return PlainTextResponse(status_code=416, headers=response_headers)

    if_range = request.headers.get("if-range")
    if if_range:
        last_modified = (
            format_datetime(metadata.last_modified, usegmt=True)
            if metadata.last_modified
            else None
        )
        if if_range not in {metadata.etag, last_modified}:
            ranges = None

    if ranges is None:
        status_code = 200
        _set_header(response_headers, "Content-Length", str(metadata.size))
        response_media_type = media_type
        stream_ranges = None
    elif len(ranges) == 1:
        start, end = ranges[0]
        status_code = 206
        _set_header(response_headers, "Content-Range", f"bytes {start}-{end - 1}/{metadata.size}")
        _set_header(response_headers, "Content-Length", str(end - start))
        response_media_type = media_type
        stream_ranges = ranges
    else:
        boundary = token_hex(13)
        status_code = 206
        response_media_type = f"multipart/byteranges; boundary={boundary}"
        _set_header(
            response_headers,
            "Content-Range",
            f"multipart/byteranges; boundary={boundary}",
        )
        multipart_length = sum(
            len(
                (
                    f"--{boundary}\n"
                    f"Content-Type: {media_type}\n"
                    f"Content-Range: bytes {start}-{end - 1}/{metadata.size}\n"
                    "\n"
                ).encode("latin-1")
            )
            + (end - start)
            + 1
            for start, end in ranges
        ) + len(f"\n--{boundary}--\n".encode("latin-1"))
        _set_header(response_headers, "Content-Length", str(multipart_length))
        stream_ranges = (ranges, boundary)

    if request.method.upper() == "HEAD":
        return Response(
            status_code=status_code,
            headers=response_headers,
            media_type=response_media_type,
        )

    if stream_ranges is None:
        stream = storage.open_read(area, key)
        body = _iter_stream(stream)
    elif len(ranges) == 1:
        start, end = ranges[0]
        stream = storage.open_read(area, key, offset=start, length=end - start)
        body = _iter_stream(stream)
    else:
        range_list, boundary = stream_ranges
        body = _iter_multipart(
            storage,
            area,
            key,
            range_list,
            boundary,
            media_type,
            metadata.size,
        )
    return StreamingResponse(
        body,
        status_code=status_code,
        headers=response_headers,
        media_type=response_media_type,
    )
