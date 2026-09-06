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
    monkeypatch.setattr(database_module, "DATABASE_PATH", tmp_path / "integer-declaration-e2e.db")
    monkeypatch.setattr(database_module, "DATA_DIR", tmp_path)
    database_module.init_database()
    monkeypatch.setattr(app_module, "verify_auth", lambda: True)
    monkeypatch.setattr(app_module, "GROQ_API_KEY", "teste")
    monkeypatch.setattr(app_module.LLMGateway, "PROVIDER_FACTORY", NoCallGroq)


def test_completed_variable_storage_enters_and_completes_integer_declaration(monkeypatch, tmp_path):
    prepare(monkeypatch, tmp_path)
    ConceptProgress.update(
        "ads",
        "ads.algorithms.variable_storage",
        mastery=0.8,
        last_evidence="Portfólio confirmado.",
    )
    LearnerState.update(
        "ads",
        current_concept_id="ads.algorithms.variable_storage",
        stage="concluido",
        mastery=0.8,
        last_evidence="Portfólio confirmado.",
    )
    client = app_module.app.test_client()

    start = client.post(
        "/chat/stream",
        json={"message": "continuar", "area": "ads", "turn_id": "declaration-start"},
    ).get_data(as_text=True)
    start_turn = LearningHistory.find("declaration-start")
    start_task = LearningTask.find_by_source_turn("declaration-start")
    state = LearnerState.get("ads")

    assert '"done": true' in start.lower()
    assert state["current_concept_id"] == "ads.algorithms.integer_declaration"
    assert state["stage"] == "compreender"
    assert state["mastery"] == 0.0
    first_text = start_turn["assistant_message"].lower()
    assert "var" in first_text
    assert "inteiro" not in first_text
    assert "leia" not in first_text
    assert "escreva" not in first_text
    assert start_task is not None
    assert start_task["concept_id"] == "ads.algorithms.integer_declaration"
    assert EvidenceEvent.for_turn("declaration-start") is None

    journey = (
        ("declaration-answer-var", "var", "números sem parte decimal"),
        ("declaration-answer-type", "inteiro", "variável pontos"),
        ("declaration-answer-line", "pontos: inteiro", "coloque em ordem estes elementos"),
        (
            "declaration-answer-block",
            'algoritmo "conta"; var; saldo: inteiro; inicio; fimalgoritmo',
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
        assert evidence["concept_id"] == "ads.algorithms.integer_declaration"
        assert evidence["outcome"] == "demonstrated"
        assert evidence["source"] == "deterministic_task"

    state = LearnerState.get("ads")
    assert state["stage"] == "concluido"
    assert state["mastery"] == 0.8
    assert LearningTask.find_by_source_turn("declaration-answer-block") is None
