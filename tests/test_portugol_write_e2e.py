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
    monkeypatch.setattr(database_module, "DATABASE_PATH", tmp_path / "portugol-write-e2e.db")
    monkeypatch.setattr(database_module, "DATA_DIR", tmp_path)
    database_module.init_database()
    monkeypatch.setattr(app_module, "verify_auth", lambda: True)
    monkeypatch.setattr(app_module, "GROQ_API_KEY", "teste")
    monkeypatch.setattr(app_module.LLMGateway, "PROVIDER_FACTORY", NoCallGroq)


def test_completed_skeleton_enters_and_completes_write_deterministically(monkeypatch, tmp_path):
    prepare(monkeypatch, tmp_path)
    ConceptProgress.update(
        "ads",
        "ads.algorithms.portugol_skeleton",
        mastery=0.8,
        last_evidence="Portfólio confirmado.",
    )
    LearnerState.update(
        "ads",
        current_concept_id="ads.algorithms.portugol_skeleton",
        stage="concluido",
        mastery=0.8,
        last_evidence="Portfólio confirmado.",
    )
    client = app_module.app.test_client()

    start = client.post(
        "/chat/stream",
        json={"message": "continuar", "area": "ads", "turn_id": "write-start"},
    ).get_data(as_text=True)
    start_turn = LearningHistory.find("write-start")
    start_task = LearningTask.find_by_source_turn("write-start")
    state = LearnerState.get("ads")

    assert '"done": true' in start.lower()
    assert state["current_concept_id"] == "ads.algorithms.portugol_write"
    assert state["stage"] == "compreender"
    assert state["mastery"] == 0.0
    assert "escreva" in start_turn["assistant_message"].lower()
    assert "leia" not in start_turn["assistant_message"].lower()
    assert start_task is not None
    assert start_task["concept_id"] == "ads.algorithms.portugol_write"
    assert EvidenceEvent.for_turn("write-start") is None

    journey = (
        ("write-answer-keyword", "escreva", "Pronto"),
        ("write-answer-effect", "Pronto", "Concluído"),
        ("write-answer-line", 'escreva("Concluído")', "algoritmo chamado"),
        (
            "write-answer-program",
            'algoritmo "saida"\ninicio\nescreva("OK")\nfimalgoritmo',
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
        assert evidence["concept_id"] == "ads.algorithms.portugol_write"
        assert evidence["outcome"] == "demonstrated"
        assert evidence["source"] == "deterministic_task"

    state = LearnerState.get("ads")
    assert state["stage"] == "concluido"
    assert state["mastery"] == 0.8
    assert LearningTask.find_by_source_turn("write-answer-program") is None
