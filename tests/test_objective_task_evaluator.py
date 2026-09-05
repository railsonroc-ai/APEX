import pytest

from backend.services.objective_task_evaluator import ObjectiveTaskEvaluator


def evaluation(answer, prompt=None):
    return {
        "concept_id": "ads.algorithms.ordered_steps",
        "tutor_message": prompt or (
            "coloque estes passos na ordem correta: secar as mãos; "
            "abrir a torneira; lavar as mãos."
        ),
        "student_answer": answer,
    }


@pytest.mark.parametrize(
    "answer",
    (
        "Abrir a torneira, lavar as mãos e secar as mãos.",
        "Primeiro abro a torneira; depois lavo; por último seco.",
        "2, 3, 1",
    ),
)
def test_accepts_correct_order_without_llm(answer):
    result = ObjectiveTaskEvaluator.evaluate(evaluation(answer))

    assert result["outcome"] == "demonstrated"
    assert result["confidence"] == 1.0
    assert result["source"] == "deterministic_task"


def test_rejects_original_wrong_order():
    result = ObjectiveTaskEvaluator.evaluate(
        evaluation("Secar as mãos, abrir a torneira e lavar as mãos.")
    )

    assert result["outcome"] == "misconception"


def test_does_not_claim_open_or_unrelated_tasks():
    assert ObjectiveTaskEvaluator.evaluate(
        evaluation(
            "Abrir a torneira, lavar as mãos e secar as mãos.",
            prompt="Descreva uma atividade cotidiana em três passos.",
        )
    ) is None
    assert ObjectiveTaskEvaluator.evaluate(
        {
            **evaluation("Abrir, lavar, secar"),
            "concept_id": "ads.variables",
        }
    ) is None
