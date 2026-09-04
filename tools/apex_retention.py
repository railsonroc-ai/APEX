#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.config import PRIVACY_RETENTION_DAYS
from backend.services.data_lifecycle import DataLifecycle


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Aplica a política de retenção do APEX. "
            "Por padrão apenas mostra candidatos."
        )
    )
    parser.add_argument(
        "--days",
        type=int,
        default=PRIVACY_RETENTION_DAYS,
        help="dias de inatividade (mínimo 30)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="executa exclusões; sem esta flag é dry-run",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    result = DataLifecycle.apply_retention(
        args.days,
        dry_run=not args.apply,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
