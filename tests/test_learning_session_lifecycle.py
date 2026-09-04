import sqlite3

import pytest

import backend.database as database_module
from backend.identity import DEFAULT_STUDENT_ID, default_session_id
from backend.services.learner_state import LearnerState
from backend.services.learning_history import LearningHistory
from backend.services.learning_task import LearningTask
from backend.services.learning_session_lifecycle import (
    LearningSessionLifecycle,
    SessionLifecycleError,
)


def prepare_database(monkeypatch, tmp_path):
    path = tmp_path / "session-lifecycle.db"
    monkeypatch.setattr(database_module, "DATABASE_PATH", path)
    monkeypatch.setattr(database_module, "DATA_DIR", tmp_path)
    database_module.init_database()
    return path


def event_rows(path):
    connection = sqlite3.connect(str(path))
    connection.row_factory = sqlite3.Row
    try:
        return [
            dict(row)
            for row in connection.execute(
                """
                SELECT *
                FROM learning_session_events
                ORDER BY id
                """
            ).fetchall()
        ]
    finally:
        connection.close()


def test_default_sessions_start_studying(monkeypatch, tmp_path):
    prepare_database(monkeypatch, tmp_path)

    ads = LearningSessionLifecycle.get("ads")
    it = LearningSessionLifecycle.get("it")

    assert ads["student_id"] == DEFAULT_STUDENT_ID
    assert ads["session_id"] == default_session_id("ads")
    assert ads["status"] == "studying"
    assert ads["resume_concept_id"] is None
    assert it["status"] == "studying"


def test_pause_snapshots_current_concept_and_stage_once(monkeypatch, tmp_path):
    path = prepare_database(monkeypatch, tmp_path)

    LearnerState.update(
        "ads",
        current_concept_id="ads.variables",
        stage="testar",
        mastery=0.4,
    )

    paused = LearningSessionLifecycle.pause("ads")
    duplicate = LearningSessionLifecycle.pause("ads")

    assert paused["status"] == "paused"
    assert paused["resume_concept_id"] == "ads.variables"
    assert paused["resume_stage"] == "testar"
    assert paused["duplicate"] is False
    assert duplicate["duplicate"] is True

    rows = event_rows(path)
    assert [row["event_type"] for row in rows] == ["paused"]
    assert rows[0]["status_before"] == "studying"
    assert rows[0]["status_after"] == "paused"
    assert rows[0]["concept_id"] == "ads.variables"
    assert rows[0]["stage_snapshot"] == "testar"
    assert rows[0]["policy_id"] == LearningSessionLifecycle.POLICY_ID
    assert rows[0]["policy_version"] == LearningSessionLifecycle.POLICY_VERSION


def test_direct_resume_restores_studying_without_changing_learner_state(
    monkeypatch,
    tmp_path,
):
    path = prepare_database(monkeypatch, tmp_path)
    LearnerState.update(
        "ads",
        current_concept_id="ads.variables",
        stage="fixar",
        mastery=0.6,
    )

    LearningSessionLifecycle.pause("ads")
    resumed = LearningSessionLifecycle.resume("ads", mode="direct")
    state = LearnerState.get("ads")

    assert resumed["status"] == "studying"
    assert resumed["resume_concept_id"] is None
    assert resumed["resume_stage"] is None
    assert state["current_concept_id"] == "ads.variables"
    assert state["stage"] == "fixar"

    rows = event_rows(path)
    assert [row["event_type"] for row in rows] == [
        "paused",
        "resumed_direct",
    ]


def test_review_resume_enters_reencontrar_and_restores_previous_stage(
    monkeypatch,
    tmp_path,
):
    path = prepare_database(monkeypatch, tmp_path)
    LearnerState.update(
        "ads",
        current_concept_id="ads.variables",
        stage="testar",
        mastery=0.5,
    )

    LearningSessionLifecycle.pause("ads")
    reviewing = LearningSessionLifecycle.resume("ads", mode="review")
    review_state = LearnerState.get("ads")

    assert reviewing["status"] == "reviewing"
    assert reviewing["resume_stage"] == "testar"
    assert review_state["stage"] == "reencontrar"
    assert reviewing["review_task_id"] is None

    LearningHistory.record(
        turn_id="resume-review-task-turn",
        area="ads",
        user_message="Vamos revisar antes de retomar.",
        assistant_message="Explique novamente o que é uma variável.",
        concept_id="ads.variables",
        student_id=DEFAULT_STUDENT_ID,
        session_id=default_session_id("ads"),
    )
    task = LearningTask.record(
        source_turn_id="resume-review-task-turn",
        area="ads",
        concept_id="ads.variables",
        stage="reencontrar",
        teaching_action="revisar",
        prompt_text="Explique novamente o que é uma variável.",
        student_id=DEFAULT_STUDENT_ID,
        session_id=default_session_id("ads"),
    )
    bound = LearningSessionLifecycle.bind_review_task(
        task["task_id"],
        "ads",
    )
    assert bound["review_task_id"] == task["task_id"]

    not_done = LearningSessionLifecycle.complete_resume_review(
        "ads",
        review_state,
        {
            "outcome": "partial",
            "confidence": 0.95,
            "evidence": "Ainda parcial.",
        },
        evidence_applied=True,
        task_id=task["task_id"],
    )
    assert not_done is None
    assert LearningSessionLifecycle.get("ads")["status"] == "reviewing"

    completed = LearningSessionLifecycle.complete_resume_review(
        "ads",
        LearnerState.get("ads"),
        {
            "outcome": "demonstrated",
            "confidence": 0.95,
            "evidence": "Recuperou o conceito.",
        },
        evidence_applied=True,
        task_id=task["task_id"],
    )

    assert completed["session"]["status"] == "studying"
    assert completed["learner_state"]["stage"] == "testar"
    assert completed["learner_state"]["current_concept_id"] == "ads.variables"

    rows = event_rows(path)
    assert [row["event_type"] for row in rows] == [
        "paused",
        "resume_review_started",
        "resume_review_completed",
    ]


def test_review_resume_requires_active_concept(monkeypatch, tmp_path):
    prepare_database(monkeypatch, tmp_path)

    LearningSessionLifecycle.pause("ads")

    with pytest.raises(
        SessionLifecycleError,
        match="não há conceito ativo",
    ):
        LearningSessionLifecycle.resume("ads", mode="review")

    assert LearningSessionLifecycle.get("ads")["status"] == "paused"


def test_pause_rejects_review_stage(monkeypatch, tmp_path):
    prepare_database(monkeypatch, tmp_path)
    LearnerState.update(
        "ads",
        current_concept_id="ads.variables",
        stage="reencontrar",
    )

    with pytest.raises(SessionLifecycleError, match="revisão em andamento"):
        LearningSessionLifecycle.pause("ads")

    assert LearningSessionLifecycle.get("ads")["status"] == "studying"


def test_session_events_are_immutable(monkeypatch, tmp_path):
    path = prepare_database(monkeypatch, tmp_path)
    LearnerState.update(
        "ads",
        current_concept_id="ads.variables",
        stage="testar",
    )
    LearningSessionLifecycle.pause("ads")

    connection = sqlite3.connect(str(path))
    try:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE learning_session_events SET event_type='resumed_direct'"
            )

        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("DELETE FROM learning_session_events")
    finally:
        connection.close()


def test_invalid_resume_mode_is_rejected(monkeypatch, tmp_path):
    prepare_database(monkeypatch, tmp_path)
    LearningSessionLifecycle.pause("ads")

    with pytest.raises(SessionLifecycleError, match="modo de retomada inválido"):
        LearningSessionLifecycle.resume("ads", mode="qualquer")


def test_process_finalize_completes_resume_review_and_restores_stage(
    monkeypatch,
    tmp_path,
):
    from backend.identity import default_session_id
    from backend.services.process_learning_turn import ProcessLearningTurn

    prepare_database(monkeypatch, tmp_path)
    LearnerState.update(
        "ads",
        current_concept_id="ads.variables",
        stage="testar",
        mastery=0.4,
    )
    LearningSessionLifecycle.pause("ads")
    LearningSessionLifecycle.resume("ads", mode="review")

    LearningHistory.record(
        turn_id="process-resume-review-task",
        area="ads",
        user_message="Revisar antes.",
        assistant_message="Explique novamente uma variável.",
        concept_id="ads.variables",
        student_id=DEFAULT_STUDENT_ID,
        session_id=default_session_id("ads"),
    )
    task = LearningTask.record(
        source_turn_id="process-resume-review-task",
        area="ads",
        concept_id="ads.variables",
        stage="reencontrar",
        teaching_action="revisar",
        prompt_text="Explique novamente uma variável.",
        student_id=DEFAULT_STUDENT_ID,
        session_id=default_session_id("ads"),
    )
    LearningSessionLifecycle.bind_review_task(task["task_id"], "ads")

    result = ProcessLearningTurn.finalize(
        "ads",
        "Uma variável guarda um valor.",
        LearnerState.get("ads"),
        {
            "outcome": "demonstrated",
            "confidence": 0.95,
            "evidence": "Recuperou corretamente.",
        },
        session_id=default_session_id("ads"),
        evidence_context={"task_id": task["task_id"]},
    )

    assert result["learner_state"]["stage"] == "testar"
    assert result["learner_state"]["mastery"] == pytest.approx(0.6)
    assert LearningSessionLifecycle.get("ads")["status"] == "studying"
