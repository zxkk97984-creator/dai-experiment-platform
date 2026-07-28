"""Rubric 版本服务——生成、校验、锁定与发布门禁"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import QuestionRubric
from app.schemas.ai_grading import AIQuestionConfigUpdate, RubricDocument
from app.services.ai_client import AIServiceError, DeepSeekClient
from app.services.ai_prompts import build_rubric_messages

logger = logging.getLogger("dai.rubric")


def _canonical_json(obj: Any) -> str:
    """生成对象的 canonical JSON 表示（排序键，紧凑格式）"""
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _sha256(text: str) -> str:
    """SHA-256 十六进制摘要"""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_question_snapshot(
    title: str,
    description: str | None = None,
    function_name: str | None = None,
    teacher_constraints: dict | None = None,
    test_groups: list | None = None,
    reference_solution: str | None = None,
    is_exam: bool = False,
) -> dict:
    """从题目属性构建 canonical 输入快照"""
    # 保留测试组的所有字段（包括 tests）确保 source_hash 可复现
    groups_for_hash = [dict(g) for g in (test_groups or [])]

    return {
        "title": title,
        "description": description or "",
        "function_name": function_name or "",
        "is_exam": is_exam,
        "teacher_constraints": teacher_constraints or {},
        "test_groups": groups_for_hash,
        "reference_solution": reference_solution,
    }


def get_latest_locked_rubric(
    db: Session, *, kind: str, question_id: int
) -> QuestionRubric | None:
    """按版本倒序返回最新 locked Rubric"""
    col = _target_column(kind)
    return db.scalars(
        select(QuestionRubric)
        .where(col == question_id, QuestionRubric.status == "locked")
        .order_by(QuestionRubric.version.desc())
        .limit(1)
    ).first()


def generate_rubric(
    db: Session,
    client: DeepSeekClient,
    *,
    kind: str,
    question_id: int,
) -> QuestionRubric:
    """调用 AI 生成新 Rubric 并保存为 draft"""
    col = _target_column(kind)

    # 计算当前最高版本
    max_ver = db.scalar(
        select(QuestionRubric.version)
        .where(col == question_id)
        .order_by(QuestionRubric.version.desc())
        .limit(1)
    )
    next_version = (max_ver or 0) + 1

    # 这里需要实际题目数据——调用方负责传入
    # 简化接口：通过 question_id 和 snapshot 工作
    # generate_rubric 的调用方应提供完整快照
    raise NotImplementedError("请使用 generate_rubric_from_snapshot")


def generate_rubric_from_snapshot(
    db: Session,
    client: DeepSeekClient,
    *,
    kind: str,
    question_id: int,
    snapshot: dict,
) -> QuestionRubric:
    """从快照生成 Rubric 并保存为 draft"""
    col = _target_column(kind)

    # 计算版本号
    max_ver = db.scalar(
        select(QuestionRubric.version)
        .where(col == question_id)
        .order_by(QuestionRubric.version.desc())
        .limit(1)
    )
    next_version = (max_ver or 0) + 1

    # 计算 source hash（不含 reference_solution 以避免暴露给 hash 碰撞分析）
    hash_snapshot = {k: v for k, v in snapshot.items() if k != "reference_solution"}
    source_hash = _sha256(_canonical_json(hash_snapshot))

    # 调用 AI
    messages = build_rubric_messages(snapshot)
    raw_response = client.chat_json(messages)
    raw_json_str = json.dumps(raw_response, ensure_ascii=False)

    # Pydantic 校验
    rubric_doc = RubricDocument.model_validate(raw_response)

    rubric = QuestionRubric(
        **{_kind_to_column(kind): question_id},
        version=next_version,
        status="draft",
        source_hash=source_hash,
        source_snapshot=snapshot,
        rubric_json=rubric_doc.model_dump(),
        model_name=client._settings.ai_model,
        raw_response=raw_json_str,
        locked_at=None,
    )
    db.add(rubric)
    db.flush()

    logger.info(
        "rubric_generated",
        extra={
            "kind": kind,
            "question_id": question_id,
            "version": next_version,
            "source_hash": source_hash,
        },
    )
    return rubric


def update_draft_rubric(
    db: Session, rubric_id: int, document: RubricDocument
) -> QuestionRubric:
    """更新 draft Rubric——locked Rubric 不可修改"""
    rubric = db.get(QuestionRubric, rubric_id)
    if rubric is None:
        raise ValueError(f"Rubric {rubric_id} 不存在")
    if rubric.status != "draft":
        raise ValueError(f"只有 draft 状态可修改，当前状态为 {rubric.status}")

    rubric.rubric_json = document.model_dump()
    db.flush()
    return rubric


def lock_rubric(db: Session, rubric_id: int) -> QuestionRubric:
    """锁定目标 Rubric，同题旧 locked 版本变为 superseded"""
    rubric = db.get(QuestionRubric, rubric_id)
    if rubric is None:
        raise ValueError(f"Rubric {rubric_id} 不存在")
    if rubric.status == "locked":
        raise ValueError("Rubric 已锁定")

    # 查询同题旧 locked 版本
    target_kind = _detect_kind(rubric)
    col = _target_column(target_kind)
    target_id = getattr(rubric, _kind_to_column(target_kind))

    old_locked = db.scalars(
        select(QuestionRubric)
        .where(
            col == target_id,
            QuestionRubric.status == "locked",
            QuestionRubric.id != rubric_id,
        )
    ).all()

    for old in old_locked:
        old.status = "superseded"

    rubric.status = "locked"
    rubric.locked_at = datetime.now(timezone.utc)
    db.flush()

    logger.info(
        "rubric_locked",
        extra={
            "rubric_id": rubric_id,
            "kind": target_kind,
            "question_id": target_id,
            "version": rubric.version,
        },
    )
    return rubric


def ensure_locked_rubrics_for_publish(
    db: Session,
    client: DeepSeekClient,
    questions: Sequence[dict],
) -> None:
    """发布前确保所有影子/正式题目有锁定 Rubric

    questions: 每个元素是包含 id、grading_mode、title 等字段的 dict
    对 legacy 题目跳过；对已有锁定 Rubric 的复用；缺失的生成并锁定。
    """
    for q in questions:
        if q.get("grading_mode") == "legacy":
            continue

        question_id = q["id"]
        # 判断是作业题还是考试题
        kind = _detect_kind_from_dict(q)

        existing = get_latest_locked_rubric(db, kind=kind, question_id=question_id)
        if existing is not None:
            # 检查 source hash 是否有变化——使用 build_question_snapshot
            snapshot = build_question_snapshot(
                title=q.get("title", ""),
                description=q.get("description"),
                function_name=q.get("function_name"),
                teacher_constraints=q.get("teacher_constraints"),
                test_groups=q.get("test_groups"),
                reference_solution=q.get("reference_solution"),
                is_exam=kind == "exam",
            )
            hash_snapshot = {k: v for k, v in snapshot.items() if k != "reference_solution"}
            current_hash = _sha256(_canonical_json(hash_snapshot))
            if current_hash == existing.source_hash:
                continue  # 复用已有锁定 Rubric

        # 生成并锁定
        snapshot = build_question_snapshot(
            title=q.get("title", ""),
            description=q.get("description"),
            function_name=q.get("function_name"),
            teacher_constraints=q.get("teacher_constraints"),
            test_groups=q.get("test_groups"),
            reference_solution=q.get("reference_solution"),
            is_exam=kind == "exam",
        )

        try:
            rubric = generate_rubric_from_snapshot(
                db, client, kind=kind, question_id=question_id, snapshot=snapshot
            )
            lock_rubric(db, rubric.id)
        except AIServiceError:
            db.rollback()
            raise
        except Exception:
            db.rollback()
            raise AIServiceError(
                "rubric_generation_failed",
                f"题目 {question_id} 的 Rubric 生成失败",
                retryable=True,
            )


# ── 内部辅助 ──


def _target_column(kind: str):
    """返回 QuestionRubric 的目标列"""
    if kind == "assignment":
        return QuestionRubric.judge_question_id
    if kind == "exam":
        return QuestionRubric.exam_question_id
    raise ValueError(f"未知 type: {kind}")


def _kind_to_column(kind: str) -> str:
    """kind 转为 ORM column 键名"""
    if kind == "assignment":
        return "judge_question_id"
    if kind == "exam":
        return "exam_question_id"
    raise ValueError(f"未知 kind: {kind}")


def _detect_kind(rubric: QuestionRubric) -> str:
    """从 Rubric 实例检测 kind"""
    if rubric.judge_question_id is not None:
        return "assignment"
    if rubric.exam_question_id is not None:
        return "exam"
    raise ValueError("Rubric 未关联任何题目")


def _detect_kind_from_dict(q: dict) -> str:
    """从题目 dict 检测 kind——通过是否有 exam_id 字段区分"""
    if "exam_id" in q:
        return "exam"
    return "assignment"
