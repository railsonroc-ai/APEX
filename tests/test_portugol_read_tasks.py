from backend.services.objective_task_evaluator import ObjectiveTaskEvaluator
from backend.services.portugol_read_tasks import PortugolReadTasks
from backend.services.rubric_policy import RubricPolicy


def evaluation(mastery, answer):
    definition = PortugolReadTasks.definition_for_mastery(mastery)
    return ObjectiveTaskEvaluator.evaluate(
        {
            "concept_id": PortugolReadTasks.CONCEPT_ID,
            "tutor_message": definition["prompt"],
            "student_answer": answer,
        }
    )


def test_task_progression_keeps_leia_as_the_only_new_command():
    assert PortugolReadTasks.definition_for_mastery(0.0)["task_id"] == "read_keyword_input"
    assert PortugolReadTasks.definition_for_mastery(0.2)["task_id"] == "read_role_input"
    assert PortugolReadTasks.definition_for_mastery(0.4)["task_id"] == "read_before_write"
    assert PortugolReadTasks.definition_for_mastery(0.6)["task_id"] == "read_flow_integration"


def test_keyword_and_role_are_evaluated_deterministically():
    assert evaluation(0.0, "leia")["outcome"] == RubricPolicy.OUTCOME_DEMONSTRATED
    assert evaluation(0.0, "escreva")["outcome"] != RubricPolicy.OUTCOME_DEMONSTRATED
    assert evaluation(0.2, "entrada")["outcome"] == RubricPolicy.OUTCOME_DEMONSTRATED
    assert evaluation(0.2, "saída")["outcome"] != RubricPolicy.OUTCOME_DEMONSTRATED


def test_placement_task_requires_only_the_read_keyword():
    assert evaluation(0.4, "leia")["outcome"] == RubricPolicy.OUTCOME_DEMONSTRATED
    wrong = evaluation(0.4, "escreva")
    assert wrong["outcome"] != RubricPolicy.OUTCOME_DEMONSTRATED
    assert wrong["missing_essential_criteria"]


def test_integration_requires_read_between_inicio_and_known_output():
    good = evaluation(
        0.6,
        'algoritmo "fluxo"; inicio; leia; escreva("OK"); fimalgoritmo',
    )
    wrong_order = evaluation(
        0.6,
        'algoritmo "fluxo"; leia; inicio; escreva("OK"); fimalgoritmo',
    )
    missing = evaluation(
        0.6,
        'algoritmo "fluxo"; inicio; escreva("OK"); fimalgoritmo',
    )
    assert good["outcome"] == RubricPolicy.OUTCOME_DEMONSTRATED
    assert wrong_order["outcome"] != RubricPolicy.OUTCOME_DEMONSTRATED
    assert missing["outcome"] != RubricPolicy.OUTCOME_DEMONSTRATED
    assert wrong_order["missing_essential_criteria"]
    assert missing["missing_essential_criteria"]


def test_review_is_canonical_context():
    definition = PortugolReadTasks.definition_for_prompt(PortugolReadTasks.review_prompt())
    assert definition["task_id"] == "read_review_role"
