from backend.services.concept_progress import ConceptProgress
from backend.services.learner_state import LearnerState


class ConceptActivation:
    INITIAL_STAGE = "compreender"

    @classmethod
    def activate(cls, area, concept):
        progress = ConceptProgress.get(area, concept)

        if not progress:
            return LearnerState.get(area)

        known_concept = progress.get("updated_at") is not None

        if known_concept:
            return LearnerState.update(
                area,
                current_concept=progress["concept"],
                stage=cls.INITIAL_STAGE,
                last_evidence=progress.get("last_evidence") or "",
                difficulty_count=progress.get("difficulty_count", 0),
                mastery=progress.get("mastery", 0.0),
            )

        return LearnerState.update(
            area,
            current_concept=progress["concept"],
            stage=cls.INITIAL_STAGE,
            last_evidence="",
            difficulty_count=0,
            mastery=0.0,
        )
