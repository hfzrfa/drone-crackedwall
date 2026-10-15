"""Mengubah folder hasil ekstrak PyTorch menjadi satu berkas .pt."""
from __future__ import annotations

import argparse
import os
import zipfile
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path, help="folder model hasil ekstrak, mis. ..\\best.pt")
    parser.add_argument("output", type=Path, help="berkas .pt yang akan dibuat")
    args = parser.parse_args()
    if not args.source.is_dir():
        raise SystemExit(f"Bukan folder: {args.source}")

    files = [path for path in args.source.rglob("*") if path.is_file()]
    if not files:
        raise SystemExit("Folder model kosong.")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.output, "w", zipfile.ZIP_STORED) as archive:
        for file in files:
            archive.write(file, file.relative_to(args.source).as_posix())
    print(f"Model dibuat: {args.output} ({len(files)} berkas)")


if __name__ == "__main__":
    main()
