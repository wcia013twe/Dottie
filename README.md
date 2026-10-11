# Magneto

A simple local 3D parts viewer for a Braille prototype. View components, assemblies and ideal motion, or save designs in your browser. No Autodesk, web framework or cloud service is required.

## Run on localhost

Install Python 3, clone this repository and run:

```sh
git clone https://github.com/wcia013twe/magneto.git
cd magneto
python3 scripts/serve.py
```

Open **http://127.0.0.1:8080/**. Stop the server with **Ctrl+C**.

If port 8080 is already in use:

```sh
python3 scripts/serve.py --port 8081
```

Then open **http://127.0.0.1:8081/**. On Windows, use `py` in place of `python3` if needed. The included viewer runs offline after cloning; Node and npm are only needed to rebuild CAD.

## Project structure

```text
web/                     Local viewer, controls and bundled Three.js
  models/                Generated meshes and built-in design data
  documents/             Readable manuscript and measurement references
  vendor/                Third-party code and its license
cad/
  drive/                 Four-part drive source, dimensions and manifest
  servo-reset/           Solid servo/reset CAD source and dimensions
  readable/              Research reconstruction notes
exports/
  drive/                 Four individual draft 3MFs and STLs
  servo-reset/           Five individual draft 3MFs and concept assembly
  readable/              Research concept assembly 3MF
scripts/                 Local server, CAD builders, 3MF export and checks
cane-vision/             Cane camera: YOLO object detection, speech and Braille spelling
cell-firmware/           Arduino Uno sketch that drives the six dot servos
docs/                    Design assumptions and provenance
AGENTS.md                Brief guidance for coding agents
```

## Use the viewer

Open **System** in the viewer header, or the system-map link in the learning companion's **Grown-up corner**, to see the animated Databricks scaffolding at `/system.html`. Select services for their implementation paths. **Check Databricks access** performs bounded, read-only resource metadata checks using the existing `.venv-agent` and `magneto` login; it does not run models, SQL queries, deployment, or trace writes. Implemented wiring, optional adapters and missing integrations are labeled separately. A successful access check is not an end-to-end integration test.

Open **Designs → Servo + reset → Open** to inspect the solid servo concept. Select dots, click **Write selected**, then **Pull reset tab**. The view selector and checkboxes isolate groups; Explode separates them. Drag to orbit, scroll to zoom and right-drag to pan.

The Designs library includes **Motor arm — four-part drive**, Servo + reset, and the Readable reconstruction. Their source geometry ships with this repository, including `web/models/drive-design.json`, so a fresh browser can install the motor-arm entry. The yellow **8-cell track** button appears only in Servo + reset. **Assemble** restores assembled positions; **Center view** frames the current view. Import STL files to start a design, then name and save it. Saved designs live in localStorage: changing the browser or localhost port creates a separate library, and clearing browser data removes saves. They are not written into this Git repository.

The eight-cell track page includes separate concept 3MFs for its casing, cells, reset and two drive arms under `exports/eight-cell/`. Its drive arms share CAD with the browser: a 225 mm short arm with PK244M-03BA shaft clamp and a 550 mm connecting arm with a bearing seat. Bearing width, printed fits and mechanical performance remain provisional; see [eight-cell notes](cad/eight-cell/README.md).

## Rebuild the CAD and 3MF files

Requires Node.js, npm and Python 3:

```sh
npm ci
npm run build:cad
npm run check
```

CAD uses Manifold for joined solid bodies and subtracted holes. Generated 3MFs use millimeters and contain geometry only, without slicer profiles. Open individual `*_DRAFT.3mf` files in a slicer to choose print orientation and settings. Assembly files preserve the assembled positions and include bought hardware envelopes; they are for inspection.

Servo/reset has ten printed bodies: the standalone servo docking base, removable cell base with integrated supports and stem guide, reading plate, catch carrier, and six ball-seat plungers. The cell base, plate and carrier come from the same CAD as a rail cell, translated down 20 mm; the plungers and bought 5 mm steel balls are also shared. The module seats on four locating posts for standalone use and can be installed in the rail casing. All 28 assembly bodies are connected solids. Mesh validation does not validate mechanical performance.

Dimensions and tolerances are provisional. Test a single catch and pin before printing the full mechanism. The flex animation illustrates intent, and the model has no force, fatigue or collision simulation. Verify SG90 dimensions, mounting, catch material, friction and gravity return. The four-part drive bearing width and shaft fit also need confirmation. See [design notes](docs/design-notes.md).

## References and licenses

The Readable reconstruction includes the author manuscript, documented measurements and approximation notes under `web/documents/`. It is independently reconstructed geometry, not the authors' original CAD. Third-party manuscript rights remain with the authors/publisher. The servo/reset catch mechanism is a new concept inspired by six-servo actuation and guided pins.

Three.js is vendored under its MIT license in `web/vendor/THREE-LICENSE.txt`. Manifold is an npm dependency under its own license. This repository does not grant additional rights to reference documents.

## Learning companion design preview

Open `/learn/` on the local server (for example http://127.0.0.1:8094/learn/ after running `python3 scripts/serve.py --port 8094`). The mobile-first static companion includes four demo activities, browser-local learning progress, optional browser speech, and clearly unintegrated camera, Braille, and voice-input connectors. Source lives in `web/learn/`; design and audit notes are in `docs/companion-design.txt`.

## Cane vision

`cane-vision/` is a separate Python component. A camera fixed to the cane sees what the tip touches. YOLO identifies the object, a voice says what it is (ElevenLabs with a local fallback), and the word is spelled letter by letter on the single six-dot cell. Touch sensing is not connected yet, so a key press stands in for a tap. The word goes to the servo cell when its Arduino is plugged in, and to the terminal and preview window otherwise. See [cane-vision/README.md](cane-vision/README.md).

## Braille cell firmware

`cell-firmware/` is the Arduino Uno sketch for the six-servo cell, one servo per dot on D2–D7. The board stores the Braille table, the letter timing and each servo's calibrated up/down positions. Any host sends `SPELL chair` over USB serial and the board spells it letter by letter, clearing between letters. The logic is plain C++, so it has host tests and a simulator. It compiles for the Uno but has not yet been run on real servos. See [cell-firmware/README.md](cell-firmware/README.md) for wiring, calibration and the command list.
