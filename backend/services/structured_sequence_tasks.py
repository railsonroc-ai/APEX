from backend.concepts import normalize_alias


class StructuredSequenceTasks:
    """Tarefas canônicas para representar uma lógica sem entrar em sintaxe de código."""

    CONCEPT_ID = "ads.algorithms.structured_sequence"

    TASKS = (
        {
            "task_id": "structured_toast_numbered",
            "max_mastery": 0.20,
            "focus": "representar passos em uma sequência numerada",
            "prompt": (
                "Tarefa: uma rotina tem estes passos: pegar o pão; colocar o pão na "
                "torradeira; retirar a torrada. Represente a sequência usando 1, 2 e 3, "
                "na ordem correta."
            ),
            "prompt_markers": ("pegar o pao", "colocar o pao", "retirar a torrada", "1", "2", "3"),
            "kind": "numbered_order",
            "ordered_groups": (
                ("pegar o pao", "pegar pao"),
                ("colocar o pao", "colocar pao", "por o pao", "pôr o pão"),
                ("retirar a torrada", "tirar a torrada", "retirar torrada"),
            ),
            "success": "Representou os três passos com ordem explícita.",
        },
        {
            "task_id": "structured_water_boundaries",
            "max_mastery": 0.40,
            "focus": "delimitar a sequência com INÍCIO e FIM",
            "prompt": (
                "Agora uma novidade: uma representação estruturada pode marcar claramente "
                "onde a sequência começa e termina.\n\n"
                "Tarefa: represente pegar o copo, beber a água e guardar o copo usando "
                "INÍCIO antes dos passos e FIM depois deles."
            ),
            "prompt_markers": ("pegar o copo", "beber a agua", "guardar o copo", "inicio", "fim"),
            "kind": "bounded_order",
            "ordered_groups": (
                ("pegar o copo", "pegar copo"),
                ("beber a agua", "beber agua"),
                ("guardar o copo", "guardar copo"),
            ),
            "success": "Delimitou e ordenou corretamente a sequência.",
        },
        {
            "task_id": "structured_message_missing_step",
            "max_mastery": 0.60,
            "focus": "ler uma sequência estruturada e localizar um passo ausente",
            "prompt": (
                "Tarefa: leia a representação: INÍCIO → abrir a conversa → ____ → clicar "
                "em Enviar → FIM. Qual passo está faltando?"
            ),
            "prompt_markers": ("inicio", "abrir a conversa", "clicar em enviar", "qual passo", "fim"),
            "kind": "missing_step",
            "essential_groups": (
                ("escrever a mensagem", "escrever mensagem", "digitar a mensagem", "digitar mensagem"),
            ),
            "success": "Identificou o passo que faltava na representação.",
        },
        {
            "task_id": "structured_coffee_flow",
            "max_mastery": 1.01,
            "focus": "reunir uma sequência completa em representação estruturada",
            "prompt": (
                "Tarefa: uma cafeteira recebe água e pó de café, prepara a bebida e entrega "
                "café pronto. Represente essa lógica entre INÍCIO e FIM, mantendo a ordem "
                "receber → preparar → entregar."
            ),
            "prompt_markers": ("cafeteira", "agua", "po de cafe", "inicio", "fim", "receber", "preparar", "entregar"),
            "kind": "bounded_order",
            "ordered_groups": (
                ("receber agua", "recebe agua", "agua e po de cafe", "receber agua e po de cafe"),
                ("preparar a bebida", "prepara a bebida", "preparar cafe", "fazer o cafe"),
                ("entregar cafe pronto", "entrega cafe pronto", "cafe pronto"),
            ),
            "success": "Transformou uma lógica conhecida em representação estruturada.",
        },
    )

    REVIEW_TASK = {
        "task_id": "structured_review_toaster",
        "focus": "recuperar a representação estruturada completa",
        "prompt": (
            "Tarefa: represente entre INÍCIO e FIM a sequência: receber pão → aquecer o pão "
            "→ entregar torrada."
        ),
        "prompt_markers": ("receber pao", "aquecer o pao", "entregar torrada", "inicio", "fim"),
        "kind": "bounded_order",
        "ordered_groups": (
            ("receber pao", "recebe pao", "pao"),
            ("aquecer o pao", "aquece o pao", "aquecer pao"),
            ("entregar torrada", "entrega torrada", "torrada"),
        ),
        "success": "Recuperou a estrutura completa em outra atividade.",
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
