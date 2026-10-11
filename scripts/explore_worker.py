"""Persistent local YOLO worker. Frames stay in memory; stdout is JSON only."""
import base64
from contextlib import redirect_stdout
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'cane-vision'))
os.environ.setdefault('OPENCV_IO_MAX_IMAGE_PIXELS', '1000000')
os.environ.setdefault('YOLO_CONFIG_DIR', str(ROOT / '.local/camera'))
os.environ.setdefault('MPLCONFIGDIR', str(ROOT / '.local/camera/matplotlib'))


def main():
    detector = None
    for line in sys.stdin:
        try:
            payload = json.loads(line)
            with redirect_stdout(sys.stderr):
                import cv2
                import numpy as np
                from cane_vision.detector import Detector
                from cane_vision.labels import LabelMap
                if detector is None:
                    model = Path(os.environ.get('MAGNETO_CAMERA_MODEL', str(ROOT / '.local/camera/yolo11n.pt')))
                    if not model.is_file():
                        raise RuntimeError('Camera model is missing. Run the camera setup command in docs/explore-camera.md.')
                    detector = Detector(model=str(model), confidence=0.35, image_size=640)
                frame = cv2.imdecode(np.frombuffer(base64.b64decode(payload['jpeg'], validate=True), dtype=np.uint8), cv2.IMREAD_COLOR)
                if frame is None or frame.shape[0] * frame.shape[1] > 1000000:
                    raise ValueError('Send a JPEG camera frame no larger than one megapixel.')
                height, width = frame.shape[:2]
                labels = LabelMap()
                detections = []
                for detection in sorted(detector(frame), key=lambda d: d.confidence, reverse=True)[:10]:
                    label = labels(detection.label)
                    detections.append({'label': label.spoken, 'braille': label.braille,
                                       'confidence': round(detection.confidence, 3),
                                       'box': [round(v, 1) for v in detection.box]})
            result = {'detections': detections, 'width': width, 'height': height, 'physical_ready': False}
        except Exception as exc:
            print(f'Explore recognition: {exc}', file=sys.stderr, flush=True)
            result = {'error': str(exc) if isinstance(exc, (RuntimeError, ValueError)) else 'Camera recognition is unavailable. Check the camera environment and model.'}
        print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
