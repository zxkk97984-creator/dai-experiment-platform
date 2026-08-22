"""Phase 4 scheduler regressions: synchronous maintenance work stays off-loop."""

import asyncio


def test_sync_scheduler_work_is_delegated_to_thread_runner(monkeypatch):
    from app import main

    calls = []

    async def fake_to_thread(func, *args, **kwargs):
        calls.append((func, args, kwargs))
        return func(*args, **kwargs)

    monkeypatch.setattr(main.asyncio, "to_thread", fake_to_thread)

    def sync_work(value):
        return value

    assert asyncio.run(main._run_sync_in_thread(sync_work, "done")) == "done"
    assert calls == [(sync_work, ("done",), {})]
