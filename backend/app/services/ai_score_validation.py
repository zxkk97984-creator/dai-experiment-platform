"""AI 输出业务校验——版本、criterion、行号、防重复扣分"""
from __future__ import annotations

from typing import Any


def validate_ai_output(
    rubric: dict[str, Any],
    ai_result: dict[str, Any],
    code_lines: list[int],
) -> list[str]:
    """校验 AI 评分输出——返回错误列表，空列表表示通过"""
    errors = []

    # 0. rubric_version 匹配
    rubric_ver = rubric.get("rubric_version")
    ai_ver = ai_result.get("rubric_version")
    if rubric_ver is not None and ai_ver is not None and rubric_ver != ai_ver:
        errors.append(f"Rubric 版本不匹配：期望 {rubric_ver}，实际 {ai_ver}")

    # 提取 criterion 集合
    rubric_a_ids = {c["id"] for c in rubric.get("algorithm_criteria", [])}
    rubric_q_ids = {"Q1", "Q2", "Q3", "Q4"}

    max_code_line = max(code_lines) if code_lines else 0

    # 1. 校验 A 维度
    algorithm = ai_result.get("algorithm", {})
    a_items = algorithm.get("items", [])

    for item in a_items:
        cid = item.get("criterion_id")
        if cid not in rubric_a_ids:
            errors.append(f"未知的算法 criterion_id: {cid}")
            continue

        # 行号校验
        for line in item.get("code_lines", []):
            if line not in code_lines:
                errors.append(f"行号 {line} 不存在于学生代码中（criterion {cid}）")

        # 分数校验
        level = item.get("level")
        if level not in ("complete", "partial", "missing"):
            errors.append(f"非法的等级 {level}（criterion {cid}）")

    # 2. 校验 Q 维度
    code_quality = ai_result.get("code_quality", {})
    q_items = code_quality.get("items", [])

    for item in q_items:
        cid = item.get("criterion_id")
        if cid not in rubric_q_ids:
            errors.append(f"未知的代码质量 criterion_id: {cid}（只能是 Q1-Q4）")

        for line in item.get("code_lines", []):
            if line not in code_lines:
                errors.append(f"行号 {line} 不存在于学生代码中（criterion {cid}）")

    # 3. 跨维度重复扣分检测
    duplicates = detect_cross_dimension_duplicates(a_items, q_items)
    if duplicates:
        for dup in duplicates:
            errors.append(
                f"跨维度重复扣分：A 的 {dup['a_criterion']} 与 Q 的 {dup['q_criterion']} "
                f"使用相同 reason_code={dup['reason_code']} 且代码行重叠"
            )

    return errors


def detect_cross_dimension_duplicates(
    a_items: list[dict],
    q_items: list[dict],
) -> list[dict]:
    """检测 A 和 Q 之间的重复扣分"""
    duplicates = []

    for ai in a_items:
        a_reason = ai.get("reason_code")
        if not a_reason:
            continue
        a_lines = set(ai.get("code_lines", []))

        for qi in q_items:
            q_reason = qi.get("reason_code")
            if not q_reason:
                continue
            q_lines = set(qi.get("code_lines", []))

            if a_reason == q_reason and a_lines & q_lines:
                duplicates.append({
                    "a_criterion": ai.get("criterion_id"),
                    "q_criterion": qi.get("criterion_id"),
                    "reason_code": a_reason,
                    "overlapping_lines": sorted(a_lines & q_lines),
                })

    return duplicates
