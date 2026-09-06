from backend.services.goal_result_tasks import GoalResultTasks
from backend.services.input_process_output_tasks import InputProcessOutputTasks
from backend.services.structured_sequence_tasks import StructuredSequenceTasks
from backend.services.portugol_skeleton_tasks import PortugolSkeletonTasks
from backend.services.portugol_write_tasks import PortugolWriteTasks
from backend.services.portugol_read_tasks import PortugolReadTasks
from backend.services.variable_storage_tasks import VariableStorageTasks
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


def test_structured_sequence_prompt_has_stable_context_identity():
    prompt = StructuredSequenceTasks.prompt_for_mastery(0.25)
    assert TaskContextIdentity.for_prompt(
        TaskContextIdentity.STRUCTURED_SEQUENCE, prompt
    ) == "structured_water_boundaries"
    assert TaskContextIdentity.requires_explicit_context(
        TaskContextIdentity.STRUCTURED_SEQUENCE
    )


def test_unknown_controlled_prompt_does_not_invent_context():
    assert TaskContextIdentity.for_prompt(
        TaskContextIdentity.GOAL_RESULT,
        "Tarefa: uma atividade qualquer.",
    ) is None


def test_portugol_skeleton_prompt_has_stable_context_identity():
    prompt = PortugolSkeletonTasks.prompt_for_mastery(0.45)
    assert TaskContextIdentity.for_prompt(
        TaskContextIdentity.PORTUGOL_SKELETON, prompt
    ) == "portugol_keyword_fimalgoritmo"
    assert TaskContextIdentity.requires_explicit_context(
        TaskContextIdentity.PORTUGOL_SKELETON
    )


def test_portugol_write_prompt_has_stable_context_identity():
    prompt = PortugolWriteTasks.prompt_for_mastery(0.45)
    assert TaskContextIdentity.for_prompt(
        TaskContextIdentity.PORTUGOL_WRITE, prompt
    ) == "write_line_done"
    assert TaskContextIdentity.requires_explicit_context(
        TaskContextIdentity.PORTUGOL_WRITE
    )


def test_portugol_read_prompt_has_stable_context_identity():
    prompt = PortugolReadTasks.prompt_for_mastery(0.65)
    assert TaskContextIdentity.for_prompt(
        TaskContextIdentity.PORTUGOL_READ, prompt
    ) == "read_flow_integration"
    assert TaskContextIdentity.requires_explicit_context(
        TaskContextIdentity.PORTUGOL_READ
    )


def test_variable_storage_prompt_has_stable_context_identity():
    prompt = VariableStorageTasks.prompt_for_mastery(0.65)
    assert TaskContextIdentity.for_prompt(
        TaskContextIdentity.VARIABLE_STORAGE, prompt
    ) == "variable_current_value_balance"
    assert TaskContextIdentity.requires_explicit_context(
        TaskContextIdentity.VARIABLE_STORAGE
    )
