import os
from pathlib import Path
import subprocess
import sys

from backend.app import create_app


def test_create_app_exposes_expected_routes_without_database_bootstrap():
    application = create_app({"TESTING": True})

    rules = {rule.rule for rule in application.url_map.iter_rules()}
    assert "/" in rules
    assert "/health" in rules
    assert "/chat/stream" in rules
    assert "/api/session" in rules

def test_import_backend_app_does_not_create_sqlite_database(tmp_path):
    isolated_data = tmp_path / "import-only"
    project_root = Path(__file__).resolve().parents[1]

    env = os.environ.copy()
    env["APP_ENV"] = "test"
    env["APEX_DATA_DIR"] = str(isolated_data)
    env.pop("PYTEST_CURRENT_TEST", None)

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import backend.app; "
                "print('import-ok')"
            ),
        ],
        cwd=project_root,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "import-ok" in result.stdout
    assert not (isolated_data / "apex.db").exists()


def test_pytest_bootstrap_never_points_to_project_database():
    from backend.config import DATABASE_PATH, PROJECT_ROOT

    project_database = (PROJECT_ROOT / "data" / "apex.db").resolve()
    assert Path(DATABASE_PATH).resolve() != project_database


def test_start_script_bootstraps_database_before_gunicorn():
    project_root = Path(__file__).resolve().parents[1]
    script = (project_root / "start_apex.sh").read_text()

    assert "init_database()" in script
    assert "exec gunicorn backend.app:app" in script
    assert script.index("init_database()") < script.index(
        "exec gunicorn backend.app:app"
    )


def test_security_headers_are_applied_to_http_responses():
    application = create_app({"TESTING": True})
    client = application.test_client()

    response = client.get("/")

    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert response.headers["Referrer-Policy"] == "no-referrer"
    assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
    assert "camera=()" in response.headers["Permissions-Policy"]


def test_start_script_bootstraps_access_control_after_database():
    project_root = Path(__file__).resolve().parents[1]
    script = (project_root / "start_apex.sh").read_text()

    assert "bootstrap_access_control()" in script
    assert script.index("init_database()") < script.index(
        "bootstrap_access_control()"
    ) < script.index("exec gunicorn backend.app:app")


def test_request_id_header_is_generated_for_each_response():
    application = create_app({"TESTING": True})
    client = application.test_client()

    first = client.get("/")
    second = client.get("/")

    first_id = first.headers.get("X-Apex-Request-ID")
    second_id = second.headers.get("X-Apex-Request-ID")

    assert first_id
    assert second_id
    assert first_id != second_id
    assert len(first_id) == 32
    assert len(second_id) == 32
