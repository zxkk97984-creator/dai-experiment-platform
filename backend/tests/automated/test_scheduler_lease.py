"""SchedulerLease 租约——获取、未过期拒绝、过期接管、同 owner 续租、并发首插"""
import threading
from datetime import datetime, timedelta, timezone

from app.models import SchedulerLease
from app.services.scheduler_lease import try_acquire_lease


class TestLeaseBasics:
    def test_acquire_new_task(self, db_session_factory):
        with db_session_factory() as db:
            ok = try_acquire_lease(db, "exam-expiry", "api-1", ttl_seconds=90)
            assert ok is True

            row = db.get(SchedulerLease, "exam-expiry")
            assert row is not None
            assert row.owner_id == "api-1"
            assert row.lease_until > row.heartbeat_at

    def test_reject_active_lease_other_owner(self, db_session_factory):
        with db_session_factory() as db:
            assert try_acquire_lease(db, "exam-expiry", "api-1", ttl_seconds=90) is True

        with db_session_factory() as db:
            ok = try_acquire_lease(db, "exam-expiry", "api-2", ttl_seconds=90)
            assert ok is False, "未过期的他人租约应拒绝"

        with db_session_factory() as db:
            row = db.get(SchedulerLease, "exam-expiry")
            assert row.owner_id == "api-1", "owner 不应被改变"

    def test_renew_same_owner(self, db_session_factory):
        with db_session_factory() as db:
            assert try_acquire_lease(db, "exam-expiry", "api-1", ttl_seconds=90) is True

        with db_session_factory() as db:
            ok = try_acquire_lease(db, "exam-expiry", "api-1", ttl_seconds=90)
            assert ok is True, "同 owner 应可续租"

        with db_session_factory() as db:
            row = db.get(SchedulerLease, "exam-expiry")
            assert row.owner_id == "api-1"

    def test_takeover_expired_lease(self, db_session_factory):
        with db_session_factory() as db:
            assert try_acquire_lease(db, "exam-expiry", "api-1", ttl_seconds=90) is True
            row = db.get(SchedulerLease, "exam-expiry")
            row.lease_until = datetime.now(timezone.utc) - timedelta(seconds=10)
            db.commit()

        with db_session_factory() as db:
            ok = try_acquire_lease(db, "exam-expiry", "api-2", ttl_seconds=90)
            assert ok is True, "过期租约应可被接管"

        with db_session_factory() as db:
            from app.services.time_utils import as_utc
            row = db.get(SchedulerLease, "exam-expiry")
            assert row.owner_id == "api-2"
            assert as_utc(row.lease_until) > datetime.now(timezone.utc)


class TestLeaseSameHostMultiProcess:
    """P1: 同机多 API 进程 owner 唯一性——hostname 相同但 pid/实例不同视为不同 owner"""

    def test_same_host_different_pid_are_distinct_owners(self, db_session_factory):
        """模拟同机两个 API 进程（api:host:100 vs api:host:200）：第二个应被拒绝"""
        with db_session_factory() as db:
            assert try_acquire_lease(db, "exam-expiry", "api:host1:100", 90) is True

        with db_session_factory() as db:
            ok = try_acquire_lease(db, "exam-expiry", "api:host1:200", 90)
            assert ok is False, "同 host 不同 pid 是不同 owner，未过期应拒绝"

        with db_session_factory() as db:
            row = db.get(SchedulerLease, "exam-expiry")
            assert row.owner_id == "api:host1:100", "owner 不应被同 host 另一进程改变"


class TestLeaseConcurrency:
    def test_concurrent_first_insert_single_winner(self, db_session_factory):
        """两个实例并发首插：PK/IntegrityError 路径，只有一个成功"""
        results = []
        barrier = threading.Barrier(2, timeout=5)
        errors = []

        def do_acquire(instance):
            try:
                with db_session_factory() as db:
                    barrier.wait()
                    results.append((instance, try_acquire_lease(db, "exam-expiry", instance, 90)))
            except Exception as e:
                errors.append((instance, str(e)))

        t1 = threading.Thread(target=do_acquire, args=("api-1",))
        t2 = threading.Thread(target=do_acquire, args=("api-2",))
        t1.start(); t2.start()
        t1.join(timeout=10); t2.join(timeout=10)

        assert len(errors) == 0, f"并发获取出错: {errors}"
        winners = [i for i, ok in results if ok]
        assert len(winners) == 1, f"并发首插应只有一个成功: {results}"

        with db_session_factory() as db:
            row = db.get(SchedulerLease, "exam-expiry")
            assert row.owner_id == winners[0]

    def test_concurrent_takeover_single_winner(self, db_session_factory):
        """两个实例并发接管过期租约：只有一个成功"""
        with db_session_factory() as db:
            assert try_acquire_lease(db, "exam-expiry", "api-1", 90) is True
            row = db.get(SchedulerLease, "exam-expiry")
            row.lease_until = datetime.now(timezone.utc) - timedelta(seconds=10)
            db.commit()

        results = []
        barrier = threading.Barrier(2, timeout=5)
        errors = []

        def do_acquire(instance):
            try:
                with db_session_factory() as db:
                    barrier.wait()
                    results.append((instance, try_acquire_lease(db, "exam-expiry", instance, 90)))
            except Exception as e:
                errors.append((instance, str(e)))

        t1 = threading.Thread(target=do_acquire, args=("api-2",))
        t2 = threading.Thread(target=do_acquire, args=("api-3",))
        t1.start(); t2.start()
        t1.join(timeout=10); t2.join(timeout=10)

        assert len(errors) == 0, f"并发接管出错: {errors}"
        winners = [i for i, ok in results if ok]
        assert len(winners) == 1, f"过期接管应只有一个成功: {results}"

        with db_session_factory() as db:
            row = db.get(SchedulerLease, "exam-expiry")
            assert row.owner_id == winners[0]
