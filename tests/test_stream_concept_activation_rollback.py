from types import SimpleNamespace

import backend.app as app_module
import backend.database as database_module
from backend.services.learner_state import LearnerState


class BrokenStream:
    def __iter__(self):
        raise RuntimeError(
            "falha simulada após ativação"
        )


class FakeCompletions:
    def create(self, **kwargs):
        if kwargs.get("stream") is False:
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(
                            content='{"concept_id":"ads.functions"}'
                        )
                    )
                ]
            )

        return BrokenStream()


class FakeGroq:
    def __init__(self, **kwargs):
        self.chat = SimpleNamespace(
            completions=FakeCompletions()
        )


def test_stream_failure_rolls_back_new_concept_activation(
    monkeypatch,
    tmp_path,
):
    path = tmp_path / "activation-rollback.db"

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
        app_module.LLMGateway,
        "PROVIDER_FACTORY",
        FakeGroq,
    )

    response = app_module.app.test_client().post(
        "/chat/stream",
        json={
            "message":
                "Quero aprender funções.",
            "history": [],
            "area": "ads",
        },
    )

    body = response.get_data(
        as_text=True
    )

    assert '"error"' in body

    state = LearnerState.get("ads")

    assert state["current_concept_id"] is None
    assert state["current_concept"] is None
    assert state["mastery"] == 0.0
    assert state["updated_at"] is None
