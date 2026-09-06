from backend.services.turn_teaching_contract import TurnTeachingContract
from backend.services.tutor_response_validator import TutorResponseValidator


def contract(mastery, action="consolidar", outcome="demonstrated", difficulty=0):
    return TurnTeachingContract.build(
        {
            "area": "ads",
            "current_concept_id": "ads.algorithms.portugol_read",
            "stage": "fixar",
            "mastery": mastery,
            "difficulty_count": difficulty,
        },
        action,
        evidence_outcome=outcome,
    )


def test_first_turn_introduces_only_leia_and_reuses_prior_concepts():
    item = contract(0.0, action="explicar", outcome=None)
    assert item.focus == "comando leia"
    assert "variável" in item.forbidden_terms
    assert "inteiro" in item.forbidden_terms
    assert "leia" not in item.forbidden_terms
    assert "escreva" not in item.forbidden_terms
    assert item.allow_code is True
    assert "leia" in item.safe_response.lower()
    assert "variável" not in item.safe_response.lower()


def test_later_turns_keep_future_storage_and_control_syntax_blocked():
    for mastery in (0.2, 0.4, 0.6, 0.8):
        item = contract(mastery)
        assert "variável" in item.forbidden_terms
        assert "inteiro" in item.forbidden_terms
        assert "condicional" in item.forbidden_terms
        assert "leia" not in item.forbidden_terms


def test_completion_is_terminal_for_this_release_slice():
    item = contract(0.8, action="avancar")
    assert "Esta fatia do percurso está concluída." in item.safe_response


def test_all_read_fallbacks_validate_against_their_contract():
    for mastery in (0.0, 0.2, 0.4, 0.6, 0.8):
        for action in ("explicar", "testar", "verificar", "consolidar", "corrigir", "avancar"):
            for outcome in (None, "demonstrated", "partial", "misconception", "insufficient", "unverified"):
                for difficulty in (0, 2):
                    item = contract(mastery, action=action, outcome=outcome, difficulty=difficulty)
                    if item.safe_response:
                        result = TutorResponseValidator.validate(item.safe_response, item)
                        assert result["valid"], (mastery, action, outcome, difficulty, result["errors"])
