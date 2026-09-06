from backend.services.objective_task_evaluator import ObjectiveTaskEvaluator
from backend.services.rubric_policy import RubricPolicy
from backend.services.variable_storage_tasks import VariableStorageTasks


def evaluation(mastery, answer):
    definition = VariableStorageTasks.definition_for_mastery(mastery)
    return ObjectiveTaskEvaluator.evaluate(
        {
            "concept_id": VariableStorageTasks.CONCEPT_ID,
            "tutor_message": definition["prompt"],
            "student_answer": answer,
        }
    )


def test_task_progression_teaches_variable_semantics_without_declaration_syntax():
    assert VariableStorageTasks.definition_for_mastery(0.0)["task_id"] == "variable_named_place_points"
    assert VariableStorageTasks.definition_for_mastery(0.2)["task_id"] == "variable_name_value_age"
    assert VariableStorageTasks.definition_for_mastery(0.4)["task_id"] == "variable_stable_name_attempts"
    assert VariableStorageTasks.definition_for_mastery(0.6)["task_id"] == "variable_current_value_balance"


def test_name_and_value_are_evaluated_deterministically():
    assert evaluation(0.0, "pontos")["outcome"] == RubricPolicy.OUTCOME_DEMONSTRATED
    assert evaluation(0.0, "10")["outcome"] != RubricPolicy.OUTCOME_DEMONSTRATED
    assert evaluation(0.2, "25")["outcome"] == RubricPolicy.OUTCOME_DEMONSTRATED
    assert evaluation(0.2, "idade")["outcome"] != RubricPolicy.OUTCOME_DEMONSTRATED


def test_name_remains_when_value_changes():
    assert evaluation(0.4, "tentativas")["outcome"] == RubricPolicy.OUTCOME_DEMONSTRATED
    wrong = evaluation(0.4, "2")
    assert wrong["outcome"] != RubricPolicy.OUTCOME_DEMONSTRATED
    assert wrong["missing_essential_criteria"]


def test_integration_requires_name_and_current_value_but_not_literal_format():
    good_plain = evaluation(0.6, "saldo 80")
    good_labeled = evaluation(0.6, "nome = saldo; valor atual = 80")
    missing_name = evaluation(0.6, "80")
    missing_value = evaluation(0.6, "saldo")

    assert good_plain["outcome"] == RubricPolicy.OUTCOME_DEMONSTRATED
    assert good_labeled["outcome"] == RubricPolicy.OUTCOME_DEMONSTRATED
    assert missing_name["outcome"] == RubricPolicy.OUTCOME_PARTIAL
    assert missing_value["outcome"] == RubricPolicy.OUTCOME_PARTIAL
    assert missing_name["missing_essential_criteria"]
    assert missing_value["missing_essential_criteria"]


def test_review_is_canonical_context():
    definition = VariableStorageTasks.definition_for_prompt(VariableStorageTasks.review_prompt())
    assert definition["task_id"] == "variable_review_level"
