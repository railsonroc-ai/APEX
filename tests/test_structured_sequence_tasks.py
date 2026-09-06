from backend.services.objective_task_evaluator import ObjectiveTaskEvaluator
from backend.services.structured_sequence_tasks import StructuredSequenceTasks


CONCEPT = "ads.algorithms.structured_sequence"


def evaluate(prompt, answer):
    return ObjectiveTaskEvaluator.evaluate(
        {
            "concept_id": CONCEPT,
            "tutor_message": prompt,
            "student_answer": answer,
        }
    )


def test_task_sequence_moves_from_numbering_to_boundaries_then_reading_and_integration():
    assert "numerada" in StructuredSequenceTasks.focus_for_mastery(0.0)
    assert "INÍCIO" in StructuredSequenceTasks.focus_for_mastery(0.2)
    assert "ler" in StructuredSequenceTasks.focus_for_mastery(0.4)
    assert "completa" in StructuredSequenceTasks.focus_for_mastery(0.6)


def test_numbered_representation_is_demonstrated_when_structure_and_order_are_explicit():
    result = evaluate(
        StructuredSequenceTasks.prompt_for_mastery(0.0),
        "1 pegar o pão; 2 colocar o pão na torradeira; 3 retirar a torrada.",
    )
    assert result["outcome"] == "demonstrated"
    assert result["missing_essential_criteria"] == []


def test_correct_actions_without_required_numbered_structure_are_partial():
    result = evaluate(
        StructuredSequenceTasks.prompt_for_mastery(0.0),
        "pegar o pão; colocar o pão na torradeira; retirar a torrada.",
    )
    assert result["outcome"] == "partial"
    assert any("1, 2 e 3" in item for item in result["missing_essential_criteria"])


def test_boundaries_are_part_of_the_learning_objective():
    prompt = StructuredSequenceTasks.prompt_for_mastery(0.2)
    good = evaluate(
        prompt,
        "INÍCIO; pegar o copo; beber a água; guardar o copo; FIM.",
    )
    missing_end = evaluate(
        prompt,
        "INÍCIO; pegar o copo; beber a água; guardar o copo.",
    )
    assert good["outcome"] == "demonstrated"
    assert missing_end["outcome"] == "partial"
    assert any("FIM" in item for item in missing_end["missing_essential_criteria"])


def test_missing_step_can_be_answered_without_reproducing_the_whole_structure():
    result = evaluate(
        StructuredSequenceTasks.prompt_for_mastery(0.4),
        "escrever a mensagem.",
    )
    assert result["outcome"] == "demonstrated"


def test_final_task_reuses_previous_ipo_logic_inside_structured_representation():
    result = evaluate(
        StructuredSequenceTasks.prompt_for_mastery(0.7),
        "INÍCIO; receber água e pó de café; preparar a bebida; entregar café pronto; FIM.",
    )
    assert result["outcome"] == "demonstrated"


def test_wrong_order_is_not_demonstrated_even_with_boundaries():
    result = evaluate(
        StructuredSequenceTasks.prompt_for_mastery(0.7),
        "INÍCIO; entregar café pronto; preparar a bebida; receber água e pó de café; FIM.",
    )
    assert result["outcome"] != "demonstrated"
    assert result["missing_essential_criteria"]
