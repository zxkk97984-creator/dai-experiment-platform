"""第五轮——AI 队列恢复：先 commit 再 rpush 防止竞态"""
import json
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch


def make_grade(**kw):
    """构造 mock CodeGrade"""
    g = MagicMock()
    g.id = kw.get("id", 1)
    g.status = kw.get("status", "running")
    g.started_at = kw.get("started_at", datetime.now(timezone.utc) - timedelta(minutes=20))
    g.created_at = kw.get("created_at", datetime.now(timezone.utc) - timedelta(minutes=5))
    g.queued_at = kw.get("queued_at", datetime.now(timezone.utc) - timedelta(minutes=10))
    g.attempt_count = kw.get("attempt_count", 1)
    return g


class TestStaleRecoveryCommitOrder:
    """验证 recover_stale_ai_grades 先 commit 再 rpush，消费者不会先收到消息却 claim 失败"""

    def test_running_recovery_commits_before_rpush(self):
        """running→queued：commit 必须在 rpush 之前"""
        from app.services.ai_grading_queue import recover_stale_ai_grades

        db = MagicMock()
        redis_client = MagicMock()

        stale = make_grade(id=1, status="running",
                          started_at=datetime.now(timezone.utc) - timedelta(minutes=20))
        db.scalars.return_value.all.return_value = [stale]

        call_order = []

        def track_execute(*args, **kwargs):
            call_order.append("db_execute")
            return MagicMock(rowcount=1)

        def track_commit():
            call_order.append("db_commit")

        def track_rpush(*args, **kwargs):
            call_order.append("redis_rpush")

        db.execute = track_execute
        db.commit = track_commit
        redis_client.rpush = track_rpush

        recover_stale_ai_grades(db, redis_client)

        # 验证顺序：execute → commit → rpush
        assert "db_execute" in call_order
        assert "db_commit" in call_order
        assert "redis_rpush" in call_order
        db_exec_idx = call_order.index("db_execute")
        db_commit_idx = call_order.index("db_commit")
        redis_idx = call_order.index("redis_rpush")
        assert db_commit_idx < redis_idx, f"commit({db_commit_idx}) 必须在 rpush({redis_idx}) 之前，顺序: {call_order}"

    def test_pending_recovery_commits_before_rpush(self):
        """pending→queued：commit 必须在 rpush 之前"""
        from app.services.ai_grading_queue import recover_stale_ai_grades

        db = MagicMock()
        redis_client = MagicMock()

        stale = make_grade(id=2, status="pending",
                          created_at=datetime.now(timezone.utc) - timedelta(minutes=5))
        db.scalars.return_value.all.return_value = [stale]

        call_order = []

        def track_execute(*args, **kwargs):
            call_order.append("db_execute")
            return MagicMock(rowcount=1)

        def track_commit():
            call_order.append("db_commit")

        def track_rpush(*args, **kwargs):
            call_order.append("redis_rpush")

        db.execute = track_execute
        db.commit = track_commit
        redis_client.rpush = track_rpush

        recover_stale_ai_grades(db, redis_client)

        db_exec_idx = call_order.index("db_execute")
        db_commit_idx = call_order.index("db_commit")
        redis_idx = call_order.index("redis_rpush")
        assert db_commit_idx < redis_idx, f"pending: commit({db_commit_idx}) 必须在 rpush({redis_idx}) 之前"


class TestRedisFailure:
    """Redis 推送失败后任务不丢失（DB 已 queued，等下次恢复）"""

    def test_enqueue_redis_failure_leaves_queued(self):
        """Redis 推送失败→DB 保持 queued，恢复重推"""
        from app.services.ai_grading_queue import enqueue_ai_grade

        db = MagicMock()
        db.execute.return_value.rowcount = 1
        redis_client = MagicMock()
        redis_client.rpush.side_effect = ConnectionError("Redis 不可用")

        result = enqueue_ai_grade(db, redis_client, 1)
        # 即使 Redis 推送失败，入队仍然返回 True（DB 已正确更新为 queued）
        assert result is True
        # commit 被调用（DB 状态已持久化）
        db.commit.assert_called()

    def test_recovery_repushed_after_redis_failure(self):
        """queued 超时→恢复重推（Redis 消息丢失场景）"""
        from app.services.ai_grading_queue import recover_stale_ai_grades

        db = MagicMock()
        redis_client = MagicMock()

        stale = make_grade(id=3, status="queued",
                          queued_at=datetime.now(timezone.utc) - timedelta(minutes=10))
        db.scalars.return_value.all.return_value = [stale]

        db.execute.return_value.rowcount = 1
        recover_stale_ai_grades(db, redis_client)

        # 应该重新推送 Redis
        redis_client.rpush.assert_called()


class TestEnqueueMessageFormat:
    """入队消息格式验证"""

    def test_message_contains_type_and_id(self):
        """消息含 type=ai_grade 和 id"""
        from app.services.ai_grading_queue import enqueue_ai_grade

        db = MagicMock()
        db.execute.return_value.rowcount = 1
        redis_client = MagicMock()

        enqueue_ai_grade(db, redis_client, 42)

        # 验证 rpush 参数
        call_args = redis_client.rpush.call_args
        assert call_args is not None
        msg = json.loads(call_args[0][1])
        assert msg["type"] == "ai_grade"
        assert msg["id"] == 42
        assert "attempt" in msg
