from threading import Event, Thread
from types import SimpleNamespace

import backend.app as app_module
import backend.database as database_module
from backend.services.learning_turn_lease import LearningTurnLease


def prepare_database(monkeypatch, tmp_path):
    path = tmp_path / "server-serialization.db"

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


def prepare_turn(monkeypatch, learner_state):
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


def test_concurrent_server_turn_is_rejected_before_llm(
    monkeypatch,
    tmp_path,
):
    prepare_database(monkeypatch, tmp_path)

    learner_state = {
        "area": "ads",
        "current_concept": "variáveis",
        "stage": "testar",
        "last_evidence": None,
        "difficulty_count": 0,
        "mastery": 0.5,
        "updated_at": None,
    }
    prepare_turn(monkeypatch, learner_state)

    started = Event()
    finish = Event()
    captured = {
        "llm_streams": 0,
        "commits": 0,
    }

    class BlockingStream:
        def __iter__(self):
            started.set()

            if not finish.wait(timeout=5):
                raise RuntimeError(
                    "teste excedeu o tempo de espera"
                )

            yield SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        delta=SimpleNamespace(
                            content="Resposta confirmada."
                        )
                    )
                ]
            )

    class BlockingCompletions:
        def create(self, **kwargs):
            captured["llm_streams"] += 1
            return BlockingStream()

    class BlockingGroq:
        def __init__(self, **kwargs):
            self.chat = SimpleNamespace(
                completions=BlockingCompletions()
            )

    def commit_turn(*args, **kwargs):
        captured["commits"] += 1
        return {
            "learner_state": learner_state,
            "teaching_action": "testar",
        }

    monkeypatch.setattr(
        app_module,
        "Groq",
        BlockingGroq,
    )
    monkeypatch.setattr(
        app_module.ProcessLearningTurn,
        "commit_turn",
        commit_turn,
    )

    first_result = {}

    def run_first_turn():
        response = app_module.app.test_client().post(
            "/chat/stream",
            json={
                "message": "Primeira resposta.",
                "area": "ads",
                "turn_id": "concurrent-turn-1",
            },
        )
        first_result["body"] = response.get_data(
            as_text=True
        )

    first_thread = Thread(
        target=run_first_turn
    )
    first_thread.start()

    assert started.wait(timeout=5)

    second_response = app_module.app.test_client().post(
        "/chat/stream",
        json={
            "message": "Segunda resposta.",
            "area": "ads",
            "turn_id": "concurrent-turn-2",
        },
    )
    second_body = second_response.get_data(
        as_text=True
    )

    assert "Já existe um turno" in second_body
    assert '"done": true' not in second_body.lower()
    assert captured["llm_streams"] == 1

    finish.set()
    first_thread.join(timeout=5)

    assert not first_thread.is_alive()
    assert '"done": true' in first_result["body"].lower()
    assert captured["commits"] == 1
    assert LearningTurnLease.get("ads") is None


def test_turn_is_rechecked_after_lease_acquisition(
    monkeypatch,
    tmp_path,
):
    prepare_database(monkeypatch, tmp_path)

    calls = {"find": 0}

    def find_turn(turn_id):
        calls["find"] += 1

        if calls["find"] == 1:
            return None

        return {
            "turn_id": turn_id,
            "area": "ads",
            "user_message": "Mesma pergunta",
            "assistant_message": "Resposta já confirmada.",
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
        app_module.LearningHistory,
        "find",
        find_turn,
    )

    class ForbiddenGroq:
        def __init__(self, **kwargs):
            raise AssertionError(
                "replay não deve chamar o LLM"
            )

    monkeypatch.setattr(
        app_module,
        "Groq",
        ForbiddenGroq,
    )

    response = app_module.app.test_client().post(
        "/chat/stream",
        json={
            "message": "Mesma pergunta",
            "area": "ads",
            "turn_id": "race-replay-turn",
        },
    )
    body = response.get_data(as_text=True)

    assert calls["find"] == 2
    assert "Resposta já confirmada." in body
    assert '"done": true' in body.lower()
    assert LearningTurnLease.get("ads") is None


def test_lease_is_released_when_stream_fails(
    monkeypatch,
    tmp_path,
):
    prepare_database(monkeypatch, tmp_path)

    learner_state = {
        "area": "ads",
        "current_concept": "variáveis",
        "stage": "testar",
        "last_evidence": None,
        "difficulty_count": 0,
        "mastery": 0.5,
        "updated_at": None,
    }
    prepare_turn(monkeypatch, learner_state)

    class BrokenStream:
        def __iter__(self):
            raise RuntimeError(
                "falha simulada"
            )

    class BrokenCompletions:
        def create(self, **kwargs):
            return BrokenStream()

    class BrokenGroq:
        def __init__(self, **kwargs):
            self.chat = SimpleNamespace(
                completions=BrokenCompletions()
            )

    monkeypatch.setattr(
        app_module,
        "Groq",
        BrokenGroq,
    )

    response = app_module.app.test_client().post(
        "/chat/stream",
        json={
            "message": "Resposta do aluno.",
            "area": "ads",
            "turn_id": "broken-lease-turn",
        },
    )
    body = response.get_data(as_text=True)

    assert '"error"' in body.lower()
    assert '"done": true' not in body.lower()
    assert LearningTurnLease.get("ads") is None
