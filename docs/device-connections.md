# Sidebar connection checks

The learning app sidebar shows actual webcam track status: Off, Starting, Live, Paused, Blocked or Unavailable. Stopping the camera, leaving Explore or losing the track updates it immediately. It describes the webcam used by this browser app, not every camera attached to the computer. Checking connections does not silently start the webcam or request permission.

Jetson Nano status is checked on page load, on Check connections, and every 30 seconds while the page is visible. Without a configured target it shows Not configured, never Connected.

Configure an existing trusted SSH target in the server environment (`MAGNETO_NANO_SSH=user@host`) or create `.local/device-connections.json` in the repository root:

```json
{"nano_ssh":"user@your-nano-host"}
```

The local file is ignored by Git and read on every check, so it needs no server restart. SSH must already have a trusted host key and support noninteractive key authentication. The probe uses strict host-key checking and batch mode; it never stores credentials, accepts a new host key, prompts for a password, or modifies the Nano. It only reads `/proc/device-tree/model` and verifies a Jetson Nano or Jetson Orin Nano model. A ping or an open SSH port is insufficient.

SSH connected means the Nano's identity was verified over a live authenticated connection. The connection lasts only for this read-only check. It does not mean the browser is using a Nano webcam, the Orin app runtime is connected, or physical Braille is ready. Those are separate integrations. Failures show Unverified or Different device, with no raw SSH error or credential material returned to the browser.

The updated local server exposes `GET /api/nano-status`, restricted to same-origin localhost requests. The status probe lives in the harness devices directory; simulated execution and existing v1 tool contracts remain unchanged.

## Connect the real Nano to Story Mode

Connecting the USB cable alone does not configure actuation. Use a powered Nano with working USB networking (or another reachable SSH network), and connect the flashed Braille controller to a Nano USB host port. The controller needs the `cell-firmware/magneto_cell` firmware and the servo power described in `cell-firmware/README.md`.

On the Nano, copy this repository, preserving `orin-harness/` and `cane-vision/` together. From its repository root, create `.venv-harness` with Python 3.11 or newer. The original Nano's stock Python is too old for this code; check the interpreter explicitly. The Story-only receiver needs just PyYAML and pyserial; it does not need camera models, microphone libraries or a cloud credential:

```sh
python3.11 -m venv .venv-harness
.venv-harness/bin/pip install pyyaml 'pyserial>=3.5,<4'
PYTHONPATH=orin-harness .venv-harness/bin/python -m magneto_harness.devices.story_cell --check
```

The last command is read-only: it checks the configured serial port and access without opening it or moving dots. `cell.port: auto` in `orin-harness/config.yaml` discovers supported Arduino USB adapters. For multiple controllers, use a fixed `/dev/serial/by-id/...` path. The SSH user must have serial read/write permission, and no other application may own the port. On Linux, add that user to the device's serial group (commonly `dialout`) and log in again if needed.

On the laptop, establish trusted SSH host keys and key authentication for your Nano. Verify `ssh -o BatchMode=yes -o StrictHostKeyChecking=yes USER@HOST 'cat /proc/device-tree/model'`. Then merge these fields into the existing `.local/device-connections.json`, preserving any other local settings:

```json
{
  "story_cell_transport": "ssh",
  "nano_ssh": "USER@HOST",
  "nano_repository": "/absolute/path/to/magneto/on/the/nano"
}
```

Use the Nano's actual user, reachable address and repository path. From the laptop you can also run the read-only receiver check over SSH, substituting that path:

```sh
ssh -T -o BatchMode=yes -o StrictHostKeyChecking=yes USER@HOST 'cd /absolute/path/to/magneto/on/the/nano && PYTHONPATH=orin-harness .venv-harness/bin/python -m magneto_harness.devices.story_cell --check'
```

Run `python3 scripts/serve.py` on the laptop and open `http://127.0.0.1:8080/learn/`. Check connections, then start a Story activity with the cell powered and clear of hands during initial setup. The activity enters its response phase only after a matching firmware `CELL` receipt. Continuing or leaving requests CLEAR. A failed command is not automatically replayed; resolve the connection and explicitly start again. An acknowledgement verifies the controller protocol, not servo motion or mechanical reliability.

The general harness may stay `backend: sim`: Story's explicitly configured SSH receiver always uses the physical serial controller. Full companion/harness operation is a separate setup described in `orin-harness/README.md`.
