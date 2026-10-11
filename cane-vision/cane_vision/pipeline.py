"""Camera -> YOLO -> touched object -> speech + Braille cell.

Touch is simulated, since the cane has no sensor yet:
- "key":   press SPACE in the preview window to "tap" whatever is at the tip
- "dwell": the tip resting on the same object for N frames counts as a tap

Detection runs on every frame. On a tap we take a majority vote over the
last few frames' selections, which smooths over a single blurry frame.
"""

from __future__ import annotations

import argparse
import threading
import time
from collections import Counter, deque
from dataclasses import dataclass, field
from pathlib import Path

import cv2
import yaml

from .braille import Timing
from .cane import Cane, select_touched
from .detector import Detection, Detector, load_vocabulary
from .labels import LabelMap, format_phrase
from .elevenlabs import ElevenLabsSpeaker, make_speaker
from .serial_cell import make_cell

DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "config.yaml"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


@dataclass
class TouchTracker:
    """Decides when to announce, given the object under the tip each frame."""

    vote_frames: int = 5
    dwell_frames: int = 8
    cooldown_s: float = 4.0
    history: deque = field(init=False)
    _streak_label: str | None = field(default=None, init=False)
    _streak: int = field(default=0, init=False)
    _streak_announced: bool = field(default=False, init=False)
    _last_label: str | None = field(default=None, init=False)
    _last_time: float = field(default=float("-inf"), init=False)

    def __post_init__(self) -> None:
        self.history = deque(maxlen=self.vote_frames)

    def update(self, label: str | None) -> None:
        self.history.append(label)
        if label is not None and label == self._streak_label:
            self._streak += 1
        else:
            self._streak_label, self._streak = label, 1 if label else 0
            self._streak_announced = False

    def voted(self) -> str | None:
        """Most common non-empty label over the recent frames."""
        counts = Counter(lbl for lbl in self.history if lbl is not None)
        return counts.most_common(1)[0][0] if counts else None

    def dwell_ready(self, now: float) -> str | None:
        """Label to announce in dwell mode: once per rest on an object, and not
        again for the same object within the cooldown (absorbs flicker)."""
        label = self._streak_label
        if label is None or self._streak_announced or self._streak < self.dwell_frames:
            return None
        if label == self._last_label and now - self._last_time < self.cooldown_s:
            return None
        return label

    def announced(self, label: str, now: float) -> None:
        self._last_label, self._last_time = label, now
        if label == self._streak_label:
            self._streak_announced = True


class LatestFrame:
    """Reads a live camera on its own thread and keeps only the newest frame.

    Without this, frames queue up whenever detection is slower than the
    camera, and the preview (and what the cane "touches") falls further and
    further behind. Video files don't need it: there every frame is wanted.
    """

    def __init__(self, cap: cv2.VideoCapture):
        self.cap = cap
        self._frame = None
        self._ok = True
        self._stopped = False
        self._new = threading.Condition()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while self._ok and not self._stopped:
            ok, frame = self.cap.read()
            with self._new:
                self._ok = ok
                if ok:
                    self._frame = frame
                self._new.notify_all()

    def read(self):
        """Wait for a frame newer than the last one returned."""
        with self._new:
            self._new.wait_for(lambda: self._frame is not None or not self._ok)
            frame, self._frame = self._frame, None
            return (frame is not None), frame

    def release(self) -> None:
        self._stopped = True
        self._thread.join(timeout=1)
        self.cap.release()


def is_live(source: str | int) -> bool:
    return isinstance(source, int) or str(source).startswith(("rtsp://", "http://", "https://"))


def resolve_detector_config(det_cfg: dict, base_dir: Path) -> dict:
    """Resolve the vocabulary file and local model paths against the config's folder."""
    cfg = dict(det_cfg)
    cfg["vocabulary"] = load_vocabulary(cfg.get("vocabulary"), base_dir)
    model = cfg.get("model")
    if model and (base_dir / model).exists():
        cfg["model"] = str(base_dir / model)
    return cfg


class CaneVision:
    def __init__(self, config: dict, base_dir: Path = Path(".")):
        cane_cfg = config.get("cane", {})
        det_cfg = config.get("detector", {})
        trig_cfg = config.get("trigger", {})
        braille_cfg = config.get("braille", {})
        speech_cfg = config.get("speech", {})
        label_cfg = config.get("labels", {})

        self.cane = Cane(**cane_cfg)
        self.detector = Detector(**resolve_detector_config(det_cfg, base_dir))
        self.labels = LabelMap(
            label_cfg.get("renames"), label_cfg.get("ignore"), label_cfg.get("min_confidence")
        )
        self.tracker = TouchTracker(
            vote_frames=trig_cfg.get("vote_frames", 5),
            dwell_frames=trig_cfg.get("dwell_frames", 8),
            cooldown_s=trig_cfg.get("cooldown_s", 4.0),
        )
        self.mode = trig_cfg.get("mode", "key")
        self.unknown_phrase = trig_cfg.get("unknown_phrase", "unknown")
        self.timing = Timing(**braille_cfg)
        self.phrase = speech_cfg.get("phrase", "{object}")
        self.speaker = make_speaker(speech_cfg)
        if isinstance(self.speaker, ElevenLabsSpeaker) and (speech_cfg.get("elevenlabs") or {}).get("prewarm"):
            names = [n for n in self.detector.class_names if self.labels.allowed(n)]
            phrases = [format_phrase(self.phrase, self.labels(n).spoken) for n in names]
            self.speaker.tts.prewarm([self.unknown_phrase, *phrases])
        self.cell = make_cell(config.get("cell", {}), self.timing)

    def process(self, frame) -> tuple[list[Detection], Detection | None]:
        h, w = frame.shape[:2]
        detections = [d for d in self.detector(frame) if self.labels.allowed(d.label, d.confidence)]
        touched = select_touched(detections, self.cane, w, h)
        self.tracker.update(touched.label if touched else None)
        return detections, touched

    def announce(self, label: str | None) -> None:
        if label is None:
            self.speaker.say(self.unknown_phrase)
            self.cell.stop()
            return
        a = self.labels(label)
        self.speaker.say(format_phrase(self.phrase, a.spoken))
        self.cell.spell(a.braille)
        self.tracker.announced(label, time.monotonic())

    def draw(self, frame, detections: list[Detection], touched: Detection | None, hint: bool = True) -> None:
        h, w = frame.shape[:2]
        for d in detections:
            hit = d is touched
            color = (0, 220, 0) if hit else (160, 160, 160)
            x1, y1, x2, y2 = map(int, d.box)
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 3 if hit else 1)
            cv2.putText(frame, f"{d.label} {d.confidence:.2f}", (x1, max(y1 - 6, 12)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)
        tip = self.cane.tip_px(w, h)
        cv2.circle(frame, tip, int(self.cane.reach_px(w, h)), (0, 200, 255), 1)
        cv2.drawMarker(frame, tip, (0, 200, 255), cv2.MARKER_CROSS, 24, 2)
        self._draw_cell(frame)
        if not hint:
            return
        text = "SPACE = tap, Q = quit" if self.mode == "key" else "dwell mode, Q = quit"
        cv2.putText(frame, text, (10, h - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)

    def _draw_cell(self, frame) -> None:
        """Mirror of the physical cell in the corner of the preview."""
        x0, y0, pitch, r = 20, 20, 22, 7
        cv2.rectangle(frame, (x0 - 12, y0 - 12), (x0 + pitch + 12, y0 + 2 * pitch + 12), (40, 40, 40), -1)
        for n in range(6):
            col, row = divmod(n, 3)
            center = (x0 + col * pitch, y0 + row * pitch)
            up = self.cell.mask & (1 << n)
            cv2.circle(frame, center, r, (255, 255, 255) if up else (90, 90, 90), -1 if up else 1)
        if self.cell.char:
            cv2.putText(frame, self.cell.char, (x0 + pitch + 20, y0 + pitch + 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2, cv2.LINE_AA)

    def run_image(self, path: str, display: bool) -> None:
        frame = cv2.imread(path)
        if frame is None:
            raise SystemExit(f"Could not read image: {path}")
        detections, touched = self.process(frame)
        for d in detections:
            mark = "  <-- touched" if d is touched else ""
            print(f"  {d.label:<16} {d.confidence:.2f}{mark}")
        self.announce(touched.label if touched else None)
        if display:
            while self.cell.busy:
                view = frame.copy()
                self.draw(view, detections, touched)
                cv2.imshow("cane-vision", view)
                if cv2.waitKey(30) & 0xFF == ord("q"):
                    break
            cv2.destroyAllWindows()
        else:
            self.cell.wait()

    def run_stream(self, source: str | int, display: bool) -> None:
        cap = cv2.VideoCapture(source)
        if not cap.isOpened():
            raise SystemExit(f"Could not open video source: {source}")
        frames = LatestFrame(cap) if is_live(source) else cap
        if not display and self.mode == "key":
            print("No display, so SPACE can't be read: switching to dwell mode.")
            self.mode = "dwell"
        try:
            while True:
                ok, frame = frames.read()
                if not ok:
                    break
                detections, touched = self.process(frame)
                now = time.monotonic()
                if self.mode == "dwell" and (label := self.tracker.dwell_ready(now)):
                    self.announce(label)
                if display:
                    self.draw(frame, detections, touched)
                    cv2.imshow("cane-vision", frame)
                    key = cv2.waitKey(1) & 0xFF
                    if key == ord("q"):
                        break
                    if key == ord(" "):
                        self.announce(self.tracker.voted())
        finally:
            frames.release()
            self.cell.stop()
            self.speaker.stop()
            if display:
                cv2.destroyAllWindows()


def main() -> None:
    parser = argparse.ArgumentParser(description="Magneto cane object announcer")
    parser.add_argument("--source", default="0", help="webcam index, video file, or image file")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--model", help="override detector.model from the config")
    parser.add_argument("--mode", choices=["key", "dwell"], help="override trigger.mode")
    parser.add_argument("--no-display", action="store_true", help="run without a preview window")
    parser.add_argument("--cell", help="override cell.port: auto, a serial port, or none")
    args = parser.parse_args()

    config = yaml.safe_load(Path(args.config).read_text()) or {}
    if args.model:
        config.setdefault("detector", {})["model"] = args.model
    if args.mode:
        config.setdefault("trigger", {})["mode"] = args.mode
    if args.cell:
        config.setdefault("cell", {})["port"] = args.cell

    app = CaneVision(config, Path(args.config).resolve().parent)
    cell = getattr(app.cell, "port_name", "console")
    print(f"device: {app.detector.device}   speech: {app.speaker.engine}   trigger: {app.mode}   cell: {cell}")
    display = not args.no_display
    if Path(args.source).suffix.lower() in IMAGE_SUFFIXES:
        app.run_image(args.source, display)
    else:
        app.run_stream(int(args.source) if args.source.isdigit() else args.source, display)


if __name__ == "__main__":
    main()
