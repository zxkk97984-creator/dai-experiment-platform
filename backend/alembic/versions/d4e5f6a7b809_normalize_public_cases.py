"""规范化历史 public_cases：input → args。

Revision ID: d4e5f6a7b809
Revises: c3d4e5f6a708
Create Date: 2026-07-27
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision: str = "d4e5f6a7b809"
down_revision: Union[str, None] = "c3d4e5f6a708"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """将 exam_questions 和 judge_questions 中 public_cases 的 input 字段重命名为 args。

    此迁移在应用层完成 JSON 变换，在 Python 侧逐行处理以确保正确性。
    """
    import json

    conn = op.get_bind()

    # ── exam_questions.public_cases ───────────────────────────────
    rows = conn.execute(
        sa.text("SELECT id, public_cases FROM exam_questions WHERE public_cases IS NOT NULL")
    ).fetchall()

    for row_id, public_cases in rows:
        if public_cases is None:
            continue
        try:
            if isinstance(public_cases, str):
                cases = json.loads(public_cases)
            else:
                cases = public_cases
        except (json.JSONDecodeError, TypeError):
            continue

        changed = False
        normalized = []
        for case in (cases if isinstance(cases, list) else []):
            if isinstance(case, dict) and "input" in case and "args" not in case:
                case = {**case, "args": case.pop("input")}
                changed = True
            normalized.append(case)

        if changed:
            conn.execute(
                sa.text("UPDATE exam_questions SET public_cases = :cases WHERE id = :id"),
                {"cases": json.dumps(normalized), "id": row_id},
            )

    # ── judge_questions.public_cases ──────────────────────────────
    rows = conn.execute(
        sa.text("SELECT id, public_cases FROM judge_questions WHERE public_cases IS NOT NULL")
    ).fetchall()

    for row_id, public_cases in rows:
        if public_cases is None:
            continue
        try:
            if isinstance(public_cases, str):
                cases = json.loads(public_cases)
            else:
                cases = public_cases
        except (json.JSONDecodeError, TypeError):
            continue

        changed = False
        normalized = []
        for case in (cases if isinstance(cases, list) else []):
            if isinstance(case, dict) and "input" in case and "args" not in case:
                case = {**case, "args": case.pop("input")}
                changed = True
            normalized.append(case)

        if changed:
            conn.execute(
                sa.text("UPDATE judge_questions SET public_cases = :cases WHERE id = :id"),
                {"cases": json.dumps(normalized), "id": row_id},
            )


def downgrade() -> None:
    """反向操作：将 args 改回 input（不建议在生产环境执行）"""
    import json

    conn = op.get_bind()

    for table in ("exam_questions", "judge_questions"):
        rows = conn.execute(
            sa.text(f"SELECT id, public_cases FROM {table} WHERE public_cases IS NOT NULL")
        ).fetchall()

        for row_id, public_cases in rows:
            if public_cases is None:
                continue
            try:
                if isinstance(public_cases, str):
                    cases = json.loads(public_cases)
                else:
                    cases = public_cases
            except (json.JSONDecodeError, TypeError):
                continue

            changed = False
            normalized = []
            for case in (cases if isinstance(cases, list) else []):
                if isinstance(case, dict) and "args" in case and "input" not in case:
                    case = {**case, "input": case.pop("args")}
                    changed = True
                normalized.append(case)

            if changed:
                conn.execute(
                    sa.text(f"UPDATE {table} SET public_cases = :cases WHERE id = :id"),
                    {"cases": json.dumps(normalized), "id": row_id},
                )
