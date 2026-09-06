from backend.services.turn_teaching_contract import TurnTeachingContract
from backend.services.tutor_response_validator import TutorResponseValidator


def contract(mastery, action="consolidar", outcome="demonstrated", difficulty=0):
    return TurnTeachingContract.build(
        {
            "area": "ads",
            "current_concept_id": "ads.algorithms.write_variable",
            "stage": "fixar",
            "mastery": mastery,
            "difficulty_count": difficulty,
        },
        action,
        evidence_outcome=outcome,
    )


def test_first_turn_connects_escreva_to_declared_variable_without_future_operators_or_types():
    item = contract(0.0, action="explicar", outcome=None)
    text = item.safe_response.lower()
    assert item.focus == "variável cujo valor é mostrado"
    assert item.allow_code is True
    assert "escreva" in text
    assert "pontos" in text
    assert "inteiro" in text
    assert "operador" in item.forbidden_terms
    assert "atribuição" in item.forbidden_terms
    assert "real" in item.forbidden_terms
    assert "real" not in text


def test_middle_turns_keep_scope_on_escreva_with_existing_integer_variable():
    for mastery in (0.2, 0.4, 0.6, 0.8):
        item = contract(mastery)
        assert "escreva" in item.safe_response.lower()
        assert "atribuição" in item.forbidden_terms
        assert "operador" in item.forbidden_terms
        assert "real" in item.forbidden_terms
        assert "cadeia" in item.forbidden_terms


def test_completion_is_terminal_for_this_release_slice():
    item = contract(0.8, action="avancar")
    assert "Esta fatia do percurso está concluída." in item.safe_response


def test_all_write_variable_fallbacks_validate_against_contract():
    for mastery in (0.0, 0.2, 0.4, 0.6, 0.8):
        for action in ("explicar", "testar", "verificar", "consolidar", "corrigir", "avancar"):
            for outcome in (None, "demonstrated", "partial", "misconception", "insufficient", "unverified"):
                for difficulty in (0, 2):
                    item = contract(mastery, action=action, outcome=outcome, difficulty=difficulty)
                    if item.safe_response:
                        result = TutorResponseValidator.validate(item.safe_response, item)
                        assert result["valid"], (mastery, action, outcome, difficulty, result["errors"], item.safe_response)
