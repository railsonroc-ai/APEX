from backend.services.turn_teaching_contract import TurnTeachingContract
from backend.services.tutor_response_validator import TutorResponseValidator


def contract(mastery, action="consolidar", outcome="demonstrated"):
    return TurnTeachingContract.build(
        {
            "area": "ads",
            "current_concept_id": "ads.algorithms.structured_sequence",
            "stage": "fixar",
            "mastery": mastery,
            "difficulty_count": 0,
        },
        action,
        evidence_outcome=outcome,
    )


def test_first_turn_introduces_only_explicit_numbered_representation():
    item = contract(0.0, action="explicar", outcome=None)
    assert "numerada" in item.focus
    assert "início" in item.forbidden_terms
    assert "fim" in item.forbidden_terms
    assert item.allow_code is False
    assert "código" not in item.safe_response.lower()
    assert "programação" not in item.safe_response.lower()
    assert "usando 1, 2 e 3" in item.safe_response


def test_second_turn_releases_begin_end_markers_but_still_forbids_code_syntax():
    item = contract(0.2)
    assert "INÍCIO" in item.focus
    assert "início" not in item.forbidden_terms
    assert "fim" not in item.forbidden_terms
    assert "portugol" in item.forbidden_terms
    assert item.allow_code is False


def test_third_turn_reads_existing_structure_without_new_programming_syntax():
    item = contract(0.4)
    assert "ler" in item.focus
    assert "Qual passo está faltando" in item.safe_response
    assert item.allow_code is False


def test_final_turn_integrates_known_logic_without_unlocking_code():
    item = contract(0.6)
    assert "completa" in item.focus
    assert "cafeteira" in item.safe_response.lower()
    assert item.allow_code is False
    assert "python" in item.forbidden_terms


def test_all_controlled_fallbacks_respect_their_own_forbidden_terms():
    for mastery in (0.0, 0.2, 0.4, 0.6, 0.8):
        for action in ("explicar", "testar", "verificar", "consolidar", "corrigir", "avancar"):
            for outcome in (None, "demonstrated", "partial", "misconception", "insufficient", "unverified"):
                for difficulty in (0, 2):
                    item = TurnTeachingContract.build(
                        {
                            "area": "ads",
                            "current_concept_id": "ads.algorithms.structured_sequence",
                            "stage": "fixar",
                            "mastery": mastery,
                            "difficulty_count": difficulty,
                        },
                        action,
                        evidence_outcome=outcome,
                    )
                    if item.safe_response:
                        result = TutorResponseValidator.validate(item.safe_response, item)
                        assert result["valid"], (mastery, action, outcome, difficulty, result["errors"])
