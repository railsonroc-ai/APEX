from backend.services.integer_declaration_tasks import IntegerDeclarationTasks
from backend.services.objective_task_evaluator import ObjectiveTaskEvaluator
from backend.services.rubric_policy import RubricPolicy


def evaluation(mastery, answer):
    definition = IntegerDeclarationTasks.definition_for_mastery(mastery)
    return ObjectiveTaskEvaluator.evaluate(
        {
            "concept_id": IntegerDeclarationTasks.CONCEPT_ID,
            "tutor_message": definition["prompt"],
            "student_answer": answer,
        }
    )


def test_progression_introduces_var_then_inteiro_then_declaration_then_position():
    assert IntegerDeclarationTasks.definition_for_mastery(0.0)["task_id"] == "declaration_var_section"
    assert IntegerDeclarationTasks.definition_for_mastery(0.2)["task_id"] == "declaration_integer_type"
    assert IntegerDeclarationTasks.definition_for_mastery(0.4)["task_id"] == "declaration_line_points"
    assert IntegerDeclarationTasks.definition_for_mastery(0.6)["task_id"] == "declaration_block_order"


def test_keywords_are_evaluated_deterministically():
    assert evaluation(0.0, "var")["outcome"] == RubricPolicy.OUTCOME_DEMONSTRATED
    assert evaluation(0.0, "inteiro")["outcome"] != RubricPolicy.OUTCOME_DEMONSTRATED
    assert evaluation(0.2, "inteiro")["outcome"] == RubricPolicy.OUTCOME_DEMONSTRATED
    assert evaluation(0.2, "var")["outcome"] != RubricPolicy.OUTCOME_DEMONSTRATED


def test_declaration_line_requires_name_colon_and_type_because_syntax_is_objective():
    good = evaluation(0.4, "pontos: inteiro")
    missing_colon = evaluation(0.4, "pontos inteiro")
    reversed_line = evaluation(0.4, "inteiro: pontos")
    assert good["outcome"] == RubricPolicy.OUTCOME_DEMONSTRATED
    assert missing_colon["outcome"] == RubricPolicy.OUTCOME_PARTIAL
    assert reversed_line["outcome"] == RubricPolicy.OUTCOME_PARTIAL
    assert missing_colon["missing_essential_criteria"]
    assert reversed_line["missing_essential_criteria"]


def test_block_integration_requires_declaration_before_inicio():
    good = evaluation(
        0.6,
        'algoritmo "conta"; var; saldo: inteiro; inicio; fimalgoritmo',
    )
    wrong_order = evaluation(
        0.6,
        'algoritmo "conta"; inicio; var; saldo: inteiro; fimalgoritmo',
    )
    assert good["outcome"] == RubricPolicy.OUTCOME_DEMONSTRATED
    assert wrong_order["outcome"] == RubricPolicy.OUTCOME_PARTIAL
    assert wrong_order["missing_essential_criteria"]


def test_review_maps_to_stable_canonical_task():
    definition = IntegerDeclarationTasks.definition_for_prompt(
        IntegerDeclarationTasks.review_prompt()
    )
    assert definition["task_id"] == "declaration_review_attempts"
