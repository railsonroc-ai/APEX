import sqlite3

import pytest

import backend.database as database_module
from backend.identity import DEFAULT_STUDENT_ID, default_session_id
from backend.services.evidence_evaluator import EvidenceEvaluator
from backend.services.learner_state import LearnerState
from backend.services.learning_session_lifecycle import LearningSessionLifecycle
from backend.services.learning_task import LearningTask
from backend.services.process_learning_turn import ProcessLearningTurn


pytestmark = [pytest.mark.e2e, pytest.mark.reliability]


def _fresh_database(monkeypatch, tmp_path):
    path = tmp_path / "e2e-session-resume.db"
    monkeypatch.setattr(database_module, "DATABASE_PATH", path)
    monkeypatch.setattr(database_module, "DATA_DIR", tmp_path)
    database_module.init_database()
    return path


def _demonstrated():
    return {
        "outcome": "demonstrated",
        "confidence": 0.95,
        "evidence": "Recuperou o conceito sem novidade.",
        "criteria": {
            "task_response": "met",
            "conceptual_correctness": "met",
            "understanding_application": "met",
        },
        "rubric_complete": True,
        "outcome_source": "rubric",
    }


def test_pause_review_before_resume_restores_exact_previous_stage(
    monkeypatch,
    tmp_path,
):
    path = _fresh_database(monkeypatch, tmp_path)
    student_id = DEFAULT_STUDENT_ID
    session_id = default_session_id("ads")

    LearnerState.update(
        "ads",
        current_concept_id="ads.variables",
        stage="testar",
        mastery=0.4,
        student_id=student_id,
    )

    paused = LearningSessionLifecycle.pause(
        "ads",
        student_id=student_id,
        session_id=session_id,
    )
    assert paused["status"] == "paused"
    assert paused["resume_concept_id"] == "ads.variables"
    assert paused["resume_stage"] == "testar"

    reviewing = LearningSessionLifecycle.resume(
        "ads",
        mode="review",
        student_id=student_id,
        session_id=session_id,
    )
    assert reviewing["status"] == "reviewing"
    assert LearnerState.get(
        "ads",
        student_id=student_id,
    )["stage"] == "reencontrar"

    review_turn = ProcessLearningTurn.commit_turn(
        "ads",
        "Quero revisar antes de retomar",
        None,
        None,
        turn_id="resume-review-task",
        assistant_message=(
            "Explique novamente, sem consultar, o que uma variável representa."
        ),
        student_id=student_id,
        session_id=session_id,
    )
    assert review_turn["teaching_action"] == "revisar"

    runtime = LearningSessionLifecycle.get(
        "ads",
        student_id=student_id,
        session_id=session_id,
    )
    task = LearningTask.find_by_source_turn(
        "resume-review-task",
        student_id=student_id,
        session_id=session_id,
    )

    assert runtime["review_task_id"] == task["task_id"]
    assert task["task_kind"] == "retention"
    assert task["assistance_level"] == "independent"

    answer = "Uma variável guarda um valor que pode mudar durante o programa."
    state = LearnerState.get("ads", student_id=student_id)
    context = EvidenceEvaluator.build_evaluation(
        answer,
        [],
        state,
        task_context=task,
    )
    assert context is not None

    ProcessLearningTurn.commit_turn(
        "ads",
        answer,
        None,
        _demonstrated(),
        turn_id="resume-review-answer",
        assistant_message="Certo. Vamos retomar de onde você parou.",
        student_id=student_id,
        session_id=session_id,
        evidence_context=context,
    )

    restored = LearnerState.get("ads", student_id=student_id)
    runtime = LearningSessionLifecycle.get(
        "ads",
        student_id=student_id,
        session_id=session_id,
    )

    assert restored["current_concept_id"] == "ads.variables"
    assert restored["stage"] == "testar"
    assert restored["mastery"] == pytest.approx(0.6)
    assert runtime["status"] == "studying"
    assert runtime["resume_concept_id"] is None
    assert runtime["resume_stage"] is None
    assert runtime["review_task_id"] is None

    connection = sqlite3.connect(str(path))
    connection.row_factory = sqlite3.Row
    try:
        events = connection.execute(
            """
            SELECT event_type, status_before, status_after, stage_snapshot
            FROM learning_session_events
            WHERE student_id = ? AND session_id = ?
            ORDER BY id
            """,
            (student_id, session_id),
        ).fetchall()
        assert [row["event_type"] for row in events] == [
            "paused",
            "resume_review_started",
            "resume_review_completed",
        ]
        assert events[-1]["stage_snapshot"] == "testar"
        assert connection.execute(
            "PRAGMA foreign_key_check"
        ).fetchall() == []
    finally:
        connection.close()
