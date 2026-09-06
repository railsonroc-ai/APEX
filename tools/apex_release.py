#!/usr/bin/env python3
"""Release transacional do APEX após o pacote já estar em /public.

Automatiza o fluxo operacional pós-transferência:
- valida contrato do pacote e base Git;
- para o Gunicorn;
- aplica o pacote pelo updater com staging;
- aplica migration real apenas quando declarada;
- exige probe pedagógico com FAIL=0 e WARN=0;
- limita o commit aos arquivos declarados no manifesto;
- cria commit, faz push, reinicia o APEX e valida /health.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import apex_apply_update


DEFAULT_PORT = 5000
DEFAULT_COMMIT_MESSAGE = "chore: aplica atualização validada do APEX"


def run(command, *, cwd, capture=False, check=True):
    kwargs = {
        "cwd": cwd,
        "text": True,
        "check": False,
    }
    if capture:
        kwargs["stdout"] = subprocess.PIPE
        kwargs["stderr"] = subprocess.STDOUT
    result = subprocess.run(command, **kwargs)
    if check and result.returncode != 0:
        if capture and result.stdout:
            print(result.stdout, end="")
        raise RuntimeError(
            f"comando falhou ({result.returncode}): {' '.join(command)}"
        )
    return result


def parse_release_metadata(manifest_text):
    text = str(manifest_text or "")
    base = re.search(
        r"^\s*Base commit esperado\s*:\s*([^\s]+)\s*$",
        text,
        flags=re.IGNORECASE | re.MULTILINE,
    )
    if base is None:
        raise RuntimeError("manifesto sem 'Base commit esperado'")

    commit = re.search(
        r"^\s*(?:Commit sugerido|Commit)\s*:\s*(.+?)\s*$",
        text,
        flags=re.IGNORECASE | re.MULTILINE,
    )
    commit_message = commit.group(1).strip() if commit else DEFAULT_COMMIT_MESSAGE
    if not commit_message:
        commit_message = DEFAULT_COMMIT_MESSAGE

    return {
        "expected_head": base.group(1).strip(),
        "commit_message": commit_message,
    }


def read_package_contract(package):
    with tarfile.open(package, "r:gz") as archive:
        members = apex_apply_update.safe_members(archive)
        manifest = apex_apply_update.validate_update_manifest(archive, members)
    metadata = parse_release_metadata(manifest["text"])
    migration = manifest["requires_migration"]
    if migration is None:
        raise RuntimeError("manifesto precisa declarar explicitamente se há migration nova")
    return {
        **manifest,
        **metadata,
        "requires_migration": bool(migration),
    }


def ensure_clean_probe(output):
    return apex_apply_update.ensure_clean_pedagogical_probe(output)


def status_paths(status_text):
    paths = set()
    for raw in str(status_text or "").splitlines():
        if not raw.strip():
            continue
        payload = raw[3:] if len(raw) >= 4 else raw.strip()
        if " -> " in payload:
            payload = payload.split(" -> ", 1)[1]
        paths.add(payload.strip().strip('"'))
    return paths


def assert_only_manifest_changes(root, manifest_files):
    status = run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=root,
        capture=True,
    ).stdout
    changed = status_paths(status)
    allowed = set(manifest_files)
    unexpected = sorted(changed - allowed)
    if unexpected:
        raise RuntimeError(
            "working tree contém alterações fora do pacote: " + ", ".join(unexpected)
        )
    if not changed:
        raise RuntimeError("pacote não produziu alterações versionáveis")
    return changed


def tracked_in_head(root, path):
    result = run(
        ["git", "cat-file", "-e", f"HEAD:{path}"],
        cwd=root,
        capture=True,
        check=False,
    )
    return result.returncode == 0


def restore_manifest_files(root, manifest_files):
    for relative in manifest_files:
        target = root / relative
        if tracked_in_head(root, relative):
            run(
                ["git", "restore", "--source=HEAD", "--staged", "--worktree", "--", relative],
                cwd=root,
                check=False,
            )
        elif target.is_dir():
            shutil.rmtree(target, ignore_errors=True)
        elif target.exists():
            target.unlink()


def stop_gunicorn():
    pkill = shutil.which("pkill")
    pgrep = shutil.which("pgrep")
    if not pkill:
        return
    subprocess.run([pkill, "-TERM", "-x", "gunicorn"], check=False)
    if not pgrep:
        time.sleep(1.0)
        return
    deadline = time.time() + 6.0
    while time.time() < deadline:
        result = subprocess.run(
            [pgrep, "-x", "gunicorn"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        if result.returncode != 0:
            return
        time.sleep(0.2)
    subprocess.run([pkill, "-KILL", "-x", "gunicorn"], check=False)


def health_payload(port=DEFAULT_PORT, timeout=1.5):
    with urllib.request.urlopen(
        f"http://127.0.0.1:{port}/health",
        timeout=timeout,
    ) as response:
        if response.status != 200:
            raise RuntimeError(f"/health respondeu HTTP {response.status}")
        return json.loads(response.read().decode("utf-8"))


def wait_for_health(port=DEFAULT_PORT, timeout=30.0):
    deadline = time.time() + timeout
    last_error = None
    while time.time() < deadline:
        try:
            payload = health_payload(port=port)
            if payload.get("ok") is True and payload.get("database") == "ok":
                return payload
            last_error = RuntimeError(f"payload inesperado: {payload}")
        except Exception as exc:  # serviço ainda subindo
            last_error = exc
        time.sleep(0.5)
    raise RuntimeError(f"APEX não ficou saudável: {last_error}")


def start_apex_detached(root, port=DEFAULT_PORT):
    logs = root / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    log_path = logs / "release_start.log"
    stream = log_path.open("a", encoding="utf-8")
    try:
        subprocess.Popen(
            ["bash", "./start_apex.sh"],
            cwd=root,
            stdout=stream,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    finally:
        stream.close()
    return wait_for_health(port=port)


def push_with_retry(root, attempts=3):
    branch = run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=root,
        capture=True,
    ).stdout.strip()
    if not branch or branch == "HEAD":
        raise RuntimeError("release exige branch Git ativa")

    last = None
    for attempt in range(1, attempts + 1):
        result = run(
            ["git", "push", "origin", branch],
            cwd=root,
            capture=True,
            check=False,
        )
        if result.stdout:
            print(result.stdout, end="")
        if result.returncode == 0:
            return branch
        last = result.returncode
        if attempt < attempts:
            time.sleep(2.0)
    raise RuntimeError(f"git push falhou após {attempts} tentativas (rc={last})")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Aplica, valida, migra, commita, publica e reinicia uma atualização APEX."
    )
    parser.add_argument("package")
    parser.add_argument("sha256")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args(argv)

    root = ROOT
    package = Path(args.package).expanduser().resolve()
    if not package.is_file():
        raise SystemExit(f"Pacote não encontrado: {package}")
    if not (root / ".git").exists():
        raise SystemExit("Repositório Git do APEX não encontrado")

    actual_sha = apex_apply_update.sha256(package)
    if actual_sha != args.sha256.strip().lower():
        raise SystemExit(f"SHA-256 divergente: {actual_sha}")

    contract = read_package_contract(package)
    head = run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=root,
        capture=True,
    ).stdout.strip()
    if head != contract["expected_head"]:
        raise SystemExit(
            f"HEAD inesperado: {head}; esperado pelo pacote: {contract['expected_head']}"
        )

    initial_status = run(
        ["git", "status", "--porcelain"],
        cwd=root,
        capture=True,
    ).stdout
    if initial_status.strip():
        raise SystemExit("Working tree precisa estar limpo antes do release")

    print("=== APEX AUTOMATED RELEASE ===")
    print("Base:", head)
    print("Migration:", "SIM" if contract["requires_migration"] else "NÃO")
    print("Arquivos:", len(contract["files"]))

    stopped = False
    applied = False
    try:
        print("\n[1/7] Parando APEX")
        stop_gunicorn()
        stopped = True

        print("\n[2/7] Staging + suíte + probe + aplicação")
        run(
            [
                sys.executable,
                "tools/apex_apply_update.py",
                str(package),
                actual_sha,
                contract["expected_head"],
            ],
            cwd=root,
        )
        applied = True

        print("\n[3/7] Banco real")
        if contract["requires_migration"]:
            run([sys.executable, "tools/apex_migrate_real.py"], cwd=root)
        else:
            print("Sem migration nova: SKIP")

        print("\n[4/7] Auditoria pedagógica final")
        probe = run(
            [sys.executable, "tools/apex_pedagogical_probe.py"],
            cwd=root,
            capture=True,
        )
        probe_output = probe.stdout or ""
        print(probe_output, end="")
        ensure_clean_probe(probe_output)

        print("\n[5/7] Integridade Git")
        run(["git", "diff", "--check"], cwd=root)
        changed = assert_only_manifest_changes(root, contract["files"])
        print("Arquivos versionáveis:", len(changed))

        print("\n[6/7] Commit + push")
        run(["git", "add", "--", *contract["files"]], cwd=root)
        run(
            ["git", "commit", "-m", contract["commit_message"]],
            cwd=root,
        )
        branch = push_with_retry(root)

        remaining = run(
            ["git", "status", "--porcelain"],
            cwd=root,
            capture=True,
        ).stdout.strip()
        if remaining:
            raise RuntimeError("working tree não ficou limpo após commit")

        print("\n[7/7] Reinício + health")
        stop_gunicorn()
        payload = start_apex_detached(root, port=args.port)
        stopped = False

        final_head = run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=root,
            capture=True,
        ).stdout.strip()
        print("\nAPEX RELEASE: OK")
        print("HEAD:", final_head)
        print("BRANCH:", branch)
        print("HEALTH:", payload)
        print("WORKTREE: clean")
        return 0
    except Exception as exc:
        print(f"\nAPEX RELEASE: FALHOU — {type(exc).__name__}: {exc}")
        if stopped and not applied:
            print("Restaurando arquivos de uma eventual aplicação parcial...")
            restore_manifest_files(root, contract["files"])
        raise
    finally:
        if stopped:
            try:
                print("Tentando manter o APEX disponível após a falha...")
                start_apex_detached(root, port=args.port)
            except Exception as restart_exc:
                print(f"REINÍCIO DE EMERGÊNCIA: FALHOU — {restart_exc}")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nAPEX RELEASE: interrompido")
        raise SystemExit(130)
    except Exception:
        raise SystemExit(1)
