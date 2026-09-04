#!/usr/bin/env python3
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


CRITICAL_TEST_FILES = (
    "tests/test_e2e_learning_pipeline.py",
    "tests/test_e2e_session_resume_review.py",
    "tests/test_e2e_privacy_lifecycle.py",
    "tests/test_e2e_http_reliability.py",
    "tests/test_server_turn_serialization.py",
    "tests/test_stream_transaction.py",
    "tests/test_learning_turn_idempotency.py",
    "tests/test_database_migrations.py",
    "tests/test_security.py",
    "tests/test_session_api.py",
    "tests/test_privacy_api.py",
    "tests/test_chat_engine_stream_confirmation.py",
    "tests/test_session_ui.py",
)


def run(command, *, cwd, env=None, capture=False):
    kwargs = {
        "cwd": cwd,
        "env": env,
        "text": True,
        "check": False,
    }
    if capture:
        kwargs["stdout"] = subprocess.PIPE
        kwargs["stderr"] = subprocess.STDOUT

    result = subprocess.run(command, **kwargs)
    if result.returncode != 0:
        if capture and result.stdout:
            print(result.stdout, end="")
        raise RuntimeError(
            f"comando falhou ({result.returncode}): {' '.join(command)}"
        )
    return result


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Gate de Release Candidate do APEX. Usa apenas banco temporario "
            "e nao altera data/apex.db."
        )
    )
    parser.add_argument(
        "--root",
        default=str(Path(__file__).resolve().parents[1]),
    )
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="Permite working tree sujo; util apenas durante desenvolvimento.",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    validate = root / "tools" / "apex_validate.py"

    print("=== APEX RELEASE GATE ===")

    if not validate.is_file():
        raise RuntimeError("tools/apex_validate.py nao encontrado")

    if (root / ".git").exists() and not args.allow_dirty:
        status = run(
            ["git", "status", "--porcelain"],
            cwd=root,
            capture=True,
        ).stdout
        if status.strip():
            raise RuntimeError(
                "working tree precisa estar limpo para Release Candidate"
            )
        head = run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=root,
            capture=True,
        ).stdout.strip()
        print("Git HEAD:", head)

    print("\n[1/3] Suite completa")
    run([sys.executable, str(validate), "--root", str(root)], cwd=root)

    print("\n[2/3] Jornadas e falhas criticas")
    missing = [name for name in CRITICAL_TEST_FILES if not (root / name).is_file()]
    if missing:
        raise RuntimeError("testes criticos ausentes: " + ", ".join(missing))

    critical_data = Path(tempfile.mkdtemp(prefix="APEX_RELEASE_TESTS_"))
    env = os.environ.copy()
    env["APP_ENV"] = "test"
    env["APEX_DATA_DIR"] = str(critical_data)
    try:
        result = run(
            [sys.executable, "-m", "pytest", "-q", *CRITICAL_TEST_FILES],
            cwd=root,
            env=env,
            capture=True,
        )
        output = result.stdout or ""
        summaries = [
            line
            for line in output.splitlines()
            if " passed" in line or " failed" in line or " error" in line
        ]
        print(summaries[-1] if summaries else "critical pytest: OK")
    finally:
        shutil.rmtree(critical_data, ignore_errors=True)

    print("\n[3/3] Banco novo e cadeia completa de migrations")
    db_data = Path(tempfile.mkdtemp(prefix="APEX_RELEASE_DB_"))
    env = os.environ.copy()
    env["APP_ENV"] = "test"
    env["APEX_DATA_DIR"] = str(db_data)
    try:
        code = r'''
import sqlite3
from backend.config import DATABASE_PATH
from backend.database import init_database
from backend.migrations import MIGRATIONS

init_database()
connection = sqlite3.connect(str(DATABASE_PATH))
try:
    applied = connection.execute(
        "SELECT version, name FROM schema_migrations ORDER BY version"
    ).fetchall()
    expected = [(m.version, m.name) for m in MIGRATIONS]
    assert applied == expected, (applied, expected)
    assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert connection.execute(
        "SELECT COUNT(*) FROM privacy_deletion_authorizations"
    ).fetchone()[0] == 0
    print("schema_version =", expected[-1][0])
    print("migrations =", len(expected))
    print("foreign_key_check = 0")
    print("integrity_check = ok")
finally:
    connection.close()
'''
        run([sys.executable, "-c", code], cwd=root, env=env)
    finally:
        shutil.rmtree(db_data, ignore_errors=True)

    print("\nAPEX RELEASE GATE: OK")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"\nAPEX RELEASE GATE: FALHOU: {exc}")
        raise SystemExit(1)
