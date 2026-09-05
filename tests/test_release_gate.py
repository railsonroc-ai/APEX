from pathlib import Path

import pytest

from tools import apex_release_gate


pytestmark = pytest.mark.reliability


def test_release_gate_covers_core_journeys_and_failure_contracts():
    required = {
        "tests/test_e2e_learning_pipeline.py",
        "tests/test_e2e_session_resume_review.py",
        "tests/test_e2e_privacy_lifecycle.py",
        "tests/test_e2e_http_reliability.py",
        "tests/test_server_turn_serialization.py",
        "tests/test_stream_transaction.py",
        "tests/test_learning_turn_idempotency.py",
        "tests/test_database_migrations.py",
        "tests/test_security.py",
        "tests/test_session_api.py",
        "tests/test_privacy_api.py",
        "tests/test_chat_engine_stream_confirmation.py",
        "tests/test_session_ui.py",
        "tests/test_learning_intent.py",
        "tests/test_tutor_response_validator.py",
        "tests/test_pedagogical_guard_e2e.py",
    }
    assert set(apex_release_gate.CRITICAL_TEST_FILES) == required


def test_release_gate_never_invokes_real_database_migration_script():
    source = Path("tools/apex_release_gate.py").read_text()
    assert "apex_migrate_real.py" not in source
    assert "APEX_RELEASE_DB_" in source
    assert 'env["APEX_DATA_DIR"]' in source
    assert "PRAGMA foreign_key_check" in source
    assert "PRAGMA integrity_check" in source
