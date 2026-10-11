"""The physical cell: an Arduino Uno running cell-firmware/magneto_cell.

The Arduino owns the Braille table, the letter timing and the servos, so the
Jetson only sends the word ("SPELL chair") and can interrupt it with a new
one. The firmware reports every step back ("CELL 13 h"), which keeps the
on-screen preview in step with the real dots.

    python -m cane_vision.serial_cell hello            # spell on the cell
    python -m cane_vision.serial_cell --send CONFIG    # raw command
"""

from __future__ import annotations

import argparse
import threading
import time

import serial
from serial.tools import list_ports

from .braille import BLANK, Timing, normalize
from .cell import CellPlayer, ConsoleCell

BAUD = 115200
MAX_TEXT = 64          # longest text the firmware keeps from one SPELL
MAX_STEP_MS = 60000
# USB vendor IDs of Uno boards and the USB-serial chips on common clones.
PERMISSION_HINT = (
    "\n[cell] Fix on Linux: sudo usermod -aG dialout $USER, then log out and back in"
)
USB_VENDORS = {0x2341: "Arduino", 0x2A03: "Arduino", 0x1A86: "CH340", 0x10C4: "CP210x", 0x0403: "FTDI"}


def find_port() -> str | None:
    """First serial port that looks like an Arduino, or None."""
    for p in sorted(list_ports.comports(), key=lambda p: p.device):
        if p.vid in USB_VENDORS:
            return p.device
    return None


def _ms(seconds: float) -> int:
    return max(0, min(MAX_STEP_MS, round(seconds * 1000)))


class SerialCell:
    """Same interface as `CellPlayer`: spell, stop, wait, busy, mask, char.

    `timing` is sent to the board on connect; None keeps the board's own
    (saved) timing.
    """

    def __init__(
        self,
        port: str,
        timing: Timing | None = Timing(),
        baud: int = BAUD,
        ready_timeout_s: float = 2.5,
        echo: bool = False,
    ):
        self.port_name = port
        self.timing = timing
        self.echo = echo
        self.mask = BLANK
        self.char = ""
        self._console = ConsoleCell()
        self._pending = 0  # SPELLs sent whose END hasn't arrived yet
        self._cond = threading.Condition()
        self._write_lock = threading.Lock()
        self._closed = False
        self._buf = b""
        self._serial = serial.Serial(port, baud, timeout=0.1)
        try:
            self._handshake(ready_timeout_s)
        except Exception:
            self._serial.close()
            raise
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()
        self._send_timing()

    @property
    def busy(self) -> bool:
        return self._pending > 0 and not self._closed

    def spell(self, text: str) -> None:
        word = normalize(text)[:MAX_TEXT].rstrip()
        with self._cond:
            self._pending += 1  # before sending, so a fast END can't be missed
        try:
            self.send(f"SPELL {word}")
        except Exception:
            with self._cond:
                self._pending -= 1
            raise

    def stop(self) -> None:
        if not self._closed:
            self.send("CLEAR")

    def wait(self, timeout: float | None = None) -> bool:
        """Block until the current word has finished (or the port is gone)."""
        with self._cond:
            return self._cond.wait_for(lambda: self._pending == 0 or self._closed, timeout)

    def send(self, line: str) -> None:
        if self.echo:
            print(f"[cell] > {line}", flush=True)
        with self._write_lock:
            self._serial.write((line + "\n").encode("ascii", "replace"))

    def close(self) -> None:
        self._closed = True
        with self._cond:
            self._cond.notify_all()
        self._reader.join(timeout=1)
        self._serial.close()

    def _send_timing(self) -> None:
        t = self.timing
        if t is not None:
            self.send(f"TIMING {_ms(t.letter_hold_s)} {_ms(t.letter_gap_s)} {_ms(t.word_gap_s)}")

    def _handshake(self, ready_timeout_s: float) -> None:
        # Opening the port resets an Uno, and the sketch prints READY once it
        # has booted. Boards that don't reset get a PING instead.
        if self._expect("READY", ready_timeout_s):
            return
        self.send("PING")
        if not self._expect("PONG", 1.5):
            raise RuntimeError(f"no Magneto cell answering on {self.port_name}")

    def _expect(self, prefix: str, timeout_s: float) -> bool:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            line = self._readline()
            if line and self.echo:
                print(f"[cell] < {line}", flush=True)
            if line and line.startswith(prefix):
                return True
        return False

    def _readline(self) -> str | None:
        """One complete line, or None if nothing arrived within the timeout."""
        while b"\n" not in self._buf:
            chunk = self._serial.read(self._serial.in_waiting or 1)
            if not chunk:
                return None
            self._buf += chunk
        line, self._buf = self._buf.split(b"\n", 1)
        return line.decode("ascii", "replace").strip()

    def _read_loop(self) -> None:
        while not self._closed:
            try:
                line = self._readline()
            except (serial.SerialException, OSError) as e:
                if not self._closed:
                    print(f"[cell] lost {self.port_name}: {e}", flush=True)
                self._closed = True
                with self._cond:
                    self._cond.notify_all()
                return
            if line:
                self._handle(line)

    def _handle(self, line: str) -> None:
        if self.echo:
            print(f"[cell] < {line}", flush=True)
        kind, _, rest = line.partition(" ")
        if kind == "CELL":
            mask, _, shown = rest.partition(" ")
            try:
                self.mask = int(mask, 16)
            except ValueError:
                return
            self.char = {"-": "", "_": " "}.get(shown, shown)
            if not self.echo:
                self._console.show(self.mask)
        elif kind == "END":
            with self._cond:
                self._pending = max(0, self._pending - 1)
                self._cond.notify_all()
        elif kind == "READY":
            # The board rebooted while connected. If this repeats, the servos
            # are probably dragging the Arduino's supply down: check the
            # separate servo supply and the shared ground.
            print("[cell] Arduino restarted", flush=True)
            self.mask, self.char = BLANK, ""
            with self._cond:
                self._pending = 0
                self._cond.notify_all()
            self._send_timing()
        elif kind == "ERR" and not self.echo:
            print(f"[cell] {line}", flush=True)


def make_cell(cell_cfg: dict, timing: Timing) -> SerialCell | CellPlayer:
    """Build the cell described by the `cell:` config section.

    port "auto" uses the first Arduino found and falls back to the console
    preview; an explicit port must work. null/none means console only.
    """
    port = cell_cfg.get("port", "auto")
    console = CellPlayer(ConsoleCell(), timing)
    if port in (None, False, "none", "console"):
        return console
    baud = cell_cfg.get("baud", BAUD)
    if port != "auto":
        return SerialCell(str(port), timing, baud)
    found = find_port()
    if found is None:
        print("[cell] no Arduino found, using the console preview", flush=True)
        return console
    try:
        return SerialCell(found, timing, baud)
    except (serial.SerialException, RuntimeError) as e:
        hint = PERMISSION_HINT if "Permission denied" in str(e) else ""
        print(f"[cell] {e}, using the console preview{hint}", flush=True)
        return console


def main() -> None:
    parser = argparse.ArgumentParser(description="Spell words on the Magneto cell or send it commands")
    parser.add_argument("words", nargs="*", help="text to spell")
    parser.add_argument("--port", default="auto", help="serial port (default: first Arduino found)")
    parser.add_argument("--send", action="append", default=[], metavar="COMMAND",
                        help='raw command such as "DOTS 125" or CONFIG; repeatable')
    parser.add_argument("--hold", type=float, help="letter hold in seconds (default: the board's)")
    args = parser.parse_args()

    port = find_port() if args.port == "auto" else args.port
    if port is None:
        ports = [f"{p.device} ({p.description})" for p in list_ports.comports()]
        raise SystemExit("No Arduino found. Serial ports: " + (", ".join(ports) or "none"))
    timing = Timing(letter_hold_s=args.hold) if args.hold else None
    cell = SerialCell(port, timing, echo=True)
    for command in args.send:
        cell.send(command)
        time.sleep(0.2)
    if args.words:
        cell.spell(" ".join(args.words))
        cell.wait()
    time.sleep(0.3)  # let the last replies arrive
    cell.close()


if __name__ == "__main__":
    main()
