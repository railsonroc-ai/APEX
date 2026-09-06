from backend.services.turn_teaching_contract import TurnTeachingContract
from backend.services.tutor_response_validator import TutorResponseValidator


def contract(mastery, action="consolidar", outcome="demonstrated", difficulty=0):
    return TurnTeachingContract.build(
        {
            "area": "ads",
            "current_concept_id": "ads.algorithms.variable_storage",
            "stage": "fixar",
            "mastery": mastery,
            "difficulty_count": difficulty,
        },
        action,
        evidence_outcome=outcome,
    )


def test_first_turn_introduces_only_variable_as_named_storage():
    item = contract(0.0, action="explicar", outcome=None)
    text = item.safe_response.lower()
    assert item.focus == "variável como lugar nomeado"
    assert item.allow_code is False
    assert "variável" in text
    assert "valor" in text
    assert "declaração" in item.forbidden_terms
    assert "inteiro" in item.forbidden_terms
    assert "leia" in item.forbidden_terms
    assert "escreva" in item.forbidden_terms
    assert "inteiro" not in text
    assert "leia" not in text
    assert "escreva" not in text


def test_later_turns_keep_declaration_types_and_other_syntax_blocked():
    for mastery in (0.2, 0.4, 0.6, 0.8):
        item = contract(mastery)
        assert "declaração" in item.forbidden_terms
        assert "inteiro" in item.forbidden_terms
        assert "condicional" in item.forbidden_terms
        assert "leia" in item.forbidden_terms
        assert "escreva" in item.forbidden_terms
        assert item.allow_code is False


def test_completion_is_terminal_for_this_release_slice():
    item = contract(0.8, action="avancar")
    assert "Esta fatia do percurso está concluída." in item.safe_response


def test_all_variable_storage_fallbacks_validate_against_their_contract():
    for mastery in (0.0, 0.2, 0.4, 0.6, 0.8):
        for action in ("explicar", "testar", "verificar", "consolidar", "corrigir", "avancar"):
            for outcome in (None, "demonstrated", "partial", "misconception", "insufficient", "unverified"):
                for difficulty in (0, 2):
                    item = contract(mastery, action=action, outcome=outcome, difficulty=difficulty)
                    if item.safe_response:
                        result = TutorResponseValidator.validate(item.safe_response, item)
                        assert result["valid"], (mastery, action, outcome, difficulty, result["errors"])
