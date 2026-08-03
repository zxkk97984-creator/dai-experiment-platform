"""多实例任务租约——同一时刻只允许一个实例执行某类扫描/恢复任务。

原则：
- 使用数据库时间（跨实例时钟一致），不依赖各实例本地时钟
- 首次插入并发用 PK/IntegrityError 防重
- 只有无租约、租约过期或同 owner 续租时返回 True
- CAS 条件 UPDATE 防并发双抢（SQLite 无行锁也安全）
- 不持有长事务：调用方获取后立即做短扫描，TTL 大于正常扫描时长、崩溃后自动释放
"""
import logging

from sqlalchemy import func, insert, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import SchedulerLease

logger = logging.getLogger("dai.scheduler_lease")


def _db_now(db: Session):
    """数据库当前时间（项目约定 naive datetime 视为 UTC）"""
    value = db.scalar(select(func.now()))
    return value


def _try_cas_acquire(db: Session, task_name: str, owner_id: str,
                     lease_until, now) -> bool:
    """CAS 接管/续租：owner 相同或租约已过期才可更新，rowcount=1 才算成功"""
    result = db.execute(
        update(SchedulerLease)
        .execution_options(synchronize_session=False)
        .where(
            SchedulerLease.task_name == task_name,
            or_(
                SchedulerLease.owner_id == owner_id,
                SchedulerLease.lease_until < now,
            ),
        )
        .values(owner_id=owner_id, lease_until=lease_until, heartbeat_at=now)
    )
    return result.rowcount == 1


def try_acquire_lease(db: Session, task_name: str, owner_id: str, ttl_seconds: int) -> bool:
    """尝试获取/续租任务租约。成功返回 True（已 commit，租约有效期 ttl_seconds）。"""
    now = _db_now(db)
    from datetime import timedelta
    lease_until = now + timedelta(seconds=ttl_seconds)

    # 1. 已有行：CAS 接管/续租
    if _try_cas_acquire(db, task_name, owner_id, lease_until, now):
        db.commit()
        return True

    # 2. 无行：首次插入（并发下 PK 冲突由 IntegrityError 处理，重试一次 CAS）
    try:
        db.execute(
            insert(SchedulerLease).values(
                task_name=task_name, owner_id=owner_id,
                lease_until=lease_until, heartbeat_at=now,
            )
        )
        db.commit()
        return True
    except IntegrityError:
        db.rollback()
        now2 = _db_now(db)
        lease_until2 = now2 + timedelta(seconds=ttl_seconds)
        if _try_cas_acquire(db, task_name, owner_id, lease_until2, now2):
            db.commit()
            return True
        db.rollback()
        return False
