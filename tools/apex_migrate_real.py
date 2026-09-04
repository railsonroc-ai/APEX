#!/usr/bin/env python3
from datetime import datetime
import os
from pathlib import Path
import sqlite3
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
DB = ROOT / "data" / "apex.db"


def sqlite_backup(source, destination):
    src = sqlite3.connect(str(source))
    dst = sqlite3.connect(str(destination))
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()


def main():
    if not DB.exists():
        raise SystemExit(f"Banco real não encontrado: {DB}")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    parent = Path("/public") if Path("/public").exists() else ROOT.parent
    backup_dir = parent / f"APEX_DB_BEFORE_MIGRATION_{stamp}"
    backup_dir.mkdir(parents=True, exist_ok=False)
    backup_db = backup_dir / "apex.db.before_migration"
    sqlite_backup(DB, backup_db)

    os.environ["APEX_DATA_DIR"] = str(ROOT / "data")
    os.environ.setdefault("APP_ENV", "test")

    from backend.database import init_database

    init_database()

    connection = sqlite3.connect(str(DB))
    try:
        versions = connection.execute(
            "SELECT version, name FROM schema_migrations ORDER BY version"
        ).fetchall()
        fk = connection.execute("PRAGMA foreign_key_check").fetchall()
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        checkpoint = connection.execute(
            "PRAGMA wal_checkpoint(TRUNCATE)"
        ).fetchone()
    finally:
        connection.close()

    if fk:
        raise RuntimeError(f"foreign_key_check falhou: {fk}")
    if integrity != "ok":
        raise RuntimeError(f"integrity_check falhou: {integrity}")
    if checkpoint[0] != 0:
        raise RuntimeError(f"wal_checkpoint ocupado: {checkpoint}")

    wal = Path(str(DB) + "-wal")
    shm = Path(str(DB) + "-shm")
    if wal.exists():
        if wal.stat().st_size != 0:
            raise RuntimeError(f"WAL permaneceu com {wal.stat().st_size} bytes")
        wal.unlink()
    if shm.exists():
        shm.unlink()

    print("=== APEX DATABASE MIGRATION ===")
    for version, name in versions:
        print(version, name)
    print("foreign_key_check = 0")
    print("integrity_check = ok")
    print("wal_checkpoint =", checkpoint)
    print("Backup:", backup_dir)
    print("APEX DATABASE MIGRATION: OK")


if __name__ == "__main__":
    main()
