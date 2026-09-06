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
    monkeypatch.setattr(database_module, "DATABASE_PATH", tmp_path / "structured-e2e.db")
    monkeypatch.setattr(database_module, "DATA_DIR", tmp_path)
    database_module.init_database()
    monkeypatch.setattr(app_module, "verify_auth", lambda: True)
    monkeypatch.setattr(app_module, "GROQ_API_KEY", "teste")
    monkeypatch.setattr(app_module.LLMGateway, "PROVIDER_FACTORY", NoCallGroq)


def test_completed_ipo_advances_to_structured_sequence_and_first_answer_is_deterministic(
    monkeypatch,
    tmp_path,
):
    prepare(monkeypatch, tmp_path)
    ConceptProgress.update(
        "ads",
        "ads.algorithms.input_process_output",
        mastery=0.8,
        last_evidence="Portfólio confirmado.",
    )
    LearnerState.update(
        "ads",
        current_concept_id="ads.algorithms.input_process_output",
        stage="concluido",
        mastery=0.8,
        last_evidence="Portfólio confirmado.",
    )
    client = app_module.app.test_client()

    start = client.post(
        "/chat/stream",
        json={"message": "continuar", "area": "ads", "turn_id": "structured-start"},
    ).get_data(as_text=True)
    start_turn = LearningHistory.find("structured-start")
    start_task = LearningTask.find_by_source_turn("structured-start")
    start_state = LearnerState.get("ads")

    assert '"done": true' in start.lower()
    assert start_state["current_concept_id"] == "ads.algorithms.structured_sequence"
    assert start_state["stage"] == "compreender"
    assert start_state["mastery"] == 0.0
    assert "código" not in start_turn["assistant_message"].lower()
    assert "programação" not in start_turn["assistant_message"].lower()
    assert "usando 1, 2 e 3" in start_turn["assistant_message"].lower()
    assert start_task is not None
    assert start_task["concept_id"] == "ads.algorithms.structured_sequence"
    assert EvidenceEvent.for_turn("structured-start") is None

    answer = client.post(
        "/chat/stream",
        json={
            "message": "1 pegar o pão; 2 colocar o pão na torradeira; 3 retirar a torrada.",
            "area": "ads",
            "turn_id": "structured-first-answer",
        },
    ).get_data(as_text=True)
    turn = LearningHistory.find("structured-first-answer")
    evidence = EvidenceEvent.for_turn("structured-first-answer")
    state = LearnerState.get("ads")

    assert '"done": true' in answer.lower()
    assert turn["assistant_message"].startswith("Correto.\n\n")
    assert "INÍCIO" in turn["assistant_message"]
    assert evidence["concept_id"] == "ads.algorithms.structured_sequence"
    assert evidence["outcome"] == "demonstrated"
    assert evidence["source"] == "deterministic_task"
    assert state["mastery"] == 0.2
