"""Ping MongoDB, insert/verify/delete one temporary document, then report PASS/FAIL."""
from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path
import uuid

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


def main() -> int:
    uri = os.getenv("MONGO_URI", "").strip()
    if not uri:
        print("FAIL: MONGO_URI is empty. No credentials were printed.")
        return 1
    try:
        from pymongo import MongoClient

        client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        print("MongoDB connection: PASS")
        client.admin.command("ping")
        print("Ping: PASS")
        collection = client[os.getenv("DB_NAME", os.getenv("MONGO_DATABASE", "seismic"))][os.getenv("COLLECTION_NAME", os.getenv("MONGO_COLLECTION", "testing"))]
        token = uuid.uuid4().hex
        inserted = collection.insert_one({"codex_test": token, "created_at": datetime.now(timezone.utc)})
        print("Insert: PASS")
        if collection.find_one({"_id": inserted.inserted_id, "codex_test": token}) is None:
            print("FAIL: inserted document could not be verified.")
            return 1
        print("Verify: PASS")
        collection.delete_one({"_id": inserted.inserted_id})
        print("Delete: PASS")
        client.close()
        return 0
    except Exception as exc:
        print(f"FAIL: {type(exc).__name__}. Check credentials, Atlas Network Access, and DNS.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
