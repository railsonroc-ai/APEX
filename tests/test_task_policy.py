from backend.services.task_policy import TaskPolicy


def test_task_policy_maps_server_actions_to_single_assessable_task_kinds():
    assert TaskPolicy.POLICY_ID == "server_assessment_task"
    assert TaskPolicy.POLICY_VERSION == 1
    assert TaskPolicy.task_kind_for_action("testar") == "practice"
    assert TaskPolicy.task_kind_for_action("revisar") == "retention"
    assert TaskPolicy.task_kind_for_action("verificar") == "verification"
    assert TaskPolicy.task_kind_for_action("consolidar") == "consolidation"
    assert TaskPolicy.task_kind_for_action("explicar") == "guided_check"
    assert TaskPolicy.task_kind_for_action("corrigir") == "correction_retry"
    assert TaskPolicy.task_kind_for_action("avancar") is None
    assert TaskPolicy.is_assessable_action("testar") is True
    assert TaskPolicy.is_assessable_action("avancar") is False


def test_task_contract_carries_rubric_and_server_instruction():
    contract = TaskPolicy.contract_for_action("testar")
    assert contract["assessable"] is True
    assert contract["task_kind"] == "practice"
    assert contract["rubric_id"] == "semantic_evidence"
    assert contract["rubric_version"] == 2
    assert "única tarefa curta" in contract["instruction"]
