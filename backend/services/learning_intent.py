import re

from backend.concepts import normalize_alias
from backend.services.concept_catalog import ConceptCatalog


class LearningIntent:
    """Interpreta comandos de trilha sem delegar decisões básicas ao LLM."""

    START_MARKERS = (
        "quero aprender", "quero estudar", "gostaria de aprender",
        "gostaria de estudar", "preciso aprender", "preciso estudar",
        "vamos aprender", "vamos estudar", "me ensine", "me ensina",
        "pode me ensinar", "poderia me ensinar", "quero comecar",
        "quero iniciar", "quero recomecar", "vamos recomecar",
    )
    RESTART_MARKERS = (
        "recomecar", "reiniciar", "comecar de novo", "desde o inicio",
        "do zero", "voltar ao inicio",
    )
    NEGATION_PATTERNS = (
        r"\bnao\s+quero\s+(?:aprender|estudar)\b",
        r"\bnao\s+(?:me\s+)?ensine\b",
    )

    @classmethod
    def detect(cls, message, area="ads"):
        normalized = normalize_alias(message)
        result = {
            "kind": "continue",
            "concept_id": None,
            "restart": False,
            "explicit": False,
        }
        if not normalized:
            return result
        if any(re.search(pattern, normalized) for pattern in cls.NEGATION_PATTERNS):
            return result

        explicit = any(marker in normalized for marker in cls.START_MARKERS)
        restart = any(marker in normalized for marker in cls.RESTART_MARKERS)
        if not explicit and not restart:
            return result

        candidates = []
        for concept in ConceptCatalog.list_selectable(area):
            resolved = ConceptCatalog.resolve(area, concept["concept_id"])
            names = (resolved["canonical_name"], concept["concept_id"])
            seed_aliases = []
            from backend.concepts import seed_by_id
            seed = seed_by_id(concept["concept_id"])
            if seed is not None:
                seed_aliases = list(seed.aliases)
            for name in (*names, *seed_aliases):
                alias = normalize_alias(name)
                if alias and re.search(rf"\b{re.escape(alias)}\b", normalized):
                    candidates.append((len(alias), concept["concept_id"]))

        concept_id = max(candidates, default=(0, None))[1]
        return {
            "kind": "restart" if restart else "study",
            "concept_id": concept_id,
            "restart": restart,
            "explicit": True,
        }

    @classmethod
    def history_since_latest_restart(cls, history):
        if not isinstance(history, list):
            return []
        last_restart = -1
        for index, item in enumerate(history):
            if not isinstance(item, dict) or item.get("role") != "user":
                continue
            if cls.detect(item.get("content"))["restart"]:
                last_restart = index
        return history[last_restart + 1:] if last_restart >= 0 else history
