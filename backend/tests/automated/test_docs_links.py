"""TASK-027（F-38/F-39/R-03）：文档链接校验——README 与 docs 的相对链接必须落盘。

命令类说明（compose up/backup.sh 等）不在此处执行，其正确性由 CI docker-smoke
与 TASK-014/016 的演练记录守护。
"""
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
DOC_FILES = sorted(
    [REPO_ROOT / "README.md"]
    + [p for p in (REPO_ROOT / "docs").rglob("*.md")]
)

LINK_RE = re.compile(r"\]\((?!https?://|mailto:|#)([^)#]+)")


@pytest.mark.parametrize("doc", DOC_FILES, ids=lambda p: str(p.relative_to(REPO_ROOT)))
def test_relative_links_resolve(doc: Path):
    """每个相对链接指向真实存在的文件（锚点是否存在由人工对照）。"""
    text = doc.read_text(encoding="utf-8")
    broken = []
    for match in LINK_RE.finditer(text):
        raw = match.group(1).strip()
        target = (doc.parent / raw).resolve()
        if not target.exists():
            broken.append(raw)
    assert not broken, f"{doc.relative_to(REPO_ROOT)} 断链: {broken}"


@pytest.mark.parametrize("doc", DOC_FILES, ids=lambda p: str(p.relative_to(REPO_ROOT)))
def test_no_bare_test_baseline(doc: Path):
    """F-39：测试基线必须标注提交/日期，禁止易漂移的裸数字表述。

    允许的形态：数字 + （日期 + 提交 hash）或明确指向 CI 门禁。
    """
    text = doc.read_text(encoding="utf-8")
    for match in re.finditer(r"基线[：:]\s*\*\*[\d\s+项通过等中文，、]+\*\*", text):
        sentence = text[match.start(): match.start() + 160]
        assert ("20" in sentence and "`" in sentence) or "CI" in sentence, (
            f"{doc.relative_to(REPO_ROOT)} 存在未标注提交/日期的测试基线: {match.group(0)!r}"
        )
