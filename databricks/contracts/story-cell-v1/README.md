# Story cell transport v1 (additive)

Producer: `scripts/story_bridge.py` validates session revision, phase, activity budget and the model-selected target against the approved story opportunity. `scripts/story_device.py` loads local configuration. Consumer/physical owner: `orin-harness/magneto_harness/devices/nano_story.py` and `story_cell.py`.

Laptop → Nano uses trusted, noninteractive SSH over the user-configured USB network connection. Nano → Braille controller uses USB serial with the existing firmware. This does not treat an ordinary USB charging connection as a working network. The Nano needs the repository, `.venv-harness`, pyserial, trusted SSH authentication and an accessible serial device. No host keys, permission grants or remote deployments are changed by this adapter.

Each JSONL request contains a canonical UUID `command_id`, `operation` (`show` or `clear`) and `target` (lowercase ASCII letters, 1–16 for show, empty for clear). Letter targets send DOTS and hold. Word targets send SPELL with 1500 ms letter holds and 300 ms gaps. Prompt prose is never parsed into executable commands. The validated proposal target is the source.

A successful receipt contains `command_id`, `cell_ack: true`, `command`, the matching new firmware `CELL` line, `sequence_started` and `sequence_complete: false`. For SPELL this acknowledges the first displayed letter only, not completion. Failure acknowledges nothing and may mean the command was sent; the bridge never automatically replays an ambiguous command. The receiver deduplicates identical command IDs within its bounded process lifetime and rejects conflicting reuse. Session revision checks prevent duplicate browser starts before actuation.

Continuing, leaving the book and entering review request CLEAR. A remote receiver closes and clears on EOF or 30 seconds of idle input. A failed clear does not unlock a live activity for timeline navigation. Serial ownership is exclusive; no console-preview fallback is accepted as physical evidence. Simulated harness dry runs remain separate and network-free. A firmware acknowledgement is not proof of mechanical reliability.

Configure `.local/device-connections.json` (ignored local settings):

```json
{
  "story_cell_transport": "ssh",
  "nano_ssh": "USER@USB_NETWORK_ADDRESS",
  "nano_repository": "/absolute/path/to/magneto"
}
```

Equivalent settings: `MAGNETO_STORY_CELL_TRANSPORT=ssh`, `MAGNETO_NANO_SSH`, `MAGNETO_NANO_REPOSITORY`. On the Nano set `cell.port` in `orin-harness/config.yaml` to the controller's USB serial port or `auto`. The receiver always requires a real port, regardless of the general harness simulation default.

If the story server itself runs on the Nano, `story_cell_transport: usb` plus `cell_port` (or `MAGNETO_STORY_CELL_PORT`) uses local USB serial directly. This is a separate topology; it is not selected automatically.

Migration: additive local hardware boundary. Deployed director/companion payloads and learner evidence schemas remain unchanged. Browser review records are local UI history, not confirmed learner evidence, and do not enter model context or telemetry through this change.
