"""Test the running Flask API and report one PASS/FAIL line per endpoint."""
from __future__ import annotations

import json
import sys
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


def request_json(base: str, path: str) -> tuple[int, object]:
    try:
        with urlopen(base + path, timeout=10) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        body = error.read().decode("utf-8")
        return error.code, json.loads(body) if body else {}


def main() -> int:
    base = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://127.0.0.1:5000"
    tests = [
        ("GET /", "/", 200), ("GET /health", "/health", 200),
        ("GET /stats", "/stats", 200), ("GET /documents?limit=5", "/documents?limit=5", 200),
        ("Invalid document ID", "/documents/not-a-valid-id", 400),
        ("Invalid document limit", "/documents?limit=9999", 400),
    ]
    failures = 0
    for label, path, expected in tests:
        try:
            status, payload = request_json(base, path)
            passed = status == expected
            failures += 0 if passed else 1
            print(f"{'PASS' if passed else 'FAIL'} | {label} | HTTP {status} | {json.dumps(payload, ensure_ascii=False)[:160]}")
        except (URLError, TimeoutError, json.JSONDecodeError) as error:
            failures += 1
            print(f"FAIL | {label} | {type(error).__name__}: {error}")
    print(f"\nResult: {len(tests) - failures}/{len(tests)} passed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
