from backend.services.turn_teaching_contract import TurnTeachingContract
from backend.services.tutor_response_validator import TutorResponseValidator


def contract(mastery, action="consolidar", outcome="demonstrated", difficulty=0):
    return TurnTeachingContract.build(
        {
            "area": "ads",
            "current_concept_id": "ads.algorithms.integer_declaration",
            "stage": "fixar",
            "mastery": mastery,
            "difficulty_count": difficulty,
        },
        action,
        evidence_outcome=outcome,
    )


def test_first_turn_introduces_var_without_inteiro_or_variable_use():
    item = contract(0.0, action="explicar", outcome=None)
    text = item.safe_response.lower()
    assert item.focus == "palavra-chave var"
    assert item.allow_code is True
    assert " var " in f" {text} "
    assert "inteiro" in item.forbidden_terms
    assert "inteiro" not in text
    assert "leia" in item.forbidden_terms
    assert "escreva" in item.forbidden_terms
    assert "leia" not in text
    assert "escreva" not in text


def test_second_turn_allows_only_new_type_inteiro_not_future_use():
    item = contract(0.2)
    assert item.focus == "tipo inteiro"
    assert "inteiro" not in item.forbidden_terms
    assert "leia" in item.forbidden_terms
    assert "escreva" in item.forbidden_terms
    assert "real" in item.forbidden_terms
    assert "inteiro" in item.safe_response.lower()


def test_later_turns_keep_other_types_input_output_and_operators_blocked():
    for mastery in (0.4, 0.6, 0.8):
        item = contract(mastery)
        assert "real" in item.forbidden_terms
        assert "cadeia" in item.forbidden_terms
        assert "leia" in item.forbidden_terms
        assert "escreva" in item.forbidden_terms
        assert "operador" in item.forbidden_terms


def test_completion_is_terminal_for_this_release_slice():
    item = contract(0.8, action="avancar")
    assert "Esta fatia do percurso está concluída." in item.safe_response


def test_all_integer_declaration_fallbacks_validate_against_contract():
    for mastery in (0.0, 0.2, 0.4, 0.6, 0.8):
        for action in ("explicar", "testar", "verificar", "consolidar", "corrigir", "avancar"):
            for outcome in (None, "demonstrated", "partial", "misconception", "insufficient", "unverified"):
                for difficulty in (0, 2):
                    item = contract(mastery, action=action, outcome=outcome, difficulty=difficulty)
                    if item.safe_response:
                        result = TutorResponseValidator.validate(item.safe_response, item)
                        assert result["valid"], (mastery, action, outcome, difficulty, result["errors"], item.safe_response)
