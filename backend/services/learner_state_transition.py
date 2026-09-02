from backend.services.learner_signals import LearnerSignals
from backend.services.evidence_evaluator import EvidenceEvaluator


class LearnerStateTransition:
    @classmethod
    def from_signals(cls, state, signals):
        if not isinstance(state, dict):
            state = {}
        if not isinstance(signals, set):
            signals = set(signals or [])

        if not signals:
            return {}

        changes = {}
        try:
            difficulty = max(0, int(state.get("difficulty_count", 0)))
        except (TypeError, ValueError):
            difficulty = 0

        if LearnerSignals.DIFFICULTY in signals:
            changes["difficulty_count"] = difficulty + 1
            changes["stage"] = "corrigir"

        if (
            LearnerSignals.TEST_REQUEST in signals
            and LearnerSignals.DIFFICULTY not in signals
        ):
            changes["stage"] = "testar"

        if (
            LearnerSignals.REVIEW_REQUEST in signals
            and LearnerSignals.DIFFICULTY not in signals
        ):
            changes["stage"] = "reencontrar"

        if (
            LearnerSignals.REEXPLAIN_REQUEST in signals
            and LearnerSignals.DIFFICULTY not in signals
            and LearnerSignals.REVIEW_REQUEST not in signals
            and LearnerSignals.TEST_REQUEST not in signals
        ):
            changes["stage"] = "compreender"

        return changes

    @classmethod
    def from_evidence(cls, state, evidence):
        if not isinstance(state, dict) or not isinstance(evidence, dict):
            return {}
        outcome = evidence.get("outcome")
        if outcome not in EvidenceEvaluator.VALID_OUTCOMES:
            return {}
        try:
            confidence = float(evidence.get("confidence"))
        except (TypeError, ValueError):
            return {}
        if confidence < EvidenceEvaluator.MIN_CONFIDENCE:
            return {}

        try:
            mastery = min(1.0, max(0.0, float(state.get("mastery", 0.0))))
        except (TypeError, ValueError):
            mastery = 0.0
        try:
            difficulty = max(0, int(state.get("difficulty_count", 0)))
        except (TypeError, ValueError):
            difficulty = 0

        if outcome == EvidenceEvaluator.INSUFFICIENT:
            return {
                "last_evidence": evidence.get("evidence") or outcome,
            }

        if outcome == EvidenceEvaluator.MISCONCEPTION:
            return {
                "mastery": max(0.0, mastery - 0.10),
                "difficulty_count": difficulty + 1,
                "stage": "corrigir",
                "last_evidence": evidence.get("evidence") or outcome,
            }

        if outcome == EvidenceEvaluator.PARTIAL:
            return {
                "mastery": min(1.0, mastery + 0.05),
                "stage": "testar",
                "last_evidence": evidence.get("evidence") or outcome,
            }

        if outcome == EvidenceEvaluator.DEMONSTRATED:
            return {
                "mastery": min(1.0, mastery + 0.20),
                "difficulty_count": max(0, difficulty - 1),
                "stage": "fixar",
                "last_evidence": evidence.get("evidence") or outcome,
            }

        return {}
