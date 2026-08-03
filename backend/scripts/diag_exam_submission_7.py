"""只读诊断 ExamSubmission #7——不打印 hidden_tests 内容、学生代码、密钥。

只输出状态/配置完整性/计数/脱敏原因；不做任何写操作。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select
from app.database import SessionLocal
from app.models import (
    CodeGrade, ExamAnswer, ExamGrade, ExamQuestion, ExamSubmission, QuestionRubric,
)

SUB_ID = int(sys.argv[1]) if len(sys.argv) > 1 else 7


def safe(v, limit=200):
    if v is None:
        return None
    s = str(v)
    return s[:limit]


def main():
    with SessionLocal() as db:
        sub = db.get(ExamSubmission, SUB_ID)
        if not sub:
            print(f"ExamSubmission #{SUB_ID} 不存在")
            return
        print("=== 父记录 ===")
        print(f"  id={sub.id} exam_id={sub.exam_id} student_id={sub.student_id}")
        print(f"  status={sub.status} score={sub.score}")
        print(f"  started_at={sub.started_at} expires_at={sub.expires_at}")
        print(f"  submitted_at={sub.submitted_at} graded_at={sub.graded_at}")
        print(f"  review_reason={safe(sub.review_reason)} review_required_at={sub.review_required_at}")

        print("=== ExamAnswer（脱敏，不含代码内容） ===")
        answers = db.scalars(select(ExamAnswer).where(ExamAnswer.submission_id == SUB_ID)).all()
        for a in answers:
            has_code = bool(a.code_answer)
            print(f"  ans_id={a.id} qid={a.question_id} status={a.grading_status} "
                  f"score={a.score} attempt={a.attempt_count} has_code={has_code} "
                  f"queued_at={a.queued_at} started_at={a.started_at} finished_at={a.finished_at}")
            print(f"    last_error={safe(a.last_error, 120)} system_error={safe(a.system_error, 120)}")

        print("=== ExamQuestion 配置完整性（不含 hidden_tests 内容） ===")
        qids = sorted({a.question_id for a in answers})
        for qid in qids:
            q = db.get(ExamQuestion, qid)
            if not q:
                print(f"  qid={qid} 不存在")
                continue
            ht = bool(q.hidden_tests and q.hidden_tests.strip())
            tg = bool(q.test_groups)
            print(f"  qid={q.id} type={q.question_type} mode={q.grading_mode} points={q.points} "
                  f"hidden_tests_present={ht} test_groups_present={tg}")

        print("=== locked Rubric ===")
        for qid in qids:
            locked = db.scalars(
                select(QuestionRubric).where(
                    QuestionRubric.exam_question_id == qid,
                    QuestionRubric.status == "locked",
                ).order_by(QuestionRubric.version.desc())
            ).all()
            print(f"  qid={qid}: locked_rubrics={[(r.id, r.version, r.model_name) for r in locked]}")

        print("=== CodeGrade（考试相关） ===")
        ans_ids = [a.id for a in answers]
        if ans_ids:
            cgs = db.scalars(
                select(CodeGrade).where(CodeGrade.exam_answer_id.in_(ans_ids))
            ).all()
            for cg in cgs:
                print(f"  cg_id={cg.id} exam_answer_id={cg.exam_answer_id} mode={cg.mode} "
                      f"status={cg.status} needs_review={cg.needs_teacher_review} "
                      f"attempt={cg.attempt_count} f={cg.functional_score} r={cg.robustness_score}")
                print(f"    review_reason={safe(cg.review_reason, 120)} last_error={safe(cg.last_error, 120)}")
        else:
            print("  无")

        print("=== ExamGrade ===")
        grades = db.scalars(select(ExamGrade).where(
            ExamGrade.exam_id == sub.exam_id,
            ExamGrade.student_id == sub.student_id,
        )).all()
        print(f"  count={len(grades)}", [g.id for g in grades])

        print("=== 结论 ===")
        blocking = [a for a in answers if a.grading_status == "system_error"]
        if blocking:
            print(f"  存在 {len(blocking)} 个 system_error 答案 → 父级应转入 review_required 终态")
        elif sub.status == "grading":
            print("  无 system_error 但父仍在 grading → 需进一步检查 pending/running 答案")
        else:
            print(f"  父状态={sub.status}，无需处理")


if __name__ == "__main__":
    main()
