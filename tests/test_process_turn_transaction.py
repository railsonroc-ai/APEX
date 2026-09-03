import pytest

import backend.database as database_module
import backend.services.process_learning_turn as turn_module
from backend.services.learner_state import LearnerState
from backend.services.process_learning_turn import ProcessLearningTurn


def test_finalize_rolls_back_state_when_progress_fails(
    monkeypatch,
    tmp_path,
):
    path = tmp_path / "learning-turn.db"

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

    LearnerState.update(
        "ads",
        current_concept="variáveis",
        stage="fixar",
        difficulty_count=0,
        mastery=0.7,
    )

    initial = LearnerState.get("ads")

    def fail_progress(*args, **kwargs):
        raise RuntimeError("falha simulada")

    monkeypatch.setattr(
        turn_module.ConceptProgress,
        "update",
        fail_progress,
    )

    evidence = {
        "outcome": "demonstrated",
        "confidence": 0.9,
        "evidence": "Aplicou corretamente.",
    }

    with pytest.raises(RuntimeError):
        ProcessLearningTurn.finalize(
            "ads",
            "Resposta correta.",
            initial,
            evidence,
        )

    restored = LearnerState.get("ads")

    assert restored["current_concept"] == "variáveis"
    assert restored["stage"] == "fixar"
    assert restored["mastery"] == 0.7
