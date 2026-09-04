import json

import backend.security as security
from backend.app import create_app
from backend.services.access_control import AccessControl
from backend.services.data_lifecycle import DataLifecycle


def test_export_requires_auth_and_never_exposes_key_hash(monkeypatch):
    AccessControl.create_credential(
        "student_privacy_export",
        "phone",
        "privacy-export-key",
    )

    monkeypatch.setattr(security, "APP_ENV", "production")
    monkeypatch.setattr(security, "APEX_ACCESS_KEY", "bootstrap-key")
    monkeypatch.setattr(security, "AUTH_RATE_LIMIT_REQUESTS", 100)

    app = create_app({"TESTING": True})
    client = app.test_client()

    denied = client.get("/api/privacy/export")
    assert denied.status_code == 401

    response = client.get(
        "/api/privacy/export",
        headers={"X-Apex-Key": "privacy-export-key"},
    )
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    assert "attachment" in response.headers["Content-Disposition"]

    payload = json.loads(response.get_data(as_text=True))
    assert payload["student_id"] == "student_privacy_export"
    serialized = response.get_data(as_text=True)
    assert "key_hash" not in serialized
    assert "privacy-export-key" not in serialized


def test_delete_requires_explicit_confirmation(monkeypatch):
    AccessControl.create_credential(
        "student_privacy_confirm",
        "phone",
        "privacy-confirm-key",
    )

    monkeypatch.setattr(security, "APP_ENV", "production")
    monkeypatch.setattr(security, "APEX_ACCESS_KEY", "bootstrap-key")
    monkeypatch.setattr(security, "AUTH_RATE_LIMIT_REQUESTS", 100)

    app = create_app({"TESTING": True})
    client = app.test_client()

    response = client.delete(
        "/api/privacy/data",
        headers={"X-Apex-Key": "privacy-confirm-key"},
        json={"confirmation": "sim"},
    )
    assert response.status_code == 400
    assert response.get_json()["code"] == "confirmation_required"
    assert AccessControl.authenticate("privacy-confirm-key") is not None


def test_delete_uses_authenticated_student_and_revokes_credential(monkeypatch):
    AccessControl.create_credential(
        "student_privacy_delete",
        "phone",
        "privacy-delete-key",
    )
    AccessControl.create_credential(
        "student_other",
        "phone",
        "other-key",
    )

    monkeypatch.setattr(security, "APP_ENV", "production")
    monkeypatch.setattr(security, "APEX_ACCESS_KEY", "bootstrap-key")
    monkeypatch.setattr(security, "AUTH_RATE_LIMIT_REQUESTS", 100)

    app = create_app({"TESTING": True})
    client = app.test_client()

    response = client.delete(
        "/api/privacy/data",
        headers={"X-Apex-Key": "privacy-delete-key"},
        json={"confirmation": DataLifecycle.DELETE_CONFIRMATION},
    )
    assert response.status_code == 200
    assert response.get_json()["receipt_id"].startswith("privacy_")

    assert AccessControl.authenticate("privacy-delete-key") is None
    assert AccessControl.authenticate("other-key") is not None

    after = client.get(
        "/api/session?area=ads",
        headers={"X-Apex-Key": "privacy-delete-key"},
    )
    assert after.status_code == 401
