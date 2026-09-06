import backend.database as database_module

from backend.services.learner_state import LearnerState
from backend.services.process_learning_turn import ProcessLearningTurn


def test_preview_does_not_persist_but_commit_does(
    monkeypatch,
    tmp_path,
):
    path = tmp_path / "preview-commit.db"

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

    preview = ProcessLearningTurn.preview_turn(
        area="ads",
        user_message="Quero aprender funções.",
        identified_concept="funções",
        semantic_evidence=None,
    )

    assert (
        preview["learner_state"]["current_concept"]
        == "funções"
    )

    after_preview = LearnerState.get("ads")

    assert after_preview["current_concept"] is None
    assert after_preview["updated_at"] is None

    committed = ProcessLearningTurn.commit_turn(
        area="ads",
        user_message="Quero aprender funções.",
        identified_concept="funções",
        semantic_evidence=None,
    )

    assert (
        committed["learner_state"]["current_concept"]
        == "funções"
    )

    after_commit = LearnerState.get("ads")

    assert after_commit["current_concept"] == "funções"
    assert after_commit["updated_at"] is not None


def test_commit_does_not_regrade_canonical_evidence(monkeypatch, tmp_path):
    """commit_turn must persist, not reinterpret, the already-decided outcome."""
    import backend.database as database_module
    from backend.services.evidence_event import EvidenceEvent
    from backend.services.learner_state import LearnerState

    path = tmp_path / "canonical-outcome.db"
    monkeypatch.setattr(database_module, "DATABASE_PATH", path)
    monkeypatch.setattr(database_module, "DATA_DIR", tmp_path)
    database_module.init_database()

    LearnerState.update(
        "ads",
        current_concept_id="ads.algorithms.goal_result",
        current_concept="objetivo e resultado de uma sequência",
        stage="compreender",
        mastery=0.6,
        difficulty_count=0,
    )

    task = (
        "escreva somente o resultado esperado de organizar uma mochila "
        "para a aula, começando com Resultado:."
    )
    answer = "Resultado: mochila organizada para a aula."
    canonical = {
        "outcome": "partial",
        "confidence": 0.95,
        "evidence": "Veredito canônico de teste.",
    }

    ProcessLearningTurn.commit_turn(
        area="ads",
        user_message=answer,
        identified_concept=None,
        semantic_evidence=canonical,
        turn_id="canonical-outcome-turn",
        assistant_message="Parcialmente correto.\n\nTarefa: " + task,
        evidence_context={
            "concept_id": "ads.algorithms.goal_result",
            "concept": "objetivo e resultado de uma sequência",
            "stage": "compreender",
            "tutor_message": task,
            "student_answer": answer,
        },
        task_prompt=task,
    )

    event = EvidenceEvent.for_turn("canonical-outcome-turn")
    assert event is not None
    assert event["outcome"] == "partial"
