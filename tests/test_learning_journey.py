from backend.services.learner_state_transition import LearnerStateTransition


def apply(
    state,
    outcome,
    confidence=0.9,
    evidence="evidencia",
    can_complete=False,
):
    changes = LearnerStateTransition.from_evidence(
        state,
        {
            "outcome": outcome,
            "confidence": confidence,
            "evidence": evidence,
        },
        mastery_decision={"can_complete": can_complete},
    )
    return {**state, **changes}


def test_learning_journey_requires_evidence_before_completion():
    state = {
        "current_concept": "variáveis",
        "stage": "compreender",
        "mastery": 0.55,
        "difficulty_count": 0,
        "last_evidence": None,
    }

    state = apply(state, "partial")
    assert state["stage"] == "testar"
    assert round(state["mastery"], 2) == 0.60

    state = apply(state, "demonstrated")
    assert state["stage"] == "fixar"
    assert round(state["mastery"], 2) == 0.80

    state = apply(state, "demonstrated", can_complete=True)
    assert state["stage"] == "concluido"
    assert round(state["mastery"], 2) == 1.00


def test_learning_journey_recovers_after_misconception():
    state = {
        "current_concept": "variáveis",
        "stage": "testar",
        "mastery": 0.70,
        "difficulty_count": 0,
        "last_evidence": None,
    }

    state = apply(state, "misconception")
    assert state["stage"] == "corrigir"
    assert round(state["mastery"], 2) == 0.60
    assert state["difficulty_count"] == 1

    state = apply(state, "demonstrated")
    assert state["stage"] == "fixar"
    assert round(state["mastery"], 2) == 0.80
    assert state["difficulty_count"] == 0
