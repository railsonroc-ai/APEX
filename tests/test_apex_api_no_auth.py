from pathlib import Path


def test_frontend_has_no_access_key_prompt_or_header():
    source = Path(
        'backend/static/js/apex-api.js'
    ).read_text(encoding='utf-8')

    assert 'window.prompt' not in source
    assert 'Acesso protegido' not in source
    assert 'X-Apex-Key' not in source
    assert 'APEX_ACCESS_KEY' not in source
