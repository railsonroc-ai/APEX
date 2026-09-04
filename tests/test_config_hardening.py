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


def _import_config_with(env_overrides):
    root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env.update(env_overrides)
    return subprocess.run(
        [sys.executable, "-c", "import backend.config"],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
    )


def test_llm_max_retries_rejects_negative_value():
    result = _import_config_with({"LLM_MAX_RETRIES": "-1"})
    assert result.returncode != 0
    assert "LLM_MAX_RETRIES" in result.stderr


def test_llm_token_limit_rejects_zero():
    result = _import_config_with({"LLM_TUTOR_MAX_TOKENS": "0"})
    assert result.returncode != 0
    assert "LLM_TUTOR_MAX_TOKENS" in result.stderr


def test_llm_limits_accept_valid_values():
    result = _import_config_with(
        {
            "LLM_MAX_RETRIES": "2",
            "LLM_IDENTIFICATION_MAX_TOKENS": "120",
            "LLM_EVIDENCE_MAX_TOKENS": "360",
            "LLM_TUTOR_MAX_TOKENS": "900",
        }
    )
    assert result.returncode == 0


def test_privacy_retention_rejects_window_below_30_days():
    result = _import_config_with({"PRIVACY_RETENTION_DAYS": "29"})
    assert result.returncode != 0
    assert "PRIVACY_RETENTION_DAYS" in result.stderr


def test_privacy_retention_accepts_valid_window():
    result = _import_config_with({"PRIVACY_RETENTION_DAYS": "365"})
    assert result.returncode == 0


def test_log_level_rejects_unknown_value():
    result = _import_config_with({"APEX_LOG_LEVEL": "VERBOSE"})
    assert result.returncode != 0
    assert "APEX_LOG_LEVEL" in result.stderr


def test_log_level_accepts_info():
    result = _import_config_with({"APEX_LOG_LEVEL": "INFO"})
    assert result.returncode == 0
