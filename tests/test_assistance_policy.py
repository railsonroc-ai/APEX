from backend.services.assistance_policy import AssistancePolicy


def test_server_actions_have_stable_assistance_levels():
    assert AssistancePolicy.level_for_action("testar") == "independent"
    assert AssistancePolicy.level_for_action("revisar") == "independent"
    assert AssistancePolicy.level_for_action("verificar") == "light"
    assert AssistancePolicy.level_for_action("consolidar") == "light"
    assert AssistancePolicy.level_for_action("explicar") == "guided"
    assert AssistancePolicy.level_for_action("corrigir") == "direct"
    assert AssistancePolicy.level_for_action("avancar") == "untracked"


def test_invalid_or_external_value_cannot_claim_independence():
    assert AssistancePolicy.level_for_action("independent") == "untracked"
    assert AssistancePolicy.level_for_action("qualquer-coisa") == "untracked"
    assert AssistancePolicy.level_for_action(None) == "untracked"


def test_contract_is_derived_from_action_not_from_model_output():
    contract = AssistancePolicy.contract_for_action("testar")

    assert contract["policy_id"] == AssistancePolicy.POLICY_ID
    assert contract["policy_version"] == AssistancePolicy.POLICY_VERSION
    assert contract["teaching_action"] == "testar"
    assert contract["assistance_level"] == "independent"
    assert "sem fornecer a resposta" in contract["instruction"]
