from backend.services.curriculum import Curriculum


def test_algorithms_enters_first_microconcept():
    assert Curriculum.entry_concept_id("ads.algorithms") == Curriculum.ORDERED_STEPS


def test_second_microconcept_has_one_declared_prerequisite():
    assert Curriculum.next_concept_id(Curriculum.ORDERED_STEPS) == Curriculum.GOAL_RESULT
    assert Curriculum.prerequisites_for(Curriculum.GOAL_RESULT) == (
        Curriculum.ORDERED_STEPS,
    )
    assert Curriculum.allows_progression(
        Curriculum.ORDERED_STEPS,
        Curriculum.GOAL_RESULT,
    )


def test_goal_result_progresses_to_input_process_output_without_skip():
    assert (
        Curriculum.next_concept_id(Curriculum.GOAL_RESULT)
        == Curriculum.INPUT_PROCESS_OUTPUT
    )
    assert Curriculum.prerequisites_for(Curriculum.INPUT_PROCESS_OUTPUT) == (
        Curriculum.GOAL_RESULT,
    )
    assert Curriculum.allows_progression(
        Curriculum.GOAL_RESULT,
        Curriculum.INPUT_PROCESS_OUTPUT,
    )
    assert not Curriculum.allows_progression(
        Curriculum.ORDERED_STEPS,
        Curriculum.INPUT_PROCESS_OUTPUT,
    )


def test_input_process_output_progresses_to_structured_sequence_without_skip():
    assert (
        Curriculum.next_concept_id(Curriculum.INPUT_PROCESS_OUTPUT)
        == Curriculum.STRUCTURED_SEQUENCE
    )
    assert Curriculum.prerequisites_for(Curriculum.STRUCTURED_SEQUENCE) == (
        Curriculum.INPUT_PROCESS_OUTPUT,
    )
    assert Curriculum.allows_progression(
        Curriculum.INPUT_PROCESS_OUTPUT,
        Curriculum.STRUCTURED_SEQUENCE,
    )
    assert not Curriculum.allows_progression(
        Curriculum.GOAL_RESULT,
        Curriculum.STRUCTURED_SEQUENCE,
    )


def test_structured_sequence_progresses_to_portugol_skeleton_without_skip():
    assert (
        Curriculum.next_concept_id(Curriculum.STRUCTURED_SEQUENCE)
        == Curriculum.PORTUGOL_SKELETON
    )
    assert Curriculum.prerequisites_for(Curriculum.PORTUGOL_SKELETON) == (
        Curriculum.STRUCTURED_SEQUENCE,
    )
    assert Curriculum.allows_progression(
        Curriculum.STRUCTURED_SEQUENCE,
        Curriculum.PORTUGOL_SKELETON,
    )
    assert not Curriculum.allows_progression(
        Curriculum.INPUT_PROCESS_OUTPUT,
        Curriculum.PORTUGOL_SKELETON,
    )
