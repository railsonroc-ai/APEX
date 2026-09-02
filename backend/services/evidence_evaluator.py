from backend.services.learner_signals import LearnerSignals


class EvidenceEvaluator:
    NOT_APPLICABLE = "not_applicable"
    INSUFFICIENT = "insufficient"
    PARTIAL = "partial"
    DEMONSTRATED = "demonstrated"
    MISCONCEPTION = "misconception"

    MIN_CONFIDENCE = 0.75

    EVALUATION_STAGES = {
        "explicar",
        "testar",
        "corrigir",
        "fixar",
        "reencontrar",
    }

    @classmethod
    def is_applicable(cls, state):
        if not isinstance(state, dict):
            return False
        concept = state.get("current_concept")
        stage = state.get("stage")
        return bool(concept) and stage in cls.EVALUATION_STAGES

    @staticmethod
    def last_assistant_message(history):
        if not isinstance(history, list):
            return None
        for item in reversed(history):
            if isinstance(item, dict) and item.get("role") == "assistant":
                content = item.get("content")
                if isinstance(content, str) and content.strip():
                    return content.strip()
        return None

    @classmethod
    def build_evaluation(cls, user_message, history, state):
        if not cls.is_applicable(state):
            return None
        tutor_message = cls.last_assistant_message(history)
        if not tutor_message:
            return None
        if not isinstance(user_message, str) or not user_message.strip():
            return None
        if LearnerSignals.detect(user_message):
            return None

        return {
            "concept": str(state["current_concept"]).strip(),
            "stage": state["stage"],
            "tutor_message": tutor_message,
            "student_answer": user_message.strip(),
        }
