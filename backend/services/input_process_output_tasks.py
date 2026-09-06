from backend.concepts import normalize_alias


class InputProcessOutputTasks:
    """Fonte canônica das tarefas concretas de entrada/processamento/saída."""

    CONCEPT_ID = "ads.algorithms.input_process_output"

    TASKS = (
        {
            "task_id": "ipo_blender_input",
            "max_mastery": 0.20,
            "focus": "entrada",
            "prompt": (
                "Tarefa: um liquidificador recebe banana e leite antes de preparar uma "
                "vitamina. O que é a entrada nessa situação?"
            ),
            "prompt_markers": ("liquidificador", "banana", "leite", "entrada"),
            "kind": "component",
            "essential_criteria": (
                {"label": "identificar banana como parte da entrada", "markers": ("banana",)},
                {"label": "identificar leite como parte da entrada", "markers": ("leite",)},
            ),
            "success": "Identificou os itens que a atividade recebe para começar.",
        },
        {
            "task_id": "ipo_washing_processing",
            "max_mastery": 0.40,
            "focus": "processamento",
            "prompt": (
                "Tarefa: uma máquina de lavar recebe roupas e água e realiza a lavagem. "
                "O que é o processamento nessa situação?"
            ),
            "prompt_markers": ("maquina de lavar", "roupas", "agua", "processamento"),
            "kind": "component",
            "essential_criteria": (
                {"label": "identificar a lavagem como processamento", "markers": ("lavagem", "lavar")},
            ),
            "success": "Identificou o que acontece com a entrada durante a atividade.",
        },
        {
            "task_id": "ipo_calculator_output",
            "max_mastery": 0.60,
            "focus": "saída",
            "prompt": (
                "Tarefa: uma calculadora recebe 2 e 3, soma os valores e mostra 5. "
                "O que é a saída nessa situação?"
            ),
            "prompt_markers": ("calculadora", "2", "3", "5", "saida"),
            "kind": "component",
            "essential_criteria": (
                {"label": "identificar 5 como saída", "markers": ("5",)},
            ),
            "success": "Identificou o que a atividade entrega ao final.",
        },
        {
            "task_id": "ipo_coffee_mapping",
            "max_mastery": 1.01,
            "focus": "relação entre entrada, processamento e saída",
            "prompt": (
                "Tarefa: uma cafeteira recebe água e pó de café, prepara a bebida e entrega "
                "café pronto. Identifique a entrada, o processamento e a saída."
            ),
            "prompt_markers": ("cafeteira", "agua", "po de cafe", "cafe pronto"),
            "kind": "mapping",
            "essential_criteria": (
                {"label": "identificar água na entrada", "markers": ("agua",)},
                {"label": "identificar pó de café na entrada", "markers": ("po de cafe", "po")},
                {"label": "identificar preparar a bebida como processamento", "markers": ("prepar", "faz")},
                {"label": "identificar café pronto como saída", "markers": ("cafe pronto", "bebida pronta")},
            ),
            "mapping_roles": {
                "entrada": (("agua",), ("po de cafe", "po")),
                "processamento": (("prepar", "faz"),),
                "saida": (("cafe pronto", "bebida pronta"),),
            },
            "success": "Relacionou corretamente entrada, processamento e saída.",
        },
    )

    REVIEW_TASK = {
        "task_id": "ipo_review_mapping",
        "focus": "relação entre entrada, processamento e saída",
        "prompt": (
            "Tarefa: uma torradeira recebe pão, aquece o pão e entrega torrada. "
            "Identifique a entrada, o processamento e a saída."
        ),
        "prompt_markers": ("torradeira", "pao", "aquece", "torrada"),
        "kind": "mapping",
        "essential_criteria": (
            {"label": "identificar pão como entrada", "markers": ("pao",)},
            {"label": "identificar aquecer como processamento", "markers": ("aquec", "tost")},
            {"label": "identificar torrada como saída", "markers": ("torrada",)},
        ),
        "mapping_roles": {
            "entrada": (("pao",),),
            "processamento": (("aquec", "tost"),),
            "saida": (("torrada",),),
        },
        "success": "Recuperou corretamente a relação entre entrada, processamento e saída.",
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
