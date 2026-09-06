from backend.concepts import normalize_alias


class PortugolSkeletonTasks:
    """Tarefas canônicas da estrutura mínima do Portugol, uma palavra nova por vez."""

    CONCEPT_ID = "ads.algorithms.portugol_skeleton"

    TASKS = (
        {
            "task_id": "portugol_keyword_algoritmo",
            "max_mastery": 0.20,
            "focus": "palavra-chave algoritmo",
            "prompt": (
                'Tarefa: complete a primeira linha: ____ "rotina". '
                "Responda somente com a palavra que falta."
            ),
            "prompt_markers": ("primeira linha", "rotina", "palavra que falta"),
            "kind": "single_keyword",
            "required_keyword": "algoritmo",
            "success": "Identificou a palavra-chave que abre o cabeçalho do algoritmo.",
        },
        {
            "task_id": "portugol_keyword_inicio",
            "max_mastery": 0.40,
            "focus": "palavra-chave inicio",
            "prompt": (
                'Tarefa: complete: algoritmo "rotina" → ____. '
                "Responda somente com a palavra que marca onde os passos começam."
            ),
            "prompt_markers": ("algoritmo", "rotina", "passos comecam"),
            "kind": "single_keyword",
            "required_keyword": "inicio",
            "success": "Identificou a palavra-chave que marca o começo dos passos.",
        },
        {
            "task_id": "portugol_keyword_fimalgoritmo",
            "max_mastery": 0.60,
            "focus": "palavra-chave fimalgoritmo",
            "prompt": (
                'Tarefa: complete: algoritmo "rotina" → inicio → ____. '
                "Responda somente com a palavra que encerra essa estrutura."
            ),
            "prompt_markers": ("algoritmo", "rotina", "inicio", "encerra essa estrutura"),
            "kind": "single_keyword",
            "required_keyword": "fimalgoritmo",
            "success": "Identificou a palavra-chave que encerra o algoritmo.",
        },
        {
            "task_id": "portugol_skeleton_integration",
            "max_mastery": 1.01,
            "focus": "ordenar as três palavras-chave da estrutura mínima",
            "prompt": (
                'Tarefa: complete as três lacunas, na ordem: ____ "rotina" → ____ → ____. '
                "Use somente as três palavras-chave estruturais já estudadas."
            ),
            "prompt_markers": ("tres lacunas", "rotina", "tres palavras chave"),
            "kind": "skeleton",
            "ordered_keywords": ("algoritmo", "inicio", "fimalgoritmo"),
            "success": "Ordenou corretamente a estrutura mínima do Portugol.",
        },
    )

    REVIEW_TASK = {
        "task_id": "portugol_skeleton_review",
        "focus": "recuperar a estrutura mínima do Portugol",
        "prompt": (
            'Tarefa: de memória, complete as três lacunas: ____ "estudo" → ____ → ____. '
            "Use somente as três palavras-chave estruturais."
        ),
        "prompt_markers": ("tres lacunas", "estudo", "tres palavras chave"),
        "kind": "skeleton",
        "ordered_keywords": ("algoritmo", "inicio", "fimalgoritmo"),
        "success": "Recuperou corretamente a estrutura mínima do Portugol.",
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
