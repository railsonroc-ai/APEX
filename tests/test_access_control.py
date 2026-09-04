import sqlite3

import backend.database as database_module
from backend.services.access_control import (
    AccessControl,
    AccessRateLimiter,
)


def configure_database(monkeypatch, tmp_path):
    path = tmp_path / "access-control.db"
    monkeypatch.setattr(database_module, "DATABASE_PATH", path)
    monkeypatch.setattr(database_module, "DATA_DIR", tmp_path)
    database_module.init_database()
    return path


def test_default_credential_is_hashed_and_authenticates(monkeypatch, tmp_path):
    path = configure_database(monkeypatch, tmp_path)

    credential_id = AccessControl.ensure_default_credential("segredo-forte")
    assert credential_id == "credential_default"

    connection = sqlite3.connect(str(path))
    try:
        stored = connection.execute(
            "SELECT key_hash FROM access_credentials WHERE credential_id=?",
            (credential_id,),
        ).fetchone()[0]
    finally:
        connection.close()

    assert stored != "segredo-forte"
    assert len(stored) == 64
    assert AccessControl.authenticate("segredo-forte") == {
        "credential_id": "credential_default",
        "student_id": "student_default",
        "label": "environment-default",
    }
    assert AccessControl.authenticate("segredo-errado") is None


def test_default_credential_rotation_invalidates_previous_key(monkeypatch, tmp_path):
    configure_database(monkeypatch, tmp_path)

    AccessControl.ensure_default_credential("chave-antiga")
    AccessControl.ensure_default_credential("chave-nova")

    assert AccessControl.authenticate("chave-antiga") is None
    assert AccessControl.authenticate("chave-nova") is not None


def test_revoked_credential_no_longer_authenticates(monkeypatch, tmp_path):
    configure_database(monkeypatch, tmp_path)

    credential_id = AccessControl.create_credential(
        "student_default",
        "celular",
        "chave-celular",
    )

    assert AccessControl.authenticate("chave-celular") is not None
    assert AccessControl.revoke(credential_id) is True
    assert AccessControl.authenticate("chave-celular") is None


def test_rate_limit_is_shared_in_sqlite(monkeypatch, tmp_path):
    configure_database(monkeypatch, tmp_path)

    assert AccessRateLimiter.allow(
        "credential-test",
        limit=2,
        window_seconds=60,
        now_epoch=1000,
    ) is True
    assert AccessRateLimiter.allow(
        "credential-test",
        limit=2,
        window_seconds=60,
        now_epoch=1001,
    ) is True
    assert AccessRateLimiter.allow(
        "credential-test",
        limit=2,
        window_seconds=60,
        now_epoch=1002,
    ) is False
    assert AccessRateLimiter.allow(
        "credential-test",
        limit=2,
        window_seconds=60,
        now_epoch=1060,
    ) is True


def test_creating_credential_provisions_student_sessions(monkeypatch, tmp_path):
    path = configure_database(monkeypatch, tmp_path)

    credential_id = AccessControl.create_credential(
        "student_new",
        "notebook",
        "chave-nova-pessoa",
    )
    assert credential_id.startswith("credential_")

    connection = sqlite3.connect(str(path))
    try:
        student_count = connection.execute(
            "SELECT COUNT(*) FROM students WHERE id='student_new'"
        ).fetchone()[0]
        sessions = connection.execute(
            "SELECT area FROM learning_sessions WHERE student_id='student_new' ORDER BY area"
        ).fetchall()
        states = connection.execute(
            "SELECT area, status FROM learning_session_states WHERE student_id='student_new' ORDER BY area"
        ).fetchall()
    finally:
        connection.close()

    assert student_count == 1
    assert [row[0] for row in sessions] == ["ads", "it"]
    assert states == [("ads", "studying"), ("it", "studying")]
