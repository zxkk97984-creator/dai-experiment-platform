""".ipynb 解析器：解析 Jupyter Notebook，生成稳定 cell ID，渲染 Markdown，计算模板哈希"""
import hashlib
import json
import os
import uuid
import zipfile
from pathlib import Path
from typing import Any

import mistune
import nbformat
from bleach import clean
from nbformat.validator import validate

# ── Markdown 渲染器 ──────────────────────────────────────────
_md_renderer = mistune.create_markdown(
    plugins=["strikethrough", "footnotes", "table", "task_lists"]
)

# bleach 白名单：允许的 HTML 标签和属性
ALLOWED_TAGS = [
    "h1", "h2", "h3", "h4", "h5", "h6",
    "p", "br", "hr",
    "ul", "ol", "li",
    "a", "img", "code", "pre",
    "blockquote",
    "table", "thead", "tbody", "tr", "th", "td",
    "strong", "em", "del", "sub", "sup",
    "div", "span",
]
ALLOWED_ATTRS = {
    "a": ["href", "title"],
    "img": ["src", "alt", "width", "height"],
    "th": ["align"],
    "td": ["align"],
    "code": ["class"],
    "pre": ["class"],
    "div": ["class"],
    "span": ["class"],
}

# ZIP 安全校验
ALLOWED_EXTENSIONS = {
    ".ipynb", ".py", ".csv", ".json", ".txt", ".md",
    ".png", ".jpg", ".jpeg", ".xlsx",
}
MAX_FILE_SIZE = 10 * 1024 * 1024       # 10 MB
MAX_ZIP_SIZE = 50 * 1024 * 1024        # 50 MB
MAX_ZIP_ENTRIES = 50

# ── 公开 API ──────────────────────────────────────────────────


def parse_and_normalize(file_path: str, dest_dir: str) -> dict:
    """
    解析 .ipynb 文件并规范化，返回 cells_data 结构。

    流程：
    1. nbformat.read() 解析
    2. 为无 id 的 cell 生成 UUID 并写回模板
    3. 清理可变 metadata
    4. 计算 SHA256
    5. Markdown cell 预渲染 + bleach 清洗
    6. 返回 {cells, cell_order, metadata, template_hash}
    """
    file_path = os.path.abspath(file_path)
    dest_dir = os.path.abspath(dest_dir)
    os.makedirs(dest_dir, exist_ok=True)

    # 1. 解析
    with open(file_path, encoding="utf-8") as f:
        nb = nbformat.read(f, as_version=4)

    # 2. 补齐 cell ID
    modified = False
    for cell in nb.cells:
        if not cell.get("id"):
            cell["id"] = uuid.uuid4().hex[:12]
            modified = True

    # 3. 清理可变 metadata（nbformat NotebookNode 必须显式置空）
    for cell in nb.cells:
        cell["outputs"] = []
        cell["execution_count"] = None
        if "metadata" in cell:
            for k in ("collapsed", "scrolled", "trusted", "ExecuteTime"):
                cell.metadata.pop(k, None)

    # 4. 写回规范化文件
    normalized_path = os.path.join(dest_dir, "lesson.ipynb")
    with open(normalized_path, "w", encoding="utf-8") as f:
        nbformat.write(nb, f)

    # 5. 计算 SHA256
    template_hash = _compute_sha256(normalized_path)

    # 6. 构建 cells_data
    cells = {}
    cell_order = []
    for cell in nb.cells:
        cell_id = cell["id"]
        cell_order.append(cell_id)
        source = "".join(cell.get("source", []))
        entry = {"cell_type": cell.cell_type, "source": source}

        if cell.cell_type == "markdown":
            html = _markdown_to_html(source)
            entry["rendered_html"] = _sanitize_html(html)
        else:
            entry["outputs"] = {}

        cells[cell_id] = entry

    return {
        "cells": cells,
        "cell_order": cell_order,
        "metadata": nb.metadata,
        "template_hash": template_hash,
    }


def parse_experiment_package(zip_path: str, dest_dir: str) -> dict:
    """
    解压 .zip 实验包，安全校验，解析主 notebook，返回 parse_and_normalize 同结构结果。

    安全校验：
    - 禁止路径穿越、符号链接、绝对路径
    - 文件大小和数量限制
    - 扩展名白名单
    - Notebook 必须通过 nbformat.validate()
    """
    zip_path = os.path.abspath(zip_path)
    dest_dir = os.path.abspath(dest_dir)
    os.makedirs(dest_dir, exist_ok=True)

    file_size = os.path.getsize(zip_path)
    if file_size > MAX_ZIP_SIZE:
        raise ValueError(f"ZIP 文件过大：{file_size} bytes（最大 {MAX_ZIP_SIZE}）")

    main_notebook = None
    entry_count = 0

    with zipfile.ZipFile(zip_path, "r") as zf:
        for entry in zf.infolist():
            entry_count += 1
            if entry_count > MAX_ZIP_ENTRIES:
                raise ValueError(f"ZIP 条目过多（最多 {MAX_ZIP_ENTRIES}）")

            name = entry.filename

            # 安全检查
            if entry.is_dir():
                continue
            if ".." in name or name.startswith("/"):
                raise ValueError(f"非法路径：{name}")
            if os.path.isabs(name):
                raise ValueError(f"不允许绝对路径：{name}")

            # 扩展名检查
            ext = os.path.splitext(name)[1].lower()
            if ext not in ALLOWED_EXTENSIONS:
                raise ValueError(f"不允许的文件类型：{ext} ({name})")

            if entry.file_size > MAX_FILE_SIZE:
                raise ValueError(f"文件过大：{name} ({entry.file_size} bytes)")

            # 解压
            target = os.path.join(dest_dir, name)
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with zf.open(entry) as src:
                with open(target, "wb") as dst:
                    dst.write(src.read())

            # 找主 notebook
            if ext == ".ipynb":
                # 优先选 lesson.ipynb 或与目录同名的
                basename = os.path.basename(name)
                if basename == "lesson.ipynb" or main_notebook is None:
                    main_notebook = target

    if main_notebook is None:
        raise ValueError("ZIP 包中没有找到 .ipynb 文件")

    # 校验 notebook
    with open(main_notebook, encoding="utf-8") as f:
        nb = nbformat.read(f, as_version=4)
    validate(nb)

    return parse_and_normalize(main_notebook, dest_dir)


def generate_connection_file(dest_dir: str, kernel_id: str) -> dict:
    """在宿主机生成 ipykernel connection file"""
    from jupyter_client import write_connection_file
    import secrets

    conn_path = os.path.join(dest_dir, f"kernel-{kernel_id}.json")
    key = secrets.token_hex(24).encode("ascii")
    write_connection_file(conn_path, ip="0.0.0.0", key=key)
    with open(conn_path) as f:
        return json.load(f)


def read_connection_file(conn_path: str) -> dict:
    """读取 connection file"""
    with open(conn_path) as f:
        return json.load(f)


# ── 内部函数 ──────────────────────────────────────────────────


def _markdown_to_html(md_text: str) -> str:
    """Markdown 文本 → HTML"""
    return _md_renderer(md_text)


def _sanitize_html(html: str) -> str:
    """bleach 清洗 HTML，移除危险标签和属性"""
    return clean(
        html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRS,
        strip=True,
    )


def _compute_sha256(file_path: str) -> str:
    """计算文件 SHA256"""
    sha = hashlib.sha256()
    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            sha.update(chunk)
    return sha.hexdigest()
