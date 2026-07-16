import json
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parents[2]


def test_worker_starts_one_empty_cycle_and_exits() -> None:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join(
        [str(PROJECT_ROOT / "backend/src"), environment.get("PYTHONPATH", "")]
    )

    completed = subprocess.run(
        [sys.executable, "-m", "cmp.apps.worker", "--once", "--json"],
        cwd=PROJECT_ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert json.loads(completed.stdout) == {
        "handlers_registered": 0,
        "service": "cmp-worker",
        "status": "idle",
            "version": "0.31.0",
    }

