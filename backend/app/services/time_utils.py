"""UTC 时间规范化——项目中所有时间比较的唯一入口。

规则：
  - 无时区 datetime 视为 UTC（MySQL 默认行为）
  - 有时区 datetime 转换为 UTC 后进行比较
  - 边界约定：now < start_at 不可开始，now >= end_at/expires_at 不可答题或交卷
"""

from datetime import datetime, timezone


def as_utc(value: datetime | None) -> datetime | None:
    """规范化 datetime 为 UTC-aware。

    None → None
    naive datetime → 视为 UTC 并附加时区
    aware datetime → 转换为 UTC
    """
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def utc_now() -> datetime:
    """当前 UTC 时间"""
    return datetime.now(timezone.utc)
