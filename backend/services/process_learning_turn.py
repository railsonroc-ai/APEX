from backend.services.concept_activation import ConceptActivation
from backend.services.concept_progress import ConceptProgress
from backend.services.concept_tracker import ConceptTracker
from backend.services.evidence_evaluator import EvidenceEvaluator
from backend.services.learner_signals import LearnerSignals
from backend.services.learner_state import LearnerState
from backend.services.learner_state_transition import LearnerStateTransition
from backend.services.review_lifecycle import ReviewLifecycle
from backend.services.review_scheduler import ReviewScheduler
from backend.services.teaching_policy import TeachingPolicy


class ProcessLearningTurn:
    @classmethod
    def activate_identified_concept(
        cls,
        area,
        learner_state,
        identified_concept,
    ):
        if not identified_concept:
            return learner_state

        resolved_concept = ConceptTracker.resolve_candidate(
            learner_state,
            identified_concept,
        )

        if not resolved_concept:
            return learner_state

        return ConceptActivation.activate(
            area,
            resolved_concept,
        )

    @classmethod
    def finalize(
        cls,
        area,
        user_message,
        learner_state,
        semantic_evidence,
    ):
        evidence_changes = LearnerStateTransition.from_evidence(
            learner_state,
            semantic_evidence,
        )

        if evidence_changes:
            previous_stage = learner_state.get("stage")

            learner_state = LearnerState.update(
                area,
                **evidence_changes,
            )

            current_concept = learner_state.get("current_concept")

            if current_concept:
                concept_progress = ConceptProgress.update(
                    area,
                    current_concept,
                    mastery=learner_state.get("mastery"),
                    difficulty_count=learner_state.get(
                        "difficulty_count"
                    ),
                    last_evidence=learner_state.get(
                        "last_evidence"
                    ),
                )

                if (
                    previous_stage == "reencontrar"
                    and semantic_evidence
                    and semantic_evidence.get("outcome")
                    == EvidenceEvaluator.DEMONSTRATED
                ):
                    review_result = ReviewLifecycle.complete_due(
                        area,
                        current_concept,
                        learner_state,
                    )

                    if review_result:
                        learner_state = review_result["state"]

                elif (
                    previous_stage != "concluido"
                    and learner_state.get("stage") == "concluido"
                ):
                    review_schedule = ReviewScheduler.schedule(
                        concept_progress
                    )

                    if review_schedule:
                        ConceptProgress.update(
                            area,
                            current_concept,
                            **review_schedule,
                        )

        signals = LearnerSignals.detect(user_message)

        if LearnerSignals.REVIEW_REQUEST in signals:
            due_review_state = ReviewLifecycle.activate_due(area)

            if due_review_state:
                learner_state = due_review_state

        state_changes = LearnerStateTransition.from_signals(
            learner_state,
            signals,
        )

        if state_changes:
            learner_state = LearnerState.update(
                area,
                **state_changes,
            )

        teaching_action = TeachingPolicy.choose_action(
            learner_state
        )

        return {
            "learner_state": learner_state,
            "teaching_action": teaching_action,
        }
