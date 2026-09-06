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
    assert payload["session"]["learning_focus"]["stage"] == "compreender"
    assert "next_step" in payload["session"]["learning_focus"]
    assert captured == {
        "area": "it",
        "student_id": "student_default",
        "session_id": "session_default_it",
    }


def test_session_focus_names_declared_next_curriculum_step(monkeypatch):
    monkeypatch.setattr(app_module, "verify_auth", lambda: True)
    monkeypatch.setattr(
        app_module.LearningSessionLifecycle,
        "get",
        lambda area, **kwargs: {
            "student_id": kwargs["student_id"],
            "session_id": kwargs["session_id"],
            "area": area,
            "status": "studying",
        },
    )
    monkeypatch.setattr(
        app_module.LearnerState,
        "get",
        lambda area, **kwargs: {
            "area": area,
            "current_concept_id": "ads.algorithms.ordered_steps",
            "current_concept": "sequência ordenada de passos",
            "stage": "concluido",
            "mastery": 0.8,
        },
    )

    response = app_module.app.test_client().get("/api/session?area=ads")
    focus = response.get_json()["session"]["learning_focus"]

    assert focus["teaching_action"] == "avancar"
    assert focus["next_step"] == (
        "Envie continuar para iniciar objetivo e resultado de uma sequência."
    )


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


def test_dashboard_projects_real_progress_and_due_reviews(monkeypatch):
    monkeypatch.setattr(app_module, "verify_auth", lambda: True)
    monkeypatch.setattr(
        app_module.LearningSessionLifecycle,
        "get",
        lambda area, **kwargs: {"status": "studying", "area": area},
    )
    monkeypatch.setattr(
        app_module.LearnerState,
        "get",
        lambda area, **kwargs: {
            "area": area,
            "current_concept_id": "ads.variables",
            "current_concept": "variáveis",
            "stage": "fixar",
        },
    )
    monkeypatch.setattr(
        app_module.TeachingPolicy,
        "choose_action",
        lambda state: "consolidar",
    )
    progress = [
        {
            "concept_id": "ads.variables",
            "concept": "variáveis",
            "mastery": 0.8,
            "difficulty_count": 1,
            "updated_at": "2026-09-06 10:00:00",
        },
        {
            "concept_id": "ads.functions",
            "concept": "funções",
            "mastery": 0.0,
            "difficulty_count": 0,
            "updated_at": None,
        },
    ]
    monkeypatch.setattr(app_module.ConceptProgress, "list_all", lambda *a, **k: progress)
    monkeypatch.setattr(app_module.ReviewQueue, "due", lambda *a, **k: [progress[0]])
    monkeypatch.setattr(
        app_module.ConceptCatalog,
        "list_selectable",
        lambda area: [{"concept_id": "ads.variables", "canonical_name": "variáveis"}],
    )

    response = app_module.app.test_client().get("/api/dashboard?area=ads")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["summary"] == {
        "started": 1,
        "mastered": 1,
        "due_reviews": 1,
        "mean_mastery": 0.8,
    }
    assert payload["session"]["learning_focus"]["concept"] == "variáveis"
    assert payload["difficulties"][0]["concept_id"] == "ads.variables"


def test_start_study_activates_selected_catalog_concept(monkeypatch):
    monkeypatch.setattr(app_module, "verify_auth", lambda: True)
    monkeypatch.setattr(
        app_module.ConceptCatalog,
        "resolve",
        lambda area, value, selectable_only=False: {
            "concept_id": "ads.algorithms",
            "canonical_name": "algoritmos",
        },
    )
    monkeypatch.setattr(
        app_module.LearningSessionLifecycle,
        "get",
        lambda *a, **k: {"status": "studying"},
    )
    monkeypatch.setattr(app_module.LearningTurnLease, "acquire", lambda *a, **k: True)
    monkeypatch.setattr(app_module.LearningTurnLease, "release", lambda *a, **k: True)
    captured = {}

    def activate(area, concept_id, **kwargs):
        captured.update(area=area, concept_id=concept_id, **kwargs)
        return {"current_concept_id": concept_id, "stage": "compreender"}

    monkeypatch.setattr(app_module.ConceptActivation, "activate", activate)
    monkeypatch.setattr(
        app_module,
        "_with_learning_focus",
        lambda session, context: {**session, "learning_focus": {"concept": "algoritmos"}},
    )

    response = app_module.app.test_client().post(
        "/api/study/start",
        json={"area": "ads", "concept_id": "ads.algorithms", "restart": True},
    )

    assert response.status_code == 200
    assert captured["concept_id"] == "ads.algorithms"
    assert captured["restart"] is True
    assert response.get_json()["session"]["learning_focus"]["concept"] == "algoritmos"


def test_start_review_restores_selected_concept_progress(monkeypatch):
    monkeypatch.setattr(app_module, "verify_auth", lambda: True)
    monkeypatch.setattr(
        app_module.LearningSessionLifecycle,
        "get",
        lambda *a, **k: {"status": "studying"},
    )
    monkeypatch.setattr(
        app_module.ConceptCatalog,
        "resolve",
        lambda area, value: {
            "concept_id": "ads.variables",
            "canonical_name": "variáveis",
        },
    )
    monkeypatch.setattr(
        app_module.ConceptProgress,
        "get",
        lambda *a, **k: {
            "concept_id": "ads.variables",
            "mastery": 0.7,
            "difficulty_count": 2,
            "last_evidence": "evidência anterior",
            "updated_at": "2026-09-06 10:00:00",
        },
    )
    monkeypatch.setattr(app_module.LearningTurnLease, "acquire", lambda *a, **k: True)
    monkeypatch.setattr(app_module.LearningTurnLease, "release", lambda *a, **k: True)
    captured = {}

    def update(area, **changes):
        captured.update(changes)
        return {"area": area, **changes}

    monkeypatch.setattr(app_module.LearnerState, "update", update)
    monkeypatch.setattr(
        app_module,
        "_with_learning_focus",
        lambda session, context: {**session, "learning_focus": {"concept": "variáveis"}},
    )

    response = app_module.app.test_client().post(
        "/api/review/start",
        json={"area": "ads", "concept_id": "ads.variables"},
    )

    assert response.status_code == 200
    assert captured["current_concept_id"] == "ads.variables"
    assert captured["stage"] == "reencontrar"
    assert captured["mastery"] == 0.7


def test_start_study_rechecks_session_after_acquiring_lease(monkeypatch):
    monkeypatch.setattr(app_module, "verify_auth", lambda: True)
    monkeypatch.setattr(
        app_module.ConceptCatalog,
        "resolve",
        lambda area, value, selectable_only=False: {
            "concept_id": "ads.algorithms",
            "canonical_name": "algoritmos",
        },
    )
    statuses = iter(("studying", "paused"))
    monkeypatch.setattr(
        app_module.LearningSessionLifecycle,
        "get",
        lambda *a, **k: {"status": next(statuses)},
    )
    monkeypatch.setattr(app_module.LearningTurnLease, "acquire", lambda *a, **k: True)
    released = {"value": False}
    monkeypatch.setattr(
        app_module.LearningTurnLease,
        "release",
        lambda *a, **k: released.update(value=True),
    )
    activated = {"value": False}
    monkeypatch.setattr(
        app_module.ConceptActivation,
        "activate",
        lambda *a, **k: activated.update(value=True),
    )

    response = app_module.app.test_client().post(
        "/api/study/start",
        json={"area": "ads", "concept_id": "ads.algorithms"},
    )

    assert response.status_code == 409
    assert response.get_json()["code"] == "session_not_studying"
    assert activated["value"] is False
    assert released["value"] is True
