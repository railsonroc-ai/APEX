from types import SimpleNamespace

import backend.app as app_module


class FakeCompletions:
    def create(self, **kwargs):
        if kwargs.get("stream") is False:
            content = (
                '{"criteria":{"task_response":"met",'
                '"conceptual_correctness":"met",'
                '"understanding_application":"met"},'
                '"confidence":0.9,"evidence":"Recordou corretamente."}'
            )
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content=content)
                    )
                ]
            )
        return []


class FakeGroq:
    def __init__(self, **kwargs):
        self.chat = SimpleNamespace(completions=FakeCompletions())


def test_review_request_activates_due_review(monkeypatch):
    initial = {
        "area": "ads",
        "current_concept_id": "ads.variables",
        "current_concept": "variáveis",
        "stage": "concluido",
        "last_evidence": None,
        "difficulty_count": 0,
        "mastery": 0.9,
    }
    review = {**initial, "stage": "reencontrar"}
    captured = {}

    monkeypatch.setattr(app_module, "verify_auth", lambda: True)
    monkeypatch.setattr(app_module, "GROQ_API_KEY", "teste")
    monkeypatch.setattr(app_module, "Groq", FakeGroq)
    monkeypatch.setattr(app_module.LearnerState, "get", lambda area, **kwargs: initial)
    monkeypatch.setattr(
        app_module.ConceptTracker,
        "build_tracking_request",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        app_module.EvidenceEvaluator,
        "build_evaluation",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        app_module.LearnerSignals,
        "detect",
        lambda message: {app_module.LearnerSignals.REVIEW_REQUEST},
    )

    def activate(area, **kwargs):
        captured["activated"] = area
        return review

    monkeypatch.setattr(
        app_module.ReviewLifecycle,
        "activate_due",
        activate,
    )
    monkeypatch.setattr(
        app_module.LearnerState,
        "update",
        lambda area, **changes: {**review, **changes},
    )
    monkeypatch.setattr(
        app_module.TeachingPolicy,
        "choose_action",
        lambda state: "revisar",
    )

    response = app_module.app.test_client().post(
        "/chat/stream",
        json={"message": "Quero revisar", "history": [], "area": "ads"},
    )
    response.get_data(as_text=True)

    assert response.status_code == 200
    assert captured["activated"] == "ads"


def test_demonstrated_review_completes_lifecycle(monkeypatch):
    initial = {
        "area": "ads",
        "current_concept_id": "ads.variables",
        "current_concept": "variáveis",
        "stage": "reencontrar",
        "last_evidence": None,
        "difficulty_count": 0,
        "mastery": 0.7,
    }
    captured = {}

    monkeypatch.setattr(app_module, "verify_auth", lambda: True)
    monkeypatch.setattr(app_module, "GROQ_API_KEY", "teste")
    monkeypatch.setattr(app_module, "Groq", FakeGroq)
    monkeypatch.setattr(app_module.LearnerState, "get", lambda area, **kwargs: initial)

    def update_state(area, **changes):
        return {**initial, **changes}

    monkeypatch.setattr(app_module.LearnerState, "update", update_state)
    monkeypatch.setattr(
        app_module.ConceptProgress,
        "update",
        lambda area, concept, **changes: {
            "area": area,
            "concept": concept,
            **changes,
        },
    )

    def complete(area, concept, state, **kwargs):
        captured["complete"] = (area, concept, state["stage"])
        return {
            "state": {**state, "stage": "concluido"},
            "progress": {},
        }

    monkeypatch.setattr(
        app_module.ReviewLifecycle,
        "complete_due",
        complete,
    )
    monkeypatch.setattr(
        app_module.LearnerSignals,
        "detect",
        lambda message: set(),
    )
    monkeypatch.setattr(
        app_module.TeachingPolicy,
        "choose_action",
        lambda state: "avancar",
    )

    server_history = [
        {
            "role": "assistant",
            "content": "Explique novamente o conceito.",
        }
    ]

    monkeypatch.setattr(
        app_module.LearningHistory,
        "get_messages",
        lambda area, concept=None, **kwargs: server_history,
    )

    response = app_module.app.test_client().post(
        "/chat/stream",
        json={
            "message": "Uma variável guarda um valor.",
            "history": [
                {
                    "role": "assistant",
                    "content": "Explique novamente o conceito.",
                }
            ],
            "area": "ads",
        },
    )
    response.get_data(as_text=True)

    assert response.status_code == 200
    assert captured["complete"] == ("ads", "ads.variables", "fixar")
