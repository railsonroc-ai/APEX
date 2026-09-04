from flask import Flask

import backend.security as security


def create_test_app():
    return Flask(
        __name__
    )


def test_development_without_access_key_allows_request(
    monkeypatch,
):
    monkeypatch.setattr(
        security,
        "APP_ENV",
        "development",
    )

    monkeypatch.setattr(
        security,
        "APEX_ACCESS_KEY",
        "",
    )

    app = create_test_app()

    with app.test_request_context(
        "/"
    ):
        assert (
            security.verify_auth()
            is True
        )


def test_production_without_access_key_blocks_request(
    monkeypatch,
):
    monkeypatch.setattr(
        security,
        "APP_ENV",
        "production",
    )

    monkeypatch.setattr(
        security,
        "APEX_ACCESS_KEY",
        "",
    )

    app = create_test_app()

    with app.test_request_context(
        "/"
    ):
        assert (
            security.verify_auth()
            is False
        )


def test_correct_access_key_allows_request(
    monkeypatch,
):
    monkeypatch.setattr(
        security,
        "APP_ENV",
        "production",
    )

    monkeypatch.setattr(
        security,
        "APEX_ACCESS_KEY",
        "chave-correta",
    )

    app = create_test_app()

    with app.test_request_context(
        "/",
        headers={
            "X-Apex-Key":
                "chave-correta",
        },
    ):
        assert (
            security.verify_auth()
            is True
        )


def test_wrong_access_key_blocks_request(
    monkeypatch,
):
    monkeypatch.setattr(
        security,
        "APP_ENV",
        "production",
    )

    monkeypatch.setattr(
        security,
        "APEX_ACCESS_KEY",
        "chave-correta",
    )

    app = create_test_app()

    with app.test_request_context(
        "/",
        headers={
            "X-Apex-Key":
                "chave-errada",
        },
    ):
        assert (
            security.verify_auth()
            is False
        )

def test_rate_limit_marks_request_as_limited(monkeypatch):
    from flask import g
    from backend.database import get_db_connection

    monkeypatch.setattr(security, "APP_ENV", "production")
    monkeypatch.setattr(security, "APEX_ACCESS_KEY", "rate-key")
    monkeypatch.setattr(security, "AUTH_RATE_LIMIT_REQUESTS", 1)
    monkeypatch.setattr(security, "AUTH_RATE_LIMIT_WINDOW_SECONDS", 60)

    connection = get_db_connection()
    try:
        connection.execute(
            "DELETE FROM api_rate_limits WHERE subject_id='environment-default'"
        )
        connection.commit()
    finally:
        connection.close()

    app = create_test_app()

    with app.test_request_context(
        "/",
        headers={"X-Apex-Key": "rate-key"},
    ):
        assert security.verify_auth() is True
        assert g.apex_student_id == "student_default"

    with app.test_request_context(
        "/",
        headers={"X-Apex-Key": "rate-key"},
    ):
        assert security.verify_auth() is False
        assert g.apex_rate_limited is True


def test_database_credential_binds_student_and_rate_limit_returns_429(monkeypatch):
    from backend.app import create_app
    from backend.services.access_control import AccessControl

    AccessControl.create_credential(
        "student_security_http",
        "integration",
        "individual-key-http",
    )

    monkeypatch.setattr(security, "APP_ENV", "production")
    monkeypatch.setattr(security, "APEX_ACCESS_KEY", "configured-bootstrap-key")
    monkeypatch.setattr(security, "AUTH_RATE_LIMIT_REQUESTS", 1)
    monkeypatch.setattr(security, "AUTH_RATE_LIMIT_WINDOW_SECONDS", 60)

    application = create_app({"TESTING": True})
    client = application.test_client()
    headers = {"X-Apex-Key": "individual-key-http"}

    first = client.get("/api/session?area=ads", headers=headers)
    assert first.status_code == 200

    second = client.get("/api/session?area=ads", headers=headers)
    assert second.status_code == 429
    assert second.get_json()["code"] == "rate_limited"
