import re
from pathlib import Path
from types import SimpleNamespace

import backend.app as app_module


def test_frontend_generates_and_sends_turn_id():
    source = Path(
        "backend/static/js/chat-engine.js"
    ).read_text()

    assert "function createTurnId()" in source

    assert re.search(
        r"const turnId\s*=\s*"
        r"createTurnId\(\)",
        source,
    )

    assert re.search(
        r"turn_id:\s*turnId",
        source,
    )

    assert "historyForRequest" not in source

    payload = re.search(
        r"await Api\.streamChat\("
        r"\s*\{(.*?)\}\s*,",
        source,
        re.DOTALL,
    )

    assert payload is not None
    assert "history:" not in payload.group(1)


def test_backend_forwards_turn_id_to_commit(
    monkeypatch,
):
    initial_state = {
        "area": "ads",
        "current_concept": None,
        "stage": "concluido",
        "last_evidence": None,
        "difficulty_count": 0,
        "mastery": 0.0,
        "updated_at": None,
    }

    activated_state = {
        **initial_state,
        "current_concept": "variáveis",
        "stage": "compreender",
    }

    captured = {}

    monkeypatch.setattr(
        app_module,
        "verify_auth",
        lambda: True,
    )

    monkeypatch.setattr(
        app_module,
        "GROQ_API_KEY",
        "teste",
    )

    monkeypatch.setattr(
        app_module.LearnerState,
        "get",
        lambda area: initial_state,
    )

    monkeypatch.setattr(
        app_module.ProcessLearningTurn,
        "preview_activation",
        lambda *args, **kwargs:
            activated_state,
    )

    monkeypatch.setattr(
        app_module.ProcessLearningTurn,
        "preview_turn",
        lambda *args, **kwargs: {
            "learner_state":
                activated_state,
            "teaching_action":
                "explicar",
        },
    )

    def fake_commit_turn(
        area,
        user_message,
        identified_concept,
        semantic_evidence,
        turn_id=None,
        assistant_message=None,
    ):
        captured["turn_id"] = turn_id
        captured["assistant_message"] = (
            assistant_message
        )

        return {
            "learner_state":
                activated_state,
            "teaching_action":
                "explicar",
        }

    monkeypatch.setattr(
        app_module.ProcessLearningTurn,
        "commit_turn",
        fake_commit_turn,
    )

    monkeypatch.setattr(
        app_module.TutorCore,
        "build_messages",
        lambda *args, **kwargs: [
            {
                "role": "user",
                "content":
                    "Quero aprender variáveis",
            }
        ],
    )

    class FakeCompletions:
        def create(self, **kwargs):
            if kwargs.get("stream") is False:
                return SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            message=SimpleNamespace(
                                content=(
                                    '{"concept":"variáveis"}'
                                )
                            )
                        )
                    ]
                )

            return [
                SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            delta=SimpleNamespace(
                                content="Resposta confirmada."
                            )
                        )
                    ]
                )
            ]

    class FakeChat:
        completions = FakeCompletions()

    class FakeGroq:
        def __init__(self, **kwargs):
            self.chat = FakeChat()

    monkeypatch.setattr(
        app_module,
        "Groq",
        FakeGroq,
    )

    response = (
        app_module.app
        .test_client()
        .post(
            "/chat/stream",
            json={
                "message":
                    "Quero aprender variáveis",
                "history": [],
                "area": "ads",
                "turn_id": "turn-end-to-end-001",
            },
        )
    )

    body = response.get_data(
        as_text=True
    )

    assert response.status_code == 200

    assert (
        captured["turn_id"]
        == "turn-end-to-end-001"
    )

    assert (
        captured["assistant_message"]
        == "Resposta confirmada."
    )

    assert '"done": true' in body.lower()


def test_empty_stream_does_not_commit_or_confirm_turn(
    monkeypatch,
):
    learner_state = {
        "area": "ads",
        "current_concept": "variáveis",
        "stage": "testar",
        "last_evidence": None,
        "difficulty_count": 0,
        "mastery": 0.5,
        "updated_at": None,
    }
    captured = {"commits": 0}

    monkeypatch.setattr(
        app_module,
        "verify_auth",
        lambda: True,
    )
    monkeypatch.setattr(
        app_module,
        "GROQ_API_KEY",
        "teste",
    )
    monkeypatch.setattr(
        app_module.LearnerState,
        "get",
        lambda area: learner_state,
    )
    monkeypatch.setattr(
        app_module.ConceptTracker,
        "build_tracking_request",
        lambda *args: None,
    )
    monkeypatch.setattr(
        app_module.ProcessLearningTurn,
        "preview_activation",
        lambda *args: learner_state,
    )
    monkeypatch.setattr(
        app_module.LearningHistory,
        "get_messages",
        lambda *args, **kwargs: [],
    )
    monkeypatch.setattr(
        app_module.EvidenceEvaluator,
        "build_evaluation",
        lambda *args: None,
    )
    monkeypatch.setattr(
        app_module.ProcessLearningTurn,
        "preview_turn",
        lambda *args: {
            "learner_state": learner_state,
            "teaching_action": "testar",
        },
    )
    monkeypatch.setattr(
        app_module.TutorCore,
        "build_messages",
        lambda *args, **kwargs: [
            {
                "role": "user",
                "content": "Resposta do aluno.",
            }
        ],
    )

    def fake_commit(*args, **kwargs):
        captured["commits"] += 1

    monkeypatch.setattr(
        app_module.ProcessLearningTurn,
        "commit_turn",
        fake_commit,
    )

    class EmptyCompletions:
        def create(self, **kwargs):
            return []

    class EmptyGroq:
        def __init__(self, **kwargs):
            self.chat = SimpleNamespace(
                completions=EmptyCompletions()
            )

    monkeypatch.setattr(
        app_module,
        "Groq",
        EmptyGroq,
    )

    response = app_module.app.test_client().post(
        "/chat/stream",
        json={
            "message": "Resposta do aluno.",
            "area": "ads",
            "turn_id": "empty-stream-turn",
        },
    )

    body = response.get_data(as_text=True).lower()

    assert response.status_code == 200
    assert captured["commits"] == 0
    assert '"error"' in body
    assert '"done": true' not in body
