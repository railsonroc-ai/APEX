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
    assert second_message.startswith("Correto.\n\n")
    assert "guardar um arquivo" in second_message.lower()
    assert LearnerState.get("ads")["stage"] == "fixar"
    assert LearnerState.get("ads")["mastery"] == 0.2
    assert evidence["outcome"] == "demonstrated"
    assert evidence["source"] == "deterministic_task"


def test_known_ordered_steps_journey_never_needs_llm_evaluation(
    monkeypatch,
    tmp_path,
):
    prepare(monkeypatch, tmp_path)
    client = app_module.app.test_client()
    monkeypatch.setattr(app_module.LLMGateway, "PROVIDER_FACTORY", NoCallGroq)
    client.post(
        "/chat/stream",
        json={
            "message": "Quero recomeçar lógica de programação do zero",
            "area": "ads",
            "turn_id": "known-journey-start",
        },
    ).get_data(as_text=True)

    answers = (
        (
            "known-journey-hands",
            "abrir a torneira; lavar as mãos; secar as mãos",
            "guardar um arquivo",
        ),
        (
            "known-journey-file",
            "abrir o menu Arquivo; selecionar Salvar como; "
            "escolher o local e confirmar o salvamento",
            "abrir a conversa",
        ),
        (
            "known-journey-message",
            "abrir a conversa; escrever a mensagem; clicar em Enviar",
            "pegar o copo",
        ),
        (
            "known-journey-cup",
            "pegar o copo; beber a água; guardar o copo",
            "envie continuar",
        ),
    )

    for turn_id, answer, expected_next in answers:
        response = client.post(
            "/chat/stream",
            json={"message": answer, "area": "ads", "turn_id": turn_id},
        )
        body = response.get_data(as_text=True)
        message = LearningHistory.find(turn_id)["assistant_message"]
        evidence = EvidenceEvent.for_turn(turn_id)

        assert '"done": true' in body.lower()
        assert message.startswith("Correto.\n\n")
        assert expected_next.lower() in message.lower()
        assert evidence["outcome"] == "demonstrated"
        assert evidence["source"] == "deterministic_task"

    state = LearnerState.get("ads")
    assert state["stage"] == "concluido"
    assert state["mastery"] == 0.8
    assert LearningTask.find_by_source_turn("known-journey-cup") is None


def test_completed_first_node_advances_to_goal_result_and_completes_locally(
    monkeypatch,
    tmp_path,
):
    prepare(monkeypatch, tmp_path)
    monkeypatch.setattr(app_module.LLMGateway, "PROVIDER_FACTORY", NoCallGroq)
    ConceptProgress.update(
        "ads",
        "ads.algorithms.ordered_steps",
        mastery=0.8,
        last_evidence="Portfólio confirmado.",
    )
    LearnerState.update(
        "ads",
        current_concept_id="ads.algorithms.ordered_steps",
        stage="concluido",
        mastery=0.8,
        last_evidence="Portfólio confirmado.",
    )
    client = app_module.app.test_client()

    started = client.post(
        "/chat/stream",
        json={
            "message": "continuar",
            "area": "ads",
            "turn_id": "goal-result-start",
        },
    ).get_data(as_text=True)
    start_turn = LearningHistory.find("goal-result-start")
    start_task = LearningTask.find_by_source_turn("goal-result-start")

    assert '"done": true' in started.lower()
    assert "resultado esperado" in start_turn["assistant_message"].lower()
    assert start_turn["concept_id"] == "ads.algorithms.goal_result"
    assert start_task["concept_id"] == "ads.algorithms.goal_result"
    assert EvidenceEvent.for_turn("goal-result-start") is None
    assert LearnerState.get("ads")["mastery"] == 0.0

    answers = (
        ("goal-choice", "A", "salvar um documento"),
        (
            "goal-document",
            "Resultado: documento salvo no local escolhido.",
            "lavar a louça",
        ),
        (
            "goal-dishes",
            "Resultado: louça limpa e guardada.",
            "organizar uma mochila",
        ),
        (
            "goal-backpack",
            "Resultado: mochila organizada com os materiais da aula.",
            "próxima microcompetência ainda não está disponível",
        ),
    )

    for turn_id, answer, expected_next in answers:
        body = client.post(
            "/chat/stream",
            json={"message": answer, "area": "ads", "turn_id": turn_id},
        ).get_data(as_text=True)
        turn = LearningHistory.find(turn_id)
        evidence = EvidenceEvent.for_turn(turn_id)

        assert '"done": true' in body.lower()
        assert turn["assistant_message"].startswith("Correto.\n\n")
        assert expected_next.lower() in turn["assistant_message"].lower()
        assert evidence["concept_id"] == "ads.algorithms.goal_result"
        assert evidence["outcome"] == "demonstrated"
        assert evidence["source"] == "deterministic_task"

    state = LearnerState.get("ads")
    first_progress = ConceptProgress.get(
        "ads",
        "ads.algorithms.ordered_steps",
    )
    assert state["current_concept_id"] == "ads.algorithms.goal_result"
    assert state["stage"] == "concluido"
    assert state["mastery"] == 0.8
    assert first_progress["mastery"] == 0.8
    assert LearningTask.find_by_source_turn("goal-backpack") is None

    end = client.post(
        "/chat/stream",
        json={"message": "continuar", "area": "ads", "turn_id": "goal-end"},
    ).get_data(as_text=True)
    end_turn = LearningHistory.find("goal-end")

    assert '"done": true' in end.lower()
    assert "próxima microcompetência ainda não está disponível" in end_turn[
        "assistant_message"
    ].lower()
    assert LearnerState.get("ads")["current_concept_id"] == (
        "ads.algorithms.goal_result"
    )
    assert LearningTask.find_by_source_turn("goal-end") is None


def test_acknowledgement_does_not_advance_goal_result(monkeypatch, tmp_path):
    prepare(monkeypatch, tmp_path)
    monkeypatch.setattr(app_module.LLMGateway, "PROVIDER_FACTORY", NoCallGroq)
    LearnerState.update(
        "ads",
        current_concept_id="ads.algorithms.ordered_steps",
        stage="concluido",
        mastery=0.8,
    )
    client = app_module.app.test_client()
    client.post(
        "/chat/stream",
        json={
            "message": "continuar",
            "area": "ads",
            "turn_id": "goal-ack-start",
        },
    ).get_data(as_text=True)

    body = client.post(
        "/chat/stream",
        json={"message": "entendi", "area": "ads", "turn_id": "goal-ack"},
    ).get_data(as_text=True)
    state = LearnerState.get("ads")
    turn = LearningHistory.find("goal-ack")

    assert '"done": true' in body.lower()
    assert turn["assistant_message"].startswith(
        "Ainda não há evidência suficiente.\n\n"
    )
    assert state["current_concept_id"] == "ads.algorithms.goal_result"
    assert state["stage"] == "compreender"
    assert state["mastery"] == 0.0


def test_short_acknowledgement_does_not_advance_the_first_task(monkeypatch, tmp_path):
    prepare(monkeypatch, tmp_path)
    monkeypatch.setattr(app_module.LLMGateway, "PROVIDER_FACTORY", NoCallGroq)
    client = app_module.app.test_client()
    client.post(
        "/chat/stream",
        json={
            "message": "Quero recomeçar lógica de programação do zero",
            "area": "ads",
            "turn_id": "guard-ack-start",
        },
    ).get_data(as_text=True)

    monkeypatch.setattr(app_module.LLMGateway, "PROVIDER_FACTORY", TutorOnlyGroq)
    response = client.post(
        "/chat/stream",
        json={"message": "entendi", "area": "ads", "turn_id": "guard-ack"},
    )
    body = response.get_data(as_text=True)
    state = LearnerState.get("ads")
    evidence = EvidenceEvent.for_turn("guard-ack")
    message = LearningHistory.find("guard-ack")["assistant_message"]

    assert '"done": true' in body.lower()
    assert message.startswith("Ainda não há evidência suficiente.\n\n")
    assert state["stage"] == "compreender"
    assert state["mastery"] == 0.0
    assert evidence["outcome"] == "insufficient"


def test_first_wrong_answer_reorients_without_delivering_the_solution(monkeypatch, tmp_path):
    prepare(monkeypatch, tmp_path)
    monkeypatch.setattr(app_module.LLMGateway, "PROVIDER_FACTORY", NoCallGroq)
    client = app_module.app.test_client()
    client.post(
        "/chat/stream",
        json={
            "message": "Quero recomeçar lógica de programação do zero",
            "area": "ads",
            "turn_id": "guard-wrong-start",
        },
    ).get_data(as_text=True)

    monkeypatch.setattr(app_module.LLMGateway, "PROVIDER_FACTORY", TutorOnlyGroq)
    client.post(
        "/chat/stream",
        json={
            "message": "Secar as mãos, abrir a torneira e lavar as mãos.",
            "area": "ads",
            "turn_id": "guard-wrong-answer",
        },
    ).get_data(as_text=True)
    state = LearnerState.get("ads")
    message = LearningHistory.find("guard-wrong-answer")["assistant_message"]
    assistance = AssistanceEvent.for_turn("guard-wrong-answer")

    assert message.startswith("Ainda não está correto.\n\n")
    assert "a ordem é abrir" not in message.lower()
    assert state["stage"] == "corrigir"
    assert state["difficulty_count"] == 1
    assert assistance["assistance_level"] == "guided"


def test_answer_plus_difficulty_is_evaluated_before_reorientation(monkeypatch, tmp_path):
    prepare(monkeypatch, tmp_path)
    monkeypatch.setattr(app_module.LLMGateway, "PROVIDER_FACTORY", NoCallGroq)
    client = app_module.app.test_client()
    client.post(
        "/chat/stream",
        json={
            "message": "Quero recomeçar lógica de programação do zero",
            "area": "ads",
            "turn_id": "guard-mixed-start",
        },
    ).get_data(as_text=True)

    monkeypatch.setattr(app_module.LLMGateway, "PROVIDER_FACTORY", TutorOnlyGroq)
    client.post(
        "/chat/stream",
        json={
            "message": (
                "Abrir a torneira, lavar as mãos e secar as mãos, "
                "mas não entendi o motivo."
            ),
            "area": "ads",
            "turn_id": "guard-mixed-answer",
        },
    ).get_data(as_text=True)
    state = LearnerState.get("ads")
    evidence = EvidenceEvent.for_turn("guard-mixed-answer")
    message = LearningHistory.find("guard-mixed-answer")["assistant_message"]

    assert evidence["outcome"] == "demonstrated"
    assert message.startswith("Correto.\n\n")
    assert state["stage"] == "corrigir"
    assert state["difficulty_count"] == 1


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
