from uuid import uuid4

from backend.database import get_db_connection
from backend.identity import DEFAULT_STUDENT_ID, default_session_id, normalize_student_id
from backend.services.assistance_policy import AssistancePolicy
from backend.services.concept_catalog import ConceptCatalog
from backend.services.evidence_policy import EvidencePolicy
from backend.services.learning_history import LearningHistory


class AssistanceEvent:
    """Ledger imutável da assistência fornecida por cada turno confirmado."""

    @classmethod
    def record(
        cls,
        *,
        turn_id,
        area,
        teaching_action,
        concept=None,
        concept_id=None,
        student_id=DEFAULT_STUDENT_ID,
        session_id=None,
        observed_level=None,
    ):
        normalized_student_id = normalize_student_id(student_id)
        normalized_area = LearningHistory.normalize_area(area)
        normalized_turn_id = LearningHistory.normalize_turn_id(turn_id)
        normalized_session_id = LearningHistory.normalize_session_id(session_id)
        normalized_action = AssistancePolicy.normalize_teaching_action(teaching_action)

        if not normalized_session_id and normalized_student_id == DEFAULT_STUDENT_ID:
            normalized_session_id = default_session_id(normalized_area)
        if not normalized_turn_id:
            raise ValueError("turn_id obrigatório para AssistanceEvent")
        if not normalized_session_id:
            raise ValueError("session_id obrigatória para AssistanceEvent")
        if not normalized_action:
            raise ValueError("teaching_action inválida para AssistanceEvent")

        requested = concept_id if concept_id is not None else concept
        definition = None
        if requested is not None:
            definition = ConceptCatalog.resolve(normalized_area, requested)
            if definition is None:
                raise ValueError("conceito não pertence ao catálogo")

        turn = LearningHistory.find(
            normalized_turn_id,
            student_id=normalized_student_id,
        )
        if turn is None:
            raise ValueError("turno confirmado não encontrado")
        if turn.get("area") != normalized_area:
            raise ValueError("área não corresponde ao turno confirmado")
        if turn.get("session_id") != normalized_session_id:
            raise ValueError("sessão não corresponde ao turno confirmado")
        turn_concept_id = turn.get("concept_id")
        resolved_concept_id = definition.get("concept_id") if definition else None
        if turn_concept_id != resolved_concept_id:
            raise ValueError("conceito não corresponde ao turno confirmado")
        if not turn.get("assistant_message"):
            raise ValueError("turno sem resposta do tutor")

        assistance_id = uuid4().hex
        assistance_level = (
            AssistancePolicy.level_for_action(normalized_action)
            if observed_level is None
            else AssistancePolicy.validate_observed_level(
                normalized_action,
                observed_level,
            )
        )

        connection = get_db_connection()
        try:
            connection.execute(
                """
                INSERT INTO assistance_events (
                    assistance_id,
                    student_id,
                    session_id,
                    turn_id,
                    area,
                    concept_id,
                    teaching_action,
                    assistance_level,
                    policy_id,
                    policy_version
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    assistance_id,
                    normalized_student_id,
                    normalized_session_id,
                    normalized_turn_id,
                    normalized_area,
                    resolved_concept_id,
                    normalized_action,
                    assistance_level,
                    AssistancePolicy.POLICY_ID,
                    AssistancePolicy.POLICY_VERSION,
                ),
            )
            connection.commit()
        finally:
            connection.close()

        return cls.for_turn(
            normalized_turn_id,
            student_id=normalized_student_id,
        )

    @staticmethod
    def _row_to_dict(row):
        return dict(row) if row is not None else None

    @classmethod
    def for_turn(cls, turn_id, student_id=DEFAULT_STUDENT_ID):
        normalized_turn_id = LearningHistory.normalize_turn_id(turn_id)
        normalized_student_id = normalize_student_id(student_id)
        if not normalized_turn_id:
            return None

        connection = get_db_connection()
        try:
            row = connection.execute(
                """
                SELECT
                    assistance.*,
                    definition.canonical_name AS concept
                FROM assistance_events AS assistance
                LEFT JOIN concept_definitions AS definition
                  ON definition.area = assistance.area
                 AND definition.concept_id = assistance.concept_id
                WHERE assistance.student_id = ?
                  AND assistance.turn_id = ?
                """,
                (normalized_student_id, normalized_turn_id),
            ).fetchone()
            return cls._row_to_dict(row)
        finally:
            connection.close()

    @classmethod
    def resolve_for_evidence(
        cls,
        *,
        area,
        evidence_context,
        student_id=DEFAULT_STUDENT_ID,
        session_id=None,
    ):
        """Retorna a ajuda do tutor que originou a resposta atual do aluno.

        A associação usa a mensagem de tutor do ``evidence_context`` e exige o
        mesmo aluno, sessão, área e conceito. Turnos anteriores à migration v9
        não possuem ledger e permanecem honestamente ``untracked``.
        """

        if not isinstance(evidence_context, dict):
            return EvidencePolicy.ASSISTANCE_UNTRACKED

        normalized_student_id = normalize_student_id(student_id)
        normalized_area = LearningHistory.normalize_area(area)
        normalized_session_id = LearningHistory.normalize_session_id(session_id)
        if not normalized_session_id and normalized_student_id == DEFAULT_STUDENT_ID:
            normalized_session_id = default_session_id(normalized_area)
        if not normalized_session_id:
            return EvidencePolicy.ASSISTANCE_UNTRACKED

        tutor_message = LearningHistory.normalize_message(evidence_context.get("tutor_message"))
        source_turn_id = LearningHistory.normalize_turn_id(
            evidence_context.get("source_turn_id")
        )
        requested_concept = evidence_context.get("concept_id")
        definition = ConceptCatalog.resolve(normalized_area, requested_concept)
        if definition is None or (not source_turn_id and not tutor_message):
            return EvidencePolicy.ASSISTANCE_UNTRACKED

        connection = get_db_connection()
        try:
            params = [
                normalized_student_id,
                normalized_session_id,
                normalized_area,
                definition["concept_id"],
            ]
            message_filter = ""
            turn_filter = ""
            if source_turn_id:
                turn_filter = " AND turns.turn_id = ?"
                params.append(source_turn_id)
            else:
                message_filter = (
                    " AND SUBSTR(TRIM(turns.assistant_message), 1, "
                    f"{LearningHistory.MAX_CONTENT_CHARS}) = ?"
                )
                params.append(tutor_message)

            row = connection.execute(
                f"""
                SELECT assistance.assistance_level
                FROM learning_turns AS turns
                JOIN assistance_events AS assistance
                  ON assistance.student_id = turns.student_id
                 AND assistance.turn_id = turns.turn_id
                WHERE turns.student_id = ?
                  AND turns.session_id = ?
                  AND turns.area = ?
                  AND turns.concept_id = ?
                  {message_filter}
                  {turn_filter}
                ORDER BY turns.id DESC
                LIMIT 1
                """,
                tuple(params),
            ).fetchone()
        finally:
            connection.close()

        if row is None:
            return EvidencePolicy.ASSISTANCE_UNTRACKED
        return EvidencePolicy.normalize_assistance_level(
            row["assistance_level"]
        )
