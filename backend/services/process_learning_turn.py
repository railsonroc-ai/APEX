# APEX_GOAL_RESULT_FIX_V3_IMPORT
try:
    from backend.services.goal_result_evidence_policy import normalize_goal_result_evidence as _normalize_goal_result_evidence
except ImportError:
    from services.goal_result_evidence_policy import normalize_goal_result_evidence as _normalize_goal_result_evidence

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
from backend.services.assistance_event import AssistanceEvent
from backend.services.concept_progress import ConceptProgress
from backend.services.concept_tracker import ConceptTracker
from backend.services.evidence_evaluator import EvidenceEvaluator
from backend.services.evidence_event import EvidenceEvent
from backend.services.evidence_policy import EvidencePolicy
from backend.services.learner_signals import LearnerSignals
from backend.services.learner_state import LearnerState
from backend.services.learner_state_transition import LearnerStateTransition
from backend.services.learning_history import LearningHistory
from backend.services.learning_attempt import LearningAttempt
from backend.services.learning_task import LearningTask
from backend.services.learning_session_lifecycle import LearningSessionLifecycle
from backend.services.mastery_assessment import MasteryAssessment
from backend.services.mastery_policy import MasteryPolicy
from backend.services.review_lifecycle import ReviewLifecycle
from backend.services.rubric_assessment import RubricAssessment
from backend.services.review_scheduler import ReviewScheduler
from backend.services.teaching_policy import TeachingPolicy
from backend.services.task_policy import TaskPolicy
from backend.services.task_spec import TaskSpec


class ProcessLearningTurn:
    @classmethod
    def activate_identified_concept(
        cls,
        area,
        learner_state,
        identified_concept,
        student_id=DEFAULT_STUDENT_ID,
        restart=False,
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
            restart=restart,
        )

    @classmethod
    def preview_activation(
        cls,
        area,
        learner_state,
        identified_concept,
        student_id=DEFAULT_STUDENT_ID,
        restart=False,
    ):
        with preview_transaction():
            return cls.activate_identified_concept(
                area,
                learner_state,
                identified_concept,
                student_id=student_id,
                restart=restart,
            )

    @classmethod
    def preview_turn(
        cls,
        area,
        user_message,
        identified_concept,
        semantic_evidence,
        student_id=DEFAULT_STUDENT_ID,
        session_id=None,
        evidence_context=None,
        restart=False,
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
                restart=restart,
            )

            assistance_level = AssistanceEvent.resolve_for_evidence(
                area=area,
                evidence_context=evidence_context,
                student_id=student_id,
                session_id=session_id,
            )

            mastery_decision = cls._build_mastery_decision(
                area=area,
                learner_state=learner_state,
                semantic_evidence=semantic_evidence,
                student_id=student_id,
                assistance_level=assistance_level,
            )

            return cls._finalize(
                area,
                user_message,
                learner_state,
                semantic_evidence,
                student_id=student_id,
                session_id=session_id,
                evidence_context=evidence_context,
                mastery_decision=mastery_decision,
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
        teaching_action=None,
        artifact_ref=None,
        observed_assistance_level=None,
        task_prompt=None,
        restart=False,
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

            if isinstance(semantic_evidence, dict):
                if not normalized_turn_id:
                    raise ValueError(
                        "turn_id obrigatória para confirmar evidência"
                    )
                if not isinstance(evidence_context, dict):
                    raise ValueError(
                        "evidence_context obrigatória para confirmar evidência"
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
                restart=restart,
            )

            # APEX_GOAL_RESULT_FIX_V3_CALL
            semantic_evidence = _normalize_goal_result_evidence(
                semantic_evidence,
                task_prompt=task_prompt,
                evidence_context=evidence_context,
                user_message=normalized_user_message,
            )

            state_before_evidence = dict(learner_state)
            proposed_changes = LearnerStateTransition.propose_from_evidence(
                state_before_evidence,
                semantic_evidence,
            )
            evidence_applied = bool(proposed_changes)

            assistance_level = AssistanceEvent.resolve_for_evidence(
                area=normalized_area,
                evidence_context=evidence_context,
                student_id=normalized_student_id,
                session_id=normalized_session_id,
            )

            mastery_decision = cls._build_mastery_decision(
                area=normalized_area,
                learner_state=state_before_evidence,
                semantic_evidence=semantic_evidence,
                student_id=normalized_student_id,
                assistance_level=assistance_level,
                proposed_changes=proposed_changes,
            )

            result = cls._finalize(
                normalized_area,
                normalized_user_message,
                learner_state,
                semantic_evidence,
                student_id=normalized_student_id,
                session_id=normalized_session_id,
                evidence_context=evidence_context,
                mastery_decision=mastery_decision,
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

                learning_attempt = cls._record_learning_attempt(
                    normalized_turn_id=normalized_turn_id,
                    normalized_area=normalized_area,
                    normalized_user_message=normalized_user_message,
                    normalized_student_id=normalized_student_id,
                    normalized_session_id=normalized_session_id,
                    semantic_evidence=semantic_evidence,
                    evidence_context=evidence_context,
                    assistance_level=assistance_level,
                    artifact_ref=artifact_ref,
                )

                evidence_event = cls._record_evidence_event(
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
                    source=(
                        semantic_evidence.get("source")
                        if isinstance(semantic_evidence, dict)
                        else None
                    )
                    or EvidencePolicy.SOURCE_SEMANTIC_LLM,
                )

                if evidence_event is not None and learning_attempt is not None:
                    RubricAssessment.record(
                        turn_id=normalized_turn_id,
                        attempt_id=learning_attempt["attempt_id"],
                        evidence_event_id=evidence_event["event_id"],
                        area=normalized_area,
                        concept_id=evidence_event["concept_id"],
                        semantic_evidence=semantic_evidence,
                        student_id=normalized_student_id,
                        session_id=normalized_session_id,
                    )

                if evidence_event is not None and mastery_decision is not None:
                    MasteryAssessment.record(
                        turn_id=normalized_turn_id,
                        evidence_event_id=evidence_event["event_id"],
                        area=normalized_area,
                        concept=evidence_event["concept_id"],
                        decision=mastery_decision,
                        student_id=normalized_student_id,
                        session_id=normalized_session_id,
                    )

                effective_action = result["teaching_action"]
                if teaching_action is not None and teaching_action != effective_action:
                    raise ValueError(
                        "teaching_action não corresponde à decisão confirmada"
                    )

                AssistanceEvent.record(
                    turn_id=normalized_turn_id,
                    area=normalized_area,
                    concept_id=result["learner_state"].get("current_concept_id"),
                    teaching_action=effective_action,
                    student_id=normalized_student_id,
                    session_id=normalized_session_id,
                    observed_level=observed_assistance_level,
                )

                active_concept_id = result["learner_state"].get(
                    "current_concept_id"
                )
                if (
                    active_concept_id
                    and TaskPolicy.is_assessable_action(effective_action)
                ):
                    # O adaptador HTTP sempre fornece somente a tarefa validada.
                    # O fallback mantém compatibilidade com chamadas internas
                    # antigas que tratavam a resposta inteira como tarefa.
                    extracted_task = (
                        task_prompt
                        or TaskSpec.extract(normalized_assistant_message)
                        or normalized_assistant_message
                    )
                    learning_task = LearningTask.record(
                        source_turn_id=normalized_turn_id,
                        area=normalized_area,
                        concept_id=active_concept_id,
                        stage=result["learner_state"].get("stage"),
                        teaching_action=effective_action,
                        prompt_text=extracted_task,
                        student_id=normalized_student_id,
                        session_id=normalized_session_id,
                        assistance_level=observed_assistance_level,
                    )
                    if learning_task is not None:
                        LearningSessionLifecycle.bind_review_task(
                            learning_task["task_id"],
                            normalized_area,
                            student_id=normalized_student_id,
                            session_id=normalized_session_id,
                        )

            return result

    @classmethod
    def _build_mastery_decision(
        cls,
        *,
        area,
        learner_state,
        semantic_evidence,
        student_id,
        assistance_level,
        proposed_changes=None,
    ):
        if not isinstance(semantic_evidence, dict):
            return None
        if not isinstance(learner_state, dict):
            return None

        concept_id = learner_state.get("current_concept_id")
        if not concept_id:
            return None

        if proposed_changes is None:
            proposed_changes = LearnerStateTransition.propose_from_evidence(
                learner_state,
                semantic_evidence,
            )

        mastery_score = proposed_changes.get(
            "mastery",
            learner_state.get("mastery", 0.0),
        )

        return MasteryPolicy.evaluate(
            area=area,
            concept=concept_id,
            stage_before=learner_state.get("stage"),
            semantic_evidence=semantic_evidence,
            mastery_score=mastery_score,
            current_applied=bool(proposed_changes),
            student_id=student_id,
            assistance_level=assistance_level,
        )

    @classmethod
    def _record_learning_attempt(
        cls,
        *,
        normalized_turn_id,
        normalized_area,
        normalized_user_message,
        normalized_student_id,
        normalized_session_id,
        semantic_evidence,
        evidence_context,
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

        return LearningAttempt.record(
            turn_id=normalized_turn_id,
            area=normalized_area,
            concept_id=evidence_context.get("concept_id"),
            stage=evidence_context.get("stage"),
            student_answer=context_answer,
            student_id=normalized_student_id,
            session_id=normalized_session_id,
            source_turn_id=evidence_context.get("source_turn_id"),
            task_id=evidence_context.get("task_id"),
            assistance_level=assistance_level,
            artifact_ref=artifact_ref,
        )

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
        source,
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

        context_stage = evidence_context.get("stage")
        state_stage = state_before_evidence.get("stage")
        if context_stage != state_stage:
            raise ValueError(
                "evidence_context não corresponde à etapa ativa"
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
            source=source,
        )

    @classmethod
    def finalize(
        cls,
        area,
        user_message,
        learner_state,
        semantic_evidence,
        student_id=DEFAULT_STUDENT_ID,
        session_id=None,
        evidence_context=None,
        mastery_decision=None,
    ):
        with transaction():
            return cls._finalize(
                area,
                user_message,
                learner_state,
                semantic_evidence,
                student_id=student_id,
                session_id=session_id,
                evidence_context=evidence_context,
                mastery_decision=mastery_decision,
            )

    @classmethod
    def _finalize(
        cls,
        area,
        user_message,
        learner_state,
        semantic_evidence,
        student_id=DEFAULT_STUDENT_ID,
        session_id=None,
        evidence_context=None,
        mastery_decision=None,
    ):
        if mastery_decision is None:
            evidence_changes = LearnerStateTransition.from_evidence(
                learner_state,
                semantic_evidence,
            )
        else:
            evidence_changes = LearnerStateTransition.from_evidence(
                learner_state,
                semantic_evidence,
                mastery_decision=mastery_decision,
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

                resume_review_result = None
                if session_id:
                    resume_review_result = (
                        LearningSessionLifecycle.complete_resume_review(
                            area,
                            learner_state,
                            semantic_evidence,
                            evidence_applied=bool(evidence_changes),
                            task_id=(
                                evidence_context.get("task_id")
                                if isinstance(evidence_context, dict)
                                else None
                            ),
                            student_id=student_id,
                            session_id=session_id,
                        )
                    )

                if resume_review_result:
                    learner_state = resume_review_result["learner_state"]

                elif (
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
