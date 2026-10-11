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
