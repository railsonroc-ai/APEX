from backend.services.turn_teaching_contract import TurnTeachingContract
from backend.services.tutor_response_validator import TutorResponseValidator


def contract(mastery, action="consolidar", outcome="demonstrated", difficulty=0):
    return TurnTeachingContract.build(
        {
            "area": "ads",
            "current_concept_id": "ads.algorithms.read_variable",
            "stage": "fixar",
            "mastery": mastery,
            "difficulty_count": difficulty,
        },
        action,
        evidence_outcome=outcome,
    )


def test_first_turn_connects_leia_to_declared_variable_without_future_output_or_operators():
    item = contract(0.0, action="explicar", outcome=None)
    text = item.safe_response.lower()
    assert item.focus == "variável que recebe a entrada"
    assert item.allow_code is True
    assert "leia" in text
    assert "idade" in text
    assert "inteiro" in text
    assert "escreva" in item.forbidden_terms
    assert "operador" in item.forbidden_terms
    assert "real" in item.forbidden_terms
    assert "escreva" not in text


def test_middle_turns_keep_scope_on_leia_with_existing_integer_variable():
    for mastery in (0.2, 0.4, 0.6, 0.8):
        item = contract(mastery)
        assert "leia" in item.safe_response.lower()
        assert "escreva" in item.forbidden_terms
        assert "atribuição" in item.forbidden_terms
        assert "real" in item.forbidden_terms
        assert "cadeia" in item.forbidden_terms


def test_completion_is_terminal_for_this_release_slice():
    item = contract(0.8, action="avancar")
    assert "Esta fatia do percurso está concluída." in item.safe_response


def test_all_read_variable_fallbacks_validate_against_contract():
    for mastery in (0.0, 0.2, 0.4, 0.6, 0.8):
        for action in ("explicar", "testar", "verificar", "consolidar", "corrigir", "avancar"):
            for outcome in (None, "demonstrated", "partial", "misconception", "insufficient", "unverified"):
                for difficulty in (0, 2):
                    item = contract(mastery, action=action, outcome=outcome, difficulty=difficulty)
                    if item.safe_response:
                        result = TutorResponseValidator.validate(item.safe_response, item)
                        assert result["valid"], (mastery, action, outcome, difficulty, result["errors"], item.safe_response)
