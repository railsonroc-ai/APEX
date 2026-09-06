from backend.concepts import normalize_alias


class PortugolReadTasks:
    """Tarefas canônicas para uma única novidade: leia como comando de entrada."""

    CONCEPT_ID = "ads.algorithms.portugol_read"

    TASKS = (
        {
            "task_id": "read_keyword_input",
            "max_mastery": 0.20,
            "focus": "comando leia",
            "prompt": (
                "Tarefa: complete: ____ é o comando do Portugol usado quando o algoritmo "
                "recebe uma entrada. Responda somente com a palavra que falta."
            ),
            "prompt_markers": ("comando do portugol", "recebe uma entrada", "palavra que falta"),
            "kind": "single_keyword",
            "required_keyword": "leia",
            "success": "Identificou leia como o comando associado à entrada.",
        },
        {
            "task_id": "read_role_input",
            "max_mastery": 0.40,
            "focus": "papel de leia como entrada",
            "prompt": (
                "Tarefa: observe leia(____). Sem preencher a lacuna, essa ação representa "
                "entrada ou saída? Responda somente com uma das duas palavras."
            ),
            "prompt_markers": ("observe leia", "sem preencher a lacuna", "entrada ou saida"),
            "kind": "role_choice",
            "expected_role": "entrada",
            "success": "Reconheceu que leia representa a entrada do algoritmo.",
        },
        {
            "task_id": "read_before_write",
            "max_mastery": 0.60,
            "focus": "posição de leia antes da saída conhecida",
            "prompt": (
                'Tarefa: complete somente a lacuna: inicio → ____ → escreva("OK") → '
                "fimalgoritmo. Use o nome do comando que recebe uma entrada."
            ),
            "prompt_markers": ("complete somente a lacuna", "inicio", "escreva", "fimalgoritmo", "recebe uma entrada"),
            "kind": "single_keyword",
            "required_keyword": "leia",
            "success": "Posicionou leia antes da saída já conhecida.",
        },
        {
            "task_id": "read_flow_integration",
            "max_mastery": 1.01,
            "focus": "integrar leia à ordem da estrutura já conhecida",
            "prompt": (
                'Tarefa: represente apenas a ordem: algoritmo "fluxo" → inicio → leia → '
                'escreva("OK") → fimalgoritmo. Reescreva essa sequência na ordem correta. '
                "Não complete o interior de leia ainda."
            ),
            "prompt_markers": ("represente apenas a ordem", "algoritmo", "inicio", "leia", "escreva", "fimalgoritmo", "nao complete o interior"),
            "kind": "ordered_flow",
            "ordered_keywords": ("algoritmo", "inicio", "leia", "escreva", "fimalgoritmo"),
            "success": "Integra leia corretamente à ordem da estrutura já conhecida.",
        },
    )

    REVIEW_TASK = {
        "task_id": "read_review_role",
        "focus": "recuperar o papel de leia",
        "prompt": (
            "Tarefa: de memória, qual comando do Portugol indica que o algoritmo recebe uma entrada? "
            "Responda somente com o nome do comando."
        ),
        "prompt_markers": ("de memoria", "qual comando do portugol", "recebe uma entrada"),
        "kind": "single_keyword",
        "required_keyword": "leia",
        "success": "Recuperou corretamente o papel de leia.",
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
