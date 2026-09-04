from types import SimpleNamespace

import pytest

import backend.app as app_module


@pytest.mark.parametrize(
    "initial_state,message",
    [
        (
            {
                "area": "ads",
                "current_concept_id": None,
                "current_concept": None,
                "stage": "concluido",
                "last_evidence": None,
                "difficulty_count": 0,
                "mastery": 0.0,
                "updated_at": None,
            },
            "Quero aprender funções",
        ),
        (
            {
                "area": "ads",
                "current_concept_id": "ads.variables",
                "current_concept": "variáveis",
                "stage": "testar",
                "last_evidence": None,
                "difficulty_count": 0,
                "mastery": 0.6,
                "updated_at": "2026-09-03T12:00:00",
            },
            "Quero aprender funções",
        ),
    ],
)
def test_concept_activation_message_is_not_learning_evidence(
    monkeypatch,
    initial_state,
    message,
):
    captured = {
        "evidence_calls": 0,
        "identified_concept": None,
    }

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
        lambda area, **kwargs: initial_state,
    )

    def fake_preview_activation(
        area,
        learner_state,
        identified_concept,
        **kwargs,
    ):
        captured["identified_concept"] = (
            identified_concept
        )

        return {
            **learner_state,
            "current_concept_id": identified_concept,
            "current_concept": "funções",
            "stage": "compreender",
            "mastery": 0.0,
        }

    monkeypatch.setattr(
        app_module.ProcessLearningTurn,
        "preview_activation",
        fake_preview_activation,
    )

    monkeypatch.setattr(
        app_module.ProcessLearningTurn,
        "preview_turn",
        lambda area,
        user_message,
        identified_concept,
        semantic_evidence,
        **kwargs: {
            "learner_state": {
                **initial_state,
                "current_concept_id":
                    identified_concept,
                "current_concept": "funções",
                "stage": "compreender",
                "mastery": 0.0,
            },
            "teaching_action": "explicar",
        },
    )

    monkeypatch.setattr(
        app_module.ProcessLearningTurn,
        "commit_turn",
        lambda *args, **kwargs: None,
    )

    def fake_build_evaluation(
        user_message,
        history,
        learner_state,
    ):
        captured["evidence_calls"] += 1
        return None

    monkeypatch.setattr(
        app_module.EvidenceEvaluator,
        "build_evaluation",
        fake_build_evaluation,
    )

    monkeypatch.setattr(
        app_module.TutorCore,
        "build_messages",
        lambda *args, **kwargs: [
            {
                "role": "user",
                "content": message,
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
                                    '{"concept_id":"ads.functions"}'
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
                "message": message,
                "history": [],
                "area": "ads",
            },
        )
    )

    response.get_data(
        as_text=True
    )

    assert response.status_code == 200

    assert (
        captured["identified_concept"]
        == "ads.functions"
    )

    assert captured["evidence_calls"] == 0
