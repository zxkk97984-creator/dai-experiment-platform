"""Regression coverage for grade ordering on MySQL and SQLite."""

from sqlalchemy.dialects import mysql, sqlite
from sqlalchemy.sql import select

from app.api.exams import _grade_sort_expressions
from app.models import ExamSubmission, User


def test_grade_sort_expressions_are_portable_without_nulls_last_syntax():
    expressions = _grade_sort_expressions()

    for dialect in (mysql.dialect(), sqlite.dialect()):
        for sort in ("score_desc", "score_asc", "time", "name"):
            statement = select(ExamSubmission.id).order_by(*expressions[sort])
            compiled = str(statement.compile(dialect=dialect)).upper()

            assert "NULLS LAST" not in compiled
            assert "CASE" in compiled


def test_grade_sort_aliases_keep_the_same_ordering_contract():
    expressions = _grade_sort_expressions()

    assert expressions["score-desc"] == expressions["score_desc"]
    assert expressions["score-asc"] == expressions["score_asc"]
    assert expressions["name"][-1].compare(User.id.asc())
