from backend.services.turn_teaching_contract import TurnTeachingContract
from backend.services.tutor_response_validator import TutorResponseValidator


def contract(mastery, action="consolidar", outcome="demonstrated"):
    return TurnTeachingContract.build(
        {
            "area": "ads",
            "current_concept_id": "ads.algorithms.portugol_skeleton",
            "stage": "fixar",
            "mastery": mastery,
            "difficulty_count": 0,
        },
        action,
        evidence_outcome=outcome,
    )


def test_first_turn_releases_only_algoritmo():
    item = contract(0.0, action="explicar", outcome=None)
    assert item.focus == "palavra-chave algoritmo"
    assert "inicio" in item.forbidden_terms
    assert "fimalgoritmo" in item.forbidden_terms
    assert "leia" in item.forbidden_terms
    assert "escreva" in item.forbidden_terms
    assert item.allow_code is True
    assert "algoritmo" in item.safe_response.lower()
    assert "fimalgoritmo" not in item.safe_response.lower()


def test_second_turn_releases_inicio_but_not_fimalgoritmo():
    item = contract(0.2)
    assert item.focus == "palavra-chave inicio"
    assert "inicio" not in item.forbidden_terms
    assert "fimalgoritmo" in item.forbidden_terms
    assert "Agora uma novidade: inicio" in item.safe_response


def test_third_turn_releases_fimalgoritmo_without_commands_inside():
    item = contract(0.4)
    assert item.focus == "palavra-chave fimalgoritmo"
    assert "fimalgoritmo" not in item.forbidden_terms
    assert "leia" in item.forbidden_terms
    assert "escreva" in item.forbidden_terms
    assert "Agora uma novidade: fimalgoritmo" in item.safe_response


def test_final_turn_combines_only_the_three_known_keywords():
    item = contract(0.6)
    assert "três palavras-chave" in item.focus
    assert "nenhum comando novo" in item.safe_response
    assert "leia" in item.forbidden_terms
    assert "escreva" in item.forbidden_terms


def test_all_portugol_fallbacks_validate_against_their_own_contract():
    for mastery in (0.0, 0.2, 0.4, 0.6, 0.8):
        for action in ("explicar", "testar", "verificar", "consolidar", "corrigir", "avancar"):
            for outcome in (None, "demonstrated", "partial", "misconception", "insufficient", "unverified"):
                for difficulty in (0, 2):
                    item = TurnTeachingContract.build(
                        {
                            "area": "ads",
                            "current_concept_id": "ads.algorithms.portugol_skeleton",
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
