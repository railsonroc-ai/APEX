from flask import g, has_request_context

from backend.identity import (
    DEFAULT_STUDENT_ID,
    default_session_id,
    session_id_for_student,
)
from backend.services.learner_state import LearnerState


class StudentContext:
    """
    Resolve a identidade pedagógica no servidor.

    O APEX individual atual possui um único aluno padrão. O
    navegador não escolhe student_id. Quando autenticação
    individual existir, esta fronteira poderá resolver o aluno
    autenticado sem alterar o Learning Kernel.
    """

    @classmethod
    def resolve(cls, area="ads"):
        normalized_area = LearnerState.normalize_area(area)

        student_id = DEFAULT_STUDENT_ID
        if has_request_context():
            student_id = getattr(
                g,
                "apex_student_id",
                DEFAULT_STUDENT_ID,
            )

        return {
            "student_id": student_id,
            "session_id": session_id_for_student(
                student_id,
                normalized_area,
            ),
            "area": normalized_area,
        }
