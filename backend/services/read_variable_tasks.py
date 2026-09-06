from backend.concepts import normalize_alias


class ReadVariableTasks:
    """Tarefas canônicas: conectar leia a uma variável inteira já declarada."""

    CONCEPT_ID = "ads.algorithms.read_variable"

    TASKS = (
        {
            "task_id": "read_variable_identify_age",
            "max_mastery": 0.20,
            "focus": "variável que recebe a entrada",
            "prompt": (
                "Tarefa: observe idade: inteiro e depois leia(idade). Qual é o nome da "
                "variável que recebe a entrada? Responda somente com o nome."
            ),
            "prompt_markers": ("observe idade inteiro", "leia idade", "variavel que recebe a entrada"),
            "kind": "exact_answer",
            "expected_answer": "idade",
            "success": "Identificou a variável indicada dentro de leia como destino da entrada.",
        },
        {
            "task_id": "read_variable_complete_attempts",
            "max_mastery": 0.40,
            "focus": "nome da variável dentro de leia",
            "prompt": (
                "Tarefa: a variável tentativas: inteiro já foi declarada. Complete somente a "
                "lacuna: leia(____). Responda somente com o nome que falta."
            ),
            "prompt_markers": ("variavel tentativas inteiro", "complete somente a lacuna", "leia", "nome que falta"),
            "kind": "exact_answer",
            "expected_answer": "tentativas",
            "success": "Colocou o nome da variável declarada dentro de leia.",
        },
        {
            "task_id": "read_variable_call_points",
            "max_mastery": 0.60,
            "focus": "forma leia(variavel)",
            "prompt": (
                "Tarefa: a variável pontos: inteiro já existe. Responda somente com o comando leia(...) que "
                "recebe uma entrada nessa variável."
            ),
            "prompt_markers": ("variavel pontos inteiro", "somente com o comando", "recebe uma entrada nessa variavel"),
            "kind": "read_call",
            "expected_name": "pontos",
            "success": "Formou leia(pontos) usando a variável inteira já declarada.",
        },
        {
            "task_id": "read_variable_program_order",
            "max_mastery": 1.01,
            "focus": "integrar declaração e leia(variavel)",
            "prompt": (
                'Tarefa: coloque em ordem estes elementos: inicio; leia(idade); idade: inteiro; '
                'fimalgoritmo; var; algoritmo "cadastro". Reescreva somente a sequência correta.'
            ),
            "prompt_markers": ("coloque em ordem estes elementos", "leia idade", "idade inteiro", "fimalgoritmo", "var", "algoritmo cadastro"),
            "kind": "program_read",
            "expected_name": "idade",
            "expected_type": "inteiro",
            "program_name": "cadastro",
            "ordered_keywords": ("algoritmo", "var", "idade", "inteiro", "inicio", "leia", "fimalgoritmo"),
            "success": "Integra a variável inteira e leia(idade) na ordem correta do programa.",
        },
    )

    REVIEW_TASK = {
        "task_id": "read_variable_review_balance",
        "focus": "recuperar a forma leia(variavel)",
        "prompt": (
            "Tarefa: de memória, a variável saldo: inteiro já foi declarada. Responda somente com "
            "o comando leia(...) que recebe uma entrada nessa variável."
        ),
        "prompt_markers": ("de memoria", "variavel saldo inteiro", "somente com o comando", "recebe uma entrada nessa variavel"),
        "kind": "read_call",
        "expected_name": "saldo",
        "success": "Recuperou corretamente a forma leia(saldo).",
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
