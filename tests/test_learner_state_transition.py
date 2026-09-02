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
