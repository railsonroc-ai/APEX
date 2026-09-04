#!/usr/bin/env python3
import argparse
from datetime import datetime
import hashlib
import os
import re
import unicodedata
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tarfile
import tempfile


MANIFEST_NAME = "APEX_UPDATE_MANIFEST.txt"


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


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()



def _fold_text(value):
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(ch for ch in normalized if not unicodedata.combining(ch)).lower()


def read_update_manifest(archive):
    try:
        member = archive.getmember(MANIFEST_NAME)
    except KeyError as exc:
        raise RuntimeError(
            f"pacote sem manifesto canonico {MANIFEST_NAME}"
        ) from exc

    source = archive.extractfile(member)
    if source is None:
        raise RuntimeError("manifesto canonico nao pode ser lido")
    return source.read().decode("utf-8")


def parse_manifest_files(text):
    lines = str(text or "").splitlines()
    files = []
    in_files = False

    for raw in lines:
        line = raw.strip()
        folded = _fold_text(line)

        if folded == "arquivos:":
            in_files = True
            continue

        if not in_files:
            continue

        if not line:
            if files:
                break
            continue

        if line.startswith("- "):
            files.append(line[2:].strip())
            continue

        if files:
            break

    return files


def manifest_requires_migration(text):
    for raw in str(text or "").splitlines():
        line = raw.strip()
        folded = _fold_text(line)

        if folded.startswith("migration nova:"):
            value = folded.split(":", 1)[1].strip()
            if value in {"nao", "nenhuma", "none", "false"}:
                return False
            return bool(value)

        if folded.startswith("migration de banco:"):
            value = folded.split(":", 1)[1].strip()
            if value.startswith("nenhuma") or "sem migration" in value:
                return False
            if value:
                return True

        if "sem migration nova" in folded:
            return False

    return None


def validate_update_manifest(archive, members):
    rogue_manifests = [
        member.name
        for member in members
        if member.name != MANIFEST_NAME
        and member.name.upper().endswith("_MANIFEST.TXT")
    ]
    if rogue_manifests:
        raise RuntimeError(
            "manifesto fora do nome canonico: "
            + ", ".join(sorted(rogue_manifests))
        )

    text = read_update_manifest(archive)
    listed = parse_manifest_files(text)
    if not listed:
        raise RuntimeError(
            "manifesto deve declarar a secao 'Arquivos:' com lista '- caminho'"
        )

    actual = {
        member.name
        for member in members
        if member.name != MANIFEST_NAME
    }
    declared = set(listed)

    if len(listed) != len(declared):
        raise RuntimeError("manifesto contem arquivos duplicados")

    if declared != actual:
        missing = sorted(declared - actual)
        extra = sorted(actual - declared)
        raise RuntimeError(
            "conteudo do pacote diverge do manifesto; "
            f"ausentes={missing}; extras={extra}"
        )

    declared_count = None
    for raw in text.splitlines():
        match = re.match(
            r"^\s*Arquivos de projeto\s*:\s*(\d+)\s*$",
            raw,
            flags=re.IGNORECASE,
        )
        if match:
            declared_count = int(match.group(1))
            break

    if declared_count is not None and declared_count != len(actual):
        raise RuntimeError(
            f"manifesto declara {declared_count} arquivos, pacote contem {len(actual)}"
        )

    return {
        "text": text,
        "files": tuple(listed),
        "requires_migration": manifest_requires_migration(text),
    }

def safe_members(archive):
    members = []
    for member in archive.getmembers():
        name = member.name
        path = Path(name)
        if (
            path.is_absolute()
            or ".." in path.parts
            or member.issym()
            or member.islnk()
        ):
            raise RuntimeError(f"entrada insegura no pacote: {name}")
        if member.isdir():
            continue
        if not member.isfile():
            raise RuntimeError(f"tipo de entrada não suportado: {name}")
        members.append(member)
    return members


def sqlite_backup(source, destination):
    destination.parent.mkdir(parents=True, exist_ok=True)
    src = sqlite3.connect(str(source))
    dst = sqlite3.connect(str(destination))
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()


def checkpoint_database(db_path):
    if not db_path.exists():
        return

    connection = sqlite3.connect(str(db_path))
    try:
        integrity = connection.execute(
            "PRAGMA integrity_check"
        ).fetchone()[0]
        if integrity != "ok":
            raise RuntimeError(
                f"integrity_check antes da atualização: {integrity}"
            )

        checkpoint = connection.execute(
            "PRAGMA wal_checkpoint(TRUNCATE)"
        ).fetchone()
        if checkpoint[0] != 0:
            raise RuntimeError(
                "WAL ocupado. Pare o Flask/Gunicorn antes de aplicar o pacote."
            )
    finally:
        connection.close()

    wal = Path(str(db_path) + "-wal")
    shm = Path(str(db_path) + "-shm")
    if wal.exists():
        if wal.stat().st_size != 0:
            raise RuntimeError(
                f"WAL permaneceu com {wal.stat().st_size} bytes"
            )
        wal.unlink()
    if shm.exists():
        shm.unlink()


def main():
    parser = argparse.ArgumentParser(
        description=(
            "Aplica pacote APEX com staging, backup e testes. "
            "Não migra o banco real e não faz commit."
        )
    )
    parser.add_argument("package")
    parser.add_argument("sha256")
    parser.add_argument("expected_head")
    args = parser.parse_args()

    root = Path.cwd().resolve()
    package = Path(args.package).resolve()

    if not (root / ".git").exists():
        raise SystemExit("Execute dentro do repositório Git do APEX.")
    if not package.is_file():
        raise SystemExit(f"Pacote não encontrado: {package}")

    real_db = root / "data" / "apex.db"
    checkpoint_database(real_db)

    head = run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=root,
        capture=True,
    ).stdout.strip()
    if head != args.expected_head:
        raise SystemExit(
            f"HEAD inesperado: {head}; esperado: {args.expected_head}"
        )

    status = run(
        ["git", "status", "--porcelain"],
        cwd=root,
        capture=True,
    ).stdout
    if status.strip():
        raise SystemExit(
            "Working tree não está limpo. Não apliquei o pacote.\n" + status
        )

    actual_sha = sha256(package)
    if actual_sha != args.sha256.lower():
        raise SystemExit(
            f"SHA-256 divergente: {actual_sha}"
        )

    with tarfile.open(package, "r:gz") as archive:
        members = safe_members(archive)
        manifest = validate_update_manifest(archive, members)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = Path("/public") / f"APEX_BACKUP_{head}_{stamp}"
    if not backup_dir.parent.exists():
        backup_dir = root.parent / f"APEX_BACKUP_{head}_{stamp}"
    backup_dir.mkdir(parents=True, exist_ok=False)

    code_backup = backup_dir / f"APEX_CODE_{head}.tar.gz"
    run(
        [
            "git",
            "archive",
            "--format=tar.gz",
            f"--output={code_backup}",
            "HEAD",
        ],
        cwd=root,
    )

    db_backup = backup_dir / "apex.db.before_update"
    if real_db.exists():
        sqlite_backup(real_db, db_backup)

    stage_parent = Path("/public") if Path("/public").exists() else root.parent
    stage = Path(tempfile.mkdtemp(prefix="APEX_UPDATE_STAGE_", dir=stage_parent))

    try:
        base_tar = stage / "base.tar"
        run(
            ["git", "archive", "--format=tar", f"--output={base_tar}", "HEAD"],
            cwd=root,
        )
        with tarfile.open(base_tar, "r:") as archive:
            archive.extractall(stage)
        base_tar.unlink()

        with tarfile.open(package, "r:gz") as archive:
            for member in members:
                if member.name == MANIFEST_NAME:
                    continue
                archive.extract(member, stage)

        if real_db.exists():
            stage_db = stage / "data" / "apex.db"
            sqlite_backup(db_backup, stage_db)

            env = os.environ.copy()
            env["APP_ENV"] = "test"
            env["APEX_DATA_DIR"] = str(stage / "data")
            run(
                [
                    sys.executable,
                    "-c",
                    (
                        "from backend.database import init_database; "
                        "init_database(); "
                        "import sqlite3; "
                        "from backend.config import DATABASE_PATH; "
                        "c=sqlite3.connect(str(DATABASE_PATH)); "
                        "assert c.execute('PRAGMA foreign_key_check').fetchall()==[]; "
                        "assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'; "
                        "c.close(); print('STAGE DATABASE: OK')"
                    ),
                ],
                cwd=stage,
                env=env,
            )

        run(
            [sys.executable, "tools/apex_validate.py", "--root", str(stage)],
            cwd=stage,
        )

        for member in members:
            if member.name == MANIFEST_NAME:
                continue
            source = stage / member.name
            target = root / member.name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)

        run(
            [sys.executable, "tools/apex_validate.py", "--root", str(root)],
            cwd=root,
        )
        run(["git", "diff", "--check"], cwd=root)

        print("\nAPEX UPDATE: APLICADA E VALIDADA")
        print("Backup:", backup_dir)

        if manifest["requires_migration"] is False:
            print("Banco real: SEM MIGRAÇÃO NOVA")
            print("Próxima ação: python3 tools/apex_validate.py")
            print("Não execute tools/apex_migrate_real.py para este pacote.")
            print("Não faça commit antes da validação no repositório real.")
        else:
            print("Banco real: NÃO MIGRADO")
            print("Próxima ação: python3 tools/apex_migrate_real.py")
            print("Não faça commit antes da migração real.")
    finally:
        shutil.rmtree(stage, ignore_errors=True)


if __name__ == "__main__":
    main()
