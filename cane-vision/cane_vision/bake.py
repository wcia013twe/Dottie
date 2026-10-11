"""Bake the vocabulary into a YOLO-World model, optionally exporting it.

    python -m cane_vision.bake                  # models/cane-world.pt
    python -m cane_vision.bake --export onnx    # + models/cane-world.onnx
    python -m cane_vision.bake --export engine  # + TensorRT, run on the Jetson

A baked model already knows its class names, so it starts without encoding
the vocabulary with CLIP. Point `detector.model` at the output and remove
`detector.vocabulary` from the config.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from .detector import drop_text_encoder, fp16_args, load_vocabulary
from .pipeline import DEFAULT_CONFIG


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--base", help="YOLO-World checkpoint (default: detector.model)")
    parser.add_argument("--out", default="models/cane-world.pt", help="relative to the config folder")
    parser.add_argument("--export", choices=["onnx", "engine"], help="also export for deployment")
    parser.add_argument("--half", action="store_true", help="FP16 for TensorRT export")
    args = parser.parse_args()

    config_path = Path(args.config).resolve()
    base_dir = config_path.parent
    det_cfg = (yaml.safe_load(config_path.read_text()) or {}).get("detector", {})
    vocabulary = load_vocabulary(det_cfg.get("vocabulary"), base_dir)
    if not vocabulary:
        raise SystemExit("detector.vocabulary is empty; nothing to bake")

    from ultralytics import YOLO

    model = YOLO(args.base or det_cfg.get("model", "yolov8s-worldv2.pt"))
    model.set_classes(vocabulary)
    drop_text_encoder(model)
    out = base_dir / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    model.save(out)
    print(f"Baked {len(vocabulary)} names into {out}")

    if args.export:
        precision = fp16_args() if args.half else {}
        exported = YOLO(out).export(format=args.export, imgsz=det_cfg.get("image_size", 640), **precision)
        print(f"Exported {exported}")


if __name__ == "__main__":
    main()
