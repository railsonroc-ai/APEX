from backend.services.learner_state_transition import LearnerStateTransition


def test_difficulty_increments_and_moves_to_correction():
    changes = LearnerStateTransition.from_signals({"difficulty_count": 1}, {"difficulty"})
    assert changes == {"difficulty_count": 2, "stage": "corrigir"}


def test_test_request_moves_to_testing():
    changes = LearnerStateTransition.from_signals({"difficulty_count": 0}, {"test_request"})
    assert changes == {"stage": "testar"}


def test_review_request_moves_to_reencounter():
    changes = LearnerStateTransition.from_signals({"difficulty_count": 0}, {"review_request"})
    assert changes == {"stage": "reencontrar"}


def test_reexplain_request_moves_to_understanding():
    changes = LearnerStateTransition.from_signals({"difficulty_count": 0}, {"reexplain_request"})
    assert changes == {"stage": "compreender"}


def test_demonstrated_evidence_advances_learning():
    state = {"mastery": 0.5, "difficulty_count": 1}
    evidence = {
        "outcome": "demonstrated",
        "confidence": 0.9,
        "evidence": "Explicou corretamente.",
    }
    result = LearnerStateTransition.from_evidence(state, evidence)
    assert result == {
        "mastery": 0.7,
        "difficulty_count": 0,
        "stage": "fixar",
        "last_evidence": "Explicou corretamente.",
    }


def test_partial_evidence_keeps_testing():
    state = {"mastery": 0.5, "difficulty_count": 1}
    evidence = {
        "outcome": "partial",
        "confidence": 0.8,
        "evidence": "Acertou parte da explicação.",
    }
    result = LearnerStateTransition.from_evidence(state, evidence)
    assert result == {
        "mastery": 0.55,
        "stage": "testar",
        "last_evidence": "Acertou parte da explicação.",
    }


def test_misconception_evidence_triggers_correction():
    state = {"mastery": 0.5, "difficulty_count": 1}
    evidence = {
        "outcome": "misconception",
        "confidence": 0.9,
        "evidence": "Confundiu variável com valor fixo.",
    }
    result = LearnerStateTransition.from_evidence(state, evidence)
    assert result == {
        "mastery": 0.4,
        "difficulty_count": 2,
        "stage": "corrigir",
        "last_evidence": "Confundiu variável com valor fixo.",
    }


def test_insufficient_evidence_only_records_evidence():
    state = {"mastery": 0.5, "difficulty_count": 1, "stage": "testar"}
    evidence = {
        "outcome": "insufficient",
        "confidence": 0.8,
        "evidence": "A resposta não demonstrou conhecimento suficiente.",
    }
    result = LearnerStateTransition.from_evidence(state, evidence)
    assert result == {
        "last_evidence": "A resposta não demonstrou conhecimento suficiente.",
    }


def test_low_confidence_evidence_does_not_change_state():
    state = {"mastery": 0.5, "difficulty_count": 1, "stage": "testar"}
    evidence = {
        "outcome": "demonstrated",
        "confidence": 0.6,
        "evidence": "Resposta aparentemente correta.",
    }
    result = LearnerStateTransition.from_evidence(state, evidence)
    assert result == {}


def test_demonstrated_while_fixing_completes_concept():
    state = {"stage": "fixar", "mastery": 0.7, "difficulty_count": 0}
    evidence = {
        "outcome": "demonstrated",
        "confidence": 0.9,
        "evidence": "Aplicou corretamente sem ajuda.",
    }
    result = LearnerStateTransition.from_evidence(state, evidence)
    assert result["stage"] == "concluido"
    assert round(result["mastery"], 2) == 0.9

def test_fixing_below_mastery_threshold_does_not_complete():
    state = {"stage": "fixar", "mastery": 0.2, "difficulty_count": 0}
    evidence = {
        "outcome": "demonstrated",
        "confidence": 0.9,
        "evidence": "Acertou novamente.",
    }

    result = LearnerStateTransition.from_evidence(state, evidence)

    assert result["stage"] == "fixar"
    assert round(result["mastery"], 2) == 0.4
