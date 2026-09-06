from backend.concepts import normalize_alias


class VariableStorageTasks:
    """Tarefas canônicas para uma única novidade: variável como armazenamento nomeado."""

    CONCEPT_ID = "ads.algorithms.variable_storage"

    TASKS = (
        {
            "task_id": "variable_named_place_points",
            "max_mastery": 0.20,
            "focus": "variável como lugar nomeado",
            "prompt": (
                "Tarefa: imagine um lugar chamado pontos que guarda o valor 10. "
                "Qual é o nome desse lugar: pontos ou 10? Responda somente com a resposta."
            ),
            "prompt_markers": ("lugar chamado pontos", "guarda o valor 10", "pontos ou 10"),
            "kind": "exact_answer",
            "expected_answer": "pontos",
            "success": "Identificou o nome do lugar usado para guardar um valor.",
        },
        {
            "task_id": "variable_name_value_age",
            "max_mastery": 0.40,
            "focus": "diferença entre nome e valor guardado",
            "prompt": (
                "Tarefa: uma variável chamada idade guarda 25. Qual é o valor guardado: "
                "idade ou 25? Responda somente com a resposta."
            ),
            "prompt_markers": ("variavel chamada idade", "guarda 25", "valor guardado"),
            "kind": "exact_answer",
            "expected_answer": "25",
            "success": "Distinguiu o nome da variável do valor que ela guarda.",
        },
        {
            "task_id": "variable_stable_name_attempts",
            "max_mastery": 0.60,
            "focus": "nome estável quando o valor muda",
            "prompt": (
                "Tarefa: a variável tentativas guarda 1 e depois passa a guardar 2. "
                "Qual continua sendo o nome da variável: tentativas ou 2? "
                "Responda somente com a resposta."
            ),
            "prompt_markers": ("variavel tentativas", "guarda 1", "guardar 2", "continua sendo o nome"),
            "kind": "exact_answer",
            "expected_answer": "tentativas",
            "success": "Reconheceu que o nome permanece enquanto o valor pode mudar.",
        },
        {
            "task_id": "variable_current_value_balance",
            "max_mastery": 1.01,
            "focus": "identificar nome e valor atual",
            "prompt": (
                "Tarefa: a variável saldo guardava 50 e depois passou a guardar 80. "
                "Informe o nome da variável e o valor atual."
            ),
            "prompt_markers": ("variavel saldo", "guardava 50", "guardar 80", "valor atual"),
            "kind": "name_value_pair",
            "expected_name": "saldo",
            "expected_value": "80",
            "success": "Identificou corretamente o nome e o valor atual da variável.",
        },
    )

    REVIEW_TASK = {
        "task_id": "variable_review_level",
        "focus": "recuperar nome e valor atual de uma variável",
        "prompt": (
            "Tarefa: de memória, a variável nivel guardava 3 e depois passou a guardar 4. "
            "Informe o nome da variável e o valor atual."
        ),
        "prompt_markers": ("de memoria", "variavel nivel", "guardava 3", "guardar 4", "valor atual"),
        "kind": "name_value_pair",
        "expected_name": "nivel",
        "expected_value": "4",
        "success": "Recuperou corretamente a relação entre nome e valor atual.",
    }

    @classmethod
    def definition_for_mastery(cls, mastery):
        try:
            value = min(1.0, max(0.0, float(mastery)))
        except (TypeError, ValueError):
            value = 0.0
        for definition in cls.TASKS:
            if value < definition["max_mastery"]:
                return definition
        return cls.TASKS[-1]

    @classmethod
    def prompt_for_mastery(cls, mastery):
        return cls.definition_for_mastery(mastery)["prompt"]

    @classmethod
    def focus_for_mastery(cls, mastery):
        return cls.definition_for_mastery(mastery)["focus"]

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
