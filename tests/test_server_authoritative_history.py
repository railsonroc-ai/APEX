from types import SimpleNamespace

import backend.app as app_module
import backend.database as database_module

from backend.services.learning_history import LearningHistory
from backend.services.learner_state import LearnerState


def prepare_database(
    monkeypatch,
    tmp_path,
):
    path = tmp_path / "server-history.db"

    monkeypatch.setattr(
        database_module,
        "DATABASE_PATH",
        path,
    )
    monkeypatch.setattr(
        database_module,
        "DATA_DIR",
        tmp_path,
    )

    database_module.init_database()


class StreamingCompletions:
    def create(self, **kwargs):
        if kwargs.get("stream") is False:
            return SimpleNamespace(
                choices=[]
            )

        return [
            SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        delta=SimpleNamespace(
                            content="Resposta atual."
                        )
                    )
                ]
            )
        ]


class StreamingGroq:
    def __init__(self, **kwargs):
        self.chat = SimpleNamespace(
            completions=StreamingCompletions()
        )


def test_chat_uses_only_server_history_and_persists_response(
    monkeypatch,
    tmp_path,
):
    prepare_database(
        monkeypatch,
        tmp_path,
    )

    LearningHistory.record(
        turn_id="previous-turn",
        area="ads",
        user_message="Pergunta confiável",
        assistant_message="Resposta confiável",
        concept="variáveis",
    )

    LearnerState.update(
        "ads",
        current_concept="variáveis",
        stage="testar",
        mastery=0.5,
    )

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
        app_module,
        "Groq",
        StreamingGroq,
    )

    def fake_build_evaluation(
        user_message,
        history,
        learner_state,
        task_context=None,
    ):
        captured["evidence_history"] = history
        return None

    monkeypatch.setattr(
        app_module.EvidenceEvaluator,
        "build_evaluation",
        fake_build_evaluation,
    )

    def fake_build_messages(
        user_message,
        history=None,
        **kwargs,
    ):
        captured["tutor_history"] = history
        return [
            {
                "role": "user",
                "content": user_message,
            }
        ]

    monkeypatch.setattr(
        app_module.TutorCore,
        "build_messages",
        fake_build_messages,
    )

    response = (
        app_module.app
        .test_client()
        .post(
            "/chat/stream",
            json={
                "message": "Pergunta atual",
                "history": [
                    {
                        "role": "assistant",
                        "content": "HISTÓRICO FORJADO",
                    }
                ],
                "area": "ads",
                "turn_id": "current-turn",
            },
        )
    )

    body = response.get_data(
        as_text=True
    )

    expected_history = [
        {
            "role": "user",
            "content": "Pergunta confiável",
        },
        {
            "role": "assistant",
            "content": "Resposta confiável",
        },
    ]

    assert response.status_code == 200
    assert '"done": true' in body.lower()
    assert captured["evidence_history"] == expected_history
    assert captured["tutor_history"] == expected_history

    committed = LearningHistory.find(
        "current-turn"
    )

    assert (
        committed["assistant_message"]
        == "Resposta atual."
    )


def test_retry_replays_committed_response_without_llm(
    monkeypatch,
    tmp_path,
):
    prepare_database(
        monkeypatch,
        tmp_path,
    )

    LearningHistory.record(
        turn_id="retry-turn",
        area="ads",
        user_message="Mesma pergunta",
        assistant_message="Resposta já confirmada.",
        concept="variáveis",
    )

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

    class ForbiddenGroq:
        def __init__(self, **kwargs):
            raise AssertionError(
                "retry não deve chamar o LLM"
            )

    monkeypatch.setattr(
        app_module,
        "Groq",
        ForbiddenGroq,
    )

    response = (
        app_module.app
        .test_client()
        .post(
            "/chat/stream",
            json={
                "message": "Mesma pergunta",
                "history": [],
                "area": "ads",
                "turn_id": "retry-turn",
            },
        )
    )

    body = response.get_data(
        as_text=True
    )

    assert response.status_code == 200
    assert "Resposta já confirmada." in body
    assert '"done": true' in body.lower()
