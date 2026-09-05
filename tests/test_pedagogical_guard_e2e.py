import json
from types import SimpleNamespace

import backend.app as app_module
import backend.database as database_module
from backend.services.assistance_event import AssistanceEvent
from backend.services.concept_progress import ConceptProgress
from backend.services.evidence_event import EvidenceEvent
from backend.services.learner_state import LearnerState
from backend.services.learning_history import LearningHistory
from backend.services.learning_task import LearningTask


class NoCallCompletions:
    def create(self, **kwargs):
        raise AssertionError("o primeiro microturno não deve chamar o LLM")


class NoCallGroq:
    def __init__(self, **kwargs):
        self.chat = SimpleNamespace(completions=NoCallCompletions())


class BadCompletions:
    def create(self, **kwargs):
        if kwargs.get("stream") is False:
            return SimpleNamespace(choices=[])
        return [SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(
            content="Agora use variável e Python. Tarefa: escreva código com if."
        ))])]


class BadGroq:
    def __init__(self, **kwargs):
        self.chat = SimpleNamespace(completions=BadCompletions())


class TutorOnlyCompletions:
    def create(self, **kwargs):
        if kwargs.get("stream") is False:
            raise AssertionError("a tarefa objetiva não deve chamar o avaliador LLM")
        return [SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(
            content="Agora use variável e Python. Tarefa: escreva código com if."
        ))])]


class TutorOnlyGroq:
    def __init__(self, **kwargs):
        self.chat = SimpleNamespace(completions=TutorOnlyCompletions())


class InvalidEvidenceCompletions:
    def create(self, **kwargs):
        if kwargs.get("stream") is True:
            raise AssertionError("o tutor não deve responder sem avaliação válida")
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
            content="não foi possível produzir a rubrica"
        ))])


class InvalidEvidenceGroq:
    def __init__(self, **kwargs):
        self.chat = SimpleNamespace(completions=InvalidEvidenceCompletions())


def prepare(monkeypatch, tmp_path):
    monkeypatch.setattr(database_module, "DATABASE_PATH", tmp_path / "guard.db")
    monkeypatch.setattr(database_module, "DATA_DIR", tmp_path)
    database_module.init_database()
    monkeypatch.setattr(app_module, "verify_auth", lambda: True)
    monkeypatch.setattr(app_module, "GROQ_API_KEY", "teste")


def test_restart_logic_from_zero_activates_first_microconcept(monkeypatch, tmp_path):
    prepare(monkeypatch, tmp_path)
    monkeypatch.setattr(app_module.LLMGateway, "PROVIDER_FACTORY", NoCallGroq)
    response = app_module.app.test_client().post(
        "/chat/stream",
        json={
            "message": "Quero recomeçar lógica de programação do zero",
            "area": "ads",
            "turn_id": "guard-start",
        },
    )
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert '"done": true' in body.lower()
    assert "variável" not in body.lower()
    assert "python" not in body.lower()
    assert LearnerState.get("ads")["current_concept_id"] == "ads.algorithms.ordered_steps"
    task = LearningTask.find_by_source_turn("guard-start")
    assert task is not None
    assert task["prompt_text"] in LearningHistory.find("guard-start")["assistant_message"]
    assert AssistanceEvent.for_turn("guard-start")["assistance_level"] == "guided"


def test_correct_first_answer_advances_and_never_repeats_first_turn(monkeypatch, tmp_path):
    prepare(monkeypatch, tmp_path)
    monkeypatch.setattr(app_module.LLMGateway, "PROVIDER_FACTORY", NoCallGroq)
    client = app_module.app.test_client()
    first = client.post(
        "/chat/stream",
        json={
            "message": "Quero recomeçar lógica de programação do zero",
            "area": "ads",
            "turn_id": "guard-sequence-start",
        },
    ).get_data(as_text=True)

    monkeypatch.setattr(app_module.LLMGateway, "PROVIDER_FACTORY", TutorOnlyGroq)
    second = client.post(
        "/chat/stream",
        json={
            "message": "Primeiro abrir a torneira, depois lavar e por último secar.",
            "area": "ads",
            "turn_id": "guard-sequence-answer",
        },
    ).get_data(as_text=True)

    first_message = LearningHistory.find("guard-sequence-start")["assistant_message"]
    second_message = LearningHistory.find("guard-sequence-answer")["assistant_message"]
    evidence = EvidenceEvent.for_turn("guard-sequence-answer")

    assert '"done": true' in second.lower()
    assert second_message != first_message
    assert "guardar um arquivo" in second_message.lower()
    assert LearnerState.get("ads")["stage"] == "fixar"
    assert LearnerState.get("ads")["mastery"] == 0.2
    assert evidence["outcome"] == "demonstrated"
    assert evidence["source"] == "deterministic_task"


def test_unavailable_evaluator_never_repeats_or_commits_as_if_answered(
    monkeypatch,
    tmp_path,
):
    prepare(monkeypatch, tmp_path)
    monkeypatch.setattr(app_module.LLMGateway, "PROVIDER_FACTORY", NoCallGroq)
    client = app_module.app.test_client()
    client.post(
        "/chat/stream",
        json={
            "message": "Quero recomeçar lógica de programação do zero",
            "area": "ads",
            "turn_id": "guard-unavailable-start",
        },
    ).get_data(as_text=True)

    monkeypatch.setattr(
        app_module.EvidenceEvaluator,
        "evaluate_objective_task",
        lambda evaluation: None,
    )
    monkeypatch.setattr(
        app_module.LLMGateway,
        "PROVIDER_FACTORY",
        InvalidEvidenceGroq,
    )
    response = client.post(
        "/chat/stream",
        json={
            "message": "Abrir a torneira, lavar as mãos e secar as mãos.",
            "area": "ads",
            "turn_id": "guard-unavailable-answer",
        },
    )
    body = response.get_data(as_text=True)

    assert "não foi possível avaliar" in body.lower()
    assert '"done": true' not in body.lower()
    assert LearningHistory.find("guard-unavailable-answer") is None
    assert LearnerState.get("ads")["stage"] == "compreender"


def test_invalid_provider_text_never_reaches_screen_or_history(monkeypatch, tmp_path):
    prepare(monkeypatch, tmp_path)
    LearnerState.update(
        "ads",
        current_concept_id="ads.algorithms.ordered_steps",
        stage="compreender",
    )
    monkeypatch.setattr(app_module.LLMGateway, "PROVIDER_FACTORY", BadGroq)
    response = app_module.app.test_client().post(
        "/chat/stream",
        json={"message": "continue", "area": "ads", "turn_id": "guard-bad"},
    )
    body = response.get_data(as_text=True)
    committed = LearningHistory.find("guard-bad")["assistant_message"]

    assert "variável" not in body.lower()
    assert "python" not in body.lower()
    assert "variável" not in committed.lower()
    assert "python" not in committed.lower()
    displayed = "".join(
        json.loads(line[6:]).get("token", "")
        for line in body.splitlines()
        if line.startswith("data: ")
    )
    assert displayed == committed


def test_restart_clears_mastery_difficulty_and_review_schedule(monkeypatch, tmp_path):
    prepare(monkeypatch, tmp_path)
    ConceptProgress.update(
        "ads",
        "ads.algorithms.ordered_steps",
        mastery=0.9,
        difficulty_count=4,
        last_evidence="antiga",
        review_count=3,
        next_review_at="2030-01-01 00:00:00",
        last_reviewed_at="2029-01-01 00:00:00",
    )
    monkeypatch.setattr(app_module.LLMGateway, "PROVIDER_FACTORY", NoCallGroq)
    response = app_module.app.test_client().post(
        "/chat/stream",
        json={
            "message": "Quero recomeçar lógica do zero",
            "area": "ads",
            "turn_id": "guard-reset",
        },
    )
    response.get_data(as_text=True)
    progress = ConceptProgress.get("ads", "ads.algorithms.ordered_steps")

    assert progress["mastery"] == 0.0
    assert progress["difficulty_count"] == 0
    assert progress["last_evidence"] is None
    assert progress["review_count"] == 0
    assert progress["next_review_at"] is None
    assert progress["last_reviewed_at"] is None
