from backend.services.objective_task_evaluator import ObjectiveTaskEvaluator
from backend.services.portugol_write_tasks import PortugolWriteTasks
from backend.services.rubric_policy import RubricPolicy


def evaluation(mastery, answer):
    definition = PortugolWriteTasks.definition_for_mastery(mastery)
    return ObjectiveTaskEvaluator.evaluate(
        {
            "concept_id": PortugolWriteTasks.CONCEPT_ID,
            "tutor_message": definition["prompt"],
            "student_answer": answer,
        }
    )


def test_task_progression_keeps_one_command_as_the_only_new_construct():
    assert PortugolWriteTasks.definition_for_mastery(0.0)["task_id"] == "write_keyword_hello"
    assert PortugolWriteTasks.definition_for_mastery(0.2)["task_id"] == "write_predict_ready"
    assert PortugolWriteTasks.definition_for_mastery(0.4)["task_id"] == "write_line_done"
    assert PortugolWriteTasks.definition_for_mastery(0.6)["task_id"] == "write_program_ok"


def test_keyword_and_effect_are_evaluated_deterministically():
    assert evaluation(0.0, "escreva")["outcome"] == RubricPolicy.OUTCOME_DEMONSTRATED
    assert evaluation(0.0, "inicio")["outcome"] != RubricPolicy.OUTCOME_DEMONSTRATED
    assert evaluation(0.2, "Pronto")["outcome"] == RubricPolicy.OUTCOME_DEMONSTRATED
    assert evaluation(0.2, "escreva")["outcome"] != RubricPolicy.OUTCOME_DEMONSTRATED


def test_write_line_requires_call_syntax_and_quoted_requested_text():
    good = evaluation(0.4, 'escreva("Concluído")')
    no_quotes = evaluation(0.4, "escreva(Concluído)")
    wrong_text = evaluation(0.4, 'escreva("Pronto")')
    assert good["outcome"] == RubricPolicy.OUTCOME_DEMONSTRATED
    assert no_quotes["outcome"] != RubricPolicy.OUTCOME_DEMONSTRATED
    assert wrong_text["outcome"] != RubricPolicy.OUTCOME_DEMONSTRATED
    assert no_quotes["missing_essential_criteria"]


def test_full_program_requires_known_structure_with_write_inside():
    good = evaluation(
        0.6,
        'algoritmo "saida"\ninicio\nescreva("OK")\nfimalgoritmo',
    )
    wrong_order = evaluation(
        0.6,
        'algoritmo "saida"\nescreva("OK")\ninicio\nfimalgoritmo',
    )
    assert good["outcome"] == RubricPolicy.OUTCOME_DEMONSTRATED
    assert wrong_order["outcome"] != RubricPolicy.OUTCOME_DEMONSTRATED
    assert wrong_order["missing_essential_criteria"]


def test_review_is_recognized_as_canonical_context():
    definition = PortugolWriteTasks.definition_for_prompt(PortugolWriteTasks.review_prompt())
    assert definition["task_id"] == "write_review_message"
