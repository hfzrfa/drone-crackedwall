"""Run deterministic in-process backend checks without changing the user's .env."""
from __future__ import annotations

import csv
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import server


def check(name: str, condition: bool) -> None:
    print(f"{'PASS' if condition else 'FAIL'} | {name}")
    if not condition:
        raise AssertionError(name)


def main() -> int:
    server.service.initialize()
    client = server.app.test_client()
    check("model loaded", server.service.model is not None)
    check("model task is segment", server.service.model_task == "segment")
    for path, expected in [("/", 200), ("/health", 200), ("/stats", 200), ("/documents?limit=5", 200), ("/documents/not-a-valid-id", 400), ("/documents?limit=9999", 400)]:
        check(f"GET {path} -> {expected}", client.get(path).status_code == expected)
    cap = server.service._open_source()
    check("sample source opens", cap is not None and cap.isOpened())
    ok, frame = cap.read() if cap is not None else (False, None)
    if cap is not None:
        cap.release()
    check("sample frame reads", bool(ok and frame is not None))
    annotated, _ = server.service._detect(server.service._resize(frame))
    check("inference annotation produced", annotated is not None and annotated.size > 0)
    stream_one = server.service.mjpeg_stream()
    first_chunk = next(stream_one)
    worker_identity = id(server.service.worker)
    stream_two = server.service.mjpeg_stream()
    second_chunk = next(stream_two)
    check("MJPEG endpoint emits JPEG data", first_chunk.startswith(b"--frame") and b"Content-Type: image/jpeg" in second_chunk)
    check("two MJPEG clients share one worker", int(server.service.stats["connected_video_clients"]) == 2 and id(server.service.worker) == worker_identity)
    stream_two.close()
    stream_one.close()
    check("evidence directory is writable", server.IMAGE_DIR.exists() and server.IMAGE_DIR.is_dir())
    original_records = list(server.service.session_records)
    server.service.session_records = [{"timestamp": "2026-10-15T00:00:00+00:00", "label": "test", "confidence": 1.0, "image_name": "test.jpg", "source": "video_file", "copy_id": server.COPY_ID}]
    csv_path = server.service.write_session_csv()
    check("session CSV generated", csv_path is not None and csv_path.is_file())
    if csv_path is not None:
        with csv_path.open(encoding="utf-8-sig") as handle:
            rows = list(csv.DictReader(handle))
        check("session CSV contains detection and summary", any(r["record_type"] == "detection" for r in rows) and any(r["record_type"] == "summary" for r in rows))
        check("session CSV contains copy ID", all(r["copy_id"] == server.COPY_ID for r in rows))
    server.service.session_records = original_records
    print("PASS | local-memory mode active" if server.service.collection is None else "PASS | MongoDB mode active")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    finally:
        server.service.shutdown()
