from backend.services.learner_signals import LearnerSignals


def test_pure_control_message_is_not_treated_as_an_answer():
    assert LearnerSignals.is_control_only("Não entendi mesmo") is True


def test_answer_plus_control_message_preserves_the_answer():
    assert LearnerSignals.is_control_only(
        "Abrir a torneira, lavar e secar; mas não entendi o motivo."
    ) is False


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
