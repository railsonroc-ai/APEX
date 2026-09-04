class AttemptPolicy:
    """Classifica de forma determinística o tipo pedagógico de uma tentativa."""

    POLICY_ID = "learning_attempt"
    POLICY_VERSION = 2

    STAGE_TO_KIND = {
        "compreender": "comprehension",
        "explicar": "explanation",
        "testar": "practice",
        "corrigir": "correction",
        "fixar": "consolidation",
        "reencontrar": "retention",
    }

    VALID_KINDS = set(STAGE_TO_KIND.values())

    @classmethod
    def kind_for_stage(cls, stage):
        if not isinstance(stage, str):
            return None
        return cls.STAGE_TO_KIND.get(stage.strip().lower())
