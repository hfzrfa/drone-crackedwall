"""Drone crack detection server: video/camera -> YOLO segmentation -> MJPEG/REST."""
from __future__ import annotations

import _thread
import atexit
import base64
import csv
import json
import logging
import os
import re
import signal
import socket
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Iterator

import cv2
import numpy as np
from dotenv import load_dotenv
from flask import Flask, Response, jsonify, redirect, request, session, url_for
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename
from werkzeug.exceptions import HTTPException

from attribution import decode_attribution

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")
IMAGE_DIR = ROOT / "static" / "images"
LOG_DIR = ROOT / "logs"
UPLOAD_DIR = ROOT / "uploads"
COPY_ID_FILE = ROOT / "distribution" / "copy_id.json"
IMAGE_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def _load_copy_id(path: Path = COPY_ID_FILE) -> str:
    """Load the package ID without ever generating a replacement at startup."""
    try:
        value = str(json.loads(path.read_text(encoding="utf-8"))["copy_id"])
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return "copy-unassigned"
    return value if re.fullmatch(r"copy-[0-9a-f]{32}", value) else "copy-unassigned"


COPY_ID = _load_copy_id()


def _watermark_strip_height(content_height: int) -> int:
    return max(32, min(64, round(content_height * 0.075)))


def _has_watermark_marker(image: np.ndarray, content_height: int, strip_height: int) -> bool:
    """Recognize the small alternating marker stored inside our evidence strip."""
    height, width = image.shape[:2]
    if height != content_height + strip_height or width < 64:
        return False
    block = 4
    marker_height = 2
    start_x = width - (8 * block) - 8
    expected_bright = [index % 2 == 0 for index in range(8)]
    for y, sample_height in ((height - marker_height - 1, marker_height), (content_height + 4, block)):
        if y < content_height or y + sample_height > height:
            continue
        observed = [float(image[y:y + sample_height, start_x + i * block:start_x + (i + 1) * block].mean()) for i in range(8)]
        if all((value > 125) == bright for value, bright in zip(observed, expected_bright)):
            return True
    return False


def _watermarked_content_height(image: np.ndarray) -> int | None:
    total_height = image.shape[0]
    for strip_height in range(32, 65):
        content_height = total_height - strip_height
        if content_height > 0 and _watermark_strip_height(content_height) == strip_height:
            if _has_watermark_marker(image, content_height, strip_height):
                return content_height
    return None


def add_evidence_watermark(image: np.ndarray) -> tuple[np.ndarray, int]:
    """Return a watermarked copy and original content height; never alter inference input."""
    if image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("evidence image must be a BGR color image")
    existing_height = _watermarked_content_height(image)
    if existing_height is not None:
        return image, existing_height
    content_height, width = image.shape[:2]
    strip_height = _watermark_strip_height(content_height)
    output = np.full((content_height + strip_height, width, 3), (35, 32, 29), dtype=np.uint8)
    output[:content_height] = image
    label = decode_attribution("short")
    scale = max(0.42, min(0.72, strip_height / 58.0))
    thickness = 1 if strip_height < 52 else 2
    text_size, baseline = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, scale, thickness)
    text_y = content_height + max(text_size[1] + 5, (strip_height + text_size[1] - baseline) // 2)
    cv2.putText(output, label, (12, min(text_y, output.shape[0] - 7)), cv2.FONT_HERSHEY_SIMPLEX, scale, (232, 236, 238), thickness, cv2.LINE_AA)
    block = 4
    marker_height = 2
    start_x = width - (8 * block) - 8
    if start_x >= 0:
        for index in range(8):
            shade = 225 if index % 2 == 0 else 30
            output[-marker_height - 1:-1, start_x + index * block:start_x + (index + 1) * block] = shade
    return output, content_height


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    return default if value is None else value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int, minimum: int = 0) -> int:
    try:
        return max(int(os.getenv(name, str(default))), minimum)
    except ValueError:
        return default


def _env_float(name: str, default: float, minimum: float = 0.0) -> float:
    try:
        return max(float(os.getenv(name, str(default))), minimum)
    except ValueError:
        return default


@dataclass(frozen=True)
class Config:
    host: str = os.getenv("HOST", "0.0.0.0")
    port: int = _env_int("PORT", 5000, 1)
    model_path_text: str = os.getenv("MODEL_PATH", "best.pt").strip() or "best.pt"
    video_path: str = os.getenv("VIDEO_PATH", "").strip()
    video_loop: bool = _env_bool("VIDEO_LOOP", True)
    camera_index: int = _env_int("CAMERA_INDEX", 0)
    camera_width: int = _env_int("CAMERA_WIDTH", 1280, 1)
    camera_height: int = _env_int("CAMERA_HEIGHT", 720, 1)
    camera_fps: int = _env_int("CAMERA_FPS", 20, 1)
    max_frame_edge: int = _env_int("MAX_FRAME_EDGE", 1280, 0)
    confidence: float = min(_env_float("CONFIDENCE", 0.45), 1.0)
    save_interval_seconds: float = _env_float("SAVE_INTERVAL_SECONDS", 5.0)
    mongo_uri: str = os.getenv("MONGO_URI", "").strip()
    db_name: str = os.getenv("DB_NAME", os.getenv("MONGO_DATABASE", "seismic")).strip() or "seismic"
    collection_name: str = os.getenv("COLLECTION_NAME", os.getenv("MONGO_COLLECTION", "testing")).strip() or "testing"
    source_override: str = os.getenv("SOURCE_TYPE", "").strip().lower()
    public_base_url: str = os.getenv("PUBLIC_BASE_URL", "").strip().rstrip("/")
    app_debug: bool = _env_bool("APP_DEBUG", False)
    admin_username: str = os.getenv("ADMIN_USERNAME", "admin").strip() or "admin"
    admin_password: str = os.getenv("ADMIN_PASSWORD", "").strip()
    admin_password_hash: str = os.getenv("ADMIN_PASSWORD_HASH", "").strip()
    session_secret: str = os.getenv("SESSION_SECRET", "").strip()
    upload_max_mib: int = _env_int("UPLOAD_MAX_MIB", 500, 10)
    upload_process_fps: float = _env_float("UPLOAD_PROCESS_FPS", 1.0, 0.1)

    @property
    def model_path(self) -> Path:
        path = Path(self.model_path_text).expanduser()
        return path if path.is_absolute() else ROOT / path

    @property
    def resolved_video_path(self) -> Path | None:
        if not self.video_path:
            return None
        path = Path(self.video_path).expanduser()
        return path if path.is_absolute() else ROOT / path

    @property
    def source_type(self) -> str:
        allowed = {"video_file", "webcam", "obs_virtual_camera", "drone_camera"}
        if self.source_override in allowed:
            return self.source_override
        return "video_file" if self.video_path else "webcam"


CONFIG = Config()


def _configure_logging() -> logging.Logger:
    app_logger = logging.getLogger("crack_detection")
    if app_logger.handlers:
        return app_logger
    app_logger.setLevel(logging.DEBUG if CONFIG.app_debug else logging.INFO)
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    file_handler = RotatingFileHandler(LOG_DIR / "server.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8")
    file_handler.setFormatter(formatter)
    app_logger.addHandler(console)
    app_logger.addHandler(file_handler)
    return app_logger


logger = _configure_logging()


def _safe_error(exc: BaseException) -> str:
    """Return a useful error without leaking credentials embedded in a URI."""
    message = str(exc).replace("\n", " ")
    message = re.sub(r"mongodb(?:\+srv)?://[^@\s]+@", "mongodb://***@", message, flags=re.I)
    return f"{type(exc).__name__}: {message[:300]}"


def network_ip() -> str:
    """Find a non-loopback IPv4 using local routing; no internet response is needed."""
    candidates: list[str] = []
    try:
        candidates.extend(item[4][0] for item in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET))
    except OSError:
        pass
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("192.0.2.1", 9))
        candidates.append(str(probe.getsockname()[0]))
    except OSError:
        pass
    finally:
        probe.close()
    for candidate in candidates:
        if candidate and not candidate.startswith("127.") and candidate != "0.0.0.0":
            return candidate
    return "127.0.0.1"


class CrackDetectionService:
    """Own one model/capture worker and share its output with all MJPEG clients."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.lock = threading.RLock()
        self.model_lock = threading.Lock()
        self.frame_ready = threading.Condition(self.lock)
        self.global_stop = threading.Event()
        self.worker_stop = threading.Event()
        self.worker: threading.Thread | None = None
        self.capture: cv2.VideoCapture | None = None
        self.model: Any = None
        self.mongo_client: Any = None
        self.collection: Any = None
        self.memory_documents: list[dict[str, Any]] = []
        self.session_records: list[dict[str, Any]] = []
        self.latest_jpeg: bytes | None = None
        self.frame_sequence = 0
        self.last_saved_monotonic = 0.0
        self.initialized = False
        self.shutdown_complete = False
        self.started_at = datetime.now(timezone.utc)
        self.started_monotonic = time.monotonic()
        self.model_task: str | None = None
        self.model_names: dict[int, str] = {}
        self.model_device = "unknown"
        self.source_status = "not started"
        self.database_status = "memory"
        self.last_error: str | None = None
        self.stats: dict[str, int | float] = {
            "frames_read": 0,
            "frames_processed": 0,
            "detections_seen": 0,
            "detections_saved": 0,
            "detections_skipped_duplicate": 0,
            "database_writes": 0,
            "database_errors": 0,
            "connected_video_clients": 0,
            "processing_fps": 0.0,
        }
        self.jobs: dict[str, dict[str, Any]] = {}
        self.jobs_lock = threading.RLock()

    @property
    def base_url(self) -> str:
        return self.config.public_base_url or f"http://{network_ip()}:{self.config.port}"

    def _set_error(self, message: str | None) -> None:
        with self.lock:
            self.last_error = message

    def initialize(self) -> None:
        with self.lock:
            if self.initialized:
                return
            self.initialized = True
        logger.info("SERVER STARTING")
        self._load_model()
        self._connect_database()

    def _load_model(self) -> None:
        model_path = self.config.model_path
        if not model_path.is_file():
            self._set_error(f"Model file is missing: {model_path}")
            logger.error("MODEL MISSING | %s", model_path)
            return
        try:
            from ultralytics import YOLO

            loaded = YOLO(str(model_path))
            task = str(getattr(loaded, "task", "unknown"))
            self.model = loaded
            self.model_task = task
            self.model_names = {int(key): str(value) for key, value in dict(getattr(loaded, "names", {})).items()}
            try:
                self.model_device = str(next(loaded.model.parameters()).device)
            except (AttributeError, StopIteration):
                self.model_device = "unknown"
            if task != "segment":
                self._set_error(f"Expected a segmentation model, received task={task}")
                logger.warning("MODEL TASK IS %s, expected segment", task)
            logger.info("MODEL LOADED | path=%s task=%s classes=%s device=%s", model_path.name, task, self.model_names, self.model_device)
        except Exception as exc:
            self.model = None
            self._set_error(f"Model could not be loaded ({_safe_error(exc)})")
            logger.error("MODEL LOAD FAILED | %s", _safe_error(exc))

    def _connect_database(self) -> None:
        if not self.config.mongo_uri:
            self.database_status = "memory"
            logger.info("MONGODB NOT CONFIGURED | using in-memory fallback")
            return
        try:
            from pymongo import MongoClient

            client = MongoClient(self.config.mongo_uri, serverSelectionTimeoutMS=4000)
            client.admin.command("ping")
            self.mongo_client = client
            self.collection = client[self.config.db_name][self.config.collection_name]
            self.collection.create_index([("data.timestamp", -1)], name="timestamp_desc")
            self.collection.create_index([("data.source", 1), ("data.timestamp", -1)], name="source_timestamp")
            self.collection.create_index([("data.status", 1), ("data.timestamp", -1)], name="status_timestamp")
            self.database_status = "connected"
            logger.info("MONGODB CONNECTED | database=%s collection=%s", self.config.db_name, self.config.collection_name)
        except Exception as exc:
            self.database_status = "degraded (memory fallback)"
            self._set_error(f"MongoDB unavailable ({_safe_error(exc)})")
            with self.lock:
                self.stats["database_errors"] += 1
            logger.error("MONGODB DEGRADED | %s", _safe_error(exc))

    def _open_source(self) -> cv2.VideoCapture | None:
        video_path = self.config.resolved_video_path
        if video_path is not None:
            if not video_path.is_file():
                self.source_status = f"video missing: {video_path}"
                self._set_error(self.source_status)
                logger.error("SOURCE ERROR | %s", self.source_status)
                return None
            cap = cv2.VideoCapture(str(video_path))
            if not cap.isOpened():
                cap.release()
                self.source_status = f"video unavailable: {video_path}"
                self._set_error(self.source_status)
                logger.error("SOURCE ERROR | %s", self.source_status)
                return None
            self.source_status = f"active video: {video_path.name}"
            logger.info("VIDEO SOURCE OPENED | %s", video_path)
            return cap
        backend = cv2.CAP_DSHOW if os.name == "nt" else cv2.CAP_ANY
        cap = cv2.VideoCapture(self.config.camera_index, backend)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.config.camera_width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.config.camera_height)
        cap.set(cv2.CAP_PROP_FPS, self.config.camera_fps)
        if not cap.isOpened():
            cap.release()
            self.source_status = f"camera unavailable (index {self.config.camera_index})"
            self._set_error(self.source_status)
            logger.error("SOURCE ERROR | %s", self.source_status)
            return None
        actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.source_status = f"active camera index {self.config.camera_index} ({actual_width}x{actual_height})"
        logger.info("CAMERA OPENED | index=%s %sx%s", self.config.camera_index, actual_width, actual_height)
        return cap

    def _status_frame(self, message: str) -> np.ndarray:
        frame = np.full((720, 1280, 3), (248, 248, 248), dtype=np.uint8)
        cv2.putText(frame, "Drone Crack Detection", (55, 100), cv2.FONT_HERSHEY_SIMPLEX, 1.5, (30, 100, 210), 3)
        cv2.putText(frame, message[:90], (55, 180), cv2.FONT_HERSHEY_SIMPLEX, 0.75, (35, 35, 35), 2)
        cv2.putText(frame, "Set VIDEO_PATH or start the configured camera source.", (55, 230), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (90, 90, 90), 1)
        return frame

    def _resize(self, frame: np.ndarray) -> np.ndarray:
        if self.config.max_frame_edge <= 0:
            return frame
        height, width = frame.shape[:2]
        longest = max(width, height)
        if longest <= self.config.max_frame_edge:
            return frame
        scale = self.config.max_frame_edge / longest
        size = (max(1, round(width * scale)), max(1, round(height * scale)))
        return cv2.resize(frame, size, interpolation=cv2.INTER_AREA)

    def _detect(self, frame: np.ndarray) -> tuple[np.ndarray, list[dict[str, Any]]]:
        if self.model is None:
            return frame, []
        try:
            # Ultralytics inference is serialized: browser camera and uploaded-video
            # jobs must never run the same model concurrently on this small ECS.
            with self.model_lock:
                result = self.model(frame, conf=self.config.confidence, imgsz=640, verbose=False)[0]
            annotated = result.plot()
            boxes = getattr(result, "boxes", None)
            masks = getattr(result, "masks", None)
            if boxes is None:
                return annotated, []
            polygons = list(getattr(masks, "xy", []) or []) if masks is not None else []
            found: list[dict[str, Any]] = []
            for index, (class_id, confidence) in enumerate(zip(boxes.cls.tolist(), boxes.conf.tolist())):
                item: dict[str, Any] = {"label": str(result.names[int(class_id)]), "confidence": round(float(confidence), 4)}
                if index < len(polygons):
                    points = polygons[index]
                    stride = max(1, len(points) // 100)
                    item["polygon"] = [[round(float(x), 1), round(float(y), 1)] for x, y in points[::stride]]
                found.append(item)
            return annotated, found
        except Exception as exc:
            self._set_error(f"Inference failed ({_safe_error(exc)})")
            logger.error("INFERENCE FAILED | %s", _safe_error(exc))
            return frame, []

    @staticmethod
    def _safe_label(label: str) -> str:
        cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "_", label).strip("_")
        return cleaned[:40] or "crack"

    def _store_detection(self, frame: np.ndarray, detections: list[dict[str, Any]], source: str | None = None) -> None:
        now_monotonic = time.monotonic()
        with self.lock:
            if now_monotonic - self.last_saved_monotonic < self.config.save_interval_seconds:
                self.stats["detections_skipped_duplicate"] += len(detections)
                return
        best = max(detections, key=lambda item: float(item["confidence"]))
        stamp = datetime.now(timezone.utc)
        filename = f"{int(stamp.timestamp() * 1000)}_{self._safe_label(str(best['label']))}_{uuid.uuid4().hex[:6]}.jpg"
        evidence, content_height = add_evidence_watermark(frame)
        if not cv2.imwrite(str(IMAGE_DIR / filename), evidence):
            self._set_error(f"Evidence image could not be written: {filename}")
            logger.error("EVIDENCE WRITE FAILED | %s", filename)
            return
        data = {
            "status": "crack_detected", "timestamp": stamp.isoformat(), **best,
            "image_name": filename,
            "image_url": f"{self.base_url}/static/images/{filename}",
            "source": source or self.config.source_type,
            "copy_id": COPY_ID,
            "image_content_width": int(frame.shape[1]),
            "image_content_height": int(content_height),
            "watermark_strip_height": int(evidence.shape[0] - content_height),
        }
        document: dict[str, Any] = {"_id": uuid.uuid4().hex, "data": data}
        if self.collection is not None:
            try:
                inserted = self.collection.insert_one({"data": data})
                document["_id"] = str(inserted.inserted_id)
                with self.lock:
                    self.stats["database_writes"] += 1
                self.database_status = "connected"
            except Exception as exc:
                self.database_status = "degraded (memory fallback)"
                with self.lock:
                    self.stats["database_errors"] += 1
                self._set_error(f"MongoDB write failed ({_safe_error(exc)})")
                logger.error("MONGODB WRITE FAILED | %s", _safe_error(exc))
        with self.lock:
            self.memory_documents.insert(0, document)
            del self.memory_documents[100:]
            self.session_records.append(data.copy())
            self.last_saved_monotonic = now_monotonic
            self.stats["detections_saved"] += 1
            self.stats["detections_skipped_duplicate"] += max(0, len(detections) - 1)
        logger.info("DETECTION SAVED | label=%s confidence=%.4f image=%s", best["label"], best["confidence"], filename)

    def process_external_frame(self, frame: np.ndarray, source: str) -> tuple[bytes, list[dict[str, Any]]]:
        """Run one browser-supplied frame through the model and return JPEG output."""
        started = time.monotonic()
        annotated, detections = self._detect(self._resize(frame))
        with self.lock:
            self.stats["frames_read"] += 1
            self.stats["frames_processed"] += 1
            self.stats["detections_seen"] += len(detections)
            fps = 1.0 / max(time.monotonic() - started, 0.0001)
            old = float(self.stats["processing_fps"])
            self.stats["processing_fps"] = round(fps if old == 0 else old * 0.8 + fps * 0.2, 2)
        if detections:
            self._store_detection(annotated, detections, source=source)
        ok, encoded = cv2.imencode(".jpg", annotated, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if not ok:
            raise ValueError("could not encode processed frame")
        return encoded.tobytes(), detections

    def create_upload_job(self, path: Path, original_name: str) -> dict[str, Any]:
        job = {
            "id": uuid.uuid4().hex,
            "name": original_name,
            "path": str(path),
            "status": "queued",
            "progress": 0.0,
            "frames_processed": 0,
            "frames_total": 0,
            "detections": 0,
            "error": None,
            "latest_jpeg": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        with self.jobs_lock:
            self.jobs[job["id"]] = job
        threading.Thread(target=self._run_upload_job, args=(job["id"],), name=f"upload-{job['id'][:8]}", daemon=True).start()
        return self.public_job(job)

    @staticmethod
    def public_job(job: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in job.items() if key not in {"path", "latest_jpeg"}}

    def get_upload_job(self, job_id: str) -> dict[str, Any] | None:
        with self.jobs_lock:
            job = self.jobs.get(job_id)
            return dict(job) if job else None

    def _run_upload_job(self, job_id: str) -> None:
        with self.jobs_lock:
            job = self.jobs.get(job_id)
            if job is None:
                return
            job["status"] = "processing"
            path = Path(str(job["path"]))
        cap = cv2.VideoCapture(str(path))
        if not cap.isOpened():
            with self.jobs_lock:
                job["status"], job["error"] = "failed", "video tidak dapat dibuka"
            return
        total = max(0, int(cap.get(cv2.CAP_PROP_FRAME_COUNT)))
        source_fps = max(1.0, float(cap.get(cv2.CAP_PROP_FPS) or 0.0))
        stride = max(1, round(source_fps / self.config.upload_process_fps))
        with self.jobs_lock:
            job["frames_total"] = total
        frame_no = 0
        try:
            while not self.global_stop.is_set():
                ok, frame = cap.read()
                if not ok or frame is None:
                    break
                frame_no += 1
                if frame_no % stride:
                    continue
                jpeg, detections = self.process_external_frame(frame, "browser_upload")
                with self.jobs_lock:
                    job["latest_jpeg"] = jpeg
                    job["frames_processed"] += 1
                    job["detections"] += len(detections)
                    job["progress"] = round(min(100.0, frame_no * 100 / total), 1) if total else 0.0
            with self.jobs_lock:
                job["progress"] = 100.0
                job["status"] = "completed"
        except Exception as exc:
            logger.error("UPLOAD JOB FAILED | id=%s error=%s", job_id, _safe_error(exc))
            with self.jobs_lock:
                job["status"], job["error"] = "failed", "pemrosesan video gagal"
        finally:
            cap.release()

    def _publish(self, frame: np.ndarray) -> None:
        encoded, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if encoded:
            with self.frame_ready:
                self.latest_jpeg = buffer.tobytes()
                self.frame_sequence += 1
                self.frame_ready.notify_all()

    def _run_worker(self) -> None:
        logger.info("INFERENCE WORKER STARTED")
        cap = self._open_source()
        with self.lock:
            self.capture = cap
        source_error_logged = False
        try:
            while not self.global_stop.is_set() and not self.worker_stop.is_set():
                with self.frame_ready:
                    while int(self.stats["connected_video_clients"]) <= 0 and not self.global_stop.is_set() and not self.worker_stop.is_set():
                        self.source_status = "paused (waiting for /video client)"
                        self.frame_ready.wait(timeout=1.0)
                    if self.global_stop.is_set() or self.worker_stop.is_set():
                        break
                    if self.config.resolved_video_path is not None:
                        self.source_status = f"active video: {self.config.resolved_video_path.name}"
                    else:
                        self.source_status = f"active camera index {self.config.camera_index}"
                cycle_started = time.monotonic()
                ok, frame = cap.read() if cap is not None else (False, None)
                if ok and frame is not None:
                    with self.lock:
                        self.stats["frames_read"] += 1
                elif cap is not None and self.config.video_path and self.config.video_loop:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    ok, frame = cap.read()
                    if ok and frame is not None:
                        with self.lock:
                            self.stats["frames_read"] += 1
                if not ok or frame is None:
                    if not source_error_logged:
                        logger.warning("SOURCE ERROR | no frame available")
                        source_error_logged = True
                    message = "Video ended." if cap is not None and self.config.video_path else "Video source unavailable."
                    self._publish(self._status_frame(message))
                    time.sleep(0.25)
                    continue
                source_error_logged = False
                annotated, detections = self._detect(self._resize(frame))
                with self.lock:
                    self.stats["frames_processed"] += 1
                    self.stats["detections_seen"] += len(detections)
                if detections:
                    self._store_detection(annotated, detections)
                self._publish(annotated)
                instant_fps = 1.0 / max(time.monotonic() - cycle_started, 0.0001)
                with self.lock:
                    previous = float(self.stats["processing_fps"])
                    self.stats["processing_fps"] = round(instant_fps if previous == 0 else previous * 0.8 + instant_fps * 0.2, 2)
        finally:
            if cap is not None:
                cap.release()
            with self.frame_ready:
                self.capture = None
                self.source_status = "stopped (waiting for /video client)"
                self.worker = None
                self.frame_ready.notify_all()
            logger.info("INFERENCE WORKER STOPPED")

    def connect_video_client(self) -> None:
        with self.frame_ready:
            self.stats["connected_video_clients"] += 1
            if self.worker is None or not self.worker.is_alive():
                self.worker_stop.clear()
                self.worker = threading.Thread(target=self._run_worker, name="yolo-inference", daemon=True)
                self.worker.start()
            clients = int(self.stats["connected_video_clients"])
        logger.info("CLIENT CONNECTED | video_clients=%s", clients)

    def disconnect_video_client(self) -> None:
        with self.frame_ready:
            self.stats["connected_video_clients"] = max(0, int(self.stats["connected_video_clients"]) - 1)
            clients = int(self.stats["connected_video_clients"])
            self.frame_ready.notify_all()
        logger.info("CLIENT DISCONNECTED | video_clients=%s", clients)

    def mjpeg_stream(self) -> Iterator[bytes]:
        self.connect_video_client()
        sequence = -1
        try:
            while not self.global_stop.is_set():
                with self.frame_ready:
                    self.frame_ready.wait_for(lambda: self.frame_sequence != sequence or self.global_stop.is_set(), timeout=5.0)
                    if self.global_stop.is_set():
                        break
                    jpeg = self.latest_jpeg
                    sequence = self.frame_sequence
                if jpeg is not None:
                    yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg + b"\r\n"
        finally:
            self.disconnect_video_client()

    def health_payload(self) -> dict[str, Any]:
        model_loaded = self.model is not None
        with self.lock:
            return {
                "status": "ok" if model_loaded else "degraded", "ok": model_loaded,
                "model_loaded": model_loaded, "model_path": str(self.config.model_path),
                "model_task": self.model_task, "model_classes": self.model_names,
                "model_device": self.model_device, "source_type": self.config.source_type,
                "source_status": self.source_status, "camera": self.source_status,
                "database_status": self.database_status, "database": self.database_status,
                "server_time": datetime.now(timezone.utc).isoformat(), "server_url": self.base_url,
                "last_error": self.last_error,
                "frames": self.stats["frames_processed"], "detections": self.stats["detections_seen"],
                "saved": self.stats["detections_saved"],
                "copy_id": COPY_ID,
            }

    def stats_payload(self) -> dict[str, Any]:
        with self.lock:
            snapshot = dict(self.stats)
            snapshot.update({
                "uptime_seconds": round(time.monotonic() - self.started_monotonic, 2),
                "frames": self.stats["frames_processed"], "detections": self.stats["detections_seen"],
                "saved": self.stats["detections_saved"], "memory_documents": len(self.memory_documents),
                "database_status": self.database_status, "source_status": self.source_status,
                "last_error": self.last_error,
                "copy_id": COPY_ID,
            })
            return snapshot

    def latest_documents(self, limit: int) -> list[dict[str, Any]]:
        if self.collection is not None and self.database_status == "connected":
            try:
                return [{"_id": str(item["_id"]), "data": item.get("data", {})} for item in self.collection.find().sort("data.timestamp", -1).limit(limit)]
            except Exception as exc:
                self.database_status = "degraded (memory fallback)"
                with self.lock:
                    self.stats["database_errors"] += 1
                self._set_error(f"MongoDB read failed ({_safe_error(exc)})")
                logger.error("MONGODB READ FAILED | %s", _safe_error(exc))
        with self.lock:
            return [dict(item) for item in self.memory_documents[:limit]]

    def get_document(self, document_id: str) -> tuple[dict[str, Any] | None, int]:
        with self.lock:
            memory_match = next((dict(item) for item in self.memory_documents if item["_id"] == document_id), None)
        if memory_match is not None:
            return memory_match, 200
        if len(document_id) == 24 and self.collection is not None:
            try:
                from bson import ObjectId

                item = self.collection.find_one({"_id": ObjectId(document_id)})
                if item is not None:
                    return {"_id": str(item["_id"]), "data": item.get("data", {})}, 200
            except Exception as exc:
                self.database_status = "degraded (memory fallback)"
                with self.lock:
                    self.stats["database_errors"] += 1
                self._set_error(f"MongoDB read failed ({_safe_error(exc)})")
                logger.error("MONGODB READ FAILED | %s", _safe_error(exc))
                return None, 503
        return None, 404

    def write_session_csv(self) -> Path | None:
        end_time = datetime.now(timezone.utc)
        path = LOG_DIR / f"session_{end_time.astimezone().strftime('%Y%m%d_%H%M%S')}.csv"
        with self.lock:
            records = [dict(item) for item in self.session_records]
            stats = dict(self.stats)
        try:
            with path.open("w", newline="", encoding="utf-8-sig") as handle:
                fields = ["record_type", "timestamp", "label", "confidence", "image_name", "source", "copy_id", "metric", "value"]
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                for item in records:
                    writer.writerow({"record_type": "detection", "timestamp": item.get("timestamp", ""), "label": item.get("label", ""), "confidence": item.get("confidence", ""), "image_name": item.get("image_name", ""), "source": item.get("source", ""), "copy_id": item.get("copy_id", COPY_ID)})
                summary = {
                    "start_time": self.started_at.isoformat(), "end_time": end_time.isoformat(),
                    "frames_read": stats["frames_read"], "frames_processed": stats["frames_processed"],
                    "detections_seen": stats["detections_seen"], "detections_saved": stats["detections_saved"],
                    "duplicate_skips": stats["detections_skipped_duplicate"], "database_errors": stats["database_errors"],
                    "copy_id": COPY_ID,
                }
                for key, value in summary.items():
                    writer.writerow({"record_type": "summary", "copy_id": COPY_ID, "metric": key, "value": value})
            logger.info("SESSION CSV WRITTEN | %s", path)
            return path
        except Exception as exc:
            logger.error("SESSION CSV FAILED | %s", _safe_error(exc))
            return None

    def shutdown(self) -> None:
        with self.lock:
            if self.shutdown_complete:
                return
            self.shutdown_complete = True
        logger.info("SERVER SHUTTING DOWN")
        self.global_stop.set()
        self.worker_stop.set()
        with self.frame_ready:
            self.frame_ready.notify_all()
        if self.capture is not None:
            self.capture.release()
        if self.worker is not None and self.worker.is_alive() and self.worker is not threading.current_thread():
            self.worker.join(timeout=5)
        if self.mongo_client is not None:
            try:
                self.mongo_client.close()
            except Exception as exc:
                logger.warning("MONGODB CLOSE FAILED | %s", _safe_error(exc))
        self.write_session_csv()


service = CrackDetectionService(CONFIG)
app = Flask(__name__, static_folder="static")
app.config["JSON_SORT_KEYS"] = False
app.config.update(
    SECRET_KEY=CONFIG.session_secret or "deployment-secret-missing",
    MAX_CONTENT_LENGTH=CONFIG.upload_max_mib * 1024 * 1024,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=True,
    SESSION_COOKIE_SAMESITE="Lax",
)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)
_LOGIN_ATTEMPTS: dict[str, list[float]] = {}
_LOGIN_ATTEMPTS_LOCK = threading.Lock()


def _login_is_rate_limited(remote_address: str) -> bool:
    """Allow at most five failed login attempts per ten minutes per client IP."""
    now = time.monotonic()
    with _LOGIN_ATTEMPTS_LOCK:
        attempts = [item for item in _LOGIN_ATTEMPTS.get(remote_address, []) if now - item < 600]
        _LOGIN_ATTEMPTS[remote_address] = attempts
        return len(attempts) >= 5


def _record_failed_login(remote_address: str) -> None:
    with _LOGIN_ATTEMPTS_LOCK:
        _LOGIN_ATTEMPTS.setdefault(remote_address, []).append(time.monotonic())


def _clear_failed_logins(remote_address: str) -> None:
    with _LOGIN_ATTEMPTS_LOCK:
        _LOGIN_ATTEMPTS.pop(remote_address, None)


def _password_matches(value: str) -> bool:
    if CONFIG.admin_password_hash:
        return check_password_hash(CONFIG.admin_password_hash, value)
    return bool(CONFIG.admin_password) and value == CONFIG.admin_password


def _is_authenticated() -> bool:
    return bool(session.get("authenticated"))


@app.before_request
def require_login() -> Response | None:
    allowed = {"login", "login_submit", "logout"}
    if request.endpoint in allowed or request.path.startswith("/.well-known/"):
        return None
    if _is_authenticated():
        return None
    if request.accept_mimetypes.accept_html and not request.path.startswith(("/health", "/stats", "/documents", "/video", "/api/")):
        return redirect(url_for("login", next=request.path))
    return jsonify({"error": "authentication required"}), 401


@app.after_request
def security_headers(response: Response) -> Response:
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(self), microphone=()")
    response.headers.setdefault("Content-Security-Policy", "default-src 'self'; img-src 'self' data:; media-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'self'; base-uri 'self'")
    return response


@app.get("/login")
def login() -> Response:
    if _is_authenticated():
        return redirect(url_for("index"))
    return Response("""<!doctype html><html lang=\"id\"><meta charset=\"utf-8\"><meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>Masuk | Crack Detection</title><style>body{margin:0;min-height:100vh;display:grid;place-items:center;background:#f3f8f7;font:16px system-ui;color:#13231f}form{width:min(360px,calc(100% - 40px));padding:28px;background:#fff;border:1px solid #d8e5df;border-radius:16px;box-shadow:0 18px 48px -34px #123}label,input,button{display:block;width:100%;box-sizing:border-box}label{margin-top:16px;font-weight:650}input{margin-top:6px;padding:11px;border:1px solid #b8cac1;border-radius:8px}button{margin-top:24px;padding:12px;border:0;border-radius:8px;background:#087d63;color:#fff;font-weight:700;cursor:pointer}.error{color:#b74635}</style><form method=\"post\" action=\"login\"><h1>Crack Detection</h1><p>Masuk untuk membuka dashboard.</p>{error}<label>Username<input name=\"username\" autocomplete=\"username\" required></label><label>Password<input type=\"password\" name=\"password\" autocomplete=\"current-password\" required></label><button>Masuk</button></form></html>""".replace("{error}", "<p class=\"error\">Kredensial belum dikonfigurasi.</p>" if not (CONFIG.admin_password or CONFIG.admin_password_hash) else ""), mimetype="text/html")


@app.post("/login")
def login_submit() -> Response:
    username = str(request.form.get("username", ""))
    password = str(request.form.get("password", ""))
    remote_address = request.remote_addr or "unknown"
    if _login_is_rate_limited(remote_address):
        return Response("Terlalu banyak percobaan login. Coba lagi dalam sepuluh menit.", status=429, mimetype="text/plain")
    if username != CONFIG.admin_username or not _password_matches(password):
        _record_failed_login(remote_address)
        time.sleep(0.5)
        return Response("Kredensial tidak valid.", status=401, mimetype="text/plain")
    _clear_failed_logins(remote_address)
    session.clear()
    session["authenticated"] = True
    session["username"] = CONFIG.admin_username
    target = request.args.get("next", "")
    return redirect(target if target.startswith("/") and not target.startswith("//") else url_for("index"))


@app.post("/logout")
def logout() -> Response:
    session.clear()
    return redirect(url_for("login"))


@app.get("/")
def index() -> Response:
    return redirect(url_for("static", filename="app.html"))


@app.get("/health")
def health() -> tuple[Response, int]:
    payload = service.health_payload()
    return jsonify(payload), 200 if payload["model_loaded"] else 503


@app.get("/video")
def video() -> Response:
    return Response(service.mjpeg_stream(), mimetype="multipart/x-mixed-replace; boundary=frame", headers={"Cache-Control": "no-store, no-cache, must-revalidate"})


def _validated_limit() -> tuple[int | None, tuple[Response, int] | None]:
    raw = request.args.get("limit", "20")
    try:
        limit = int(raw)
    except (TypeError, ValueError):
        return None, (jsonify({"error": "limit must be an integer between 1 and 100"}), 400)
    if not 1 <= limit <= 100:
        return None, (jsonify({"error": "limit must be between 1 and 100"}), 400)
    return limit, None


@app.get("/documents")
def documents() -> Response | tuple[Response, int]:
    limit, error = _validated_limit()
    return error if error is not None else jsonify(service.latest_documents(limit or 20))


@app.get("/documents/<document_id>")
def document(document_id: str) -> tuple[Response, int]:
    if not re.fullmatch(r"(?:[0-9a-fA-F]{24}|[0-9a-fA-F]{32})", document_id):
        return jsonify({"error": "invalid document id"}), 400
    item, status_code = service.get_document(document_id)
    if status_code == 503:
        return jsonify({"error": "database temporarily unavailable"}), 503
    if item is None:
        return jsonify({"error": "document not found"}), 404
    return jsonify(item), 200


@app.get("/stats")
def stats() -> Response:
    return jsonify(service.stats_payload())


@app.post("/api/upload")
def upload_video() -> Response | tuple[Response, int]:
    uploaded = request.files.get("video")
    if uploaded is None or not uploaded.filename:
        return jsonify({"error": "file video wajib diisi"}), 400
    extension = Path(secure_filename(uploaded.filename)).suffix.lower()
    if extension not in {".mp4", ".mov", ".avi", ".mkv", ".webm"}:
        return jsonify({"error": "format video tidak didukung"}), 400
    stored_name = f"{uuid.uuid4().hex}{extension}"
    destination = UPLOAD_DIR / stored_name
    uploaded.save(destination)
    job = service.create_upload_job(destination, secure_filename(uploaded.filename))
    return jsonify(job), 202


@app.get("/api/jobs/<job_id>")
def upload_job(job_id: str) -> Response | tuple[Response, int]:
    if not re.fullmatch(r"[0-9a-f]{32}", job_id):
        return jsonify({"error": "id pekerjaan tidak valid"}), 400
    job = service.get_upload_job(job_id)
    if job is None:
        return jsonify({"error": "pekerjaan tidak ditemukan"}), 404
    return jsonify(service.public_job(job))


@app.get("/api/jobs/<job_id>/frame")
def upload_job_frame(job_id: str) -> Response | tuple[Response, int]:
    job = service.get_upload_job(job_id)
    if job is None:
        return jsonify({"error": "pekerjaan tidak ditemukan"}), 404
    jpeg = job.get("latest_jpeg")
    if not isinstance(jpeg, bytes):
        return jsonify({"error": "preview belum tersedia"}), 404
    return Response(jpeg, mimetype="image/jpeg", headers={"Cache-Control": "no-store"})


@app.post("/api/camera/frame")
def browser_camera_frame() -> Response | tuple[Response, int]:
    uploaded = request.files.get("frame")
    if uploaded is None:
        return jsonify({"error": "frame wajib diisi"}), 400
    raw = uploaded.read()
    if not raw or len(raw) > 5 * 1024 * 1024:
        return jsonify({"error": "ukuran frame tidak valid"}), 400
    frame = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
    if frame is None:
        return jsonify({"error": "format frame tidak valid"}), 400
    try:
        jpeg, detections = service.process_external_frame(frame, "browser_camera")
    except Exception as exc:
        logger.error("BROWSER CAMERA FAILED | %s", _safe_error(exc))
        return jsonify({"error": "pemrosesan kamera gagal"}), 500
    return jsonify({"image": base64.b64encode(jpeg).decode("ascii"), "detections": detections})


@app.errorhandler(HTTPException)
def http_error(exc: HTTPException) -> tuple[Response, int]:
    return jsonify({"error": exc.name.lower(), "message": exc.description}), exc.code or 500


@app.errorhandler(Exception)
def unexpected_error(exc: Exception) -> tuple[Response, int]:
    logger.error("UNHANDLED REQUEST ERROR | path=%s error=%s", request.path, _safe_error(exc))
    return jsonify({"error": "internal server error"}), 500


def _watch_shutdown_request() -> None:
    stop_file = LOG_DIR / "stop.request"
    while not service.global_stop.wait(0.5):
        if stop_file.exists():
            try:
                stop_file.unlink()
            except OSError:
                pass
            logger.info("SHUTDOWN REQUEST RECEIVED")
            _thread.interrupt_main()
            return


def _print_startup_banner() -> None:
    base = service.base_url
    for line in [
        "=" * 60, "CRACK DETECTION SERVER", "=" * 60,
        f"SERVER URL: {base}", f"DASHBOARD:  {base}/static/app.html",
        f"VIDEO:      {base}/video", f"DOCUMENTS:  {base}/documents?limit=20",
        f"STATS:      {base}/stats", "=" * 60,
    ]:
        logger.info(line)
    if network_ip() == "127.0.0.1":
        logger.warning("LAN IPv4 was not found. Run ipconfig and use the active Wi-Fi IPv4 address.")


def _handle_termination(signum: int, _frame: Any) -> None:
    logger.info("TERMINATION SIGNAL RECEIVED | signal=%s", signum)
    service.shutdown()
    raise SystemExit(0)


atexit.register(service.shutdown)


if __name__ == "__main__":
    service.initialize()
    _print_startup_banner()
    signal.signal(signal.SIGTERM, _handle_termination)
    signal.signal(signal.SIGINT, _handle_termination)
    threading.Thread(target=_watch_shutdown_request, name="shutdown-watcher", daemon=True).start()
    try:
        app.run(host=CONFIG.host, port=CONFIG.port, threaded=True, debug=CONFIG.app_debug, use_reloader=False)
    except KeyboardInterrupt:
        logger.info("KEYBOARD INTERRUPT RECEIVED")
    finally:
        service.shutdown()
