from backend.concepts import normalize_alias


class WriteVariableTasks:
    """Tarefas canônicas: mostrar com escreva o valor de uma variável inteira já declarada."""

    CONCEPT_ID = "ads.algorithms.write_variable"

    TASKS = (
        {
            "task_id": "write_variable_identify_points",
            "max_mastery": 0.20,
            "focus": "variável cujo valor é mostrado",
            "prompt": (
                "Tarefa: observe pontos: inteiro; leia(pontos); escreva(pontos). Qual é o nome "
                "da variável cujo valor é mostrado na saída? Responda somente com o nome."
            ),
            "prompt_markers": ("observe pontos inteiro", "leia pontos", "escreva pontos", "valor e mostrado na saida"),
            "kind": "exact_answer",
            "expected_answer": "pontos",
            "success": "Identificou a variável indicada dentro de escreva como valor mostrado na saída.",
        },
        {
            "task_id": "write_variable_complete_attempts",
            "max_mastery": 0.40,
            "focus": "nome da variável dentro de escreva",
            "prompt": (
                "Tarefa: a variável tentativas: inteiro já existe. Complete somente a lacuna: "
                "escreva(____). Responda somente com o nome que falta."
            ),
            "prompt_markers": ("variavel tentativas inteiro", "complete somente a lacuna", "escreva", "nome que falta"),
            "kind": "exact_answer",
            "expected_answer": "tentativas",
            "success": "Colocou o nome da variável dentro de escreva.",
        },
        {
            "task_id": "write_variable_call_balance",
            "max_mastery": 0.60,
            "focus": "forma escreva(variavel)",
            "prompt": (
                "Tarefa: a variável saldo: inteiro já existe. Responda somente com o comando escreva(...) "
                "que mostra o valor guardado nessa variável."
            ),
            "prompt_markers": ("variavel saldo inteiro", "somente com o comando", "mostra o valor guardado nessa variavel"),
            "kind": "write_call",
            "expected_name": "saldo",
            "success": "Formou escreva(saldo) usando a variável inteira já existente.",
        },
        {
            "task_id": "write_variable_program_order",
            "max_mastery": 1.01,
            "focus": "integrar declaração, entrada e escreva(variavel)",
            "prompt": (
                'Tarefa: coloque em ordem estes elementos: escreva(valor); inicio; leia(valor); valor: inteiro; '
                'fimalgoritmo; var; algoritmo "eco". Reescreva somente a sequência correta.'
            ),
            "prompt_markers": ("coloque em ordem estes elementos", "escreva valor", "leia valor", "valor inteiro", "fimalgoritmo", "var", "algoritmo eco"),
            "kind": "program_write",
            "expected_name": "valor",
            "expected_type": "inteiro",
            "program_name": "eco",
            "ordered_keywords": ("algoritmo", "var", "valor", "inteiro", "inicio", "leia", "escreva", "fimalgoritmo"),
            "success": "Integra declaração, leia(valor) e escreva(valor) na ordem correta do programa.",
        },
    )

    REVIEW_TASK = {
        "task_id": "write_variable_review_age",
        "focus": "recuperar a forma escreva(variavel)",
        "prompt": (
            "Tarefa: de memória, a variável idade: inteiro já existe. Responda somente com o comando "
            "escreva(...) que mostra o valor guardado nessa variável."
        ),
        "prompt_markers": ("de memoria", "variavel idade inteiro", "somente com o comando", "mostra o valor guardado nessa variavel"),
        "kind": "write_call",
        "expected_name": "idade",
        "success": "Recuperou corretamente a forma escreva(idade).",
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
