#!/usr/bin/env python3
import argparse
import compileall
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


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
        raise SystemExit(result.returncode)
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Gate local do APEX sem tocar no banco real."
    )
    parser.add_argument(
        "--root",
        default=str(Path(__file__).resolve().parents[1]),
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    backend = root / "backend"
    tests = root / "tests"
    tools = root / "tools"

    print("=== APEX VALIDATE ===")

    ok = compileall.compile_dir(str(backend), quiet=1)
    ok = compileall.compile_dir(str(tests), quiet=1) and ok
    if tools.exists():
        ok = compileall.compile_dir(str(tools), quiet=1) and ok
    if not ok:
        raise SystemExit("Python: FALHOU")
    print("Python: OK")

    node = shutil.which("node")
    js_files = sorted((backend / "static" / "js").glob("*.js"))
    if node:
        for js_file in js_files:
            run([node, "--check", str(js_file)], cwd=root)
        print(f"JavaScript: OK ({len(js_files)} arquivos)")
    else:
        print("JavaScript: SKIP (node ausente)")

    preferred_parent = Path("/public")
    temp_parent = preferred_parent if preferred_parent.exists() else None
    test_data = Path(
        tempfile.mkdtemp(
            prefix="APEX_TEST_GATE_",
            dir=str(temp_parent) if temp_parent else None,
        )
    )

    env = os.environ.copy()
    env["APP_ENV"] = "test"
    env["APEX_DATA_DIR"] = str(test_data)

    try:
        result = run(
            [sys.executable, "-m", "pytest", "-q"],
            cwd=root,
            env=env,
            capture=True,
        )
        output = result.stdout or ""
        summary = [
            line
            for line in output.splitlines()
            if " passed" in line or " failed" in line or " error" in line
        ]
        print(summary[-1] if summary else "pytest: OK")
    finally:
        shutil.rmtree(test_data, ignore_errors=True)

    if (root / ".git").exists():
        run(["git", "diff", "--check"], cwd=root)
        print("git diff --check: OK")

    print("APEX VALIDATE: OK")


if __name__ == "__main__":
    main()
