from backend.database import (
    preview_transaction,
    transaction,
)
from backend.identity import (
    DEFAULT_STUDENT_ID,
    default_session_id,
    normalize_student_id,
)
from backend.services.concept_activation import ConceptActivation
from backend.services.concept_progress import ConceptProgress
from backend.services.concept_tracker import ConceptTracker
from backend.services.evidence_evaluator import EvidenceEvaluator
from backend.services.evidence_event import EvidenceEvent
from backend.services.evidence_policy import EvidencePolicy
from backend.services.learner_signals import LearnerSignals
from backend.services.learner_state import LearnerState
from backend.services.learner_state_transition import LearnerStateTransition
from backend.services.learning_history import LearningHistory
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
        student_id=DEFAULT_STUDENT_ID,
    ):
        if not identified_concept:
            return learner_state

        resolved_concept = (
            ConceptTracker
            .resolve_identified_candidate(
                learner_state,
                identified_concept,
                area=area,
            )
        )

        if not resolved_concept:
            return learner_state

        return ConceptActivation.activate(
            area,
            resolved_concept,
            student_id=student_id,
        )

    @classmethod
    def preview_activation(
        cls,
        area,
        learner_state,
        identified_concept,
        student_id=DEFAULT_STUDENT_ID,
    ):
        with preview_transaction():
            return cls.activate_identified_concept(
                area,
                learner_state,
                identified_concept,
                student_id=student_id,
            )

    @classmethod
    def preview_turn(
        cls,
        area,
        user_message,
        identified_concept,
        semantic_evidence,
        student_id=DEFAULT_STUDENT_ID,
    ):
        with preview_transaction():
            learner_state = LearnerState.get(
                area,
                student_id=student_id,
            )

            learner_state = cls.activate_identified_concept(
                area,
                learner_state,
                identified_concept,
                student_id=student_id,
            )

            return cls._finalize(
                area,
                user_message,
                learner_state,
                semantic_evidence,
                student_id=student_id,
            )

    @classmethod
    def commit_turn(
        cls,
        area,
        user_message,
        identified_concept,
        semantic_evidence,
        turn_id=None,
        assistant_message=None,
        student_id=DEFAULT_STUDENT_ID,
        session_id=None,
        evidence_context=None,
        assistance_level=EvidencePolicy.ASSISTANCE_UNTRACKED,
        artifact_ref=None,
    ):
        normalized_turn_id = (
            LearningHistory.normalize_turn_id(
                turn_id
            )
        )
        normalized_area = LearningHistory.normalize_area(
            area
        )
        normalized_user_message = (
            LearningHistory.normalize_message(
                user_message
            )
        )
        normalized_assistant_message = (
            LearningHistory.normalize_message(
                assistant_message
            )
        )
        normalized_student_id = normalize_student_id(
            student_id
        )
        normalized_session_id = (
            LearningHistory.normalize_session_id(
                session_id
            )
        )

        if (
            not normalized_session_id
            and normalized_student_id == DEFAULT_STUDENT_ID
        ):
            normalized_session_id = default_session_id(
                normalized_area
            )

        if not normalized_user_message:
            raise ValueError(
                "user_message obrigatória"
            )

        if normalized_turn_id and not normalized_session_id:
            raise ValueError(
                "session_id obrigatória para confirmar o turno"
            )

        with transaction():
            if normalized_turn_id:
                existing = LearningHistory.find(
                    normalized_turn_id,
                    student_id=normalized_student_id,
                )

                if existing is not None:
                    if (
                        existing["area"] != normalized_area
                        or existing["user_message"]
                        != normalized_user_message
                    ):
                        raise ValueError(
                            "turn_id reutilizado "
                            "com conteúdo diferente"
                        )

                    if (
                        not existing.get(
                            "assistant_message"
                        )
                        and not normalized_assistant_message
                    ):
                        raise ValueError(
                            "assistant_message obrigatória "
                            "para confirmar o turno"
                        )

                    learner_state = LearnerState.get(
                        normalized_area,
                        student_id=normalized_student_id,
                    )

                    existing = (
                        LearningHistory
                        .attach_response(
                            normalized_turn_id,
                            normalized_assistant_message,
                            concept_id=learner_state.get(
                                "current_concept_id"
                            ),
                            student_id=normalized_student_id,
                        )
                    )

                    return {
                        "learner_state":
                            learner_state,
                        "teaching_action":
                            TeachingPolicy.choose_action(
                                learner_state
                            ),
                        "duplicate": True,
                        "assistant_message": (
                            existing.get(
                                "assistant_message"
                            )
                            if existing
                            else None
                        ),
                    }

            if (
                normalized_turn_id
                and not normalized_assistant_message
            ):
                raise ValueError(
                    "assistant_message obrigatória "
                    "para confirmar o turno"
                )

            learner_state = LearnerState.get(
                normalized_area,
                student_id=normalized_student_id,
            )

            learner_state = cls.activate_identified_concept(
                normalized_area,
                learner_state,
                identified_concept,
                student_id=normalized_student_id,
            )

            state_before_evidence = dict(learner_state)
            evidence_applied = bool(
                LearnerStateTransition.from_evidence(
                    state_before_evidence,
                    semantic_evidence,
                )
            )

            result = cls._finalize(
                normalized_area,
                normalized_user_message,
                learner_state,
                semantic_evidence,
                student_id=normalized_student_id,
            )

            if normalized_turn_id:
                LearningHistory.record(
                    turn_id=normalized_turn_id,
                    area=normalized_area,
                    user_message=normalized_user_message,
                    assistant_message=normalized_assistant_message,
                    concept_id=result["learner_state"].get(
                        "current_concept_id"
                    ),
                    student_id=normalized_student_id,
                    session_id=normalized_session_id,
                )

                cls._record_evidence_event(
                    normalized_turn_id=normalized_turn_id,
                    normalized_area=normalized_area,
                    normalized_user_message=normalized_user_message,
                    normalized_student_id=normalized_student_id,
                    normalized_session_id=normalized_session_id,
                    semantic_evidence=semantic_evidence,
                    evidence_context=evidence_context,
                    state_before_evidence=state_before_evidence,
                    state_after=result["learner_state"],
                    applied=evidence_applied,
                    assistance_level=assistance_level,
                    artifact_ref=artifact_ref,
                )

            return result

    @classmethod
    def _record_evidence_event(
        cls,
        *,
        normalized_turn_id,
        normalized_area,
        normalized_user_message,
        normalized_student_id,
        normalized_session_id,
        semantic_evidence,
        evidence_context,
        state_before_evidence,
        state_after,
        applied,
        assistance_level,
        artifact_ref,
    ):
        if (
            not isinstance(semantic_evidence, dict)
            or not isinstance(evidence_context, dict)
        ):
            return None

        context_answer = LearningHistory.normalize_message(
            evidence_context.get("student_answer")
        )

        if context_answer != normalized_user_message:
            raise ValueError(
                "evidence_context não corresponde ao turno confirmado"
            )

        context_concept_id = evidence_context.get("concept_id")
        state_concept_id = state_before_evidence.get("current_concept_id")

        if not context_concept_id or context_concept_id != state_concept_id:
            raise ValueError(
                "evidence_context não corresponde ao conceito ativo"
            )

        return EvidenceEvent.record(
            turn_id=normalized_turn_id,
            area=normalized_area,
            concept_id=context_concept_id,
            stage_before=evidence_context.get("stage"),
            stage_after=state_after.get("stage"),
            semantic_evidence=semantic_evidence,
            tutor_message=evidence_context.get("tutor_message"),
            student_answer=context_answer,
            mastery_before=state_before_evidence.get("mastery"),
            mastery_after=state_after.get("mastery"),
            applied=applied,
            student_id=normalized_student_id,
            session_id=normalized_session_id,
            assistance_level=assistance_level,
            artifact_ref=artifact_ref,
        )

    @classmethod
    def finalize(
        cls,
        area,
        user_message,
        learner_state,
        semantic_evidence,
        student_id=DEFAULT_STUDENT_ID,
    ):
        with transaction():
            return cls._finalize(
                area,
                user_message,
                learner_state,
                semantic_evidence,
                student_id=student_id,
            )

    @classmethod
    def _finalize(
        cls,
        area,
        user_message,
        learner_state,
        semantic_evidence,
        student_id=DEFAULT_STUDENT_ID,
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
                student_id=student_id,
            )

            current_concept_id = learner_state.get("current_concept_id")

            if current_concept_id:
                concept_progress = ConceptProgress.update(
                    area,
                    current_concept_id,
                    mastery=learner_state.get("mastery"),
                    difficulty_count=learner_state.get(
                        "difficulty_count"
                    ),
                    last_evidence=learner_state.get(
                        "last_evidence"
                    ),
                    student_id=student_id,
                )

                if (
                    previous_stage == "reencontrar"
                    and semantic_evidence
                    and semantic_evidence.get("outcome")
                    == EvidenceEvaluator.DEMONSTRATED
                ):
                    review_result = ReviewLifecycle.complete_due(
                        area,
                        current_concept_id,
                        learner_state,
                        student_id=student_id,
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
                            current_concept_id,
                            **review_schedule,
                            student_id=student_id,
                        )

        signals = LearnerSignals.detect(user_message)

        if LearnerSignals.REVIEW_REQUEST in signals:
            due_review_state = ReviewLifecycle.activate_due(
                area,
                student_id=student_id,
            )

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
                student_id=student_id,
            )

        teaching_action = TeachingPolicy.choose_action(
            learner_state
        )

        return {
            "learner_state": learner_state,
            "teaching_action": teaching_action,
        }
