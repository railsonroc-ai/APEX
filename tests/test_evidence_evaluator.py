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


def test_comprehension_stage_is_not_evaluated():
    state = {"current_concept": "variáveis", "stage": "compreender"}
    history = [{"role": "assistant", "content": "Uma variável guarda um valor."}]
    result = EvidenceEvaluator.build_evaluation("Certo, entendi.", history, state)
    assert result is None


def test_without_previous_tutor_message_is_not_evaluated():
    state = {"current_concept": "variáveis", "stage": "testar"}
    history = [{"role": "user", "content": "Quero estudar variáveis."}]
    result = EvidenceEvaluator.build_evaluation("Uma variável guarda um valor.", history, state)
    assert result is None
