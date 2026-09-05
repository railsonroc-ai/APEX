import re

from backend.concepts import normalize_alias
from backend.services.evidence_policy import EvidencePolicy
from backend.services.task_spec import TaskSpec


class TutorResponseValidator:
    LEVEL_RANK = {
        EvidencePolicy.ASSISTANCE_UNTRACKED: 0,
        "independent": 0,
        "light": 1,
        "guided": 2,
        "direct": 3,
    }

    @classmethod
    def observe_assistance(cls, response):
        text = normalize_alias(response) or ""
        if any(marker in text for marker in (
            "a resposta e", "a solucao e", "passo a passo da solucao",
            "faca assim", "correcao completa",
        )):
            return "direct"
        if any(marker in text for marker in (
            "por exemplo", "pense em", "pode ser entendido", "significa",
            "vamos entender", "explicacao",
        )):
            return "guided"
        if any(marker in text for marker in ("pista", "lembre", "dica")):
            return "light"
        return "independent"

    @classmethod
    def validate(cls, response, contract):
        errors = []
        if not isinstance(response, str) or not response.strip():
            return {"valid": False, "errors": ["empty"], "assistance_level": "independent"}

        text = response.strip()
        normalized = normalize_alias(text) or ""
        if contract.feedback_text:
            expected_feedback = normalize_alias(contract.feedback_text) or ""
            if not normalized.startswith(expected_feedback):
                errors.append("feedback_missing")
        if len(text) > contract.max_chars:
            errors.append("too_long")
        if text.count("?") > contract.max_questions:
            errors.append("too_many_questions")
        if not contract.allow_code and ("```" in text or re.search(r"(?m)^\s*(?:def|class|if|for|while)\b", text)):
            errors.append("code_not_allowed")
        for forbidden in contract.forbidden_terms:
            term = normalize_alias(forbidden)
            if term and re.search(rf"\b{re.escape(term)}\b", normalized):
                errors.append(f"forbidden:{forbidden}")
        task_count = TaskSpec.count(text)
        if contract.task_required and task_count != 1:
            errors.append("task_count")
        if not contract.task_required and task_count > 1:
            errors.append("task_count")
        if contract.review_mode:
            task_match = re.search(r"(?im)^\s*(?:tarefa|desafio|sua vez)\s*:", text)
            prefix = text[:task_match.start()] if task_match else text
            if len(normalize_alias(prefix) or "") > 40:
                errors.append("review_teaches_before_retrieval")

        observed = cls.observe_assistance(text)
        if cls.LEVEL_RANK[observed] > cls.LEVEL_RANK.get(contract.assistance_ceiling, 0):
            errors.append("assistance_above_ceiling")
        return {"valid": not errors, "errors": errors, "assistance_level": observed}

    @classmethod
    def validate_or_fallback(cls, response, contract):
        result = cls.validate(response, contract)
        if result["valid"]:
            return {**result, "response": response.strip(), "fallback_used": False}
        if contract.safe_response:
            fallback = cls.validate(contract.safe_response, contract)
            if not fallback["valid"]:
                raise ValueError(f"fallback pedagógico inválido: {fallback['errors']}")
            return {
                **fallback,
                "response": contract.safe_response.strip(),
                "fallback_used": True,
                "rejected_errors": result["errors"],
            }
        raise ValueError(f"resposta viola contrato pedagógico: {result['errors']}")

    @staticmethod
    def chunks(response, size=180):
        return [response[index:index + size] for index in range(0, len(response), size)]
