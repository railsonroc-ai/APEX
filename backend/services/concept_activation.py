from backend.identity import DEFAULT_STUDENT_ID
from backend.services.concept_progress import ConceptProgress
from backend.services.learner_state import LearnerState
from backend.services.curriculum import Curriculum


class ConceptActivation:
    INITIAL_STAGE = "compreender"

    @classmethod
    def activate(cls, area, concept, student_id=DEFAULT_STUDENT_ID, restart=False):
        concept = Curriculum.entry_concept_id(concept)
        progress = ConceptProgress.get(area, concept, student_id=student_id)
        if not progress:
            return LearnerState.get(area, student_id=student_id)

        known_concept = progress.get("updated_at") is not None and not restart
        changes = {
            "current_concept_id": progress["concept_id"],
            "stage": cls.INITIAL_STAGE,
            "student_id": student_id,
        }
        if known_concept:
            changes.update(
                last_evidence=progress.get("last_evidence") or "",
                difficulty_count=progress.get("difficulty_count", 0),
                mastery=progress.get("mastery", 0.0),
            )
        else:
            changes.update(last_evidence="", difficulty_count=0, mastery=0.0)

        if restart:
            ConceptProgress.update(
                area,
                progress["concept_id"],
                mastery=0.0,
                difficulty_count=0,
                last_evidence="",
                review_count=0,
                next_review_at="",
                last_reviewed_at="",
                student_id=student_id,
            )

        return LearnerState.update(area, **changes)
