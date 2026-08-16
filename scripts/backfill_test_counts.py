"""回填 submissions / exam_answers 的 tests_passed 与 tests_total。

数据来源优先级：
1. result_details.groups[*].counts（active/shadow 测试组）
2. legacy stdout 中的 DAI_RESULT_JSON=
3. 无法解析则保持 NULL

用法：
    cd backend
    .venv/bin/python ../scripts/backfill_test_counts.py --batch-size 500
    .venv/bin/python ../scripts/backfill_test_counts.py --dry-run
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(ROOT))

from sqlalchemy import select

from app.database import SessionLocal
from app.models import ExamAnswer, Submission


def counts_from_groups(details) -> tuple[int, int] | None:
    if not isinstance(details, dict):
        return None
    groups = details.get("groups")
    if not isinstance(groups, list):
        return None
    passed = 0
    total = 0
    for group in groups:
        counts = group.get("counts") if isinstance(group, dict) else None
        if not isinstance(counts, dict):
            continue
        passed += int(counts.get("passed", 0) or 0)
        total += sum(int(counts.get(key, 0) or 0) for key in ("passed", "failed", "errors", "skipped"))
    return (passed, total) if total > 0 else None


def counts_from_stdout(stdout: str | None) -> tuple[int, int] | None:
    if not stdout:
        return None
    match = re.search(r"DAI_RESULT_JSON=(\{.*?\})", stdout)
    if not match:
        return None
    try:
        data = json.loads(match.group(1))
    except Exception:
        return None
    keys = ("passed", "failed", "errors", "skipped")
    if not all(isinstance(data.get(key), int) for key in keys):
        return None
    total = sum(data[key] for key in keys)
    return (data["passed"], total) if total > 0 else None


def update_submissions(dry_run: bool, batch_size: int) -> int:
    updated = 0
    db = SessionLocal()
    try:
        while True:
            rows = list(
                db.scalars(
                    select(Submission)
                    .where(
                        Submission.grading_status == "completed",
                        Submission.tests_total.is_(None),
                    )
                    .limit(batch_size)
                ).all()
            )
            if not rows:
                break
            batch_updated = 0
            for row in rows:
                parsed = counts_from_groups(row.result_details) or counts_from_stdout(row.stdout)
                if parsed is None:
                    continue
                row.tests_passed, row.tests_total = parsed
                batch_updated += 1
            updated += batch_updated
            if not dry_run:
                db.commit()
                print(f"已回填 {batch_updated} 条作业提交，累计 {updated}")
            else:
                print(f"[dry-run] 本批可回填 {batch_updated} 条作业提交")
                break
    finally:
        db.close()
    return updated


def update_exam_answers(dry_run: bool, batch_size: int) -> int:
    updated = 0
    db = SessionLocal()
    try:
        while True:
            rows = list(
                db.scalars(
                    select(ExamAnswer)
                    .where(
                        ExamAnswer.grading_status == "completed",
                        ExamAnswer.tests_total.is_(None),
                    )
                    .limit(batch_size)
                ).all()
            )
            if not rows:
                break
            batch_updated = 0
            for row in rows:
                parsed = counts_from_groups(row.result_details)
                if parsed is None:
                    continue
                row.tests_passed, row.tests_total = parsed
                batch_updated += 1
            updated += batch_updated
            if not dry_run:
                db.commit()
                print(f"已回填 {batch_updated} 条考试答案，累计 {updated}")
            else:
                print(f"[dry-run] 本批可回填 {batch_updated} 条考试答案")
                break
    finally:
        db.close()
    return updated


def main() -> int:
    parser = argparse.ArgumentParser(description="回填测试通过数")
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    try:
        submissions_updated = update_submissions(args.dry_run, args.batch_size)
        answers_updated = update_exam_answers(args.dry_run, args.batch_size)
    except Exception as exc:
        print(f"回填失败：{exc}")
        print("请先执行 alembic upgrade head 并确认数据库迁移已应用。")
        return 2
    if args.dry_run:
        print("dry-run 完成，未写库")
    else:
        print(f"完成：作业提交 {submissions_updated} 条，考试答案 {answers_updated} 条")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
