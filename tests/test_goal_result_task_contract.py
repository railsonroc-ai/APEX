from backend.services.goal_result_tasks import GoalResultTasks
from backend.services.objective_task_evaluator import ObjectiveTaskEvaluator


def evaluation(prompt, answer):
    return {
        "concept_id": "ads.algorithms.goal_result",
        "tutor_message": prompt,
        "student_answer": answer,
    }


def test_generated_prompts_are_resolved_by_the_same_task_definition():
    for mastery in (0.0, 0.25, 0.45, 0.75):
        prompt = GoalResultTasks.prompt_for_mastery(mastery)
        definition = GoalResultTasks.definition_for_prompt(prompt)
        assert definition is not None
        assert definition["prompt"] == prompt


def test_minimal_explicit_results_satisfy_shared_rubric():
    cases = (
        (0.25, "Resultado: documento salvo."),
        (0.45, "Resultado: louça limpa."),
        (0.75, "Resultado: mochila organizada para a aula."),
    )
    for mastery, answer in cases:
        prompt = GoalResultTasks.prompt_for_mastery(mastery)
        result = ObjectiveTaskEvaluator.evaluate(evaluation(prompt, answer))
        assert result["outcome"] == "demonstrated"
        assert result["missing_essential_criteria"] == []


def test_partial_goal_result_always_names_a_missing_essential_criterion():
    prompt = GoalResultTasks.prompt_for_mastery(0.75)
    result = ObjectiveTaskEvaluator.evaluate(
        evaluation(prompt, "Resultado: mochila.")
    )
    assert result["outcome"] == "partial"
    assert result["missing_essential_criteria"]
