from backend.identity import DEFAULT_STUDENT_ID
from backend.services.concept_progress import ConceptProgress
from backend.services.learner_state import LearnerState


class ConceptActivation:
    INITIAL_STAGE = "compreender"

    @classmethod
    def activate(
        cls,
        area,
        concept,
        student_id=DEFAULT_STUDENT_ID,
    ):
        progress = ConceptProgress.get(
            area,
            concept,
            student_id=student_id,
        )

        if not progress:
            return LearnerState.get(
                area,
                student_id=student_id,
            )

        known_concept = progress.get("updated_at") is not None

        if known_concept:
            return LearnerState.update(
                area,
                current_concept=progress["concept"],
                stage=cls.INITIAL_STAGE,
                last_evidence=progress.get("last_evidence") or "",
                difficulty_count=progress.get("difficulty_count", 0),
                mastery=progress.get("mastery", 0.0),
                student_id=student_id,
            )

        return LearnerState.update(
            area,
            current_concept=progress["concept"],
            stage=cls.INITIAL_STAGE,
            last_evidence="",
            difficulty_count=0,
            mastery=0.0,
            student_id=student_id,
        )
