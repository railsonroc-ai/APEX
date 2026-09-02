from backend.services.learner_signals import LearnerSignals


class EvidenceEvaluator:
    NOT_APPLICABLE = "not_applicable"
    INSUFFICIENT = "insufficient"
    PARTIAL = "partial"
    DEMONSTRATED = "demonstrated"
    MISCONCEPTION = "misconception"

    MIN_CONFIDENCE = 0.75

    VALID_OUTCOMES = {
        INSUFFICIENT,
        PARTIAL,
        DEMONSTRATED,
        MISCONCEPTION,
    }

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

    @classmethod
    def build_evaluation_messages(cls, evaluation):
        if not isinstance(evaluation, dict):
            return None
        concept = evaluation.get("concept")
        tutor = evaluation.get("tutor_message")
        student = evaluation.get("student_answer")
        if not all(isinstance(x, str) and x.strip() for x in (concept, tutor, student)):
            return None
        system = (
            "Avalie semanticamente a evidência de aprendizagem do aluno. "
            "Não considere declarações como entendi como prova suficiente. "
            "Responda somente JSON com outcome, confidence e evidence. "
            "outcome deve ser insufficient, partial, demonstrated ou misconception."
        )
        user = f"Conceito: {concept}\nTutor: {tutor}\nAluno: {student}"
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

    @classmethod
    def parse_evaluation_response(cls, content):
        import json
        if not isinstance(content, str) or not content.strip():
            return None
        try:
            data = json.loads(content)
        except (json.JSONDecodeError, TypeError):
            return None
        if not isinstance(data, dict):
            return None
        outcome = data.get("outcome")
        if outcome not in cls.VALID_OUTCOMES:
            return None
        try:
            confidence = float(data.get("confidence"))
        except (TypeError, ValueError):
            return None
        if not 0.0 <= confidence <= 1.0:
            return None
        evidence = data.get("evidence")
        if evidence is not None and not isinstance(evidence, str):
            return None
        return {"outcome": outcome, "confidence": confidence, "evidence": evidence}
