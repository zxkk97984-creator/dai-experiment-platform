# -*- coding: utf-8 -*-
"""Demo 数据所有权登记表（评审 3）：--reset-demo 的唯一删除依据。

设计：
- 辅助表 demo_seed_marks（Seed 首次运行时 CREATE TABLE IF NOT EXISTS 幂等创建，
  不引入 Alembic 迁移、不属于业务模型）；
- Seed 每创建/接管一行业务数据，即登记一条 mark（mark_key=table_name:row_id）；
- --reset-demo 只删除已登记的行，未登记行（即使用户手动给 Demo 题目提交过）
  绝不删除；
- 登记表本身在 reset 最后清空。
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

MARKS_TABLE = "demo_seed_marks"

# 方言无关的建表语句（SQLite / MySQL 均支持）
_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS demo_seed_marks (
    mark_key VARCHAR(200) PRIMARY KEY,
    table_name VARCHAR(100) NOT NULL,
    row_id BIGINT NOT NULL,
    created_at DATETIME NOT NULL
)
"""


def _dialect(db: Session) -> str:
    return db.get_bind().dialect.name


def ensure_marks_table(db: Session) -> None:
    """幂等创建所有权登记表（不触发业务迁移）。"""
    db.execute(text(_CREATE_SQL))
    db.commit()


def mark(db: Session, table_name: str, row_id: int) -> None:
    """登记一行业务数据为 Demo 所有（幂等 upsert）。"""
    key = f"{table_name}:{row_id}"
    now = datetime.now(timezone.utc)
    dialect = _dialect(db)
    if dialect == "sqlite":
        sql = (
            f"INSERT OR IGNORE INTO {MARKS_TABLE} (mark_key, table_name, row_id, created_at)"
            " VALUES (:key, :t, :rid, :now)"
        )
    else:  # mysql / mariadb
        sql = (
            f"INSERT INTO {MARKS_TABLE} (mark_key, table_name, row_id, created_at)"
            " VALUES (:key, :t, :rid, :now)"
            " ON DUPLICATE KEY UPDATE created_at = VALUES(created_at)"
        )
    db.execute(text(sql), {"key": key, "t": table_name, "rid": row_id, "now": now})


def marked_ids(db: Session, table_name: str) -> list[int]:
    rows = db.execute(
        text(f"SELECT row_id FROM {MARKS_TABLE} WHERE table_name = :t"),
        {"t": table_name},
    ).all()
    return [int(r[0]) for r in rows]


def all_marks(db: Session) -> dict[str, list[int]]:
    """返回 {table_name: [row_id, ...]}。"""
    rows = db.execute(
        text(f"SELECT table_name, row_id FROM {MARKS_TABLE}")
    ).all()
    result: dict[str, list[int]] = {}
    for table, row_id in rows:
        result.setdefault(table, []).append(int(row_id))
    return result


def clear_marks(db: Session) -> None:
    db.execute(text(f"DELETE FROM {MARKS_TABLE}"))
