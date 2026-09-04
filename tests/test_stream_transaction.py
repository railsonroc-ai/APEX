from types import SimpleNamespace

import backend.app as app_module
import backend.database as database_module
from backend.services.concept_progress import ConceptProgress
from backend.services.learner_state import LearnerState
from backend.services.learning_history import LearningHistory


class BrokenStream:
    def __iter__(self):
        raise RuntimeError("falha simulada no streaming")


class FakeCompletions:
    def create(self, **kwargs):
        if kwargs.get("stream") is False:
            content = (
                '{"criteria":{"task_response":"met",'
                '"conceptual_correctness":"met",'
                '"understanding_application":"met"},'
                '"confidence":0.9,"evidence":"Aplicou corretamente."}'
            )
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content=content)
                    )
                ]
            )

        return BrokenStream()


class FakeGroq:
    def __init__(self, **kwargs):
        self.chat = SimpleNamespace(
            completions=FakeCompletions()
        )


def test_stream_failure_rolls_back_learning_turn(
    monkeypatch,
    tmp_path,
):
    path = tmp_path / "stream-rollback.db"

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

    LearnerState.update(
        "ads",
        current_concept="variáveis",
        stage="fixar",
        mastery=0.7,
        difficulty_count=0,
    )

    ConceptProgress.update(
        "ads",
        "variáveis",
        mastery=0.7,
        difficulty_count=0,
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
    monkeypatch.setattr(
        app_module,
        "Groq",
        FakeGroq,
    )

    response = app_module.app.test_client().post(
        "/chat/stream",
        json={
            "message": "Resolvi corretamente.",
            "history": [
                {
                    "role": "assistant",
                    "content": "Aplique o conceito.",
                }
            ],
            "area": "ads",
            "turn_id": "broken-stream-turn",
        },
    )

    body = response.get_data(as_text=True)

    assert '"error"' in body

    state = LearnerState.get("ads")
    progress = ConceptProgress.get(
        "ads",
        "variáveis",
    )

    assert state["stage"] == "fixar"
    assert state["mastery"] == 0.7
    assert progress["mastery"] == 0.7
    assert (
        LearningHistory.find(
            "broken-stream-turn"
        )
        is None
    )
