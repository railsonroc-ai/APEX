from backend.services.learner_signals import LearnerSignals


class ConceptTracker:
    """Acompanha o conceito pedagógico atual do aluno."""

    EXPLICIT_STUDY_REQUESTS = (
        "quero aprender",
        "quero estudar",
        "gostaria de aprender",
        "gostaria de estudar",
        "preciso aprender",
        "preciso estudar",
        "vamos aprender",
        "vamos estudar",
        "me ensine",
        "me ensina",
        "pode me ensinar",
        "poderia me ensinar",
    )

    @staticmethod
    def has_current_concept(state):
        if not isinstance(state, dict):
            return False
        if state.get("stage") == "concluido":
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
    def is_explicit_study_request(cls, user_message):
        if not isinstance(user_message, str):
            return False

        normalized = " ".join(
            user_message.lower().split()
        )

        return any(
            marker in normalized
            for marker in cls.EXPLICIT_STUDY_REQUESTS
        )

    @classmethod
    def resolve_candidate(cls, state, candidate):
        if cls.has_current_concept(state):
            return cls.normalize_concept(
                state["current_concept"]
            )

        return cls.normalize_concept(candidate)

    @classmethod
    def resolve_identified_candidate(
        cls,
        state,
        candidate,
    ):
        normalized_candidate = cls.normalize_concept(
            candidate
        )

        if normalized_candidate:
            return normalized_candidate

        return cls.resolve_candidate(
            state,
            candidate,
        )

    @classmethod
    def build_tracking_request(cls, user_message, state, area):
        if not isinstance(user_message, str) or not user_message.strip():
            return None

        if LearnerSignals.detect(user_message):
            return None

        has_active_concept = cls.has_current_concept(
            state
        )

        if (
            has_active_concept
            and not cls.is_explicit_study_request(
                user_message
            )
        ):
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

        system = (
            "Identifique apenas o conceito pedagógico principal que o aluno "
            "está pedindo para estudar. Não invente conceito quando a mensagem "
            "for vaga. Responda somente JSON no formato: "
            "{\"concept\": \"nome\"} ou {\"concept\": null}."
        )

        user = (
            f"Área: {area}\n"
            f"Mensagem do aluno: {message.strip()}"
        )

        return [
            {
                "role": "system",
                "content": system,
            },
            {
                "role": "user",
                "content": user,
            },
        ]

    @classmethod
    def parse_identification_response(cls, content):
        import json

        if not isinstance(content, str) or not content.strip():
            return None

        try:
            data = json.loads(content)
        except (json.JSONDecodeError, TypeError):
            return None

        if not isinstance(data, dict):
            return None

        return cls.normalize_concept(
            data.get("concept")
        )
