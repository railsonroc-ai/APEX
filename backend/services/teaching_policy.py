class TeachingPolicy:
    ACTIONS_BY_STAGE = {
        "ler": "explicar",
        "compreender": "explicar",
        "explicar": "verificar",
        "testar": "testar",
        "corrigir": "corrigir",
        "fixar": "consolidar",
        "concluido": "avancar",
        "reencontrar": "revisar",
    }

    @classmethod
    def choose_action(cls, state):
        if not isinstance(state, dict):
            return "explicar"

        stage = state.get("stage", "compreender")
        difficulty = state.get("difficulty_count", 0)
        mastery = state.get("mastery", 0.0)
        try:
            difficulty = max(0, int(difficulty))
        except (TypeError, ValueError):
            difficulty = 0

        try:
            mastery = min(1.0, max(0.0, float(mastery)))
        except (TypeError, ValueError):
            mastery = 0.0

        # Revisão começa sempre por recuperação, mesmo quando o histórico do
        # conceito registra dificuldade. A ajuda só aumenta depois da tentativa.
        if stage == "reencontrar":
            return "revisar"

        if difficulty >= 2:
            return "corrigir"

        if stage not in cls.ACTIONS_BY_STAGE:
            stage = "compreender"

        if mastery >= 0.8 and stage in {"compreender", "explicar", "testar"}:
            return "consolidar"

        return cls.ACTIONS_BY_STAGE[stage]
