from backend.identity import DEFAULT_STUDENT_ID
from backend.services.concept_progress import ConceptProgress
from backend.services.learner_state import LearnerState
from backend.services.review_queue import ReviewQueue
from backend.services.review_scheduler import ReviewScheduler


class ReviewLifecycle:
    REVIEW_STAGE = "reencontrar"
    COMPLETED_STAGE = "concluido"

    @classmethod
    def activate_due(
        cls,
        area,
        now=None,
        student_id=DEFAULT_STUDENT_ID,
    ):
        progress = ReviewQueue.next_due(
            area,
            now=now,
            student_id=student_id,
        )
        if not progress:
            return None

        return LearnerState.update(
            area,
            current_concept=progress["concept"],
            stage=cls.REVIEW_STAGE,
            last_evidence=progress.get("last_evidence") or "",
            difficulty_count=progress.get("difficulty_count", 0),
            mastery=progress.get("mastery", 0.0),
            student_id=student_id,
        )

    @classmethod
    def complete_due(
        cls,
        area,
        concept,
        learner_state,
        now=None,
        student_id=DEFAULT_STUDENT_ID,
    ):
        if not isinstance(learner_state, dict):
            return None

        if learner_state.get("current_concept") != concept:
            return None

        progress = ConceptProgress.get(
            area,
            concept,
            student_id=student_id,
        )
        if not progress or not ReviewScheduler.is_due(progress, now=now):
            return None

        current_time = ReviewScheduler.normalize_now(now)
        review_count = ReviewScheduler.normalize_count(
            progress.get("review_count", 0)
        ) + 1

        candidate = {
            **progress,
            "review_count": review_count,
            "difficulty_count": learner_state.get("difficulty_count", 0),
        }

        schedule = ReviewScheduler.schedule(candidate, now=current_time)
        if not schedule:
            return None

        updated_progress = ConceptProgress.update(
            area,
            concept,
            mastery=learner_state.get("mastery", 0.0),
            difficulty_count=learner_state.get("difficulty_count", 0),
            last_evidence=learner_state.get("last_evidence"),
            review_count=review_count,
            last_reviewed_at=current_time.isoformat(timespec="seconds"),
            next_review_at=schedule["next_review_at"],
            student_id=student_id,
        )

        updated_state = LearnerState.update(
            area,
            stage=cls.COMPLETED_STAGE,
            student_id=student_id,
        )

        return {
            "state": updated_state,
            "progress": updated_progress,
        }
