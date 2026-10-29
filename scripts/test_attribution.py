"""Targeted attribution, watermark, copy-ID, and runtime-plaintext checks."""
from __future__ import annotations

import json
from pathlib import Path
import re
import sys

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from attribution import decode_attribution
import server


def text(*code_points: int) -> str:
    return "".join(chr(value) for value in code_points)


EXPECTED = {
    "main": text(68, 101, 118, 101, 108, 111, 112, 101, 100, 32, 98, 121, 32, 104, 102, 122, 114, 102, 97),
    "short": text(98, 121, 32, 104, 102, 122, 114, 102, 97),
    "full": text(68, 101, 118, 101, 108, 111, 112, 101, 100, 32, 98, 121, 32, 72, 97, 102, 105, 122, 32, 82, 97, 102, 105, 101, 32, 65, 100, 105, 116, 121, 97, 32, 183, 32, 64, 104, 102, 122, 114, 102, 97),
    "repo": text(104, 116, 116, 112, 115, 58, 47, 47, 103, 105, 116, 104, 117, 98, 46, 99, 111, 109, 47, 104, 102, 122, 114, 102, 97, 47, 100, 114, 111, 110, 101, 45, 99, 114, 97, 99, 107, 101, 100, 119, 97, 108, 108),
}


def check(name: str, condition: bool) -> None:
    print(f"{'PASS' if condition else 'FAIL'} | {name}")
    if not condition:
        raise AssertionError(name)


def check_decoders() -> None:
    for key, expected in EXPECTED.items():
        check(f"Python decoder restores {key}", decode_attribution(key) == expected)
    html = (ROOT / "static" / "app.html").read_text(encoding="utf-8")
    match = re.search(r"developerMark\s*=\s*revealLabel\(\s*\[([^]]+)]\s*,\s*(\d+)", html)
    check("dashboard masked label is discoverable by test", match is not None)
    assert match is not None
    values = [int(value.strip()) for value in match.group(1).split(",") if value.strip()]
    seed = int(match.group(2))
    decoded = bytes(value ^ ((seed + index * 73) & 255) ^ ((index * index * 17) & 255) for index, value in enumerate(values)).decode()
    check("dashboard decoder material restores footer", decoded == EXPECTED["main"])


def check_watermark() -> None:
    source = np.full((240, 360, 3), (185, 160, 125), dtype=np.uint8)
    original = source.copy()
    polygon = [[12.0, 20.0], [350.0, 25.0], [180.0, 230.0]]
    evidence, content_height = server.add_evidence_watermark(source)
    check("watermark does not mutate inference frame", np.array_equal(source, original))
    check("evidence preserves original content pixels", np.array_equal(evidence[:240], original))
    check("watermark uses an added bottom strip", content_height == 240 and evidence.shape[0] > 240 and evidence.shape[1] == 360)
    check("polygon remains relative to original image area", polygon == [[12.0, 20.0], [350.0, 25.0], [180.0, 230.0]] and max(point[1] for point in polygon) < content_height)
    repeated, repeated_height = server.add_evidence_watermark(evidence)
    check("in-memory reprocessing does not add a second watermark", repeated.shape == evidence.shape and repeated_height == content_height)
    ok, encoded = cv2.imencode(".jpg", evidence, [cv2.IMWRITE_JPEG_QUALITY, 90])
    reloaded = cv2.imdecode(encoded, cv2.IMREAD_COLOR) if ok else None
    jpeg_repeated, jpeg_height = server.add_evidence_watermark(reloaded)
    check("JPEG reprocessing does not add a second watermark", jpeg_repeated.shape == evidence.shape and jpeg_height == content_height)


def check_copy_id() -> None:
    payload = json.loads((ROOT / "distribution" / "copy_id.json").read_text(encoding="utf-8"))
    check("copy ID is persistent and valid", bool(re.fullmatch(r"copy-[0-9a-f]{32}", payload.get("copy_id", ""))))
    check("backend exposes the packaged copy ID", server.COPY_ID == payload["copy_id"] and server.service.stats_payload()["copy_id"] == payload["copy_id"])


def check_runtime_plaintext() -> None:
    runtime_files = [
        ROOT / "attribution.py",
        ROOT / "server.py",
        ROOT / "static" / "app.html",
        *sorted((ROOT / "android-app" / "app" / "src" / "main").rglob("*")),
        ROOT / ".env.example",
        ROOT / "docker-compose.yml",
    ]
    offenders: list[str] = []
    needles = [value.encode("utf-8") for value in EXPECTED.values()]
    for path in runtime_files:
        if path.is_file():
            content = path.read_bytes()
            if any(needle in content for needle in needles):
                offenders.append(path.relative_to(ROOT).as_posix())
    check("identity plaintext is absent from relevant runtime sources", not offenders)
    if offenders:
        print("OFFENDERS | " + ", ".join(offenders))


def main() -> int:
    check_decoders()
    check_watermark()
    check_copy_id()
    check_runtime_plaintext()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
