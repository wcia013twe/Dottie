# Explore camera connection

Explore at `/learn/#explore` now sends bounded JPEG snapshots from the browser webcam to `POST /api/explore-observe`. The same-origin localhost bridge runs a persistent recognition worker in an isolated Python environment. That worker reuses `cane_vision.detector.Detector` and `LabelMap`; it does not open a second webcam. Images are processed in memory, not saved or uploaded to Databricks. Recognition is sequential, with a 1.5-second gap after each result, and stops when the camera stops or the learner leaves Explore.

Explore shows two compact connection checks, Webcam and Jetson Nano, in place of the large camera preview. Camera capture runs in a hidden video element for recognition. Detected objects have selection buttons. Choosing a suggestion speaks the object name using browser speech and shows its uncontracted English Braille spelling. Detection is a suggestion, not a confirmed learner observation; it never changes About me or practice progress. Camera preview remains available if recognition fails, with a retry button and an explicit error.

## Setup

From the repository root:

```sh
python3 -m venv --system-site-packages .venv-camera
.venv-camera/bin/python -m pip install ultralytics pyyaml
mkdir -p .local/camera
curl -fL https://github.com/ultralytics/assets/releases/download/v8.3.0/yolo11n.pt -o .local/camera/yolo11n.pt
python3 scripts/serve.py --port 8102
```

Open `http://127.0.0.1:8102/learn/#explore`, start the camera and allow browser camera access. A server that was already running before this change needs a restart to load the new API route. The isolated worker avoids changing the Python environment used by Story Mode and learner intelligence. Set `MAGNETO_CAMERA_PYTHON` and `MAGNETO_CAMERA_MODEL` to explicit paths to use another environment or locally stored YOLO model.

The default YOLO11n model recognizes common COCO classes. It does not use the broader cane YOLO-World vocabulary. Cane-tip targeting, physical Braille execution and device acknowledgements remain unconnected to Explore. The physical-device connector still returns `ready: false`. No companion planner or voice input is added by this camera change.

## Local interface

Request: `{ "jpeg": "<base64 JPEG without data URL prefix>" }`, no extra fields. Maximum HTTP body 1.5 MB; encoded JPEG at most 1 MB; decoded image at most one megapixel. The browser sends a maximum 640-pixel edge.

Success: `{ "detections": [{ "label": "cup", "braille": "cup", "confidence": 0.8, "box": [x1,y1,x2,y2] }], "width": 640, "height": 480, "physical_ready": false }`. At most ten detections; box coordinates refer to the submitted image. Empty detections mean a successful scan with no recognized object. Scores are model confidence, not learner evidence.

Failures return `{ "error": "..." }` with a non-200 status. The bridge rejects cross-origin requests, invalid images and oversized bodies. Concurrent recognition gets 409; worker errors/timeouts get 503. This is a separate local camera interface; existing director, Story Mode and companion v1 contracts remain unchanged.

Verify with `python3 -m unittest discover -s tests -p test_explore_bridge.py` and `npm run check`, then check Explore and the System map in the browser. A live camera check requires an attached camera and browser permission; model smoke checks alone do not prove camera or physical hardware readiness.
