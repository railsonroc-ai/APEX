from backend.services.input_process_output_tasks import InputProcessOutputTasks
from backend.services.objective_task_evaluator import ObjectiveTaskEvaluator


CONCEPT = "ads.algorithms.input_process_output"


def evaluate(prompt, answer):
    return ObjectiveTaskEvaluator.evaluate(
        {
            "concept_id": CONCEPT,
            "tutor_message": prompt,
            "student_answer": answer,
        }
    )


def test_task_sequence_introduces_one_component_at_a_time():
    assert InputProcessOutputTasks.focus_for_mastery(0.0) == "entrada"
    assert InputProcessOutputTasks.focus_for_mastery(0.2) == "processamento"
    assert InputProcessOutputTasks.focus_for_mastery(0.4) == "saída"
    assert "relação" in InputProcessOutputTasks.focus_for_mastery(0.6)


def test_concrete_component_answers_are_semantically_demonstrated():
    cases = (
        (0.0, "banana e leite."),
        (0.2, "lavar as roupas."),
        (0.4, "5."),
    )
    for mastery, answer in cases:
        result = evaluate(InputProcessOutputTasks.prompt_for_mastery(mastery), answer)
        assert result["outcome"] == "demonstrated"
        assert result["missing_essential_criteria"] == []


def test_partial_component_names_real_missing_criterion():
    result = evaluate(
        InputProcessOutputTasks.prompt_for_mastery(0.0),
        "banana.",
    )
    assert result["outcome"] == "partial"
    assert result["missing_essential_criteria"]


def test_final_mapping_does_not_require_literal_role_labels():
    result = evaluate(
        InputProcessOutputTasks.prompt_for_mastery(0.7),
        "água e pó de café; preparar a bebida; café pronto.",
    )
    assert result["outcome"] == "demonstrated"


def test_explicit_wrong_mapping_is_not_demonstrated():
    result = evaluate(
        InputProcessOutputTasks.prompt_for_mastery(0.7),
        "entrada: café pronto; processamento: água e pó de café; saída: preparar a bebida.",
    )
    assert result["outcome"] != "demonstrated"
    assert result["missing_essential_criteria"]
