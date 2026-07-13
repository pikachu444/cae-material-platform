import os
import socket
import subprocess
import sys
import time
from pathlib import Path

from cmp_api_client import Client

PROJECT_ROOT = Path(__file__).parents[2]


def _unused_local_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def test_generated_client_calls_live_health_endpoint() -> None:
    port = _unused_local_port()
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join(
        [
            str(PROJECT_ROOT / "backend/src"),
            str(PROJECT_ROOT / "generated/python"),
            environment.get("PYTHONPATH", ""),
        ]
    )
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "cmp.apps.api:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "error",
        ],
        cwd=PROJECT_ROOT,
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    client = Client(f"http://127.0.0.1:{port}", timeout_seconds=0.25)
    try:
        deadline = time.monotonic() + 10
        while True:
            try:
                result = client.get_health()
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise
                time.sleep(0.05)

        assert result.status == "ok"
        assert result.service == "cmp-api"
        assert result.version == "0.16.0"
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)

