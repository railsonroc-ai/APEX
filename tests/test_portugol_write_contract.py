from backend.services.turn_teaching_contract import TurnTeachingContract
from backend.services.tutor_response_validator import TutorResponseValidator


def contract(mastery, action="consolidar", outcome="demonstrated", difficulty=0):
    return TurnTeachingContract.build(
        {
            "area": "ads",
            "current_concept_id": "ads.algorithms.portugol_write",
            "stage": "fixar",
            "mastery": mastery,
            "difficulty_count": difficulty,
        },
        action,
        evidence_outcome=outcome,
    )


def test_first_turn_introduces_only_escreva_and_reuses_known_structure():
    item = contract(0.0, action="explicar", outcome=None)
    assert item.focus == "comando escreva"
    assert "leia" in item.forbidden_terms
    assert "variável" in item.forbidden_terms
    assert "escreva" not in item.forbidden_terms
    assert item.allow_code is True
    assert 'escreva("Olá")' in item.safe_response
    assert "leia" not in item.safe_response.lower()


def test_later_turns_keep_same_command_without_releasing_future_syntax():
    for mastery in (0.2, 0.4, 0.6, 0.8):
        item = contract(mastery)
        assert "leia" in item.forbidden_terms
        assert "variável" in item.forbidden_terms
        assert "escreva" not in item.forbidden_terms


def test_completion_is_terminal_for_this_release_slice():
    item = contract(0.8, action="avancar")
    assert "Esta fatia do percurso está concluída." in item.safe_response


def test_all_write_fallbacks_validate_against_their_own_contract():
    for mastery in (0.0, 0.2, 0.4, 0.6, 0.8):
        for action in ("explicar", "testar", "verificar", "consolidar", "corrigir", "avancar"):
            for outcome in (None, "demonstrated", "partial", "misconception", "insufficient", "unverified"):
                for difficulty in (0, 2):
                    item = contract(mastery, action=action, outcome=outcome, difficulty=difficulty)
                    if item.safe_response:
                        result = TutorResponseValidator.validate(item.safe_response, item)
                        assert result["valid"], (mastery, action, outcome, difficulty, result["errors"])
