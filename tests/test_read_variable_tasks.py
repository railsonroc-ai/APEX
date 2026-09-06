from backend.services.read_variable_tasks import ReadVariableTasks
from backend.services.objective_task_evaluator import ObjectiveTaskEvaluator
from backend.services.rubric_policy import RubricPolicy


def evaluation(mastery, answer):
    definition = ReadVariableTasks.definition_for_mastery(mastery)
    return ObjectiveTaskEvaluator.evaluate(
        {
            "concept_id": ReadVariableTasks.CONCEPT_ID,
            "tutor_message": definition["prompt"],
            "student_answer": answer,
        }
    )


def test_progression_identifies_target_then_completes_then_forms_call_then_integrates():
    assert ReadVariableTasks.definition_for_mastery(0.0)["task_id"] == "read_variable_identify_age"
    assert ReadVariableTasks.definition_for_mastery(0.2)["task_id"] == "read_variable_complete_attempts"
    assert ReadVariableTasks.definition_for_mastery(0.4)["task_id"] == "read_variable_call_points"
    assert ReadVariableTasks.definition_for_mastery(0.6)["task_id"] == "read_variable_program_order"


def test_exact_target_answers_are_deterministic():
    assert evaluation(0.0, "idade")["outcome"] == RubricPolicy.OUTCOME_DEMONSTRATED
    wrong = evaluation(0.0, "inteiro")
    assert wrong["outcome"] != RubricPolicy.OUTCOME_DEMONSTRATED
    assert wrong["missing_essential_criteria"]
    assert evaluation(0.2, "tentativas")["outcome"] == RubricPolicy.OUTCOME_DEMONSTRATED


def test_read_call_requires_command_parentheses_and_declared_variable_name():
    good = evaluation(0.4, "leia(pontos)")
    no_parentheses = evaluation(0.4, "leia pontos")
    wrong_name = evaluation(0.4, "leia(idade)")
    assert good["outcome"] == RubricPolicy.OUTCOME_DEMONSTRATED
    assert no_parentheses["outcome"] == RubricPolicy.OUTCOME_PARTIAL
    assert wrong_name["outcome"] == RubricPolicy.OUTCOME_PARTIAL
    assert no_parentheses["missing_essential_criteria"]
    assert wrong_name["missing_essential_criteria"]


def test_program_integration_requires_declaration_before_inicio_and_read_after_inicio():
    good = evaluation(
        0.6,
        'algoritmo "cadastro"; var; idade: inteiro; inicio; leia(idade); fimalgoritmo',
    )
    wrong_order = evaluation(
        0.6,
        'algoritmo "cadastro"; var; inicio; idade: inteiro; leia(idade); fimalgoritmo',
    )
    wrong_target = evaluation(
        0.6,
        'algoritmo "cadastro"; var; idade: inteiro; inicio; leia(pontos); fimalgoritmo',
    )
    assert good["outcome"] == RubricPolicy.OUTCOME_DEMONSTRATED
    assert wrong_order["outcome"] == RubricPolicy.OUTCOME_PARTIAL
    assert wrong_target["outcome"] == RubricPolicy.OUTCOME_PARTIAL
    assert wrong_order["missing_essential_criteria"]
    assert wrong_target["missing_essential_criteria"]


def test_review_maps_to_stable_canonical_task():
    definition = ReadVariableTasks.definition_for_prompt(
        ReadVariableTasks.review_prompt()
    )
    assert definition["task_id"] == "read_variable_review_balance"
