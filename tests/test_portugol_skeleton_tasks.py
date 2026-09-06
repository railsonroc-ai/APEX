from backend.services.objective_task_evaluator import ObjectiveTaskEvaluator
from backend.services.portugol_skeleton_tasks import PortugolSkeletonTasks


CONCEPT = "ads.algorithms.portugol_skeleton"


def evaluate(prompt, answer):
    return ObjectiveTaskEvaluator.evaluate(
        {
            "concept_id": CONCEPT,
            "tutor_message": prompt,
            "student_answer": answer,
        }
    )


def test_task_sequence_releases_one_keyword_at_a_time():
    assert PortugolSkeletonTasks.focus_for_mastery(0.0) == "palavra-chave algoritmo"
    assert PortugolSkeletonTasks.focus_for_mastery(0.2) == "palavra-chave inicio"
    assert PortugolSkeletonTasks.focus_for_mastery(0.4) == "palavra-chave fimalgoritmo"
    assert "três palavras-chave" in PortugolSkeletonTasks.focus_for_mastery(0.6)


def test_each_single_keyword_answer_is_deterministically_demonstrated():
    cases = (
        (0.0, "algoritmo"),
        (0.2, "inicio"),
        (0.4, "fimalgoritmo"),
    )
    for mastery, answer in cases:
        result = evaluate(PortugolSkeletonTasks.prompt_for_mastery(mastery), answer)
        assert result["outcome"] == "demonstrated"
        assert result["missing_essential_criteria"] == []


def test_integrated_skeleton_requires_keywords_in_correct_order():
    prompt = PortugolSkeletonTasks.prompt_for_mastery(0.7)
    good = evaluate(prompt, "algoritmo; inicio; fimalgoritmo")
    wrong = evaluate(prompt, "inicio; algoritmo; fimalgoritmo")
    assert good["outcome"] == "demonstrated"
    assert wrong["outcome"] == "misconception"
    assert wrong["missing_essential_criteria"]


def test_partial_skeleton_names_real_missing_keyword():
    result = evaluate(
        PortugolSkeletonTasks.prompt_for_mastery(0.7),
        "algoritmo; inicio",
    )
    assert result["outcome"] == "partial"
    assert "incluir fimalgoritmo" in result["missing_essential_criteria"]
