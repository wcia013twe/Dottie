"""Camera + YOLO observation device.

`observe` returns a bounded list of detections with a `touched` flag, using the
same cane-tip geometry and label mapping as `cane_vision`. It never announces
by itself: the harness, not the camera, decides what to say or show.
"""

from __future__ import annotations

from itertools import cycle
from pathlib import Path
from typing import Any


class SimulatedVisionDevice:
    """Replays a scripted list of frames (test/dry-run only)."""

    def __init__(self, script: list[list[dict[str, Any]]] | None = None):
        self._frames = [list(frame) for frame in (script or [])]
        self._iter = cycle(self._frames) if self._frames else None

    def observe(self, max_items: int) -> dict[str, Any]:
        frame = next(self._iter, []) if self._iter else []
        detections = []
        for item in frame[:max_items]:
            detections.append(
                {
                    "label": item.get("label", "unknown"),
                    "confidence": float(item.get("confidence", 0.0)),
                    "box": list(item.get("box", [])),
                    "touched": bool(item.get("touched", False)),
                }
            )
        return {"camera_available": bool(self._frames), "detections": detections}

    def close(self) -> None:
        return None


class RealVisionDevice:
    def __init__(self, config: dict[str, Any], base_dir: Path):
        import cv2

        from cane_vision.cane import Cane, select_touched
        from cane_vision.detector import Detector
        from cane_vision.labels import LabelMap
        from cane_vision.pipeline import resolve_detector_config

        self._cv2 = cv2
        self._select_touched = select_touched
        self.cane = Cane(**config.get("cane", {}))
        self.detector = Detector(**resolve_detector_config(config.get("detector", {}), base_dir))
        label_cfg = config.get("labels", {})
        self.labels = LabelMap(
            label_cfg.get("renames"), label_cfg.get("ignore"), label_cfg.get("min_confidence")
        )
        source = config.get("camera", {}).get("source", "none")
        if isinstance(source, str) and source.isdigit():
            source = int(source)
        elif source in (None, "", "none"):
            source = None
        self._source = source
        self._cap = None

    def _frame(self):
        if self._source is None:
            return None
        if self._cap is None:
            self._cap = self._cv2.VideoCapture(self._source)
        ok, frame = self._cap.read()
        return frame if ok else None

    def observe(self, max_items: int) -> dict[str, Any]:
        frame = self._frame()
        if frame is None:
            return {"camera_available": False, "detections": []}
        height, width = frame.shape[:2]
        detections = [d for d in self.detector(frame) if self.labels.allowed(d.label, d.confidence)]
        touched = self._select_touched(detections, self.cane, width, height)
        out = []
        for det in detections[:max_items]:
            announcement = self.labels(det.label)
            out.append(
                {
                    "label": announcement.spoken,
                    "confidence": round(det.confidence, 3),
                    "box": [round(v, 1) for v in det.box],
                    "touched": det is touched,
                }
            )
        return {"camera_available": True, "detections": out}

    def close(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None


def make_vision_device(config: dict[str, Any], base_dir: Path, backend: str):
    if backend != "real":
        return SimulatedVisionDevice(config.get("camera", {}).get("script"))
    return RealVisionDevice(config, base_dir)
