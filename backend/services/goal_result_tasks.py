from backend.concepts import normalize_alias


class GoalResultTasks:
    """Fonte única de enunciados e critérios essenciais de resultado esperado.

    O mesmo objeto que gera a tarefa exibida ao aluno também fornece a rubrica
    determinística usada pelo avaliador. Isso impede que o enunciado peça uma
    coisa e o avaliador exija outra não declarada.
    """

    TASKS = (
        {
            "task_id": "goal_phone_charge",
            "kind": "choice",
            "mastery_lt": 0.2,
            "prompt": (
                "Tarefa: para a atividade carregar o celular, escolha o resultado "
                "esperado: A) celular conectado e carregando; B) quarto varrido; "
                "C) porta trancada."
            ),
            "prompt_markers": (
                "carregar o celular",
                "resultado esperado",
                "celular conectado e carregando",
            ),
            "essential_criteria": (
                {
                    "id": "activity_object",
                    "label": "identificar o celular/aparelho da atividade",
                    "markers": ("celular", "aparelho"),
                },
                {
                    "id": "final_state",
                    "label": "indicar que o celular ficou carregando ou recebendo carga",
                    "markers": ("carreg", "carga"),
                },
            ),
            "success": "Identificou o resultado esperado de carregar o celular.",
        },
        {
            "task_id": "goal_document_saved",
            "kind": "result",
            "mastery_lt": 0.4,
            "prompt": (
                "Tarefa: escreva somente o resultado esperado de salvar um documento."
            ),
            "prompt_markers": (
                "resultado esperado de salvar um documento",
            ),
            "essential_criteria": (
                {
                    "id": "activity_object",
                    "label": "identificar o documento/arquivo",
                    "markers": ("documento", "arquivo"),
                },
                {
                    "id": "final_state",
                    "label": "indicar que o documento ficou salvo/armazenado",
                    "markers": ("salv", "armazen"),
                },
            ),
            "success": "Descreveu o resultado final de salvar um documento.",
        },
        {
            "task_id": "goal_dishes_clean",
            "kind": "result",
            "mastery_lt": 0.6,
            "prompt": (
                "Tarefa: escreva somente o resultado esperado de lavar a louça."
            ),
            "prompt_markers": (
                "resultado esperado de lavar a louca",
            ),
            "essential_criteria": (
                {
                    "id": "activity_object",
                    "label": "identificar a louça",
                    "markers": ("louca",),
                },
                {
                    "id": "final_state",
                    "label": "indicar que a louça ficou limpa/lavada",
                    "markers": ("limp", "lavada"),
                },
            ),
            "success": "Descreveu o resultado final de lavar a louça.",
        },
        {
            "task_id": "goal_backpack_organized",
            "kind": "result",
            "mastery_lt": None,
            "prompt": (
                "Tarefa: escreva somente o resultado esperado de organizar uma mochila "
                "para a aula."
            ),
            "prompt_markers": (
                "resultado esperado de organizar uma mochila",
            ),
            "essential_criteria": (
                {
                    "id": "activity_object",
                    "label": "identificar a mochila",
                    "markers": ("mochila",),
                },
                {
                    "id": "final_state",
                    "label": "indicar que a mochila ficou organizada/pronta",
                    "markers": ("organiz", "pront"),
                },
            ),
            "success": "Descreveu o resultado final de organizar a mochila.",
        },
    )

    REVIEW_TASK = {
        "task_id": "goal_teeth_clean_review",
        "kind": "result",
        "prompt": (
            "Tarefa: sem consultar, escreva somente o resultado esperado de "
            "escovar os dentes."
        ),
        "prompt_markers": (
            "resultado esperado de escovar os dentes",
        ),
        "essential_criteria": (
            {
                "id": "activity_object",
                "label": "identificar os dentes",
                "markers": ("dentes",),
            },
            {
                "id": "final_state",
                "label": "indicar que os dentes ficaram limpos/escovados",
                "markers": ("limp", "escov"),
            },
        ),
        "success": "Recuperou o resultado final de escovar os dentes.",
    }

    @classmethod
    def prompt_for_mastery(cls, mastery):
        try:
            score = min(1.0, max(0.0, float(mastery)))
        except (TypeError, ValueError):
            score = 0.0

        for definition in cls.TASKS:
            limit = definition["mastery_lt"]
            if limit is None or score < limit:
                return definition["prompt"]
        return cls.TASKS[-1]["prompt"]

    @classmethod
    def review_prompt(cls):
        return cls.REVIEW_TASK["prompt"]

    @classmethod
    def definition_for_prompt(cls, prompt):
        normalized = normalize_alias(prompt) or ""
        for definition in (*cls.TASKS, cls.REVIEW_TASK):
            if all(marker in normalized for marker in definition["prompt_markers"]):
                return definition
        return None
