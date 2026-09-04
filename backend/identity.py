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
