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


def test_curriculum_rejects_skips_and_has_no_invented_third_node():
    assert not Curriculum.allows_progression(
        "ads.variables",
        Curriculum.GOAL_RESULT,
    )
    assert Curriculum.next_concept_id(Curriculum.GOAL_RESULT) is None
