"""Create a SHA-256 manifest for the exact archive or directory being shared."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_DIRS = {
    ".git", ".gradle", ".idea", ".venv", "__pycache__", "datasets", "env", "logs", "node_modules", "venv", "video",
}
EXCLUDED_NAMES = {
    ".env", "local.properties", "distribution-manifest.sha256", "sha256sums.txt",
}
EXCLUDED_SUFFIXES = {
    ".db", ".jks", ".keystore", ".key", ".log", ".pem", ".pyc", ".pyo", ".sha256", ".sqlite", ".sqlite3",
}
SECRET_NAME = re.compile(r"(?:credential|private|secret|token)", re.IGNORECASE)


def excluded(relative: Path) -> bool:
    lower_name = relative.name.lower()
    return (
        any(part in EXCLUDED_DIRS for part in relative.parts)
        or lower_name in EXCLUDED_NAMES
        or ((lower_name == ".env" or lower_name.startswith(".env.") or lower_name.endswith(".env")) and lower_name != ".env.example")
        or relative.suffix.lower() in EXCLUDED_SUFFIXES
        or bool(SECRET_NAME.search(relative.name))
        or "build" in relative.parts
        or (len(relative.parts) >= 2 and relative.parts[0] == "static" and relative.parts[1] == "images")
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Hash a final distribution archive or a sanitized package directory.")
    parser.add_argument("package", nargs="?", type=Path, default=ROOT, help="final archive/file or package directory")
    parser.add_argument("--output", type=Path, default=Path("distribution-manifest.sha256"))
    args = parser.parse_args()
    package = args.package.resolve()
    output = args.output.resolve()
    if not package.exists():
        parser.error(f"package does not exist: {package}")
    if package.is_file():
        files = [(package.name, package)]
    else:
        files = [
            (path.relative_to(package).as_posix(), path)
            for path in sorted(package.rglob("*"))
            if path.is_file() and path.resolve() != output and not excluded(path.relative_to(package))
        ]
    output.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"{sha256(path)}  {name}" for name, path in files]
    output.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"MANIFEST WRITTEN | {output} | files={len(files)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
