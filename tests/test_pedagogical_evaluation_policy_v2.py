from backend.services.evaluation_policy import (
    CONTRACT_MARKER,
    load_evaluation_contract,
    postprocess_evaluation_result,
    install_evaluator_policy,
)


def test_contract_v2_is_present():
    text = load_evaluation_contract()
    assert CONTRACT_MARKER in text
    assert 'outcome="partial"' in text
    assert 'missing_essential_criteria' in text


def test_partial_without_audit_field_is_not_invented():
    original = {"outcome": "partial", "confidence": 0.9, "evidence": "Incompleta."}
    assert postprocess_evaluation_result(original) == original


def test_partial_with_real_missing_criterion_is_preserved():
    original = {
        "outcome": "partial",
        "missing_essential_criteria": ["estado final explicitamente pedido"],
    }
    assert postprocess_evaluation_result(original) == original


def test_partial_with_empty_missing_criteria_becomes_demonstrated():
    out = postprocess_evaluation_result({
        "outcome": "partial",
        "missing_essential_criteria": [],
    })
    assert out["outcome"] == "demonstrated"
    assert out["policy_adjustment"] == "partial_without_missing_essential_criterion"


def test_runtime_policy_never_wraps_imported_classes():
    class ImportedRubric:
        @classmethod
        def record(cls):
            return "ok"
    ImportedRubric.__module__ = "some.other.module"

    class ImportedLearningHistory:
        @classmethod
        def to_messages(cls):
            return [{"role": "user", "content": "x"}]
    ImportedLearningHistory.__module__ = "some.other.module"

    ns = {
        "__name__": "backend.services.fake_evaluator",
        "RubricAssessment": ImportedRubric,
        "LearningHistory": ImportedLearningHistory,
    }
    result = install_evaluator_policy(ns)
    assert result["evaluation"] == 0
    assert ImportedRubric.record() == "ok"
    assert ImportedLearningHistory.to_messages() == [{"role": "user", "content": "x"}]
