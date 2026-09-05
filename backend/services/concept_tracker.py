import json

from backend.services.concept_catalog import ConceptCatalog
from backend.services.learner_signals import LearnerSignals
from backend.services.learning_intent import LearningIntent


class ConceptTracker:
    """Seleciona apenas conceitos estáveis do catálogo pedagógico."""

    EXPLICIT_STUDY_REQUESTS = (
        "quero aprender", "quero estudar", "gostaria de aprender",
        "gostaria de estudar", "preciso aprender", "preciso estudar",
        "vamos aprender", "vamos estudar", "me ensine", "me ensina",
        "pode me ensinar", "poderia me ensinar",
    )

    @staticmethod
    def has_current_concept(state):
        if not isinstance(state, dict) or state.get("stage") == "concluido":
            return False
        concept_id = state.get("current_concept_id")
        if isinstance(concept_id, str) and concept_id.strip():
            return True
        concept = state.get("current_concept")
        if not isinstance(concept, str) or not concept.strip():
            return False
        area = state.get("area", "ads")
        return ConceptCatalog.resolve(area, concept) is not None

    @classmethod
    def needs_tracking(cls, state):
        return not cls.has_current_concept(state)

    @staticmethod
    def normalize_concept(concept):
        if not isinstance(concept, str):
            return None
        concept = " ".join(concept.split())
        return concept or None

    @classmethod
    def is_explicit_study_request(cls, user_message):
        return LearningIntent.detect(user_message).get("explicit", False)

    @classmethod
    def identify_locally(cls, user_message, area="ads"):
        """Resolve pedidos explícitos reconhecíveis sem uma chamada ao LLM."""
        intent = LearningIntent.detect(user_message, area=area)
        return intent.get("concept_id") if intent.get("explicit") else None

    @classmethod
    def resolve_candidate(cls, state, candidate, area="ads"):
        if cls.has_current_concept(state):
            current_id = state.get("current_concept_id")
            if current_id:
                return current_id
            concept = ConceptCatalog.resolve(area, state.get("current_concept"))
            return concept.get("concept_id") if concept else None

        concept = ConceptCatalog.resolve(area, candidate, selectable_only=True)
        return concept.get("concept_id") if concept else None

    @classmethod
    def resolve_identified_candidate(cls, state, candidate, area="ads"):
        concept = ConceptCatalog.resolve(area, candidate, selectable_only=True)
        if concept:
            return concept["concept_id"]
        return cls.resolve_candidate(state, candidate, area=area)

    @classmethod
    def build_tracking_request(cls, user_message, state, area):
        if not isinstance(user_message, str) or not user_message.strip():
            return None
        if LearnerSignals.detect(user_message):
            return None

        has_active_concept = cls.has_current_concept(state)
        if has_active_concept and not cls.is_explicit_study_request(user_message):
            return None

        return {
            "area": area,
            "student_message": user_message.strip(),
        }

    @staticmethod
    def build_identification_messages(tracking_request):
        if not isinstance(tracking_request, dict):
            return None

        area = tracking_request.get("area")
        message = tracking_request.get("student_message")
        if not isinstance(message, str) or not message.strip():
            return None

        candidates = ConceptCatalog.list_selectable(area)
        if not candidates:
            return None

        candidate_lines = "\n".join(
            f'- {item["concept_id"]}: {item["canonical_name"]}'
            for item in candidates
        )
        system = (
            "Escolha o conceito pedagógico principal somente entre os IDs "
            "fornecidos. Nunca invente, altere ou componha um concept_id. "
            "Se nenhum candidato representar claramente o pedido, use null. "
            "Responda somente JSON no formato "
            '{"concept_id":"id.exato"} ou {"concept_id":null}.'
        )
        user = (
            f"Área: {area}\n"
            f"Conceitos permitidos:\n{candidate_lines}\n"
            f"Mensagem do aluno: {message.strip()}"
        )
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

    @classmethod
    def parse_identification_response(cls, content, area="ads"):
        if not isinstance(content, str) or not content.strip():
            return None
        try:
            data = json.loads(content)
        except (json.JSONDecodeError, TypeError):
            return None
        if not isinstance(data, dict):
            return None

        candidate = data.get("concept_id")
        if candidate is None:
            # Compatibilidade defensiva com respostas antigas, sem voltar a
            # aceitar texto livre: o alias ainda precisa existir no catálogo.
            candidate = data.get("concept")

        concept = ConceptCatalog.resolve(area, candidate, selectable_only=True)
        return concept.get("concept_id") if concept else None
