"""输入硬上限测试：代码/隐藏测试/考试答案的分层字符与 UTF-8 字节上限。

超限必须在写库、入队或启动 Docker 之前被拒绝（422 / ValidationError），
且拒绝后不得产生任何 DB/队列副作用。
"""

import pytest
from pydantic import ValidationError

from app.schemas import (
    ExperimentCellExecuteRequest,
    ExamAnswerSaveItem,
    JudgeQuestionCreate,
    JudgeQuestionUpdate,
    SubmissionCreate,
)
from conftest import auth_header, create_user, login

MAX_CODE_CHARS = 50_000
MAX_CODE_BYTES = 64 * 1024
MAX_TEXT_ANSWER_CHARS = 20_000


def _multibyte_over_bytes(chars: int, unit: str = "界") -> str:
    # 3 字节/字符的 CJK 文本，字符数小于上限但字节数超限
    return unit * chars


# ── Schema 层：SubmissionCreate ───────────────────────────────


def test_submission_code_at_exact_char_limit_ok():
    SubmissionCreate(question_id=1, code="x" * MAX_CODE_CHARS)


def test_submission_code_over_char_limit_rejected():
    with pytest.raises(ValidationError):
        SubmissionCreate(question_id=1, code="x" * (MAX_CODE_CHARS + 1))


def test_submission_code_over_utf8_bytes_rejected():
    # 21,846 个 CJK 字符 = 65,538 字节 > 64 KiB，但字符数 < 50,000
    with pytest.raises(ValidationError):
        SubmissionCreate(question_id=1, code=_multibyte_over_bytes(21_846))


# ── Schema 层：JudgeQuestionCreate / Update ───────────────────


def test_judge_question_hidden_tests_over_limit_rejected():
    with pytest.raises(ValidationError):
        JudgeQuestionCreate(
            title="t",
            function_name="f",
            hidden_tests="x" * (MAX_CODE_CHARS + 1),
        )


def test_judge_question_starter_code_over_utf8_bytes_rejected():
    with pytest.raises(ValidationError):
        JudgeQuestionCreate(
            title="t",
            function_name="f",
            hidden_tests="ok",
            starter_code=_multibyte_over_bytes(21_846),
        )


def test_judge_question_update_code_fields_optional_and_bounded():
    JudgeQuestionUpdate(hidden_tests=None, starter_code=None)  # 可选字段缺省合法
    with pytest.raises(ValidationError):
        JudgeQuestionUpdate(hidden_tests="x" * (MAX_CODE_CHARS + 1))


# ── Schema 层：考试答案 ───────────────────────────────────────


def test_exam_code_answer_over_limit_rejected():
    with pytest.raises(ValidationError):
        ExamAnswerSaveItem(question_id=1, code_answer="x" * (MAX_CODE_CHARS + 1))


def test_exam_text_answer_at_exact_limit_ok():
    ExamAnswerSaveItem(question_id=1, text_answers={"a": "x" * MAX_TEXT_ANSWER_CHARS})


def test_exam_text_answer_over_char_limit_rejected():
    with pytest.raises(ValidationError):
        ExamAnswerSaveItem(
            question_id=1, text_answers={"a": "x" * (MAX_TEXT_ANSWER_CHARS + 1)}
        )


def test_exam_text_answer_over_utf8_bytes_rejected():
    with pytest.raises(ValidationError):
        ExamAnswerSaveItem(question_id=1, text_answers={"a": _multibyte_over_bytes(21_846)})


# ── Schema 层：实验 Cell 执行 ─────────────────────────────────


def test_experiment_cell_code_over_limit_rejected():
    with pytest.raises(ValidationError):
        ExperimentCellExecuteRequest(code="x" * (MAX_CODE_CHARS + 1))


# ── API 层：超限被拒绝且无 DB 副作用 ──────────────────────────


def test_oversized_submission_rejected_without_db_side_effects(
    client, db_session_factory
):
    create_user(db_session_factory, "student", "student")
    token, _ = login(client, "student")
    response = client.post(
        "/api/v1/judge/submissions",
        headers=auth_header(token),
        json={"question_id": 1, "code": "x" * (MAX_CODE_CHARS + 1)},
    )
    assert response.status_code == 422
    # 拒绝后无任何提交行写入
    from app.models import Submission

    with db_session_factory() as db:
        assert db.query(Submission).count() == 0


def test_oversized_multibyte_submission_rejected(
    client, db_session_factory
):
    create_user(db_session_factory, "student", "student")
    token, _ = login(client, "student")
    response = client.post(
        "/api/v1/judge/submissions",
        headers=auth_header(token),
        json={"question_id": 1, "code": _multibyte_over_bytes(21_846)},
    )
    assert response.status_code == 422
    from app.models import Submission

    with db_session_factory() as db:
        assert db.query(Submission).count() == 0
