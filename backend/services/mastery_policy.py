from backend.identity import DEFAULT_STUDENT_ID, normalize_student_id
from backend.services.evidence_evaluator import EvidenceEvaluator
from backend.services.evidence_event import EvidenceEvent
from backend.services.evidence_policy import EvidencePolicy
from backend.services.learning_history import LearningHistory
from backend.services.task_context_identity import TaskContextIdentity


class MasteryPolicy:
    """Política determinística e auditável para conclusão de uma competência.

    O score numérico continua compatível com o kernel atual, porém sozinho não
    autoriza conclusão. A decisão exige um pequeno portfólio de evidências
    confirmadas e diversidade mínima de contexto pedagógico.
    """

    POLICY_ID = "evidence_portfolio_mastery"
    POLICY_VERSION = 3

    MIN_SCORE_TO_COMPLETE = 0.80
    MIN_APPLIED_EVIDENCE = 3
    MIN_DEMONSTRATED = 2
    MIN_DEMONSTRATED_STAGES = 2
    MIN_DEMONSTRATED_CONTEXTS = 2

    LOW_ASSISTANCE_LEVELS = {
        "independent",
        "light",
    }
    TRACKED_ASSISTANCE_LEVELS = (
        EvidencePolicy.ASSISTANCE_LEVELS
        - {EvidencePolicy.ASSISTANCE_UNTRACKED}
    )

    BLOCK_CURRENT_NOT_APPLIED = "current_evidence_not_applied"
    BLOCK_STAGE_NOT_FIXING = "stage_not_fixar"
    BLOCK_SCORE = "score_below_threshold"
    BLOCK_EVIDENCE_COUNT = "insufficient_applied_evidence"
    BLOCK_DEMONSTRATED_COUNT = "insufficient_demonstrated_evidence"
    BLOCK_STAGE_DIVERSITY = "insufficient_demonstrated_stage_diversity"
    BLOCK_CONTEXT_DIVERSITY = "insufficient_demonstrated_task_context_diversity"
    BLOCK_LATEST_OUTCOME = "latest_outcome_not_demonstrated"
    BLOCK_ASSISTANCE = "no_low_assistance_demonstration"
    BLOCK_CURRENT_ASSISTANCE = "current_assistance_too_high_or_untracked"

    @staticmethod
    def _normalize_score(value):
        try:
            score = float(value)
        except (TypeError, ValueError):
            score = 0.0
        return min(1.0, max(0.0, score))

    @classmethod
    def evaluate(
        cls,
        *,
        area,
        concept,
        stage_before,
        semantic_evidence,
        mastery_score,
        current_applied,
        student_id=DEFAULT_STUDENT_ID,
        assistance_level=EvidencePolicy.ASSISTANCE_UNTRACKED,
        current_context_id=None,
    ):
        normalized_area = LearningHistory.normalize_area(area)
        normalized_student_id = normalize_student_id(student_id)
        score = cls._normalize_score(mastery_score)
        normalized_assistance = EvidencePolicy.normalize_assistance_level(
            assistance_level
        )

        events = EvidenceEvent.list_for_concept(
            normalized_area,
            concept,
            student_id=normalized_student_id,
            limit=200,
        )

        portfolio = [
            {
                "outcome": event.get("outcome"),
                "stage_before": event.get("stage_before"),
                "assistance_level": event.get("assistance_level"),
                "context_id": TaskContextIdentity.for_evidence_event(event),
                "applied": bool(event.get("applied")),
            }
            for event in events
        ]

        candidate_outcome = None
        if isinstance(semantic_evidence, dict):
            candidate_outcome = semantic_evidence.get("outcome")

        portfolio.append(
            {
                "outcome": candidate_outcome,
                "stage_before": stage_before,
                "assistance_level": normalized_assistance,
                "context_id": current_context_id,
                "applied": bool(current_applied),
            }
        )

        applied = [item for item in portfolio if item["applied"]]
        demonstrated = [
            item
            for item in applied
            if item["outcome"] == EvidenceEvaluator.DEMONSTRATED
        ]
        demonstrated_stages = {
            item["stage_before"]
            for item in demonstrated
            if isinstance(item.get("stage_before"), str)
            and item["stage_before"].strip()
        }
        demonstrated_contexts = {
            item["context_id"]
            for item in demonstrated
            if isinstance(item.get("context_id"), str)
            and item["context_id"].strip()
        }
        requires_context_diversity = TaskContextIdentity.requires_explicit_context(
            concept
        )
        retention_demonstrated = [
            item
            for item in demonstrated
            if item.get("stage_before") == "reencontrar"
        ]

        tracked_demonstrated = [
            item
            for item in demonstrated
            if item.get("assistance_level") in cls.TRACKED_ASSISTANCE_LEVELS
        ]
        low_assistance_demonstrated = [
            item
            for item in demonstrated
            if item.get("assistance_level") in cls.LOW_ASSISTANCE_LEVELS
        ]

        blockers = []

        if not current_applied:
            blockers.append(cls.BLOCK_CURRENT_NOT_APPLIED)
        if stage_before != "fixar":
            blockers.append(cls.BLOCK_STAGE_NOT_FIXING)
        if score < cls.MIN_SCORE_TO_COMPLETE:
            blockers.append(cls.BLOCK_SCORE)
        if len(applied) < cls.MIN_APPLIED_EVIDENCE:
            blockers.append(cls.BLOCK_EVIDENCE_COUNT)
        if len(demonstrated) < cls.MIN_DEMONSTRATED:
            blockers.append(cls.BLOCK_DEMONSTRATED_COUNT)
        if len(demonstrated_stages) < cls.MIN_DEMONSTRATED_STAGES:
            blockers.append(cls.BLOCK_STAGE_DIVERSITY)
        if (
            requires_context_diversity
            and len(demonstrated_contexts) < cls.MIN_DEMONSTRATED_CONTEXTS
        ):
            blockers.append(cls.BLOCK_CONTEXT_DIVERSITY)
        if candidate_outcome != EvidenceEvaluator.DEMONSTRATED:
            blockers.append(cls.BLOCK_LATEST_OUTCOME)
        if not low_assistance_demonstrated:
            blockers.append(cls.BLOCK_ASSISTANCE)
        if normalized_assistance not in cls.LOW_ASSISTANCE_LEVELS:
            blockers.append(cls.BLOCK_CURRENT_ASSISTANCE)

        recommended_stage = None
        if (
            stage_before == "fixar"
            and (
                cls.BLOCK_STAGE_DIVERSITY in blockers
                or cls.BLOCK_CONTEXT_DIVERSITY in blockers
                or cls.BLOCK_ASSISTANCE in blockers
                or cls.BLOCK_CURRENT_ASSISTANCE in blockers
            )
        ):
            recommended_stage = "testar"

        return {
            "policy_id": cls.POLICY_ID,
            "policy_version": cls.POLICY_VERSION,
            "score": score,
            "can_complete": not blockers,
            "applied_evidence_count": len(applied),
            "demonstrated_count": len(demonstrated),
            "demonstrated_stage_count": len(demonstrated_stages),
            "demonstrated_context_count": len(demonstrated_contexts),
            "context_diversity_required": requires_context_diversity,
            "retention_demonstrated_count": len(retention_demonstrated),
            "low_assistance_demonstrated_count": len(
                low_assistance_demonstrated
            ),
            "latest_outcome": candidate_outcome,
            "recommended_stage": recommended_stage,
            "blockers": blockers,
        }

# APEX_PEDAGOGICAL_EVAL_FIX_V2
# Conservative evaluator-only compatibility hook.
try:
    from backend.services.evaluation_policy import install_evaluator_policy as _apex_install_eval_v2
except ImportError:
    try:
        from services.evaluation_policy import install_evaluator_policy as _apex_install_eval_v2
    except ImportError:
        _apex_install_eval_v2 = None
if _apex_install_eval_v2 is not None:
    _apex_install_eval_v2(globals())

