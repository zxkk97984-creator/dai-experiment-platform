"""站内通知服务——从教师工作台待办与公告派生并持久化已读状态。"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Notification, NotificationRead, User
from app.schemas.notifications import NotificationListRead, NotificationRead as NotificationReadSchema

NOTIFICATION_LIMIT = 50


def _urgency_priority(urgency: str) -> str:
    return {"urgent": "urgent", "soon": "important"}.get(urgency, "normal")


def sync_teacher_notifications(db: Session, user: User, now: datetime | None = None) -> None:
    """物化当前可见通知；已消失的待办自动隐藏，已读回执保留。"""
    from app.services.dashboard_service import build_teacher_dashboard

    dashboard = build_teacher_dashboard(db, user, now=now)
    current: dict[str, dict] = {}

    for item in dashboard.work_items:
        key = f"work:{item.kind}:{item.id}"
        content = " · ".join(
            part for part in (item.course_title or "", item.detail or "") if part
        )
        current[key] = {
            "type": "work",
            "title": item.title[:200],
            "content": content[:500],
            "entity_kind": item.kind[:30],
            "entity_id": item.id,
            "route": item.route or "",
            "priority": _urgency_priority(item.urgency),
        }

    for notice in dashboard.announcements:
        key = f"announcement:{notice.id}"
        content = notice.content if notice.course_title is None else f"{notice.course_title} · {notice.content}"
        current[key] = {
            "type": "announcement",
            "title": notice.title[:200],
            "content": content[:500],
            "entity_kind": "announcement",
            "entity_id": notice.id,
            "route": "",
            "priority": notice.priority,
        }

    existing = db.scalars(
        select(Notification).where(Notification.recipient_id == user.id)
    ).all()
    by_key = {row.dedupe_key: row for row in existing}

    for key, payload in current.items():
        row = by_key.get(key)
        if row is None:
            db.add(Notification(
                recipient_id=user.id,
                dedupe_key=key,
                **payload,
            ))
            continue
        changed = False
        for field, value in payload.items():
            if getattr(row, field) != value:
                setattr(row, field, value)
                changed = True
        if not row.visible or changed:
            row.visible = True
    for key, row in by_key.items():
        if key not in current:
            row.visible = False

    try:
        db.commit()
    except IntegrityError:
        # 多实例同时派生时唯一键冲突视为已同步
        db.rollback()


def list_notifications(db: Session, user: User, unread_only: bool = False) -> NotificationListRead:
    sync_teacher_notifications(db, user)

    query = select(Notification).where(
        Notification.recipient_id == user.id,
        Notification.visible.is_(True),
    )
    if unread_only:
        read_ids = select(NotificationRead.notification_id).where(
            NotificationRead.user_id == user.id
        )
        query = query.where(~Notification.id.in_(read_ids))

    rows = db.scalars(
        query.order_by(Notification.created_at.desc(), Notification.id.desc()).limit(NOTIFICATION_LIMIT)
    ).all()
    read_ids = set(
        db.scalars(
            select(NotificationRead.notification_id).where(
                NotificationRead.user_id == user.id,
                NotificationRead.notification_id.in_([row.id for row in rows]),
            )
        ).all()
    )
    unread_count = (
        db.scalar(
            select(func.count(Notification.id)).where(
                Notification.recipient_id == user.id,
                Notification.visible.is_(True),
                ~Notification.id.in_(
                    select(NotificationRead.notification_id).where(
                        NotificationRead.user_id == user.id
                    )
                ),
            )
        )
        or 0
    )
    items = [
        NotificationReadSchema(
            id=row.id,
            type=row.type,
            title=row.title,
            content=row.content,
            entity_kind=row.entity_kind,
            entity_id=row.entity_id,
            route=row.route or None,
            priority=row.priority,
            created_at=row.created_at,
            is_read=row.id in read_ids,
        )
        for row in rows
    ]
    return NotificationListRead(items=items, unread_count=unread_count, total=len(items))


def mark_notification_read(db: Session, user: User, notification_id: int) -> bool:
    row = db.scalar(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.recipient_id == user.id,
            Notification.visible.is_(True),
        )
    )
    if row is None:
        return False
    existing = db.scalar(
        select(NotificationRead).where(
            NotificationRead.notification_id == notification_id,
            NotificationRead.user_id == user.id,
        )
    )
    if existing is None:
        db.add(NotificationRead(notification_id=notification_id, user_id=user.id))
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
    return True


def mark_all_notifications_read(db: Session, user: User) -> int:
    rows = db.scalars(
        select(Notification).where(
            Notification.recipient_id == user.id,
            Notification.visible.is_(True),
        )
    ).all()
    existing = set(
        db.scalars(
            select(NotificationRead.notification_id).where(
                NotificationRead.user_id == user.id,
            )
        ).all()
    )
    created = 0
    for row in rows:
        if row.id not in existing:
            db.add(NotificationRead(notification_id=row.id, user_id=user.id))
            created += 1
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
    return created
