from backend.services.learner_signals import LearnerSignals


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
