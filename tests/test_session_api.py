import backend.app as app_module


def test_session_status_uses_server_context(monkeypatch):
    monkeypatch.setattr(app_module, "verify_auth", lambda: True)
    captured = {}

    def fake_get(area, **kwargs):
        captured["area"] = area
        captured.update(kwargs)
        return {
            "student_id": kwargs["student_id"],
            "session_id": kwargs["session_id"],
            "area": area,
            "status": "studying",
        }

    monkeypatch.setattr(
        app_module.LearningSessionLifecycle,
        "get",
        fake_get,
    )

    response = app_module.app.test_client().get(
        "/api/session?area=it"
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["session"]["status"] == "studying"
    assert captured == {
        "area": "it",
        "student_id": "student_default",
        "session_id": "session_default_it",
    }


def test_pause_and_resume_api_delegate_to_lifecycle(monkeypatch):
    monkeypatch.setattr(app_module, "verify_auth", lambda: True)
    monkeypatch.setattr(
        app_module.LearningTurnLease,
        "acquire",
        lambda *args, **kwargs: True,
    )
    monkeypatch.setattr(
        app_module.LearningTurnLease,
        "release",
        lambda *args, **kwargs: True,
    )
    captured = []

    def fake_pause(area, **kwargs):
        captured.append(("pause", area, kwargs))
        return {"status": "paused", "duplicate": False}

    def fake_resume(area, **kwargs):
        captured.append(("resume", area, kwargs))
        return {"status": "reviewing", "duplicate": False}

    monkeypatch.setattr(
        app_module.LearningSessionLifecycle,
        "pause",
        fake_pause,
    )
    monkeypatch.setattr(
        app_module.LearningSessionLifecycle,
        "resume",
        fake_resume,
    )

    client = app_module.app.test_client()
    paused = client.post("/api/session/pause", json={"area": "ads"})
    resumed = client.post(
        "/api/session/resume",
        json={"area": "ads", "mode": "review"},
    )

    assert paused.status_code == 200
    assert paused.get_json()["session"]["status"] == "paused"
    assert resumed.status_code == 200
    assert resumed.get_json()["session"]["status"] == "reviewing"
    assert captured[0][0:2] == ("pause", "ads")
    assert captured[1][0:2] == ("resume", "ads")
    assert captured[1][2]["mode"] == "review"
    assert captured[0][2]["student_id"] == "student_default"
    assert captured[0][2]["session_id"] == "session_default_ads"


def test_resume_api_rejects_unknown_mode_without_mutating(monkeypatch):
    monkeypatch.setattr(app_module, "verify_auth", lambda: True)
    called = {"resume": 0}

    def fake_resume(*args, **kwargs):
        called["resume"] += 1
        return {}

    monkeypatch.setattr(
        app_module.LearningSessionLifecycle,
        "resume",
        fake_resume,
    )

    response = app_module.app.test_client().post(
        "/api/session/resume",
        json={"area": "ads", "mode": "inventado"},
    )

    assert response.status_code == 400
    assert "modo de retomada inválido" in response.get_json()["error"]
    assert called["resume"] == 0


def test_paused_session_blocks_new_chat_before_groq(monkeypatch):
    monkeypatch.setattr(app_module, "verify_auth", lambda: True)
    monkeypatch.setattr(
        app_module.LearningSessionLifecycle,
        "get",
        lambda *args, **kwargs: {"status": "paused"},
    )

    response = app_module.app.test_client().post(
        "/chat/stream",
        json={
            "message": "Quero continuar sem retomar",
            "area": "ads",
        },
    )

    assert response.status_code == 409
    payload = response.get_json()
    assert payload == {
        "error": "Sessão pausada",
        "code": "session_paused",
    }
