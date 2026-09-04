from backend.identity import DEFAULT_STUDENT_ID
from backend.services.concept_progress import ConceptProgress
from backend.services.review_scheduler import ReviewScheduler


class ReviewQueue:
    @classmethod
    def due(
        cls,
        area,
        now=None,
        student_id=DEFAULT_STUDENT_ID,
    ):
        scheduled = ConceptProgress.list_scheduled(
            area,
            student_id=student_id,
        )

        return [
            progress
            for progress in scheduled
            if ReviewScheduler.is_due(progress, now=now)
        ]

    @classmethod
    def next_due(
        cls,
        area,
        now=None,
        student_id=DEFAULT_STUDENT_ID,
    ):
        due = cls.due(
            area,
            now=now,
            student_id=student_id,
        )
        return due[0] if due else None
