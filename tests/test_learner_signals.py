from backend.services.learner_signals import LearnerSignals


def test_detects_difficulty_and_reexplain():
    signals = LearnerSignals.detect("Não entendi, explique de outro jeito")
    assert LearnerSignals.DIFFICULTY in signals
    assert LearnerSignals.REEXPLAIN_REQUEST in signals


def test_detects_test_request():
    signals = LearnerSignals.detect("Pode me testar?")
    assert LearnerSignals.TEST_REQUEST in signals


def test_detects_review_request():
    signals = LearnerSignals.detect("Quero revisar antes")
    assert LearnerSignals.REVIEW_REQUEST in signals


def test_does_not_infer_comprehension_from_simple_statement():
    signals = LearnerSignals.detect("Entendi a variável")
    assert signals == set()
