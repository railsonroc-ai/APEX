from backend.services.learner_signals import LearnerSignals


class ConceptTracker:
    """Acompanha o conceito pedagógico atual do aluno."""

    @staticmethod
    def has_current_concept(state):
        if not isinstance(state, dict):
            return False
        concept = state.get("current_concept")
        return isinstance(concept, str) and bool(concept.strip())

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
    def resolve_candidate(cls, state, candidate):
        if cls.has_current_concept(state):
            return cls.normalize_concept(state["current_concept"])
        return cls.normalize_concept(candidate)

    @classmethod
    def build_tracking_request(cls, user_message, state, area):
        if not cls.needs_tracking(state):
            return None
        if not isinstance(user_message, str) or not user_message.strip():
            return None
        if LearnerSignals.detect(user_message):
            return None
        return {
            "area": area,
            "student_message": user_message.strip(),
        }
