from backend.services.concept_catalog import ConceptCatalog
from backend.services.learner_signals import LearnerSignals
from backend.services.evidence_policy import EvidencePolicy
from backend.services.rubric_policy import RubricPolicy


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
        "compreender",
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
        concept_value = (
            state.get("current_concept_id")
            or state.get("current_concept")
        )
        concept = ConceptCatalog.resolve(
            state.get("area", "ads"),
            concept_value,
        )
        stage = state.get("stage")
        return concept is not None and stage in cls.EVALUATION_STAGES

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

        definition = ConceptCatalog.resolve(
            state.get("area", "ads"),
            state.get("current_concept_id")
            or state.get("current_concept"),
        )
        if definition is None:
            return None

        return {
            "concept_id": definition["concept_id"],
            "concept": definition["canonical_name"],
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
            f"Rubrica {EvidencePolicy.RUBRIC_ID} v{EvidencePolicy.RUBRIC_VERSION}. "
            "Classifique separadamente três critérios: "
            "task_response (respondeu ao que o tutor pediu), "
            "conceptual_correctness (correção conceitual) e "
            "understanding_application (demonstrou compreensão ou aplicação, não mera concordância). "
            "Para cada critério use somente met, partial, not_met ou unknown. "
            "Não transforme frases como 'entendi' em prova de compreensão. "
            "O servidor derivará o outcome final; não tente decidir domínio. "
            "Responda somente JSON com criteria, confidence e evidence. "
            "criteria deve conter exatamente task_response, conceptual_correctness "
            "e understanding_application."
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

        try:
            confidence = float(data.get("confidence"))
        except (TypeError, ValueError):
            return None
        if not 0.0 <= confidence <= 1.0:
            return None

        evidence = data.get("evidence")
        if evidence is not None and not isinstance(evidence, str):
            return None

        normalized = RubricPolicy.normalize_payload(data)
        if normalized is None:
            return None

        # Respostas no contrato v2 precisam trazer os três critérios.
        # O fallback legacy_outcome existe apenas para compatibilidade de
        # chamadas internas e dados antigos; a saída do avaliador atual deve
        # estar completa para ser aceita como avaliação semântica nova.
        if normalized["outcome_source"] != "rubric":
            return None

        return {
            "outcome": normalized["outcome"],
            "confidence": confidence,
            "evidence": evidence,
            "criteria": normalized["criteria"],
            "rubric_complete": True,
            "outcome_source": "rubric",
        }
