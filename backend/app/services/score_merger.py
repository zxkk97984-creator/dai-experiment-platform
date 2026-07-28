"""分数合并——固定公式、上限、考试折算"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MergedScore:
    raw_total: float
    final_score_100: float
    scaled_score: float


def merge_scores(
    *,
    f: float,
    a: float,
    r: float,
    q: float,
    cap: float | None,
    exam_points: float | None,
) -> MergedScore:
    """后端固定公式合并 F60 + A20 + R10 + Q10"""
    raw = round(f + a + r + q, 4)
    final_100 = min(raw, cap) if cap is not None else raw
    final_100 = round(final_100, 4)
    scaled = round(final_100 / 100 * exam_points, 4) if exam_points is not None else final_100
    return MergedScore(raw_total=raw, final_score_100=final_100, scaled_score=scaled)
