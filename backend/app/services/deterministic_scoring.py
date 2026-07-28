"""确定性 F/R 评分——测试组执行与计分"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from app.schemas.ai_grading import TestGroup


class DeterministicSystemError(RuntimeError):
    """测试组系统错误——不是学生错误"""

    def __init__(self, message: str):
        super().__init__(message)


@dataclass(frozen=True)
class DeterministicGrade:
    functional_score: float
    robustness_score: float
    groups: list[dict] = field(default_factory=list)
    system_errors: list[str] = field(default_factory=list)


def calculate_group_score(max_score: float, counts: dict[str, int]) -> float:
    """根据测试通过比例计算分组分数"""
    denominator = counts["passed"] + counts["failed"] + counts["errors"]
    if denominator <= 0:
        raise DeterministicSystemError("测试组没有可计分用例")
    return round(max_score * counts["passed"] / denominator, 4)


def parse_result_json(output: str) -> dict | None:
    """从 pytest 输出中提取 DAI_RESULT_JSON={...}"""
    if not output:
        return None
    # 查找最后一行的 DAI_RESULT_JSON=
    match = re.search(r"DAI_RESULT_JSON=(\{.*?\})", output)
    if match:
        try:
            data = json.loads(match.group(1))
            # 校验计数为非负整数
            for key in ("passed", "failed", "errors", "skipped"):
                val = data.get(key, -1)
                if not isinstance(val, int) or val < 0:
                    return None
            return data
        except (json.JSONDecodeError, TypeError):
            return None
    return None


def calculate_deterministic_grade(
    groups: list[TestGroup],
    results: dict[str, dict[str, int]],
) -> DeterministicGrade:
    """按测试组汇总 F 和 R 分数"""
    f_total = 0.0
    r_total = 0.0
    group_details = []
    system_errors = []

    for group in groups:
        counts = results.get(group.id)
        if counts is None:
            system_errors.append(f"测试组 {group.id} 缺少结果")
            continue

        try:
            score = calculate_group_score(group.max_score, counts)
        except DeterministicSystemError as exc:
            system_errors.append(f"测试组 {group.id}: {exc}")
            continue

        group_details.append({
            "id": group.id,
            "name": group.name,
            "dimension": group.dimension,
            "max_score": group.max_score,
            "score": score,
            "counts": counts,
        })

        if group.dimension == "F":
            f_total += score
        elif group.dimension == "R":
            r_total += score

    return DeterministicGrade(
        functional_score=round(f_total, 4),
        robustness_score=round(r_total, 4),
        groups=group_details,
        system_errors=system_errors,
    )
