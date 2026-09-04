class EvidencePolicy:
    """Metadados versionados da avaliação semântica atual.

    Este bloco não inventa um nível de ajuda que o APEX ainda não mede.
    Enquanto o scaffolding explícito não existir, a assistência é registrada
    como ``untracked`` para preservar honestidade do dado.
    """

    RUBRIC_ID = "semantic_evidence"
    RUBRIC_VERSION = 1

    POLICY_ID = "learner_state_transition"
    POLICY_VERSION = 1

    ASSISTANCE_UNTRACKED = "untracked"
    ASSISTANCE_LEVELS = {
        ASSISTANCE_UNTRACKED,
        "independent",
        "light",
        "guided",
        "direct",
    }

    SOURCE_SEMANTIC_LLM = "semantic_llm"

    @classmethod
    def normalize_assistance_level(cls, value):
        if not isinstance(value, str):
            return cls.ASSISTANCE_UNTRACKED

        normalized = value.strip().lower()

        if normalized not in cls.ASSISTANCE_LEVELS:
            return cls.ASSISTANCE_UNTRACKED

        return normalized
