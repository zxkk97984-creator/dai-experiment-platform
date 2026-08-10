"""E2E 状态重置——清除 E2E 测试数据的提交/评分状态，使流程测试可重复运行。

e2e 流程（考试交卷、实验提交评分）会写入数据库；同一数据重复运行会因
状态变化（已交卷/已评分）产生假失败。运行 e2e 前执行本脚本可恢复初始状态。
用法：python scripts/reset_e2e_state.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(ROOT))

from app.database import SessionLocal
from app.models import (
    Exam, ExamSubmission, ExamAnswer,
    ExperimentModule, ExperimentSubmission, ExperimentRecord,
)

db = SessionLocal()

try:
    # ── 1. 考试提交（答案逐行删除，避免外键残留） ──
    exam = db.query(Exam).filter_by(title="E2E 测试考试").first()
    if exam:
        submissions = db.query(ExamSubmission).filter_by(exam_id=exam.id).all()
        for sub in submissions:
            db.query(ExamAnswer).filter_by(submission_id=sub.id).delete()
        db.query(ExamSubmission).filter_by(exam_id=exam.id).delete()
        print(f"  [清理] 考试提交 {len(submissions)} 条 (exam_id={exam.id})")
    else:
        print("  [跳过] 未找到 E2E 测试考试")

    # ── 2. 实验提交 + 记录状态复位 ──
    module = db.query(ExperimentModule).filter_by(name="E2E 测试实验").first()
    if module:
        records = db.query(ExperimentRecord).filter_by(module_id=module.id).all()
        for record in records:
            db.query(ExperimentSubmission).filter_by(record_id=record.id).delete()
            record.status = "started"
        print(f"  [清理] 实验提交已删除，记录复位 started ({len(records)} 条)")
    else:
        print("  [跳过] 未找到 E2E 测试实验模块")

    db.commit()
    print("\nE2E 状态已重置，可以运行 e2e 流程测试。")

except Exception as e:
    db.rollback()
    print(f"失败: {e}")
    raise
finally:
    db.close()
