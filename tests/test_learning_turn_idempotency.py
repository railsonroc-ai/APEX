import pytest

import backend.database as database_module

from backend.services.learner_state import LearnerState
from backend.services.process_learning_turn import ProcessLearningTurn


def prepare_database(
    monkeypatch,
    tmp_path,
):
    path = tmp_path / "idempotency.db"

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


def demonstrated_evidence():
    return {
        "outcome": "demonstrated",
        "confidence": 0.95,
        "evidence": "Resposta correta.",
    }


def test_same_turn_id_does_not_apply_evidence_twice(
    monkeypatch,
    tmp_path,
):
    prepare_database(
        monkeypatch,
        tmp_path,
    )

    evidence = demonstrated_evidence()

    ProcessLearningTurn.commit_turn(
        area="ads",
        user_message="Uma variável guarda um valor.",
        identified_concept="variáveis",
        semantic_evidence=evidence,
        turn_id="turn-001",
        assistant_message="Próxima orientação.",
    )

    after_first = LearnerState.get("ads")

    result = ProcessLearningTurn.commit_turn(
        area="ads",
        user_message="Uma variável guarda um valor.",
        identified_concept="variáveis",
        semantic_evidence=evidence,
        turn_id="turn-001",
    )

    after_second = LearnerState.get("ads")

    assert result["duplicate"] is True

    assert (
        after_second["mastery"]
        == after_first["mastery"]
    )

    assert (
        after_second["difficulty_count"]
        == after_first["difficulty_count"]
    )

    assert (
        after_second["last_evidence"]
        == after_first["last_evidence"]
    )


def test_turn_id_cannot_be_reused_for_different_message(
    monkeypatch,
    tmp_path,
):
    prepare_database(
        monkeypatch,
        tmp_path,
    )

    ProcessLearningTurn.commit_turn(
        area="ads",
        user_message="Uma variável guarda um valor.",
        identified_concept="variáveis",
        semantic_evidence=demonstrated_evidence(),
        turn_id="turn-002",
        assistant_message="Próxima orientação.",
    )

    with pytest.raises(
        ValueError,
        match="turn_id reutilizado",
    ):
        ProcessLearningTurn.commit_turn(
            area="ads",
            user_message="Agora quero responder outra coisa.",
            identified_concept="variáveis",
            semantic_evidence=demonstrated_evidence(),
            turn_id="turn-002",
        )


def test_new_turn_requires_confirmed_assistant_response(
    monkeypatch,
    tmp_path,
):
    prepare_database(
        monkeypatch,
        tmp_path,
    )

    before = LearnerState.get("ads")

    with pytest.raises(
        ValueError,
        match="assistant_message obrigatória",
    ):
        ProcessLearningTurn.commit_turn(
            area="ads",
            user_message="Uma variável guarda um valor.",
            identified_concept="variáveis",
            semantic_evidence=demonstrated_evidence(),
            turn_id="turn-without-response",
            assistant_message="   ",
        )

    after = LearnerState.get("ads")

    assert after == before
