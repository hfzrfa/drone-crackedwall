"""Generate one persistent, non-personal distribution copy ID on demand."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import secrets

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "distribution" / "copy_id.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a new ID for a recipient-specific distribution package.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="copy_id.json to create or replace")
    args = parser.parse_args()
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    copy_id = f"copy-{secrets.token_hex(16)}"
    output.write_text(json.dumps({"copy_id": copy_id}, indent=2) + "\n", encoding="utf-8")
    print(f"COPY ID WRITTEN | {output} | {copy_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
