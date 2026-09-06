import importlib.util
from pathlib import Path

import pytest

from tools import apex_apply_update


MODULE_PATH = Path("tools/apex_release.py")
spec = importlib.util.spec_from_file_location("apex_release", MODULE_PATH)
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


pytestmark = pytest.mark.reliability


def test_parse_release_metadata_reads_base_and_commit():
    result = release.parse_release_metadata(
        "Base commit esperado: 6678cf5\n"
        "Migration nova: NAO\n"
        "Commit sugerido: ops: automatiza release\n"
    )
    assert result["expected_head"] == "6678cf5"
    assert result["commit_message"] == "ops: automatiza release"


def test_parse_release_metadata_requires_base():
    with pytest.raises(RuntimeError, match="Base commit esperado"):
        release.parse_release_metadata("Migration nova: NAO\n")


def test_status_paths_supports_modified_new_and_rename():
    text = (
        " M tools/apex_apply_update.py\n"
        "?? tools/apex_release.py\n"
        "R  old.py -> new.py\n"
    )
    assert release.status_paths(text) == {
        "tools/apex_apply_update.py",
        "tools/apex_release.py",
        "new.py",
    }


def test_clean_probe_requires_zero_fail_and_warn():
    good = (
        "=== APEX PEDAGOGICAL PROBE ===\n"
        "PASS: 116\nFAIL: 0\nWARN: 0\n"
        "APEX PEDAGOGICAL PROBE: OK\n"
    )
    assert release.ensure_clean_probe(good)

    with pytest.raises(RuntimeError, match="WARN=1"):
        release.ensure_clean_probe(
            "PASS: 10\nFAIL: 0\nWARN: 1\nAPEX PEDAGOGICAL PROBE: OK\n"
        )


def test_apply_update_probe_gate_rejects_missing_counters():
    with pytest.raises(RuntimeError, match="contadores FAIL/WARN"):
        apex_apply_update.ensure_clean_pedagogical_probe(
            "APEX PEDAGOGICAL PROBE: OK\n"
        )


def test_tracked_in_head_suppresses_expected_git_error_output(monkeypatch, tmp_path):
    calls = []

    class Result:
        returncode = 1

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return Result()

    monkeypatch.setattr(release, "run", fake_run)
    assert release.tracked_in_head(tmp_path, "new-file.py") is False
    assert calls[0][1]["capture"] is True
    assert calls[0][1]["check"] is False
