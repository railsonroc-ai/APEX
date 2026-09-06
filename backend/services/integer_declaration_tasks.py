from backend.concepts import normalize_alias


class IntegerDeclarationTasks:
    """Tarefas canônicas: declaração de uma variável inteira, uma novidade por interação."""

    CONCEPT_ID = "ads.algorithms.integer_declaration"

    TASKS = (
        {
            "task_id": "declaration_var_section",
            "max_mastery": 0.20,
            "focus": "palavra-chave var",
            "prompt": (
                "Tarefa: no Portugol, qual palavra marca a área em que as variáveis são "
                "apresentadas antes de inicio? Responda somente com a palavra que falta: ____."
            ),
            "prompt_markers": ("qual palavra marca a area", "variaveis", "antes de inicio", "palavra que falta"),
            "kind": "single_keyword",
            "required_keyword": "var",
            "success": "Identificou var como a palavra que marca a área de declarações.",
        },
        {
            "task_id": "declaration_integer_type",
            "max_mastery": 0.40,
            "focus": "tipo inteiro",
            "prompt": (
                "Tarefa: uma variável guardará somente números sem parte decimal, como 7. "
                "Qual palavra representa esse tipo no Portugol? Responda somente com a palavra."
            ),
            "prompt_markers": ("somente numeros sem parte decimal", "como 7", "qual palavra representa esse tipo"),
            "kind": "single_keyword",
            "required_keyword": "inteiro",
            "success": "Identificou inteiro como o tipo usado para números sem parte decimal.",
        },
        {
            "task_id": "declaration_line_points",
            "max_mastery": 0.60,
            "focus": "forma nome: inteiro",
            "prompt": (
                "Tarefa: forme somente a declaração da variável pontos usando o tipo inteiro."
            ),
            "prompt_markers": ("declaracao da variavel pontos", "tipo inteiro"),
            "kind": "declaration_line",
            "expected_name": "pontos",
            "expected_type": "inteiro",
            "success": "Escreveu a declaração pontos: inteiro na forma correta.",
        },
        {
            "task_id": "declaration_block_order",
            "max_mastery": 1.01,
            "focus": "posição da declaração antes de inicio",
            "prompt": (
                'Tarefa: coloque em ordem estes elementos: inicio; saldo: inteiro; fimalgoritmo; '
                'var; algoritmo "conta". Reescreva somente a sequência correta.'
            ),
            "prompt_markers": ("coloque em ordem estes elementos", "saldo inteiro", "fimalgoritmo", "var", "algoritmo conta"),
            "kind": "declaration_block",
            "expected_name": "saldo",
            "expected_type": "inteiro",
            "program_name": "conta",
            "ordered_keywords": ("algoritmo", "var", "saldo", "inteiro", "inicio", "fimalgoritmo"),
            "success": "Posicionou a declaração inteira corretamente antes de inicio.",
        },
    )

    REVIEW_TASK = {
        "task_id": "declaration_review_attempts",
        "focus": "recuperar a forma nome: inteiro",
        "prompt": (
            "Tarefa: de memória, forme somente a declaração da variável tentativas usando o tipo inteiro."
        ),
        "prompt_markers": ("de memoria", "declaracao da variavel tentativas", "tipo inteiro"),
        "kind": "declaration_line",
        "expected_name": "tentativas",
        "expected_type": "inteiro",
        "success": "Recuperou corretamente a forma de declarar uma variável inteira.",
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
