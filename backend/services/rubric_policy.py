class RubricPolicy:
    """Rubrica determinística para transformar critérios em um outcome.

    A LLM classifica cada critério. O servidor deriva o outcome final; assim,
    ``demonstrated`` não depende de uma etiqueta global autoatribuída pelo modelo.
    """

    RUBRIC_ID = "semantic_evidence"
    RUBRIC_VERSION = 2

    TASK_RESPONSE = "task_response"
    CONCEPTUAL_CORRECTNESS = "conceptual_correctness"
    UNDERSTANDING_APPLICATION = "understanding_application"

    CRITERIA = (
        TASK_RESPONSE,
        CONCEPTUAL_CORRECTNESS,
        UNDERSTANDING_APPLICATION,
    )

    MET = "met"
    PARTIAL = "partial"
    NOT_MET = "not_met"
    UNKNOWN = "unknown"

    VALID_LEVELS = {
        MET,
        PARTIAL,
        NOT_MET,
        UNKNOWN,
    }

    OUTCOME_INSUFFICIENT = "insufficient"
    OUTCOME_PARTIAL = "partial"
    OUTCOME_DEMONSTRATED = "demonstrated"
    OUTCOME_MISCONCEPTION = "misconception"

    VALID_OUTCOMES = {
        OUTCOME_INSUFFICIENT,
        OUTCOME_PARTIAL,
        OUTCOME_DEMONSTRATED,
        OUTCOME_MISCONCEPTION,
    }

    @classmethod
    def normalize_level(cls, value):
        if not isinstance(value, str):
            return cls.UNKNOWN
        normalized = value.strip().lower()
        if normalized not in cls.VALID_LEVELS:
            return cls.UNKNOWN
        return normalized

    @classmethod
    def normalize_criteria(cls, value):
        source = value if isinstance(value, dict) else {}
        return {
            criterion: cls.normalize_level(source.get(criterion))
            for criterion in cls.CRITERIA
        }

    @classmethod
    def is_complete(cls, criteria):
        normalized = cls.normalize_criteria(criteria)
        return all(
            normalized[criterion] != cls.UNKNOWN
            for criterion in cls.CRITERIA
        )

    @classmethod
    def derive_outcome(cls, criteria):
        normalized = cls.normalize_criteria(criteria)
        task = normalized[cls.TASK_RESPONSE]
        correctness = normalized[cls.CONCEPTUAL_CORRECTNESS]
        understanding = normalized[cls.UNDERSTANDING_APPLICATION]

        if correctness == cls.NOT_MET:
            return cls.OUTCOME_MISCONCEPTION

        if (
            task == cls.MET
            and correctness == cls.MET
            and understanding == cls.MET
        ):
            return cls.OUTCOME_DEMONSTRATED

        if task == cls.NOT_MET:
            return cls.OUTCOME_INSUFFICIENT

        if all(
            value in {cls.UNKNOWN, cls.NOT_MET}
            for value in normalized.values()
        ):
            return cls.OUTCOME_INSUFFICIENT

        return cls.OUTCOME_PARTIAL

    @classmethod
    def normalize_payload(cls, payload):
        if not isinstance(payload, dict):
            return None

        criteria = cls.normalize_criteria(payload.get("criteria"))
        complete = cls.is_complete(criteria)

        requested_outcome = payload.get("outcome")
        if requested_outcome not in cls.VALID_OUTCOMES:
            requested_outcome = None

        if complete:
            outcome = cls.derive_outcome(criteria)
            outcome_source = "rubric"
        elif requested_outcome:
            # Compatibilidade transitória para respostas antigas. Elas ficam
            # explicitamente marcadas como incompletas no ledger de rubrica.
            outcome = requested_outcome
            outcome_source = "legacy_outcome"
        else:
            outcome = cls.OUTCOME_INSUFFICIENT
            outcome_source = "rubric_incomplete"

        return {
            "criteria": criteria,
            "rubric_complete": complete,
            "outcome": outcome,
            "outcome_source": outcome_source,
        }
