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
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.models import SchedulerLease

logger = logging.getLogger("dai.scheduler_lease")

# MySQL 并发首插可抛锁等待超时（1205）或死锁（1213）——语义上等价于
# 「被对方抢赢」，应回滚后走 CAS 重试而非向上抛错（多实例生产真实场景）。
_RETRYABLE_MYSQL_LOCK_CODES = (1205, 1213)


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

    # 2. 无行：首次插入。并发下三种可恢复竞争都回滚后走 CAS 重试：
    #    · IntegrityError：对方先插（PK 冲突）
    #    · MySQL 1205 锁等待超时 / 1213 死锁：插入意向锁与对方行锁互等
    for _attempt in range(3):
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
        except OperationalError as exc:
            orig_code = getattr(getattr(exc, "orig", None), "args", (None,))[0]
            if orig_code not in _RETRYABLE_MYSQL_LOCK_CODES:
                raise
            db.rollback()
            logger.warning("租约并发竞争（%s），重试 CAS: %s", orig_code, task_name)

        now = _db_now(db)
        lease_until = now + timedelta(seconds=ttl_seconds)
        if _try_cas_acquire(db, task_name, owner_id, lease_until, now):
            db.commit()
            return True
        db.rollback()
    return False
