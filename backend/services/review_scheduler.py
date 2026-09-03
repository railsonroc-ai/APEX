from datetime import datetime, timedelta, timezone


class ReviewScheduler:
    INTERVAL_DAYS = (1, 3, 7, 14, 30)

    @staticmethod
    def normalize_count(value):
        try:
            return max(0, int(value))
        except (TypeError, ValueError):
            return 0

    @classmethod
    def interval_days(cls, review_count, difficulty_count=0):
        reviews = cls.normalize_count(review_count)
        difficulty = cls.normalize_count(difficulty_count)

        index = min(reviews, len(cls.INTERVAL_DAYS) - 1)
        days = cls.INTERVAL_DAYS[index]

        if difficulty >= 2:
            return 1
        if difficulty == 1:
            return max(1, days // 2)

        return days

    @staticmethod
    def normalize_now(now=None):
        if now is None:
            return datetime.now(timezone.utc)
        if now.tzinfo is None:
            return now.replace(tzinfo=timezone.utc)
        return now.astimezone(timezone.utc)

    @classmethod
    def schedule(cls, progress, now=None):
        if not isinstance(progress, dict):
            return None

        current_time = cls.normalize_now(now)
        days = cls.interval_days(
            progress.get("review_count", 0),
            progress.get("difficulty_count", 0),
        )

        next_review = current_time + timedelta(days=days)

        return {
            "next_review_at": next_review.isoformat(timespec="seconds"),
        }

    @classmethod
    def is_due(cls, progress, now=None):
        if not isinstance(progress, dict):
            return False

        next_review_at = progress.get("next_review_at")
        if not isinstance(next_review_at, str) or not next_review_at.strip():
            return False

        try:
            due_time = datetime.fromisoformat(next_review_at.strip())
        except ValueError:
            return False

        due_time = cls.normalize_now(due_time)
        current_time = cls.normalize_now(now)

        return due_time <= current_time
