from backend.services.turn_teaching_contract import TurnTeachingContract


def contract(mastery, action="consolidar", outcome="demonstrated"):
    return TurnTeachingContract.build(
        {
            "area": "ads",
            "current_concept_id": "ads.algorithms.input_process_output",
            "stage": "fixar",
            "mastery": mastery,
            "difficulty_count": 0,
        },
        action,
        evidence_outcome=outcome,
    )


def test_first_turn_exposes_only_input_as_new_component():
    item = contract(0.0, action="explicar", outcome=None)
    assert item.focus == "entrada"
    assert "processamento" in item.forbidden_terms
    assert "saída" in item.forbidden_terms
    assert "Entrada é" in item.safe_response


def test_second_turn_releases_processing_but_still_hides_output():
    item = contract(0.2)
    assert item.focus == "processamento"
    assert "processamento" not in item.forbidden_terms
    assert "saída" in item.forbidden_terms
    assert "Agora uma novidade: processamento" in item.safe_response


def test_third_turn_releases_output_without_code():
    item = contract(0.4)
    assert item.focus == "saída"
    assert "saída" not in item.forbidden_terms
    assert item.allow_code is False
    assert "Agora uma novidade: saída" in item.safe_response


def test_final_mapping_adds_no_new_component():
    item = contract(0.6)
    assert "relação" in item.focus
    assert "reúna as três ideias" in item.safe_response
    assert item.allow_code is False
