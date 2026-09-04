import hashlib

DEFAULT_STUDENT_ID = "student_default"
DEFAULT_SESSION_IDS = {
    "ads": "session_default_ads",
    "it": "session_default_it",
}


def normalize_student_id(student_id):
    if student_id is None:
        return DEFAULT_STUDENT_ID

    normalized = str(student_id).strip()
    return normalized or DEFAULT_STUDENT_ID


def default_session_id(area):
    normalized_area = str(area).strip().lower()
    return DEFAULT_SESSION_IDS.get(
        normalized_area,
        DEFAULT_SESSION_IDS["ads"],
    )


def session_id_for_student(student_id, area):
    normalized_student = normalize_student_id(student_id)
    normalized_area = str(area).strip().lower()

    if normalized_student == DEFAULT_STUDENT_ID:
        return default_session_id(normalized_area)

    digest = hashlib.sha256(
        normalized_student.encode("utf-8")
    ).hexdigest()[:16]

    return f"session_{digest}_{normalized_area}"
