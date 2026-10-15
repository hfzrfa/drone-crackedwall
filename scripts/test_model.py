"""Validate best.pt and optionally run one-frame segmentation inference."""
from __future__ import annotations

import argparse
import os
from pathlib import Path

import cv2
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


def resolve_path(value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else ROOT / path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validate-only", action="store_true", help="load model without running inference")
    parser.add_argument("--video", help="override VIDEO_PATH for the one-frame test")
    args = parser.parse_args()
    model_path = resolve_path(os.getenv("MODEL_PATH", "best.pt"))
    print(f"Model path: {model_path}")
    try:
        from ultralytics import YOLO

        model = YOLO(str(model_path))
        task = str(model.task)
        print(f"Model task: {task}")
        print(f"Class names: {model.names}")
        try:
            print(f"Device: {next(model.model.parameters()).device}")
        except (AttributeError, StopIteration):
            print("Device: unknown")
        if task != "segment":
            print("FAIL: best.pt is not a segmentation model.")
            return 1
        if args.validate_only:
            print("PASS: model loaded and segmentation task confirmed.")
            return 0
        source_text = args.video or os.getenv("VIDEO_PATH", "")
        if not source_text:
            candidates = sorted((ROOT / "video").glob("*"))
            source = next((item for item in candidates if item.suffix.lower() in {".mp4", ".avi", ".mov"}), None)
        else:
            source = resolve_path(source_text)
        if source is None or not source.is_file():
            print("FAIL: no test video was found. Set VIDEO_PATH or use --video.")
            return 1
        cap = cv2.VideoCapture(str(source))
        try:
            ok, frame = cap.read()
        finally:
            cap.release()
        if not ok or frame is None:
            print(f"FAIL: could not read a frame from {source}")
            return 1
        result = model(frame, conf=float(os.getenv("CONFIDENCE", "0.45")), imgsz=640, verbose=False)[0]
        annotated = result.plot()
        if annotated is None or annotated.size == 0:
            print("FAIL: annotation output is empty.")
            return 1
        count = 0 if result.boxes is None else len(result.boxes)
        print(f"Test source: {source}")
        print(f"Detections on first frame: {count}")
        print("PASS: frame inference and annotation succeeded.")
        return 0
    except Exception as exc:
        print(f"FAIL: {type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
