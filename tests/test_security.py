from flask import Flask, g

import backend.security as security
from backend.identity import DEFAULT_STUDENT_ID


def create_test_app():
    return Flask(__name__)


def test_single_user_mode_allows_request_without_credentials():
    app = create_test_app()

    with app.test_request_context('/'):
        assert security.verify_auth() is True
        assert g.apex_student_id == DEFAULT_STUDENT_ID
        assert g.apex_credential_id == 'single-user-open'
        assert g.apex_auth_source == 'single-user-open'
        assert g.apex_rate_limited is False


def test_access_key_header_is_not_required_or_interpreted():
    app = create_test_app()

    with app.test_request_context(
        '/',
        headers={'X-Apex-Key': 'qualquer-valor'},
    ):
        assert security.verify_auth() is True
        assert g.apex_student_id == DEFAULT_STUDENT_ID
        assert g.apex_credential_id == 'single-user-open'


def test_bootstrap_prepares_default_student_without_credential():
    assert security.bootstrap_access_control() == DEFAULT_STUDENT_ID
