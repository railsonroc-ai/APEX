from backend.services.rubric_policy import RubricPolicy


class TaskPolicy:
    """Contrato server-side para transformar um turno do tutor em tarefa avaliável."""

    POLICY_ID = "server_assessment_task"
    POLICY_VERSION = 1

    ACTION_TO_KIND = {
        "testar": "practice",
        "revisar": "retention",
        "verificar": "verification",
        "consolidar": "consolidation",
        "explicar": "guided_check",
        "corrigir": "correction_retry",
        "avancar": None,
    }

    INSTRUCTIONS = {
        "practice": (
            "Finalize com uma única tarefa curta de recuperação ou aplicação ativa, "
            "sem fornecer a resposta antes da tentativa."
        ),
        "retention": (
            "Finalize com uma única tarefa curta de recuperação espaçada do conceito, "
            "sem introduzir novidade."
        ),
        "verification": (
            "Finalize com uma única verificação curta que exija produção própria do aluno."
        ),
        "consolidation": (
            "Finalize com uma única aplicação curta em contexto ligeiramente diferente."
        ),
        "guided_check": (
            "Depois da explicação, finalize com uma única microtarefa que permita ao aluno "
            "produzir uma resposta própria."
        ),
        "correction_retry": (
            "Depois da correção, finalize com uma única nova tentativa curta e diferente "
            "do exemplo resolvido."
        ),
    }

    @classmethod
    def normalize_action(cls, value):
        if not isinstance(value, str):
            return None
        normalized = value.strip().lower()
        return normalized if normalized in cls.ACTION_TO_KIND else None

    @classmethod
    def task_kind_for_action(cls, teaching_action):
        normalized = cls.normalize_action(teaching_action)
        if normalized is None:
            return None
        return cls.ACTION_TO_KIND[normalized]

    @classmethod
    def is_assessable_action(cls, teaching_action):
        return cls.task_kind_for_action(teaching_action) is not None

    @classmethod
    def contract_for_action(cls, teaching_action):
        normalized = cls.normalize_action(teaching_action)
        kind = cls.task_kind_for_action(normalized)
        return {
            "policy_id": cls.POLICY_ID,
            "policy_version": cls.POLICY_VERSION,
            "teaching_action": normalized,
            "task_kind": kind,
            "assessable": kind is not None,
            "rubric_id": RubricPolicy.RUBRIC_ID,
            "rubric_version": RubricPolicy.RUBRIC_VERSION,
            "instruction": cls.INSTRUCTIONS.get(kind),
        }
