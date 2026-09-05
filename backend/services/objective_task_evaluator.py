import re

from backend.concepts import normalize_alias
from backend.services.rubric_policy import RubricPolicy


class ObjectiveTaskEvaluator:
    """Avalia tarefas fechadas sem depender de julgamento probabilístico.

    O avaliador só assume uma tarefa quando reconhece simultaneamente o
    conceito e o enunciado persistido. Respostas a tarefas abertas continuam
    seguindo para o avaliador semântico.
    """

    ORDERED_STEPS = "ads.algorithms.ordered_steps"
    HAND_WASHING_MARKERS = (
        "abrir a torneira",
        "lavar as maos",
        "secar as maos",
    )
    CORRECT_NUMERIC_ORDER = ("2", "3", "1")
    ACTION_PATTERNS = (
        re.compile(r"\babr\w*(?:\s+a)?(?:\s+torneira)?\b"),
        re.compile(r"\blav\w*(?:\s+(?:as|minhas|suas))?(?:\s+maos)?\b"),
        re.compile(r"\bsec\w*(?:\s+(?:as|minhas|suas))?(?:\s+maos)?\b"),
    )

    # Exercícios controlados da primeira microcompetência. Mesmo quando o
    # enunciado pede uma descrição, a rubrica esperada é conhecida pelo
    # servidor e não deve depender da disponibilidade ou do formato da LLM.
    ORDERED_TASKS = (
        {
            "prompt_markers": HAND_WASHING_MARKERS,
            "patterns": ACTION_PATTERNS,
            "numeric_order": ("2", "3", "1"),
            "success": "Ordenou corretamente abrir, lavar e secar.",
        },
        {
            "prompt_markers": ("guardar um arquivo", "tres passos"),
            "patterns": (
                re.compile(r"\babr\w*\b.*\b(?:menu|arquivo)\b"),
                re.compile(r"\b(?:selecion\w*|escolh\w*|clic\w*)\b.*\bsalv\w*\b"),
                re.compile(r"\bescolh\w*\b.*\b(?:local|pasta)\b.*\bconfirm\w*\b"),
            ),
            "numeric_order": None,
            "success": "Descreveu três passos válidos e ordenados para salvar um arquivo.",
        },
        {
            "prompt_markers": ("clicar em enviar", "escrever a mensagem", "abrir a conversa"),
            "patterns": (
                re.compile(r"\babr\w*\b.*\bconvers\w*\b"),
                re.compile(r"\b(?:escrev\w*|digit\w*)\b.*\bmensag\w*\b"),
                re.compile(r"(?:\bclic\w*\b.*\benvi\w*\b|\benvi\w*\b.*\bmensag\w*\b)"),
            ),
            "numeric_order": ("3", "2", "1"),
            "success": "Ordenou corretamente abrir, escrever e enviar.",
        },
        {
            "prompt_markers": ("guardar o copo", "pegar o copo", "beber a agua"),
            "patterns": (
                re.compile(r"\bpeg\w*\b.*\bcopo\b"),
                re.compile(r"\bbeb\w*\b.*\bagua\b"),
                re.compile(r"\bguard\w*\b.*\bcopo\b"),
            ),
            "numeric_order": ("2", "3", "1"),
            "success": "Ordenou corretamente pegar, beber e guardar.",
        },
    )

    @classmethod
    def _is_hand_washing_order_task(cls, evaluation):
        if not isinstance(evaluation, dict):
            return False
        if evaluation.get("concept_id") != cls.ORDERED_STEPS:
            return False
        prompt = normalize_alias(evaluation.get("tutor_message")) or ""
        return all(marker in prompt for marker in cls.HAND_WASHING_MARKERS)

    @classmethod
    def _task_definition(cls, evaluation):
        if not isinstance(evaluation, dict):
            return None
        if evaluation.get("concept_id") != cls.ORDERED_STEPS:
            return None
        prompt = normalize_alias(evaluation.get("tutor_message")) or ""
        for definition in cls.ORDERED_TASKS:
            if all(marker in prompt for marker in definition["prompt_markers"]):
                return definition
        return None

    @classmethod
    def _submitted_order(cls, answer):
        normalized = normalize_alias(answer) or ""
        numbers = tuple(re.findall(r"\b[123]\b", normalized))
        if len(numbers) == 3 and set(numbers) == {"1", "2", "3"}:
            return numbers

        positions = []
        for pattern in cls.ACTION_PATTERNS:
            match = pattern.search(normalized)
            if match is None:
                return None
            positions.append(match.start())

        if len(set(positions)) != len(positions):
            return None
        original_item_numbers = cls.CORRECT_NUMERIC_ORDER
        return tuple(
            original_item_numbers[index]
            for index in sorted(range(len(positions)), key=positions.__getitem__)
        )

    @staticmethod
    def _matches_order(answer, definition):
        normalized = normalize_alias(answer) or ""
        numbers = tuple(re.findall(r"\b[123]\b", normalized))
        expected_numbers = definition["numeric_order"]
        if expected_numbers and len(numbers) == 3 and set(numbers) == {"1", "2", "3"}:
            return numbers == expected_numbers, True

        positions = []
        for pattern in definition["patterns"]:
            match = pattern.search(normalized)
            if match is None:
                return False, False
            positions.append(match.start())

        if len(set(positions)) != len(positions):
            return False, False
        return positions == sorted(positions), True

    @staticmethod
    def _evidence(criteria, evidence):
        normalized = RubricPolicy.normalize_payload({"criteria": criteria})
        return {
            "outcome": normalized["outcome"],
            "confidence": 1.0,
            "evidence": evidence,
            "criteria": normalized["criteria"],
            "rubric_complete": True,
            "outcome_source": "rubric",
            "source": "deterministic_task",
        }

    @classmethod
    def evaluate(cls, evaluation):
        definition = cls._task_definition(evaluation)
        if definition is None:
            return None

        correct, complete = cls._matches_order(
            evaluation.get("student_answer"),
            definition,
        )
        if correct:
            return cls._evidence(
                {
                    RubricPolicy.TASK_RESPONSE: RubricPolicy.MET,
                    RubricPolicy.CONCEPTUAL_CORRECTNESS: RubricPolicy.MET,
                    RubricPolicy.UNDERSTANDING_APPLICATION: RubricPolicy.MET,
                },
                definition["success"],
            )

        if complete:
            return cls._evidence(
                {
                    RubricPolicy.TASK_RESPONSE: RubricPolicy.MET,
                    RubricPolicy.CONCEPTUAL_CORRECTNESS: RubricPolicy.NOT_MET,
                    RubricPolicy.UNDERSTANDING_APPLICATION: RubricPolicy.PARTIAL,
                },
                "Incluiu os três passos, mas em ordem incorreta.",
            )

        return cls._evidence(
            {
                RubricPolicy.TASK_RESPONSE: RubricPolicy.NOT_MET,
                RubricPolicy.CONCEPTUAL_CORRECTNESS: RubricPolicy.PARTIAL,
                RubricPolicy.UNDERSTANDING_APPLICATION: RubricPolicy.NOT_MET,
            },
            "A resposta não apresentou os três passos pedidos em uma ordem avaliável.",
        )
