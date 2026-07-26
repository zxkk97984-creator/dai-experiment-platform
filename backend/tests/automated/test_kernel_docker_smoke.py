"""Opt-in real Docker smoke tests for the isolated persistent Kernel."""
import json
import os
import secrets
import subprocess

import pytest

from app.config import Settings
from app.services.kernel_manager import KernelManager


pytestmark = pytest.mark.skipif(
    os.environ.get("DAI_RUN_DOCKER_SMOKE") != "1",
    reason="set DAI_RUN_DOCKER_SMOKE=1 to run real Docker Kernel smoke tests",
)


def test_network_none_kernel_preserves_state_and_security():
    record_id = 900_000_000 + secrets.randbelow(90_000_000)
    manager = KernelManager(Settings())

    try:
        session = manager.create_session(record_id, "")
        manager.execute(record_id, "persistent_value = 40")
        result = manager.execute(record_id, "print(persistent_value + 2)")

        stream_text = "".join(
            output.get("content", {}).get("text", "")
            for output in result["outputs"]
            if output.get("msg_type") == "stream"
        )
        assert stream_text.strip() == "42"

        inspect = subprocess.run(
            ["docker", "inspect", session.container_name],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        config = json.loads(inspect.stdout)[0]
        host = config["HostConfig"]

        assert host["NetworkMode"] == "none"
        assert host["ReadonlyRootfs"] is True
        assert host["Memory"] == 256 * 1024 * 1024
        assert host["NanoCpus"] == 1_000_000_000
        assert host["PidsLimit"] == 50
        assert "ALL" in host["CapDrop"]
        assert "no-new-privileges" in host["SecurityOpt"]
        assert "size=64m" in host["Tmpfs"]["/tmp"]
        assert not host["PortBindings"]

        work_mount = next(
            mount for mount in config["Mounts"] if mount["Destination"] == "/work"
        )
        assert work_mount["RW"] is True
    finally:
        manager.destroy(record_id)
