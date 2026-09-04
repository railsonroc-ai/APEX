import backend.services.process_learning_turn as turn_module
from backend.services.process_learning_turn import ProcessLearningTurn


def test_activates_identified_concept(monkeypatch):
    state = {"current_concept_id": None, "current_concept": None}
    activated = {"current_concept_id": "ads.variables", "current_concept": "variáveis", "stage": "compreender"}
    captured = {}

    def fake_activate(area, concept, **kwargs):
        captured["activation"] = (
            area,
            concept,
            kwargs.get("student_id"),
        )
        return activated

    monkeypatch.setattr(
        turn_module.ConceptActivation,
        "activate",
        fake_activate,
    )

    result = ProcessLearningTurn.activate_identified_concept(
        "ads",
        state,
        "variáveis",
    )

    assert result == activated
    assert captured["activation"] == (
        "ads",
        "ads.variables",
        "student_default",
    )


def test_finalize_completed_concept_schedules_review(monkeypatch):
    initial = {
        "current_concept_id": "ads.variables",
        "current_concept": "variáveis",
        "stage": "fixar",
        "mastery": 0.7,
        "difficulty_count": 0,
        "last_evidence": None,
    }
    completed = {
        **initial,
        "stage": "concluido",
        "mastery": 0.9,
        "last_evidence": "Aplicou corretamente.",
    }
    captured = []

    monkeypatch.setattr(
        turn_module.LearnerStateTransition,
        "from_evidence",
        lambda state, evidence, **kwargs: {
            "stage": "concluido",
            "mastery": 0.9,
            "last_evidence": "Aplicou corretamente.",
        },
    )
    monkeypatch.setattr(
        turn_module.LearnerState,
        "update",
        lambda area, **changes: completed,
    )

    def fake_progress(area, concept, **changes):
        captured.append(changes)
        return {"area": area, "concept": concept, **changes}

    monkeypatch.setattr(
        turn_module.ConceptProgress,
        "update",
        fake_progress,
    )
    monkeypatch.setattr(
        turn_module.ReviewScheduler,
        "schedule",
        lambda progress: {
            "next_review_at": "2026-09-04T12:00:00+00:00"
        },
    )
    monkeypatch.setattr(
        turn_module.LearnerSignals,
        "detect",
        lambda message: set(),
    )
    monkeypatch.setattr(
        turn_module.LearnerStateTransition,
        "from_signals",
        lambda state, signals: {},
    )
    monkeypatch.setattr(
        turn_module.TeachingPolicy,
        "choose_action",
        lambda state: "avancar",
    )

    result = ProcessLearningTurn.finalize(
        "ads",
        "Resposta correta.",
        initial,
        {"outcome": "demonstrated"},
        mastery_decision={"can_complete": True},
    )

    assert result["learner_state"] == completed
    assert result["teaching_action"] == "avancar"
    assert captured[-1] == {
        "next_review_at": "2026-09-04T12:00:00+00:00",
        "student_id": "student_default",
    }


def test_finalize_review_request_activates_due_review(monkeypatch):
    initial = {
        "current_concept_id": "ads.variables",
        "current_concept": "variáveis",
        "stage": "concluido",
    }
    review = {
        "current_concept": "variáveis",
        "stage": "reencontrar",
    }

    monkeypatch.setattr(
        turn_module.LearnerStateTransition,
        "from_evidence",
        lambda state, evidence: {},
    )
    monkeypatch.setattr(
        turn_module.LearnerSignals,
        "detect",
        lambda message: {turn_module.LearnerSignals.REVIEW_REQUEST},
    )
    monkeypatch.setattr(
        turn_module.ReviewLifecycle,
        "activate_due",
        lambda area, **kwargs: review,
    )
    monkeypatch.setattr(
        turn_module.LearnerStateTransition,
        "from_signals",
        lambda state, signals: {},
    )
    monkeypatch.setattr(
        turn_module.TeachingPolicy,
        "choose_action",
        lambda state: "revisar",
    )

    result = ProcessLearningTurn.finalize(
        "ads",
        "Quero revisar",
        initial,
        None,
    )

    assert result["learner_state"] == review
    assert result["teaching_action"] == "revisar"
