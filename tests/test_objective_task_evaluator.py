import pytest

from backend.services.objective_task_evaluator import ObjectiveTaskEvaluator


def evaluation(answer, prompt=None):
    return {
        "concept_id": "ads.algorithms.ordered_steps",
        "tutor_message": prompt or (
            "coloque estes passos na ordem correta: secar as mãos; "
            "abrir a torneira; lavar as mãos."
        ),
        "student_answer": answer,
    }


def goal_evaluation(answer, prompt):
    return {
        "concept_id": "ads.algorithms.goal_result",
        "tutor_message": prompt,
        "student_answer": answer,
    }


@pytest.mark.parametrize(
    "answer",
    (
        "Abrir a torneira, lavar as mãos e secar as mãos.",
        "Primeiro abro a torneira; depois lavo; por último seco.",
        "2, 3, 1",
    ),
)
def test_accepts_correct_order_without_llm(answer):
    result = ObjectiveTaskEvaluator.evaluate(evaluation(answer))

    assert result["outcome"] == "demonstrated"
    assert result["confidence"] == 1.0
    assert result["source"] == "deterministic_task"


def test_rejects_original_wrong_order():
    result = ObjectiveTaskEvaluator.evaluate(
        evaluation("Secar as mãos, abrir a torneira e lavar as mãos.")
    )

    assert result["outcome"] == "misconception"


@pytest.mark.parametrize("answer", ("entendi", "ok", "tá"))
def test_short_acknowledgement_is_insufficient_and_cannot_advance(answer):
    result = ObjectiveTaskEvaluator.evaluate(evaluation(answer))

    assert result["outcome"] == "insufficient"
    assert result["criteria"]["task_response"] == "not_met"


def test_does_not_claim_open_or_unrelated_tasks():
    assert ObjectiveTaskEvaluator.evaluate(
        evaluation(
            "Abrir a torneira, lavar as mãos e secar as mãos.",
            prompt="Descreva uma atividade cotidiana em três passos.",
        )
    ) is None
    assert ObjectiveTaskEvaluator.evaluate(
        {
            **evaluation("Abrir, lavar, secar"),
            "concept_id": "ads.variables",
        }
    ) is None


def test_accepts_known_open_file_task_without_llm():
    result = ObjectiveTaskEvaluator.evaluate(
        evaluation(
            "abrir o menu Arquivo; selecionar Salvar como; "
            "escolher o local e confirmar o salvamento",
            prompt=(
                "descreva como guardar um arquivo usando exatamente três passos "
                "na ordem em que precisam acontecer"
            ),
        )
    )

    assert result["outcome"] == "demonstrated"
    assert result["source"] == "deterministic_task"


@pytest.mark.parametrize(
    ("prompt", "answer"),
    (
        (
            "coloque em ordem: clicar em Enviar; escrever a mensagem; abrir a conversa",
            "abrir a conversa; escrever a mensagem; clicar em Enviar",
        ),
        (
            "coloque em ordem: guardar o copo; pegar o copo; beber a água",
            "pegar o copo; beber a água; guardar o copo",
        ),
    ),
)
def test_accepts_known_consolidation_tasks_without_llm(prompt, answer):
    result = ObjectiveTaskEvaluator.evaluate(evaluation(answer, prompt=prompt))

    assert result["outcome"] == "demonstrated"
    assert result["source"] == "deterministic_task"


def test_known_file_task_does_not_accept_three_unrelated_steps():
    result = ObjectiveTaskEvaluator.evaluate(
        evaluation(
            "abrir a janela; fechar a janela; tomar café",
            prompt=(
                "descreva como guardar um arquivo usando exatamente três passos "
                "na ordem em que precisam acontecer"
            ),
        )
    )

    assert result["outcome"] == "insufficient"


def test_goal_result_choice_is_evaluated_without_llm():
    prompt = (
        "para a atividade carregar o celular, escolha o resultado esperado: "
        "A) celular conectado e carregando; B) quarto varrido; C) porta trancada"
    )

    assert ObjectiveTaskEvaluator.evaluate(
        goal_evaluation("A", prompt)
    )["outcome"] == "demonstrated"
    assert ObjectiveTaskEvaluator.evaluate(
        goal_evaluation("B", prompt)
    )["outcome"] == "misconception"
    assert ObjectiveTaskEvaluator.evaluate(
        goal_evaluation("entendi", prompt)
    )["outcome"] == "insufficient"


@pytest.mark.parametrize(
    ("prompt", "answer"),
    (
        (
            "escreva somente o resultado esperado de salvar um documento, "
            "começando com Resultado:",
            "Resultado: documento salvo.",
        ),
        (
            "escreva somente o resultado esperado de lavar a louça, "
            "começando com Resultado:",
            "Resultado: louça limpa.",
        ),
        (
            "escreva somente o resultado esperado de organizar uma mochila para "
            "a aula, começando com Resultado:",
            "Resultado: mochila organizada para a aula.",
        ),
        (
            "sem consultar, escreva somente o resultado esperado de escovar os "
            "dentes, começando com Resultado:",
            "Resultado: dentes limpos.",
        ),
    ),
)
def test_goal_result_production_tasks_are_evaluated_locally(prompt, answer):
    result = ObjectiveTaskEvaluator.evaluate(goal_evaluation(answer, prompt))

    assert result["outcome"] == "demonstrated"
    assert result["source"] == "deterministic_task"


def test_goal_result_rejects_a_list_of_actions_as_the_final_result():
    result = ObjectiveTaskEvaluator.evaluate(
        goal_evaluation(
            "Resultado: primeiro abrir, depois clicar e selecionar.",
            "escreva somente o resultado esperado de salvar um documento, "
            "começando com Resultado:",
        )
    )

    assert result["outcome"] == "misconception"


def test_goal_result_partial_identifies_missing_essential_criterion():
    result = ObjectiveTaskEvaluator.evaluate(
        goal_evaluation(
            "Resultado: mochila.",
            "escreva somente o resultado esperado de organizar uma mochila "
            "para a aula, começando com Resultado:",
        )
    )

    assert result["outcome"] == "partial"
    assert result["missing_essential_criteria"]
    assert any(
        "organizada" in item or "pronta" in item
        for item in result["missing_essential_criteria"]
    )


def test_goal_result_does_not_require_unasked_consequences():
    cases = (
        (
            "escreva somente o resultado esperado de salvar um documento, "
            "começando com Resultado:",
            "Resultado: documento salvo.",
        ),
        (
            "escreva somente o resultado esperado de lavar a louça, "
            "começando com Resultado:",
            "Resultado: louça limpa.",
        ),
        (
            "escreva somente o resultado esperado de organizar uma mochila "
            "para a aula, começando com Resultado:",
            "Resultado: mochila organizada para a aula.",
        ),
    )

    for prompt, answer in cases:
        result = ObjectiveTaskEvaluator.evaluate(goal_evaluation(answer, prompt))
        assert result["outcome"] == "demonstrated"
        assert result["missing_essential_criteria"] == []

@pytest.mark.parametrize(
    ("prompt", "answer"),
    (
        (
            "escreva somente o resultado esperado de salvar um documento, "
            "começando com Resultado:",
            "documento salvo.",
        ),
        (
            "escreva somente o resultado esperado de lavar a louça, "
            "começando com Resultado:",
            "louça limpa.",
        ),
        (
            "escreva somente o resultado esperado de organizar uma mochila para "
            "a aula, começando com Resultado:",
            "mochila organizada para a aula.",
        ),
        (
            "sem consultar, escreva somente o resultado esperado de escovar os "
            "dentes, começando com Resultado:",
            "dentes limpos.",
        ),
    ),
)
def test_goal_result_literal_result_label_is_not_required_for_mastery(prompt, answer):
    result = ObjectiveTaskEvaluator.evaluate(goal_evaluation(answer, prompt))

    assert result["outcome"] == "demonstrated"
    assert result["missing_essential_criteria"] == []


def test_goal_result_steps_are_rejected_even_without_result_label():
    result = ObjectiveTaskEvaluator.evaluate(
        goal_evaluation(
            "documento salvo; primeiro abrir, depois clicar e selecionar.",
            "escreva somente o resultado esperado de salvar um documento, "
            "começando com Resultado:",
        )
    )

    assert result["outcome"] == "misconception"
    assert result["missing_essential_criteria"] == [
        "descrever somente a situação final, sem listar os passos"
    ]
