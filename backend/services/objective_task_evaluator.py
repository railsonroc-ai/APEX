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

    @classmethod
    def _is_hand_washing_order_task(cls, evaluation):
        if not isinstance(evaluation, dict):
            return False
        if evaluation.get("concept_id") != cls.ORDERED_STEPS:
            return False
        prompt = normalize_alias(evaluation.get("tutor_message")) or ""
        return all(marker in prompt for marker in cls.HAND_WASHING_MARKERS)

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
        if not cls._is_hand_washing_order_task(evaluation):
            return None

        submitted = cls._submitted_order(evaluation.get("student_answer"))
        if submitted == cls.CORRECT_NUMERIC_ORDER:
            return cls._evidence(
                {
                    RubricPolicy.TASK_RESPONSE: RubricPolicy.MET,
                    RubricPolicy.CONCEPTUAL_CORRECTNESS: RubricPolicy.MET,
                    RubricPolicy.UNDERSTANDING_APPLICATION: RubricPolicy.MET,
                },
                "Ordenou corretamente abrir, lavar e secar.",
            )

        if submitted is not None:
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
                RubricPolicy.TASK_RESPONSE: RubricPolicy.PARTIAL,
                RubricPolicy.CONCEPTUAL_CORRECTNESS: RubricPolicy.PARTIAL,
                RubricPolicy.UNDERSTANDING_APPLICATION: RubricPolicy.PARTIAL,
            },
            "A resposta não apresentou inequivocamente os três passos em ordem.",
        )
