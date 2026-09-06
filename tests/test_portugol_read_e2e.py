from types import SimpleNamespace

import backend.app as app_module
import backend.database as database_module
from backend.services.concept_progress import ConceptProgress
from backend.services.evidence_event import EvidenceEvent
from backend.services.learner_state import LearnerState
from backend.services.learning_history import LearningHistory
from backend.services.learning_task import LearningTask


class NoCallCompletions:
    def create(self, **kwargs):
        raise AssertionError("microconceito controlado não deve chamar a LLM")


class NoCallGroq:
    def __init__(self, **kwargs):
        self.chat = SimpleNamespace(completions=NoCallCompletions())


def prepare(monkeypatch, tmp_path):
    monkeypatch.setattr(database_module, "DATABASE_PATH", tmp_path / "portugol-read-e2e.db")
    monkeypatch.setattr(database_module, "DATA_DIR", tmp_path)
    database_module.init_database()
    monkeypatch.setattr(app_module, "verify_auth", lambda: True)
    monkeypatch.setattr(app_module, "GROQ_API_KEY", "teste")
    monkeypatch.setattr(app_module.LLMGateway, "PROVIDER_FACTORY", NoCallGroq)


def test_completed_write_enters_and_completes_read_deterministically(monkeypatch, tmp_path):
    prepare(monkeypatch, tmp_path)
    ConceptProgress.update(
        "ads",
        "ads.algorithms.portugol_write",
        mastery=0.8,
        last_evidence="Portfólio confirmado.",
    )
    LearnerState.update(
        "ads",
        current_concept_id="ads.algorithms.portugol_write",
        stage="concluido",
        mastery=0.8,
        last_evidence="Portfólio confirmado.",
    )
    client = app_module.app.test_client()

    start = client.post(
        "/chat/stream",
        json={"message": "continuar", "area": "ads", "turn_id": "read-start"},
    ).get_data(as_text=True)
    start_turn = LearningHistory.find("read-start")
    start_task = LearningTask.find_by_source_turn("read-start")
    state = LearnerState.get("ads")

    assert '"done": true' in start.lower()
    assert state["current_concept_id"] == "ads.algorithms.portugol_read"
    assert state["stage"] == "compreender"
    assert state["mastery"] == 0.0
    assert "leia" in start_turn["assistant_message"].lower()
    assert "variável" not in start_turn["assistant_message"].lower()
    assert start_task is not None
    assert start_task["concept_id"] == "ads.algorithms.portugol_read"
    assert EvidenceEvent.for_turn("read-start") is None

    journey = (
        ("read-answer-keyword", "leia", "entrada ou saída"),
        ("read-answer-role", "entrada", "complete somente a lacuna"),
        ("read-answer-place", "leia", "represente apenas a ordem"),
        (
            "read-answer-flow",
            'algoritmo "fluxo"; inicio; leia; escreva("OK"); fimalgoritmo',
            "fatia do percurso",
        ),
    )

    for turn_id, answer, expected_next in journey:
        body = client.post(
            "/chat/stream",
            json={"message": answer, "area": "ads", "turn_id": turn_id},
        ).get_data(as_text=True)
        turn = LearningHistory.find(turn_id)
        evidence = EvidenceEvent.for_turn(turn_id)

        assert '"done": true' in body.lower()
        assert turn["assistant_message"].startswith("Correto.\n\n")
        assert expected_next.lower() in turn["assistant_message"].lower()
        assert evidence["concept_id"] == "ads.algorithms.portugol_read"
        assert evidence["outcome"] == "demonstrated"
        assert evidence["source"] == "deterministic_task"

    state = LearnerState.get("ads")
    assert state["stage"] == "concluido"
    assert state["mastery"] == 0.8
    assert LearningTask.find_by_source_turn("read-answer-flow") is None
