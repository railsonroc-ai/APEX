from backend.services.teaching_policy import TeachingPolicy


def test_default_action_is_explain():
    assert TeachingPolicy.choose_action(None) == "explicar"


def test_difficulty_prioritizes_correction():
    state = {"stage": "testar", "difficulty_count": 2, "mastery": 0.4}
    assert TeachingPolicy.choose_action(state) == "corrigir"


def test_high_mastery_prioritizes_consolidation():
    state = {"stage": "explicar", "difficulty_count": 0, "mastery": 0.9}
    assert TeachingPolicy.choose_action(state) == "consolidar"


def test_reencounter_stage_maps_to_review():
    state = {"stage": "reencontrar", "difficulty_count": 0, "mastery": 0.6}
    assert TeachingPolicy.choose_action(state) == "revisar"
