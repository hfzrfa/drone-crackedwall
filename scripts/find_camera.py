"""Scan camera indexes 0-9 and optionally preview one camera."""
from __future__ import annotations

import argparse
import os
import cv2


def open_camera(index: int) -> cv2.VideoCapture:
    backend = cv2.CAP_DSHOW if os.name == "nt" else cv2.CAP_ANY
    return cv2.VideoCapture(index, backend)


def scan() -> list[int]:
    available: list[int] = []
    print("Scanning camera indexes 0 through 9...")
    for index in range(10):
        cap = open_camera(index)
        try:
            ok, _ = cap.read() if cap.isOpened() else (False, None)
            if ok:
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                fps = cap.get(cv2.CAP_PROP_FPS)
                fps_text = f", {fps:.1f} FPS" if fps > 0 else ""
                print(f"Camera {index}: AVAILABLE - {width}x{height}{fps_text}")
                available.append(index)
            else:
                print(f"Camera {index}: UNAVAILABLE")
        finally:
            cap.release()
    return available


def preview(index: int) -> int:
    cap = open_camera(index)
    if not cap.isOpened():
        print(f"Camera {index} could not be opened.")
        return 1
    print("Preview active. Press Q or Escape to close.")
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                print("Camera stopped returning frames.")
                return 1
            cv2.imshow(f"Camera {index}", frame)
            if cv2.waitKey(1) & 0xFF in {ord("q"), 27}:
                return 0
    finally:
        cap.release()
        cv2.destroyAllWindows()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--preview", type=int, metavar="INDEX", help="preview one camera after scanning")
    args = parser.parse_args()
    scan()
    return preview(args.preview) if args.preview is not None else 0


if __name__ == "__main__":
    raise SystemExit(main())
