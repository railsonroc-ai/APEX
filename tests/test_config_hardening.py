import os
import subprocess
import sys
from pathlib import Path


def test_production_requires_access_key():
    root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env["APP_ENV"] = "production"
    env["APEX_ACCESS_KEY"] = ""
    env["SECRET_KEY"] = "teste-secret-key"

    result = subprocess.run(
        [sys.executable, "-c", "import backend.config"],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "APEX_ACCESS_KEY" in result.stderr
