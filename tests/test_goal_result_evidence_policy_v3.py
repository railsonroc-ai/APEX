from backend.services.goal_result_evidence_policy import (
    POLICY_ID,
    normalize_goal_result_evidence,
)


def partial():
    return {"outcome": "partial", "confidence": 0.9, "evidence": "Resposta incompleta."}


def ctx(task, answer):
    return {
        "concept_id": "ads.goal_result",
        "stage": "compreender",
        "tutor_message": task,
        "student_answer": answer,
    }


def test_mochila_semantic_result_is_demonstrated():
    out = normalize_goal_result_evidence(
        partial(),
        evidence_context=ctx(
            "Tarefa: escreva somente o resultado esperado de organizar uma mochila para a aula, começando com Resultado:.",
            "Resultado: mochila organizada para a aula.",
        ),
    )
    assert out["outcome"] == "demonstrated"
    assert out["policy_adjustment"] == POLICY_ID


def test_louca_semantic_result_is_demonstrated():
    out = normalize_goal_result_evidence(
        partial(),
        evidence_context=ctx(
            "Tarefa: escreva somente o resultado esperado de lavar a louça, começando com Resultado:.",
            "Resultado: louça limpa.",
        ),
    )
    assert out["outcome"] == "demonstrated"


def test_documento_semantic_result_is_demonstrated():
    out = normalize_goal_result_evidence(
        partial(),
        task_prompt="Tarefa: escreva somente o resultado esperado de salvar um documento, começando com Resultado:.",
        evidence_context={"student_answer": "Resultado: documento salvo."},
    )
    assert out["outcome"] == "demonstrated"


def test_wrong_object_remains_partial():
    original = partial()
    out = normalize_goal_result_evidence(
        original,
        evidence_context=ctx(
            "Tarefa: escreva somente o resultado esperado de lavar a louça, começando com Resultado:.",
            "Resultado: quarto varrido.",
        ),
    )
    assert out == original


def test_missing_result_prefix_remains_partial():
    original = partial()
    out = normalize_goal_result_evidence(
        original,
        evidence_context=ctx(
            "Tarefa: escreva somente o resultado esperado de organizar uma mochila para a aula, começando com Resultado:.",
            "Mochila organizada para a aula.",
        ),
    )
    assert out == original


def test_unrelated_partial_is_untouched():
    original = partial()
    out = normalize_goal_result_evidence(
        original,
        evidence_context=ctx(
            "Tarefa: explique com suas palavras o que é uma variável.",
            "Resultado: variável guarda valor.",
        ),
    )
    assert out == original
