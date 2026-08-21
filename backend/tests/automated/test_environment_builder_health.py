"""Worker heartbeat and production orchestration contracts."""

from __future__ import annotations

from pathlib import Path
import re
from types import SimpleNamespace

import fakeredis

from app.services.environment_builder_health import (
    clear_heartbeat,
    publish_heartbeat,
    read_heartbeat,
)


def _settings(**overrides):
    values = {
        "env_builder_heartbeat_key": "environment:v2:builder:heartbeat",
        "env_builder_heartbeat_ttl_seconds": 30,
        "env_builder_heartbeat_interval_seconds": 10,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_heartbeat_has_ttl_and_does_not_expose_owner():
    redis_client = fakeredis.FakeRedis(decode_responses=True)
    settings = _settings()
    publish_heartbeat(redis_client, settings, owner_id="host:123")

    status = read_heartbeat(redis_client, settings)
    assert status["status"] == "healthy"
    assert status["ttl_seconds"] > 0
    assert "owner_id" not in status


def test_stale_or_foreign_heartbeat_cannot_be_claimed():
    redis_client = fakeredis.FakeRedis(decode_responses=True)
    settings = _settings()
    publish_heartbeat(redis_client, settings, owner_id="new-worker")
    assert clear_heartbeat(redis_client, settings, owner_id="old-worker") is False
    assert read_heartbeat(redis_client, settings)["status"] == "healthy"
    assert clear_heartbeat(redis_client, settings, owner_id="new-worker") is True
    assert read_heartbeat(redis_client, settings)["code"] == "BUILD_WORKER_NOT_READY"


def test_production_compose_gates_all_docker_workers_on_migration():
    compose = (Path(__file__).resolve().parents[2] / ".." / "docker-compose.prod.yml").read_text(
        encoding="utf-8"
    )
    service_starts = [match.start() for match in re.finditer(r"\n  [a-z0-9_-]+:\n", compose)]
    for service in ("api:", "worker:", "environment-builder:"):
        start = compose.index(f"\n  {service}")
        end = next((position for position in service_starts if position > start), -1)
        block = compose[start : end if end != -1 else len(compose)]
        assert "migrate:" in block
        assert "condition: service_completed_successfully" in block
        assert "dai_env_registry_docker_config" in block
