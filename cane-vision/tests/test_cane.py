import time

from cane_vision.cane import Cane, select_touched
from cane_vision.detector import Detection, pick_device
from cane_vision.pipeline import LatestFrame, TouchTracker, is_live

W, H = 1000, 1000
CANE = Cane(tip_x=0.5, tip_y=0.8, reach=0.05)  # tip at (500, 800), reach ~70 px


def det(label, x1, y1, x2, y2, conf=0.9):
    return Detection(label, conf, (x1, y1, x2, y2))


def test_smallest_box_containing_tip_wins():
    table = det("dining table", 100, 500, 900, 950)
    cup = det("cup", 450, 750, 550, 850)
    assert select_touched([table, cup], CANE, W, H) is cup


def test_nearest_box_within_reach():
    near = det("chair", 540, 700, 700, 900)   # 40 px right of tip
    far = det("couch", 0, 0, 200, 200)
    assert select_touched([far, near], CANE, W, H) is near


def test_nothing_within_reach():
    assert select_touched([det("tv", 0, 0, 200, 200)], CANE, W, H) is None
    assert select_touched([], CANE, W, H) is None


def test_vote_ignores_blurry_misses():
    t = TouchTracker(vote_frames=5)
    for lbl in ["chair", None, "chair", "couch", "chair"]:
        t.update(lbl)
    assert t.voted() == "chair"


def test_dwell_and_cooldown():
    t = TouchTracker(dwell_frames=3, cooldown_s=4.0)
    for _ in range(2):
        t.update("chair")
    assert t.dwell_ready(0.0) is None
    t.update("chair")
    assert t.dwell_ready(0.0) == "chair"
    t.announced("chair", 0.0)
    t.update("chair")
    assert t.dwell_ready(10.0) is None     # once per rest, however long
    t.update(None)                         # tip leaves...
    for _ in range(3):
        t.update("chair")                  # ...and comes back
    assert t.dwell_ready(1.0) is None      # still cooling down
    assert t.dwell_ready(5.0) == "chair"   # cooldown elapsed


def test_dwell_streak_resets_on_change():
    t = TouchTracker(dwell_frames=3)
    for lbl in ["chair", "chair", None, "chair"]:
        t.update(lbl)
    assert t.dwell_ready(0.0) is None


def test_vocabulary_file_skips_comments_blanks_and_duplicates(tmp_path):
    from cane_vision.detector import load_vocabulary

    (tmp_path / "vocab.txt").write_text("# header\ndoor\n\n  stairs \n# note\ndoor\n")
    assert load_vocabulary("vocab.txt", tmp_path) == ["door", "stairs"]
    assert load_vocabulary(["door", " ", "pole"]) == ["door", "pole"]
    assert load_vocabulary(None) is None


def test_shipped_vocabulary_loads():
    from pathlib import Path

    from cane_vision.detector import load_vocabulary

    names = load_vocabulary("vocabulary.txt", Path(__file__).resolve().parents[1])
    assert {"door", "stairs", "curb", "pole", "chair"} <= set(names)
    assert len(names) == len(set(names))


def test_per_class_min_confidence():
    from cane_vision.labels import LabelMap

    labels = LabelMap(ignore=["cat"], min_confidence={"mailbox": 0.45})
    assert labels.allowed("mailbox", 0.5)
    assert not labels.allowed("mailbox", 0.37)
    assert labels.allowed("door", 0.26)
    assert not labels.allowed("cat", 0.99)


def test_phrase_articles():
    from cane_vision.labels import format_phrase

    phrase = "You're looking at {a_object}. Here's how to spell it."
    assert format_phrase(phrase, "chair") == "You're looking at a chair. Here's how to spell it."
    assert format_phrase(phrase, "elevator") == "You're looking at an elevator. Here's how to spell it."
    assert format_phrase(phrase, "stairs") == "You're looking at stairs. Here's how to spell it."
    assert format_phrase("{object}", "door") == "door"


class FakeCamera:
    """Produces numbered frames as fast as it's read, then runs out."""

    def __init__(self, count):
        self.count, self.i, self.released = count, 0, False

    def read(self):
        if self.i >= self.count:
            return False, None
        self.i += 1
        time.sleep(0.001)
        return True, self.i

    def release(self):
        self.released = True


def test_latest_frame_skips_stale_frames():
    camera = FakeCamera(200)
    frames = LatestFrame(camera)
    seen = []
    while True:
        ok, frame = frames.read()
        if not ok:
            break
        seen.append(frame)
        time.sleep(0.02)  # a slow detector
    frames.release()
    assert seen == sorted(seen) and len(seen) < 100 and camera.released
    assert seen[-1] >= 190  # still caught up with the newest frames


def test_live_sources():
    assert is_live(0) and is_live("rtsp://cam/stream")
    assert not is_live("walk.mp4")


def test_pick_device():
    assert pick_device("cpu") == "cpu"
    assert pick_device("auto") in {"cuda:0", "mps", "cpu"}
