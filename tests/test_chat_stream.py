import backend.app as app_module


def test_chat_stream_without_groq_key_returns_sse_error(
    monkeypatch,
):
    monkeypatch.setattr(
        app_module,
        "verify_auth",
        lambda: True,
    )

    monkeypatch.setattr(
        app_module,
        "GROQ_API_KEY",
        "",
    )

    client = (
        app_module
        .app
        .test_client()
    )

    response = client.post(
        "/chat/stream",
        json={
            "message":
                "O que é uma variável?",
            "history": [],
            "area": "ads",
        },
    )

    body = response.get_data(
        as_text=True
    )

    assert response.status_code == 200

    assert (
        response.mimetype
        == "text/event-stream"
    )

    assert (
        response.headers[
            "Cache-Control"
        ]
        == "no-cache"
    )

    assert (
        response.headers[
            "X-Accel-Buffering"
        ]
        == "no"
    )

    assert (
        "Chave GROQ_API_KEY "
        "não configurada"
        in body
    )

def test_chat_uses_pedagogical_state(monkeypatch):
    state = {
        "area": "ads",
        "current_concept_id": "ads.variables",
        "current_concept": "variáveis",
        "stage": "testar",
        "last_evidence": None,
        "difficulty_count": 0,
        "mastery": 0.5,
        "updated_at": None,
    }
    captured = {}
    monkeypatch.setattr(app_module, "verify_auth", lambda: True)
    monkeypatch.setattr(app_module, "GROQ_API_KEY", "teste")
    monkeypatch.setattr(app_module.LearnerState, "get", lambda area, **kwargs: state)
    monkeypatch.setattr(app_module.TeachingPolicy, "choose_action", lambda value: "testar")
    def fake_build_messages(user_message, history=None, area="ads", learner_state=None, teaching_action=None):
        captured["learner_state"] = learner_state
        captured["teaching_action"] = teaching_action
        return [{"role": "user", "content": user_message}]

    monkeypatch.setattr(app_module.TutorCore, "build_messages", fake_build_messages)

    class FakeCompletions:
        def create(self, **kwargs):
            return []

    class FakeChat:
        completions = FakeCompletions()

    class FakeGroq:
        def __init__(self, **kwargs):
            self.chat = FakeChat()

    monkeypatch.setattr(app_module, "Groq", FakeGroq)

    client = app_module.app.test_client()
    response = client.post(
        "/chat/stream",
        json={"message": "teste", "history": [], "area": "ads"},
    )
    response.get_data(as_text=True)
    assert response.status_code == 200
    assert captured["learner_state"] == state
    assert captured["teaching_action"] == "testar"


def test_difficulty_signal_updates_state_before_policy(monkeypatch):
    initial_state = {"area": "ads", "current_concept_id": "ads.variables", "current_concept": "variáveis", "stage": "compreender", "last_evidence": None, "difficulty_count": 0, "mastery": 0.2, "updated_at": None}
    updated_state = {**initial_state, "stage": "corrigir", "difficulty_count": 1}
    captured = {}
    monkeypatch.setattr(app_module, "verify_auth", lambda: True)
    monkeypatch.setattr(app_module, "GROQ_API_KEY", "teste")
    monkeypatch.setattr(app_module.LearnerState, "get", lambda area, **kwargs: initial_state)

    def fake_update(area, **changes):
        captured["changes"] = changes
        return updated_state

    def fake_choose_action(state):
        captured["policy_state"] = state
        return "corrigir"

    monkeypatch.setattr(app_module.LearnerState, "update", fake_update)
    monkeypatch.setattr(app_module.TeachingPolicy, "choose_action", fake_choose_action)

    class FakeCompletions:
        def create(self, **kwargs):
            return []

    class FakeChat:
        completions = FakeCompletions()

    class FakeGroq:
        def __init__(self, **kwargs):
            self.chat = FakeChat()

    monkeypatch.setattr(app_module, "Groq", FakeGroq)

    client = app_module.app.test_client()
    response = client.post("/chat/stream", json={"message": "Não entendi", "history": [], "area": "ads"})
    response.get_data(as_text=True)

    assert response.status_code == 200
    assert captured["changes"] == {
        "difficulty_count": 1,
        "stage": "corrigir",
        "student_id": "student_default",
    }
    assert captured["policy_state"] == updated_state


def test_identified_concept_updates_state_before_policy(monkeypatch):
    from types import SimpleNamespace
    initial_state = {"area": "ads", "current_concept_id": None, "current_concept": None, "stage": "compreender", "last_evidence": None, "difficulty_count": 0, "mastery": 0.0, "updated_at": None}
    updated_state = {**initial_state, "current_concept_id": "ads.variables", "current_concept": "variáveis"}
    captured = {}
    monkeypatch.setattr(app_module, "verify_auth", lambda: True)
    monkeypatch.setattr(app_module, "GROQ_API_KEY", "teste")
    monkeypatch.setattr(app_module.LearnerState, "get", lambda area, **kwargs: initial_state)

    def fake_activate(area, concept, **kwargs):
        captured["activation"] = (area, concept)
        return updated_state

    def fake_choose_action(state):
        captured["policy_state"] = state
        return "explicar"

    monkeypatch.setattr(app_module.ConceptActivation, "activate", fake_activate)
    monkeypatch.setattr(app_module.TeachingPolicy, "choose_action", fake_choose_action)

    class FakeCompletions:
        def create(self, **kwargs):
            if kwargs.get("stream") is False:
                message = SimpleNamespace(content="{\"concept\":\"variáveis\"}")
                choice = SimpleNamespace(message=message)
                return SimpleNamespace(choices=[choice])
            return []

    class FakeChat:
        completions = FakeCompletions()

    class FakeGroq:
        def __init__(self, **kwargs):
            self.chat = FakeChat()

    monkeypatch.setattr(app_module, "Groq", FakeGroq)

    client = app_module.app.test_client()
    response = client.post(
        "/chat/stream",
        json={"message": "Quero aprender variáveis", "history": [], "area": "ads"},
    )
    response.get_data(as_text=True)

    assert response.status_code == 200
    assert captured["activation"] == ("ads", "ads.variables")
    assert captured["policy_state"] == updated_state


def test_semantic_evidence_updates_state_before_policy(monkeypatch):
    from types import SimpleNamespace
    initial_state = {"area": "ads", "current_concept_id": "ads.variables", "current_concept": "variáveis", "stage": "testar", "last_evidence": None, "difficulty_count": 1, "mastery": 0.5, "updated_at": None}
    updated_state = {**initial_state, "stage": "fixar", "last_evidence": "Explicou corretamente.", "difficulty_count": 0, "mastery": 0.7}
    captured = {"evidence_calls": 0}
    monkeypatch.setattr(app_module, "verify_auth", lambda: True)
    monkeypatch.setattr(app_module, "GROQ_API_KEY", "teste")
    monkeypatch.setattr(app_module.LearnerState, "get", lambda area, **kwargs: initial_state)

    def fake_update(area, **changes):
        captured["changes"] = changes
        return updated_state

    def fake_choose_action(state):
        captured["policy_state"] = state
        return "consolidar"

    monkeypatch.setattr(app_module.LearnerState, "update", fake_update)
    monkeypatch.setattr(
        app_module.ConceptProgress,
        "update",
        lambda area, concept, **changes: {
            "area": area,
            "concept": concept,
            **changes,
        },
    )
    monkeypatch.setattr(app_module.TeachingPolicy, "choose_action", fake_choose_action)

    class FakeCompletions:
        def create(self, **kwargs):
            if kwargs.get("stream") is False:
                captured["evidence_calls"] += 1
                content = '{"criteria":{"task_response":"met","conceptual_correctness":"met","understanding_application":"met"},"confidence":0.9,"evidence":"Explicou corretamente."}'
                message = SimpleNamespace(content=content)
                return SimpleNamespace(choices=[SimpleNamespace(message=message)])
            return []

    class FakeChat:
        completions = FakeCompletions()

    class FakeGroq:
        def __init__(self, **kwargs):
            self.chat = FakeChat()

    monkeypatch.setattr(app_module, "Groq", FakeGroq)

    history = [{
        "role": "assistant",
        "content": "Explique o que é uma variável.",
    }]

    monkeypatch.setattr(
        app_module.LearningHistory,
        "get_messages",
        lambda area, concept=None, **kwargs: history,
    )
    monkeypatch.setattr(
        app_module.LearningHistory,
        "latest_confirmed_turn",
        lambda *args, **kwargs: {
            "turn_id": "source-semantic-turn",
            "assistant_message": "Explique o que é uma variável.",
        },
    )
    monkeypatch.setattr(
        app_module.LearningTask,
        "find_by_source_turn",
        lambda *args, **kwargs: {
            "task_id": "task-semantic",
            "source_turn_id": "source-semantic-turn",
            "area": "ads",
            "concept_id": "ads.variables",
            "stage": "testar",
            "task_kind": "practice",
            "prompt_text": "Explique o que é uma variável.",
        },
    )

    client = app_module.app.test_client()
    response = client.post(
        "/chat/stream",
        json={
            "message": "É um espaço usado para guardar um valor.",
            "history": history,
            "area": "ads",
        },
    )
    response.get_data(as_text=True)

    assert response.status_code == 200
    assert captured["changes"] == {
        "mastery": 0.7,
        "difficulty_count": 0,
        "stage": "fixar",
        "last_evidence": "Explicou corretamente.",
        "student_id": "student_default",
    }
    assert captured["policy_state"] == updated_state
    assert captured["evidence_calls"] == 1

def test_completed_concept_schedules_review(monkeypatch):
    from types import SimpleNamespace

    initial = {
        "area": "ads", "current_concept_id": "ads.variables", "current_concept": "variáveis",
        "stage": "fixar", "last_evidence": None,
        "difficulty_count": 0, "mastery": 0.7, "updated_at": None,
    }
    completed = {
        **initial, "stage": "concluido",
        "mastery": 0.9, "last_evidence": "Aplicou sem ajuda.",
    }
    captured = {"progress": []}

    monkeypatch.setattr(app_module, "verify_auth", lambda: True)
    monkeypatch.setattr(app_module, "GROQ_API_KEY", "teste")
    monkeypatch.setattr(app_module.LearnerState, "get", lambda area, **kwargs: initial)
    monkeypatch.setattr(app_module.LearnerState, "update", lambda area, **changes: completed)

    def fake_progress(area, concept, **changes):
        captured["progress"].append(changes)
        return {"area": area, "concept": concept, **changes}

    monkeypatch.setattr(app_module.ConceptProgress, "update", fake_progress)
    monkeypatch.setattr(
        app_module.ReviewScheduler,
        "schedule",
        lambda progress: {"next_review_at": "2026-09-04T12:00:00+00:00"},
    )
    monkeypatch.setattr(app_module.TeachingPolicy, "choose_action", lambda state: "avancar")
    monkeypatch.setattr(
        app_module.ProcessLearningTurn,
        "_build_mastery_decision",
        classmethod(
            lambda cls, **kwargs: {
                "policy_id": "evidence_portfolio_mastery",
                "policy_version": 2,
                "score": 0.9,
                "can_complete": True,
                "applied_evidence_count": 4,
                "demonstrated_count": 4,
                "demonstrated_stage_count": 2,
                "retention_demonstrated_count": 0,
                "low_assistance_demonstrated_count": 0,
                "latest_outcome": "demonstrated",
                "blockers": [],
            }
        ),
    )

    class FakeCompletions:
        def create(self, **kwargs):
            if kwargs.get("stream") is False:
                content = '{"criteria":{"task_response":"met","conceptual_correctness":"met","understanding_application":"met"},"confidence":0.9,"evidence":"Aplicou sem ajuda."}'
                return SimpleNamespace(
                    choices=[SimpleNamespace(
                        message=SimpleNamespace(content=content)
                    )]
                )
            return []

    class FakeGroq:
        def __init__(self, **kwargs):
            self.chat = SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setattr(app_module, "Groq", FakeGroq)

    server_history = [
        {
            "role": "assistant",
            "content": "Aplique o conceito.",
        }
    ]

    monkeypatch.setattr(
        app_module.LearningHistory,
        "get_messages",
        lambda area, concept=None, **kwargs: server_history,
    )
    monkeypatch.setattr(
        app_module.LearningHistory,
        "latest_confirmed_turn",
        lambda *args, **kwargs: {
            "turn_id": "source-completion-turn",
            "assistant_message": "Aplique o conceito.",
        },
    )
    monkeypatch.setattr(
        app_module.LearningTask,
        "find_by_source_turn",
        lambda *args, **kwargs: {
            "task_id": "task-completion",
            "source_turn_id": "source-completion-turn",
            "area": "ads",
            "concept_id": "ads.variables",
            "stage": "fixar",
            "task_kind": "consolidation",
            "prompt_text": "Aplique o conceito.",
        },
    )

    response = app_module.app.test_client().post(
        "/chat/stream",
        json={
            "message": "Resolvi corretamente.",
            "history": [{"role": "assistant", "content": "Aplique o conceito."}],
            "area": "ads",
        },
    )
    response.get_data(as_text=True)

    assert response.status_code == 200
    assert captured["progress"][-1] == {
        "next_review_at": "2026-09-04T12:00:00+00:00",
        "student_id": "student_default",
    }
