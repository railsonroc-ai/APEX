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

    assert re.search(
        r"streamChat\("
        r".*?historyForRequest,"
        r"\s*turnId",
        source,
        re.DOTALL,
    )


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
    ):
        captured["turn_id"] = turn_id

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

            return []

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

    assert '"done": true' in body.lower()
