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
