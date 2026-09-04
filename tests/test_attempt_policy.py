from backend.services.attempt_policy import AttemptPolicy


def test_stage_maps_to_stable_attempt_kind():
    assert AttemptPolicy.kind_for_stage("compreender") == "comprehension"
    assert AttemptPolicy.kind_for_stage("explicar") == "explanation"
    assert AttemptPolicy.kind_for_stage("testar") == "practice"
    assert AttemptPolicy.kind_for_stage("corrigir") == "correction"
    assert AttemptPolicy.kind_for_stage("fixar") == "consolidation"
    assert AttemptPolicy.kind_for_stage("reencontrar") == "retention"


def test_non_evaluable_stage_has_no_attempt_kind():
    assert AttemptPolicy.kind_for_stage("concluido") is None
    assert AttemptPolicy.kind_for_stage(None) is None
