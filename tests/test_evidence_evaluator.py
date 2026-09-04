from backend.services.evidence_evaluator import EvidenceEvaluator


def test_builds_evaluation_when_applicable():
    state = {"current_concept": "variáveis", "stage": "testar"}
    history = [{"role": "assistant", "content": "Explique o que é uma variável."}]
    result = EvidenceEvaluator.build_evaluation("É um espaço usado para guardar um valor.", history, state)
    assert result["concept"] == "variáveis"
    assert result["stage"] == "testar"
    assert result["student_answer"] == "É um espaço usado para guardar um valor."


def test_control_message_is_not_evaluated():
    state = {"current_concept": "variáveis", "stage": "testar"}
    history = [{"role": "assistant", "content": "Explique o que é uma variável."}]
    result = EvidenceEvaluator.build_evaluation("Pode me testar?", history, state)
    assert result is None


def test_without_current_concept_is_not_applicable():
    state = {"current_concept": None, "stage": "testar"}
    history = [{"role": "assistant", "content": "Explique o conceito."}]
    result = EvidenceEvaluator.build_evaluation("Minha resposta", history, state)
    assert result is None


def test_comprehension_stage_is_evaluated():
    state = {"current_concept": "variáveis", "stage": "compreender"}
    history = [{"role": "assistant", "content": "Explique com suas palavras o que é uma variável."}]
    result = EvidenceEvaluator.build_evaluation(
        "É um espaço usado para guardar um valor.",
        history,
        state,
    )
    assert result is not None
    assert result["concept"] == "variáveis"
    assert result["stage"] == "compreender"


def test_without_previous_tutor_message_is_not_evaluated():
    state = {"current_concept": "variáveis", "stage": "testar"}
    history = [{"role": "user", "content": "Quero estudar variáveis."}]
    result = EvidenceEvaluator.build_evaluation("Uma variável guarda um valor.", history, state)
    assert result is None


def test_parses_semantic_evaluation_response():
    valid = "{\"outcome\":\"demonstrated\",\"confidence\":0.9,\"evidence\":\"Explicou corretamente.\"}"
    result = EvidenceEvaluator.parse_evaluation_response(valid)
    assert result == {"outcome": "demonstrated", "confidence": 0.9, "evidence": "Explicou corretamente."}
    assert EvidenceEvaluator.parse_evaluation_response("{\"outcome\":\"inventado\",\"confidence\":0.9}") is None
    assert EvidenceEvaluator.parse_evaluation_response("{\"outcome\":\"partial\",\"confidence\":1.5}") is None
    assert EvidenceEvaluator.parse_evaluation_response("resposta inválida") is None




def test_builds_semantic_evaluation_messages():
    evaluation = {
        "concept": "variáveis",
        "stage": "testar",
        "tutor_message": "Explique o que é uma variável.",
        "student_answer": "É um espaço usado para guardar um valor.",
    }
    result = EvidenceEvaluator.build_evaluation_messages(evaluation)
    assert len(result) == 2
    assert result[0]["role"] == "system"
    assert "Rubrica semantic_evidence v1" in result[0]["content"]
    assert "três critérios" in result[0]["content"]
    assert result[1]["role"] == "user"
    assert "Conceito: variáveis" in result[1]["content"]
