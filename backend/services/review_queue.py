from backend.services.concept_progress import ConceptProgress
from backend.services.review_scheduler import ReviewScheduler


class ReviewQueue:
    @classmethod
    def due(cls, area, now=None):
        scheduled = ConceptProgress.list_scheduled(area)

        return [
            progress
            for progress in scheduled
            if ReviewScheduler.is_due(progress, now=now)
        ]

    @classmethod
    def next_due(cls, area, now=None):
        due = cls.due(area, now=now)
        return due[0] if due else None
