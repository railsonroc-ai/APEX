from backend.services.goal_result_tasks import GoalResultTasks
from backend.services.input_process_output_tasks import InputProcessOutputTasks
from backend.services.task_context_identity import TaskContextIdentity


def test_goal_result_prompt_maps_to_stable_semantic_context():
    prompt = GoalResultTasks.prompt_for_mastery(0.75)
    assert TaskContextIdentity.for_prompt(
        TaskContextIdentity.GOAL_RESULT, prompt
    ) == "goal_backpack_organized"


def test_reissued_same_controlled_prompt_keeps_same_context_identity():
    prompt = GoalResultTasks.prompt_for_mastery(0.75)
    first = TaskContextIdentity.for_prompt(TaskContextIdentity.GOAL_RESULT, prompt)
    second = TaskContextIdentity.for_prompt(TaskContextIdentity.GOAL_RESULT, prompt)
    assert first == second == "goal_backpack_organized"


def test_input_process_output_prompt_has_stable_context_identity():
    prompt = InputProcessOutputTasks.prompt_for_mastery(0.45)
    assert TaskContextIdentity.for_prompt(
        TaskContextIdentity.INPUT_PROCESS_OUTPUT, prompt
    ) == "ipo_calculator_output"


def test_unknown_controlled_prompt_does_not_invent_context():
    assert TaskContextIdentity.for_prompt(
        TaskContextIdentity.GOAL_RESULT,
        "Tarefa: uma atividade qualquer.",
    ) is None
