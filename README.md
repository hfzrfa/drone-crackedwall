# Drone Crack Detection

A local end-to-end crack detection prototype that processes a video file, webcam, OBS Virtual Camera, or DJI FPV video relayed through OBS. A Flask server runs the existing `best.pt` YOLO segmentation model once, shares annotated MJPEG frames with browser/Android clients, stores evidence images, and writes records to MongoDB Atlas or an in-memory fallback.

Developed by hfzrfa. Original repository: <https://github.com/hfzrfa/drone-crackedwall>. See [ATTRIBUTION.md](ATTRIBUTION.md) for the honest limits of runtime label obfuscation, recipient copy IDs, and distribution integrity manifests.

`best.pt` is preserved for inference. This project does not retrain, replace, or modify its weights. The raw files in `datasets/` are future training material and are not used by the application.

## System architecture

```text
Development:
video/vidX.mp4 -> OpenCV -> best.pt -> Flask -> Browser / Android

Camera:
Webcam or OBS Virtual Camera -> OpenCV -> best.pt -> Flask -> Browser / Android

DJI target workflow:
Drone -> Air Unit/O3 -> DJI FPV Goggles V1/V2 -> USB-C data cable
      -> DJIVideoOut / Run VOC.bat -> ffplay -> OBS Window Capture
      -> OBS Virtual Camera -> OpenCV -> best.pt -> Flask
      -> evidence image + MongoDB/memory -> Android
```

The backend uses one lazy capture/inference worker. Multiple `/video` clients receive the same latest annotated frame, so opening a browser and Android at the same time does not create duplicate YOLO loops. With no video clients, inference pauses in a low-cost idle state.

## Project structure

```text
Deteksi-Retakan-Drone/
|-- server.py                   Flask API, single YOLO worker, persistence
|-- best.pt                     Existing crack segmentation model
|-- requirements.txt            Python dependencies
|-- attribution.py              Small reversible runtime-label decoder
|-- ATTRIBUTION.md              Attribution and distribution provenance guide
|-- distribution/copy_id.json   Persistent non-personal package copy ID
|-- .env.example                Safe configuration template
|-- run.ps1                     First installation and server start
|-- start.ps1                   Start an installed project
|-- stop.ps1                    Gracefully stop only this project server
|-- restart.ps1                 Stop and start again
|-- Dockerfile
|-- docker-compose.yml
|-- static/
|   |-- app.html                Responsive browser dashboard
|   `-- images/                 Generated detection evidence
|-- video/                      Local test videos (Git-ignored)
|-- datasets/                   Raw future training data (untouched)
|-- logs/                       Rotating server log and session CSV files
|-- scripts/
|   |-- find_camera.py
|   |-- test_model.py
|   |-- test_mongo.py
|   |-- test_api.py
|   |-- test_backend.py
|   |-- test_attribution.py
|   |-- generate_copy_id.py
|   |-- generate_distribution_manifest.py
|   |-- setup_firewall.ps1
|   `-- repack_model.py
`-- android-app/                Native Kotlin/Jetpack Compose client
    |-- app/
    |-- build.gradle.kts
    |-- settings.gradle.kts
    `-- gradlew.bat
```

## Requirements

Backend:

- Windows 10/11 and PowerShell
- Python 3.10 or newer
- Internet access for the first dependency installation
- Optional MongoDB Atlas account
- Optional OBS Studio and DJI tools for the hardware workflow

Android:

- Android Studio with Android SDK 37.0
- JDK 17 or a compatible Android Studio bundled JDK
- Android 8.0/API 26 or newer device/emulator

## First installation

Open PowerShell in this directory:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\run.ps1
```

`run.ps1` creates `.venv` when needed, installs dependencies, creates `.env` from the template when missing, validates `best.pt`, and starts the server. Later starts can use:

```powershell
.\start.ps1
```

The startup banner prints the LAN server URL and all useful endpoints. If LAN detection fails, run `ipconfig` and use the IPv4 address of the active Wi-Fi/Ethernet adapter.

## Configuration

Copy `.env.example` to `.env` and edit `.env`. The real `.env` is Git-ignored.

| Variable | Default | Purpose |
| --- | --- | --- |
| `HOST` | `0.0.0.0` | Listen on LAN interfaces |
| `PORT` | `5000` | Flask port |
| `MODEL_PATH` | `best.pt` | Existing YOLO model |
| `VIDEO_PATH` | empty | Local video; takes priority over camera |
| `VIDEO_LOOP` | `true` | Restart a video at EOF |
| `CAMERA_INDEX` | `0` | Webcam/OBS camera index |
| `CAMERA_WIDTH` | `1280` | Requested camera width |
| `CAMERA_HEIGHT` | `720` | Requested camera height |
| `CAMERA_FPS` | `20` | Requested camera FPS |
| `MAX_FRAME_EDGE` | `1280` | Resize only oversized frames, preserving aspect ratio |
| `CONFIDENCE` | `0.45` | YOLO inference threshold, not model accuracy |
| `SAVE_INTERVAL_SECONDS` | `5` | Minimum interval between saved detections |
| `MONGO_URI` | empty | MongoDB Atlas connection URI |
| `DB_NAME` | `seismic` | MongoDB database |
| `COLLECTION_NAME` | `testing` | MongoDB collection |
| `SOURCE_TYPE` | inferred | `video_file`, `webcam`, `obs_virtual_camera`, or `drone_camera` |
| `PUBLIC_BASE_URL` | inferred | Optional fixed LAN URL for evidence links |
| `APP_DEBUG` | `false` | Flask debug mode; keep false on a LAN |

Legacy `MONGO_DATABASE` and `MONGO_COLLECTION` values are still accepted for backward compatibility.

## Validate best.pt

Load the model, verify that its task is segmentation, and run one-frame inference:

```powershell
.\.venv\Scripts\python.exe .\scripts\test_model.py
```

Load/validate only:

```powershell
.\.venv\Scripts\python.exe .\scripts\test_model.py --validate-only
```

The script prints model path, task, class mapping, device, and PASS/FAIL. It never changes the model.

If the original model only exists as an extracted PyTorch archive folder, reconstruct the original archive without altering weights:

```powershell
.\.venv\Scripts\python.exe .\scripts\repack_model.py "..\Kelompok Deteksi Retakan File\best.pt" .\best.pt
```

## Local video testing

Place `.mp4`, `.avi`, or `.mov` footage in `video/`, then configure:

```ini
VIDEO_PATH=video/vid2.mp4
VIDEO_LOOP=true
SOURCE_TYPE=video_file
```

Restart after editing `.env`:

```powershell
.\restart.ps1
```

Open:

```text
http://127.0.0.1:5000/static/app.html
```

The dashboard shows the shared annotated stream, model/source/database health, FPS, counters, recent evidence thumbnails, and JSON from the REST API.

## Webcam and OBS Virtual Camera

Clear the video path and select a camera:

```ini
VIDEO_PATH=
CAMERA_INDEX=0
CAMERA_WIDTH=1280
CAMERA_HEIGHT=720
CAMERA_FPS=20
SOURCE_TYPE=webcam
```

Find available indexes (OBS is not always index 1):

```powershell
.\.venv\Scripts\python.exe .\scripts\find_camera.py
```

Optional interactive preview:

```powershell
.\.venv\Scripts\python.exe .\scripts\find_camera.py --preview 1
```

For OBS, start Virtual Camera first, run the scanner, set the discovered index, set `SOURCE_TYPE=obs_virtual_camera`, and restart the server.

## DJI FPV Goggles V1/V2 workflow

The Flask application does not access DJI USB hardware directly.

1. Power on the drone.
2. Power on DJI FPV Goggles V1/V2.
3. Confirm the drone camera appears in the goggles.
4. Connect the goggles with a USB-C **data** cable.
5. Run `Run VOC.bat` in the existing `DJIVideoOut` folder.
6. Confirm ffplay displays the drone feed.
7. Open OBS Studio.
8. Add a Window Capture source.
9. Select the ffplay window.
10. Fit the source to the OBS canvas.
11. Start OBS Virtual Camera.
12. Run `scripts/find_camera.py`.
13. Put the OBS index in `.env` and set `VIDEO_PATH=` plus `SOURCE_TYPE=drone_camera`.
14. Restart the server.

`Install Drivers.exe` and Zadig are manual fallback tools only. Do not automatically replace USB drivers, and do not change unrelated Windows devices. This repository documents DJI FPV Goggles V1/V2; it does not claim verified DJI Goggles 2 support.

## MongoDB Atlas

Set credentials only in `.env`:

```ini
MONGO_URI=mongodb+srv://USER:PASSWORD@CLUSTER/
DB_NAME=seismic
COLLECTION_NAME=testing
```

Test Atlas safely:

```powershell
.\.venv\Scripts\python.exe .\scripts\test_mongo.py
```

The script pings, inserts, verifies, and deletes a temporary document without printing the URI. If `MONGO_URI` is empty or Atlas is unavailable, the server remains alive and uses its bounded in-memory record list. Evidence images are still saved locally.

Atlas Network Access must allow the laptop's current public IP. `0.0.0.0/0` exposes access from anywhere and should only be temporary during controlled development.

## REST API

| Endpoint | Result |
| --- | --- |
| `GET /` | Service information and links |
| `GET /health` | Model, task, source, database, and server state |
| `GET /video` | Shared annotated MJPEG stream |
| `GET /documents?limit=20` | Newest detection records; limit 1-100 |
| `GET /documents/<id>` | One MongoDB or memory record |
| `GET /stats` | Uptime, FPS, frames, detections, duplicates, DB and client counters |
| `GET /static/images/<filename>` | Evidence image |
| `GET /static/app.html` | Browser dashboard |

Detection records retain this compatible shape:

```json
{
  "_id": "...",
  "data": {
    "status": "crack_detected",
    "timestamp": "2026-10-15T08:30:15.123456+00:00",
    "label": "retakan",
    "confidence": 0.87,
    "image_name": "1791880215123_retakan_ab12cd.jpg",
    "image_url": "http://192.168.1.10:5000/static/images/...jpg",
    "source": "video_file",
    "copy_id": "copy-0123456789abcdef0123456789abcdef",
    "image_content_width": 1280,
    "image_content_height": 720,
    "watermark_strip_height": 54,
    "polygon": [[120.2, 88.1], [121.7, 91.4]]
  }
}
```

Test a running server:

```powershell
.\.venv\Scripts\python.exe .\scripts\test_api.py http://127.0.0.1:5000
```

Run in-process backend/model/video/CSV checks:

```powershell
.\.venv\Scripts\python.exe .\scripts\test_backend.py
```

Run attribution decoder, plaintext-source, evidence-strip, duplicate-watermark, coordinate, and copy-ID checks without starting a camera worker:

```powershell
.\.venv\Scripts\python.exe .\scripts\test_attribution.py
```

Evidence watermarking occurs only after inference and annotation. The saved JPEG receives an extra strip below the original image; polygons and `image_content_*` continue to refer to the unextended inference area. Reprocessing detects the strip marker and avoids adding it twice. The live MJPEG frame, model weights, confidence, polygons, and metrics are unchanged.

## Server lifecycle and logging

```powershell
.\start.ps1
.\stop.ps1
.\restart.ps1
```

`stop.ps1` targets only this project's `server.py`, requests a clean shutdown, waits for CSV output, and uses force only as a timeout fallback. Ctrl+C also performs a clean shutdown.

Runtime events are written to `logs/server.log` with rotation. A shutdown generates `logs/session_YYYYMMDD_HHMMSS.csv` containing saved detections and summary metrics. Logging avoids per-frame terminal spam and never intentionally prints `MONGO_URI`.

## Windows Firewall and phone access

The laptop and phone must use the same Wi-Fi, LAN, or phone hotspot. Use the laptop's IPv4 address—not `127.0.0.1`—from Android.

Run this once in an Administrator PowerShell if port 5000 is blocked:

```powershell
.\scripts\setup_firewall.ps1
```

The script is never executed automatically and creates a Private-network inbound TCP rule only.

## Native Android app

`android-app/` is a real native application using Kotlin, Jetpack Compose, Material 3, OkHttp, coroutines, Coil, and DataStore Preferences. WebView is restricted to one HTML image element for the MJPEG stream; connection, records, images, status, and statistics are native UI.

Features:

- user enters only the laptop IPv4, for example `192.168.1.10`;
- app builds `http://IP:5000`;
- `/health` validates the connection;
- last successful IP is remembered;
- `/documents` and `/stats` refresh every four seconds;
- manual refresh/disconnect;
- evidence images load with Coil;
- clear timeout, offline, invalid IP/JSON, and MongoDB degraded messages;
- polling belongs to `viewModelScope` and stops with the ViewModel.

Build with Android Studio, or after Android SDK 37.0 is installed and configured:

```powershell
Set-Location .\android-app
.\gradlew.bat assembleDebug
```

Install the resulting debug APK from:

```text
android-app/app/build/outputs/apk/debug/app-debug.apk
```

The prototype deliberately allows cleartext HTTP for trusted local networks. Use HTTPS and a restricted network-security policy before any untrusted or production deployment.

## Docker

Docker Desktop support is intended for mounted video-file inference:

```powershell
docker compose up --build -d
docker compose logs -f
docker compose down
```

After `.env` or video changes:

```powershell
docker compose up -d --force-recreate
```

`video/` is mounted read-only. Evidence images persist in the `detection-images` volume. Docker sends a graceful termination signal so the server can write its session CSV, but `logs/` is not mounted by default.

For Android/LAN access to Docker, set `PUBLIC_BASE_URL=http://LAPTOP_IPV4:5000` in `.env`; otherwise Docker defaults evidence links to `http://localhost:5000` for the host browser.

Linux containers under Docker Desktop do not reliably expose Windows webcams or OBS Virtual Camera. Use native Windows execution for webcam, OBS, and DJI operation.

## Troubleshooting

| Problem | Resolution |
| --- | --- |
| `best.pt` missing | Restore it at project root or correct `MODEL_PATH`; run `test_model.py`. |
| `best.pt` invalid | Recopy the original or use `repack_model.py` only for the extracted original archive. |
| Video missing/does not open | Check `VIDEO_PATH`, extension, permissions, and test with OpenCV/model script. |
| Camera not detected | Start the camera/OBS first and run `find_camera.py`. |
| Wrong `CAMERA_INDEX` | Use the scanner result, edit `.env`, restart. |
| OBS Virtual Camera not running | Start it in OBS before starting Flask. |
| `LIBUSB_ERROR_NOT_FOUND` | Check power, a USB-C data cable, port, and DJI driver setup; use driver tools manually only. |
| ffplay black screen | Confirm the feed works in goggles, cable supports data, and DJIVideoOut recognizes the device. |
| OBS black screen | Re-select ffplay Window Capture, ensure ffplay is visible, then Fit to Screen. |
| `/video` black/unavailable | Check `/health`, source status, browser reload, and server log. |
| Low FPS | Lower `MAX_FRAME_EDGE`, close extra workloads, or use a CUDA-compatible PyTorch setup. |
| No detections | Verify model class/task and representative footage; lower `CONFIDENCE` cautiously. |
| Too many false positives | Raise `CONFIDENCE`; lasting accuracy improvements require future labeled-data training. |
| MongoDB authentication failed | Check username/password, database user roles, and rotate exposed credentials. |
| MongoDB timeout | Check Atlas Network Access, DNS, internet, and cluster availability. The server uses memory fallback. |
| Android cleartext error | Use this provided manifest/network config and rebuild; use only on trusted LAN. |
| Android timeout/wrong IP | Use laptop LAN IPv4, same network, `HOST=0.0.0.0`, and permit port 5000. |
| Firewall blocks connection | Run `setup_firewall.ps1` as Administrator on a Private network. |
| Port 5000 already used | Stop the other process or change `PORT`; Android currently expects port 5000. |
| Initial YOLO import seems frozen | Wait for Torch/Ultralytics import; pressing Ctrl+C produces `KeyboardInterrupt`. |

## Security and limitations

- Never commit `.env`, Atlas credentials, local evidence, videos, datasets, build output, or logs.
- Rotate a MongoDB password immediately if it was ever committed or shared.
- API inputs and evidence filenames are validated/sanitized; raw stack traces and DB credentials are not returned to clients.
- This is a trusted-LAN prototype without authentication or HTTPS. Do not expose port 5000 to the public internet.
- Direct DJI FPV hardware, interactive OBS, and physical Android-device behavior require manual hardware tests.
- Detection confidence is not model accuracy. Accuracy depends on the unchanged training data and domain represented by `best.pt`.
- `datasets/` remains untouched future work; there is no automatic training pipeline.

## Concise real-world operator workflow

1. Power on drone and DJI FPV Goggles V1/V2.
2. Verify video in the goggles.
3. Connect the goggles with a USB-C data cable.
4. Run `Run VOC.bat` and verify ffplay.
5. Open OBS, capture ffplay, fit it, and start Virtual Camera.
6. Run `find_camera.py`, configure `CAMERA_INDEX`, clear `VIDEO_PATH`, and set `SOURCE_TYPE=drone_camera`.
7. Start Flask and note the printed LAN server URL.
8. Put the laptop and Android phone on the same network.
9. Open Android, enter the laptop IPv4 only, and press CONNECT.
10. Verify live segmentation, crack records, evidence images, and MongoDB or memory-fallback status.
