import sqlite3

import pytest

import backend.database as database_module
from backend.identity import DEFAULT_STUDENT_ID, default_session_id
from backend.services.assistance_event import AssistanceEvent
from backend.services.concept_progress import ConceptProgress
from backend.services.evidence_evaluator import EvidenceEvaluator
from backend.services.evidence_event import EvidenceEvent
from backend.services.learner_state import LearnerState
from backend.services.learning_attempt import LearningAttempt
from backend.services.learning_task import LearningTask
from backend.services.mastery_assessment import MasteryAssessment
from backend.services.process_learning_turn import ProcessLearningTurn
from backend.services.rubric_assessment import RubricAssessment


pytestmark = [pytest.mark.e2e, pytest.mark.reliability]


def _fresh_database(monkeypatch, tmp_path, name):
    path = tmp_path / name
    monkeypatch.setattr(database_module, "DATABASE_PATH", path)
    monkeypatch.setattr(database_module, "DATA_DIR", tmp_path)
    database_module.init_database()
    return path


def _demonstrated(text="Demonstrou compreensão e aplicação."):
    return {
        "outcome": "demonstrated",
        "confidence": 0.95,
        "evidence": text,
        "criteria": {
            "task_response": "met",
            "conceptual_correctness": "met",
            "understanding_application": "met",
        },
        "rubric_complete": True,
        "outcome_source": "rubric",
    }


def _evaluation_for(task, answer, *, student_id):
    state = LearnerState.get("ads", student_id=student_id)
    evaluation = EvidenceEvaluator.build_evaluation(
        answer,
        [],
        state,
        task_context=task,
    )
    assert evaluation is not None
    return evaluation


def test_full_learning_pipeline_creates_auditable_chain_and_schedules_review(
    monkeypatch,
    tmp_path,
):
    path = _fresh_database(
        monkeypatch,
        tmp_path,
        "e2e-learning-pipeline.db",
    )
    student_id = DEFAULT_STUDENT_ID
    session_id = default_session_id("ads")

    first = ProcessLearningTurn.commit_turn(
        "ads",
        "Quero aprender variáveis",
        "ads.variables",
        None,
        turn_id="e2e-turn-1",
        assistant_message=(
            "Explique com suas palavras o que é uma variável."
        ),
        student_id=student_id,
        session_id=session_id,
    )

    assert first["learner_state"]["stage"] == "compreender"
    assert first["teaching_action"] == "explicar"

    task = LearningTask.find_by_source_turn(
        "e2e-turn-1",
        student_id=student_id,
        session_id=session_id,
    )
    assert task is not None
    assert task["assistance_level"] == "guided"

    answers = (
        "É um espaço nomeado que guarda um valor.",
        "Posso usar uma variável contador para guardar quantas vezes algo ocorreu.",
        "Se contador muda de 1 para 2, a variável passa a guardar 2.",
        "Em um formulário, uma variável pode guardar a idade informada.",
    )

    for index, answer in enumerate(answers, start=2):
        evidence_context = _evaluation_for(
            task,
            answer,
            student_id=student_id,
        )

        result = ProcessLearningTurn.commit_turn(
            "ads",
            answer,
            None,
            _demonstrated(),
            turn_id=f"e2e-turn-{index}",
            assistant_message=(
                f"Tarefa {index}: aplique novamente o conceito em outro exemplo."
            ),
            student_id=student_id,
            session_id=session_id,
            evidence_context=evidence_context,
        )

        task = LearningTask.find_by_source_turn(
            f"e2e-turn-{index}",
            student_id=student_id,
            session_id=session_id,
        )

    state = LearnerState.get("ads", student_id=student_id)
    progress = ConceptProgress.get(
        "ads",
        "ads.variables",
        student_id=student_id,
    )

    assert state["stage"] == "concluido"
    assert state["mastery"] == pytest.approx(0.8)
    assert progress["next_review_at"] is not None
    assert progress["review_count"] == 0

    attempts = LearningAttempt.list_for_concept(
        "ads",
        "ads.variables",
        student_id=student_id,
    )
    evidence = EvidenceEvent.list_for_concept(
        "ads",
        "ads.variables",
        student_id=student_id,
    )
    mastery = MasteryAssessment.list_for_concept(
        "ads",
        "ads.variables",
        student_id=student_id,
    )

    assert len(attempts) == 4
    assert len(evidence) == 4
    assert len(mastery) == 4
    assert task is None

    for index in range(2, 6):
        turn_id = f"e2e-turn-{index}"
        attempt = LearningAttempt.for_turn(
            turn_id,
            student_id=student_id,
        )
        rubric = RubricAssessment.for_turn(
            turn_id,
            student_id=student_id,
        )
        event = EvidenceEvent.for_turn(
            turn_id,
            student_id=student_id,
        )
        assessment = MasteryAssessment.for_turn(
            turn_id,
            student_id=student_id,
        )

        assert attempt is not None
        assert attempt["task_id"] is not None
        assert rubric is not None
        assert rubric["attempt_id"] == attempt["attempt_id"]
        assert rubric["evidence_event_id"] == event["event_id"]
        assert assessment["evidence_event_id"] == event["event_id"]
        assert rubric["outcome"] == "demonstrated"
        assert rubric["criteria_complete"] == 1

    first_assistance = AssistanceEvent.for_turn(
        "e2e-turn-1",
        student_id=student_id,
    )
    second_assistance = AssistanceEvent.for_turn(
        "e2e-turn-2",
        student_id=student_id,
    )
    final_assistance = AssistanceEvent.for_turn(
        "e2e-turn-5",
        student_id=student_id,
    )

    assert first_assistance["assistance_level"] == "guided"
    assert second_assistance["assistance_level"] == "light"
    assert final_assistance["assistance_level"] == "untracked"

    connection = sqlite3.connect(str(path))
    try:
        assert connection.execute(
            "PRAGMA foreign_key_check"
        ).fetchall() == []
        assert connection.execute(
            "PRAGMA integrity_check"
        ).fetchone()[0] == "ok"
    finally:
        connection.close()


def test_replaying_confirmed_turn_does_not_duplicate_ledgers(
    monkeypatch,
    tmp_path,
):
    _fresh_database(
        monkeypatch,
        tmp_path,
        "e2e-replay.db",
    )
    student_id = DEFAULT_STUDENT_ID
    session_id = default_session_id("ads")

    first = ProcessLearningTurn.commit_turn(
        "ads",
        "Quero aprender variáveis",
        "ads.variables",
        None,
        turn_id="replay-source",
        assistant_message="Explique o que é uma variável.",
        student_id=student_id,
        session_id=session_id,
    )
    assert first.get("duplicate") is not True

    task = LearningTask.find_by_source_turn(
        "replay-source",
        student_id=student_id,
        session_id=session_id,
    )
    answer = "Uma variável guarda um valor."
    context = _evaluation_for(task, answer, student_id=student_id)

    committed = ProcessLearningTurn.commit_turn(
        "ads",
        answer,
        None,
        _demonstrated(),
        turn_id="replay-answer",
        assistant_message="Agora aplique em outro exemplo.",
        student_id=student_id,
        session_id=session_id,
        evidence_context=context,
    )
    assert committed.get("duplicate") is not True

    replay = ProcessLearningTurn.commit_turn(
        "ads",
        answer,
        None,
        _demonstrated(),
        turn_id="replay-answer",
        assistant_message="Agora aplique em outro exemplo.",
        student_id=student_id,
        session_id=session_id,
        evidence_context=context,
    )

    assert replay["duplicate"] is True
    assert len(
        EvidenceEvent.list_for_concept(
            "ads",
            "ads.variables",
            student_id=student_id,
        )
    ) == 1
    assert len(
        LearningAttempt.list_for_concept(
            "ads",
            "ads.variables",
            student_id=student_id,
        )
    ) == 1
    assert len(
        MasteryAssessment.list_for_concept(
            "ads",
            "ads.variables",
            student_id=student_id,
        )
    ) == 1
