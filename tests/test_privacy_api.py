import json

from backend.app import create_app
from backend.identity import DEFAULT_STUDENT_ID
from backend.services.access_control import AccessControl
from backend.services.data_lifecycle import DataLifecycle


def test_export_is_open_for_default_student_and_never_exposes_key_hash():
    AccessControl.ensure_student_runtime(DEFAULT_STUDENT_ID)

    app = create_app({'TESTING': True})
    client = app.test_client()

    response = client.get('/api/privacy/export')

    assert response.status_code == 200
    assert response.headers['Cache-Control'] == 'no-store'
    assert 'attachment' in response.headers['Content-Disposition']

    payload = json.loads(response.get_data(as_text=True))
    assert payload['student_id'] == DEFAULT_STUDENT_ID

    serialized = response.get_data(as_text=True)
    assert 'key_hash' not in serialized


def test_delete_requires_explicit_confirmation_without_password():
    AccessControl.ensure_student_runtime(DEFAULT_STUDENT_ID)

    app = create_app({'TESTING': True})
    client = app.test_client()

    response = client.delete(
        '/api/privacy/data',
        json={'confirmation': 'sim'},
    )

    assert response.status_code == 400
    assert response.get_json()['code'] == 'confirmation_required'


def test_delete_targets_default_student_and_next_request_recreates_runtime():
    AccessControl.ensure_student_runtime(DEFAULT_STUDENT_ID)

    app = create_app({'TESTING': True})
    client = app.test_client()

    response = client.delete(
        '/api/privacy/data',
        json={'confirmation': DataLifecycle.DELETE_CONFIRMATION},
    )

    assert response.status_code == 200
    assert response.get_json()['receipt_id'].startswith('privacy_')

    # O produto individual permanece utilizavel sem login: a proxima
    # requisicao recria apenas o runtime vazio do aluno padrao.
    after = client.get('/api/session?area=ads')
    assert after.status_code == 200
    assert after.get_json()['session']['status'] == 'studying'
