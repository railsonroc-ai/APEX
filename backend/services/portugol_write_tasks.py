from backend.concepts import normalize_alias


class PortugolWriteTasks:
    """Tarefas canônicas para uma única novidade: produzir saída com escreva."""

    CONCEPT_ID = "ads.algorithms.portugol_write"

    TASKS = (
        {
            "task_id": "write_keyword_hello",
            "max_mastery": 0.20,
            "focus": "comando escreva",
            "prompt": (
                'Tarefa: complete o comando que mostra Olá na tela: ____("Olá"). '
                "Responda somente com a palavra que falta."
            ),
            "prompt_markers": ("mostra ola na tela", "palavra que falta"),
            "kind": "single_keyword",
            "required_keyword": "escreva",
            "success": "Identificou escreva como o comando que produz a saída mostrada na tela.",
        },
        {
            "task_id": "write_predict_ready",
            "max_mastery": 0.40,
            "focus": "efeito do comando escreva",
            "prompt": (
                'Tarefa: observe escreva("Pronto"). O que aparece na tela? '
                "Responda somente com o texto exibido."
            ),
            "prompt_markers": ("escreva pronto", "aparece na tela", "texto exibido"),
            "kind": "expected_output",
            "expected_output": "pronto",
            "success": "Reconheceu a saída produzida por escreva.",
        },
        {
            "task_id": "write_line_done",
            "max_mastery": 0.60,
            "focus": "linha escreva dentro da estrutura conhecida",
            "prompt": (
                "Tarefa: complete a única linha entre inicio e fimalgoritmo para mostrar "
                'Concluído: inicio → ____ → fimalgoritmo. Use escreva com o texto "Concluído" entre aspas.'
            ),
            "prompt_markers": ("unica linha", "inicio", "fimalgoritmo", "concluido", "entre aspas"),
            "kind": "write_line",
            "expected_text": "concluido",
            "success": "Formou uma linha escreva válida para produzir a saída pedida.",
        },
        {
            "task_id": "write_program_ok",
            "max_mastery": 1.01,
            "focus": "integrar escreva à estrutura mínima já conhecida",
            "prompt": (
                'Tarefa: monte um algoritmo chamado "saida" que mostre OK na tela. '
                "Use somente algoritmo, inicio, escreva e fimalgoritmo."
            ),
            "prompt_markers": ("algoritmo chamado", "mostre ok na tela", "algoritmo", "inicio", "escreva", "fimalgoritmo"),
            "kind": "program_with_write",
            "expected_text": "ok",
            "ordered_keywords": ("algoritmo", "inicio", "escreva", "fimalgoritmo"),
            "success": "Integra escreva corretamente à estrutura mínima já conhecida.",
        },
    )

    REVIEW_TASK = {
        "task_id": "write_review_message",
        "focus": "recuperar o comando escreva",
        "prompt": (
            'Tarefa: de memória, escreva a linha do Portugol que mostra "Revisão" na tela.'
        ),
        "prompt_markers": ("de memoria", "mostra revisao na tela"),
        "kind": "write_line",
        "expected_text": "revisao",
        "success": "Recuperou corretamente o comando escreva.",
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
