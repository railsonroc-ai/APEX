from backend.services.rubric_policy import RubricPolicy


def criteria(task="met", correctness="met", understanding="met"):
    return {
        "task_response": task,
        "conceptual_correctness": correctness,
        "understanding_application": understanding,
    }


def test_all_criteria_met_is_demonstrated():
    assert RubricPolicy.derive_outcome(criteria()) == "demonstrated"


def test_conceptual_error_is_misconception():
    assert RubricPolicy.derive_outcome(
        criteria(correctness="not_met")
    ) == "misconception"


def test_unanswered_task_is_insufficient():
    assert RubricPolicy.derive_outcome(
        criteria(task="not_met", understanding="unknown")
    ) == "insufficient"


def test_partial_progress_is_partial():
    assert RubricPolicy.derive_outcome(
        criteria(understanding="partial")
    ) == "partial"


def test_payload_marks_incomplete_legacy_outcome_honestly():
    result = RubricPolicy.normalize_payload({"outcome": "partial"})
    assert result["rubric_complete"] is False
    assert result["outcome"] == "partial"
    assert result["outcome_source"] == "legacy_outcome"
    assert set(result["criteria"].values()) == {"unknown"}
