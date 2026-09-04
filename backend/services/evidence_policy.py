class EvidencePolicy:
    """Metadados versionados da avaliação semântica atual.

    A assistência usada pela evidência é derivada do ledger do turno anterior
    do tutor. Turnos legados, anteriores ao rastreamento de assistência,
    permanecem ``untracked`` em vez de receber uma classificação inventada.
    """

    RUBRIC_ID = "semantic_evidence"
    RUBRIC_VERSION = 2

    POLICY_ID = "learner_state_transition"
    POLICY_VERSION = 4

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
