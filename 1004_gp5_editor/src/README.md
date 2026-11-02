# GP5 Editor — prototype 0.1

A starter project for a cross-platform Guitar Pro 5 player/editor.

## What this prototype includes
- FastAPI backend with GP3/GP4/GP5 import through PyGuitarPro
- Song/track metadata endpoint
- Track duplication endpoint (deep copy of the selected track)
- GP5 save endpoint
- React + alphaTab frontend scaffold for score rendering and playback
- Browser print stylesheet for PDF output (`Print / Save as PDF`)
- Windows packaging direction using Tauri (not yet wired into a release build)

## Important status
This is an **engineering prototype**, not a finished Guitar Pro replacement.
The following still require implementation and validation:
- direct note/fret editing UI and commands
- measure-range copy/paste
- robust track channel/instrument reassignment on duplicate
- undo/redo
- fidelity tests for bends, tuplets, repeats, alternate endings, effects and GP5 round trips
- automated PDF export with page-layout controls
- Tauri desktop packaging and a production web deployment

The backend deliberately reports unsupported operations rather than silently changing score data.

## Requirements
- Python 3.10+
- Node.js 20+
- A GP5 file for testing

## Start both servers

On Windows, double-click **start.bat** in the project root. No virtual environment
activation is required. Backend and frontend logs appear in the same window.
Once **Ready** appears, open **http://127.0.0.1:5173/**. Keep the window open and
press **Ctrl+C** there to stop both servers. If Windows asks to terminate the
batch job, answer `Y`. An occupied port 8000 or 5173 stops startup rather than
opening a second copy or silently choosing a different frontend port.

The launcher expects the existing backend `.venv`, frontend `node_modules`, and
Node.js on PATH. It installs nothing automatically. To inspect startup without
running the servers: `backend\.venv\Scripts\python.exe scripts\dev.py --check`.

### macOS

The React/Vite frontend and FastAPI/PyGuitarPro backend have no Windows-only
application code. The browser version is expected to work on both Apple Silicon
and Intel Macs, but has not been run on macOS in this workspace. Native desktop
packaging is still not implemented. Use a current Chrome or Safari and click
**Play** to start audio.

Install Python 3.13 and Node.js (Node 26 matches the development environment and
the TypeScript-based Node checks). Copy or clone the source, excluding `.venv`,
`.venv.before-*`, `.python-runtime`, `node_modules` and `dist`. Reinstall on the Mac;
Windows Python executables and native npm packages cannot be reused there.

From the project root, perform this one-time setup:

```bash
cd backend
python3.13 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
cd ../frontend
npm ci
cd ..
chmod +x start.command
```

Then double-click **start.command**, or run `bash start.command` from Terminal.
It uses the same ports and stops both servers with **Ctrl+C**. The launcher paths
are resolved from its own location, including project directories containing
spaces. Existing Undo/Redo shortcuts remain **Ctrl+Z / Ctrl+Shift+Z** on Mac.

If the project is moved after setup, recreate `.venv` and reinstall the backend
dependencies. Font and SoundFont assets are bundled under frontend/public and
do not require Windows paths or a remote sound service.

## Run the backend
```bash
cd backend
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux:
# source .venv/bin/activate
pip install -e .
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Health check: http://127.0.0.1:8000/api/health

### Windows startup and moving the project

From the project root, run `powershell -ExecutionPolicy Bypass -File .\backend\start.ps1`.
This uses the backend's own Python directly, so activating a virtual environment
is optional. From `backend`, run
`.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload`.

After moving the project, rebuild the virtual environment rather than copying
its launchers: `powershell -ExecutionPolicy Bypass -File .\backend\setup.ps1`.
The setup script uses the local `.python-runtime` when present; otherwise supply
`-Python C:\path\to\python.exe` for a working Python 3.13 installation. It preserves
the old `.venv` as `.venv.before-<id>` and reinstalls the declared dependencies.
The local runtime and environment backups are excluded from Git.

Close and reopen any terminal that still has the old virtual environment active,
or run `deactivate` before activating the new `.venv`. Do not commit or copy
`.venv`, `node_modules`, or `dist` when transferring the source to another machine;
recreate the backend environment and run `npm ci` in `frontend` instead.

## Run the frontend
In another terminal:
```bash
cd frontend
npm install
npm run dev
```
Open the Vite URL (normally http://localhost:5173).

The frontend expects the backend at `http://127.0.0.1:8000`. Set `VITE_API_BASE` if needed.

## Current workflow
1. Choose a `.gp3`, `.gp4`, or `.gp5` file in the frontend.
2. The backend parses it and returns a temporary session ID and metadata.
3. alphaTab loads the original file bytes for score display and playback.
4. Use **Duplicate selected track** to create a deep-copied track in the backend session.
5. Use **Save GP5** to download the modified song.

Note: alphaTab playback requires a SoundFont. The frontend is configured to load the alphaTab demo SoundFont URL. For an offline Windows build, bundle a legally distributable `.sf2` file locally and point `player.soundFont` to it.

## PDF
Use **Print / PDF**. The app calls alphaTab's print renderer, which opens an A4-oriented print view; choose **Save as PDF** in the browser print dialog. Page breaks and score layout still need testing on long scores.

## Architecture
- `frontend/`: React, TypeScript, alphaTab
- `backend/`: FastAPI and PyGuitarPro
- API is intentionally small and JSON-based so the same engine can later be hosted or launched locally by Tauri.

## API
- `GET /api/sessions/{id}/editing` — revision and note selection mapping
- `POST /api/sessions/{id}/fret` — validated single-note fret edit
- `POST /api/sessions/{id}/history/undo` and `/history/redo` — fret history
- `GET /api/health`
- `POST /api/sessions` — multipart upload of a Guitar Pro file
- `GET /api/sessions/{id}` — song and track metadata
- `POST /api/sessions/{id}/tracks/{track_index}/duplicate`
- `GET /api/sessions/{id}/download?format=gp5`

Sessions are held in memory and disappear when the backend restarts. Do not use this prototype as a permanent file store.

## First note editing increment
Enter **edit mode**, double-click an ordinary TAB note, enter a fret number, and click **Apply fret** while
playback is stopped. The input opens beside the selected TAB note; Enter applies
the value and Escape or **Cancel** closes it without changing the score.
The backend validates the change by writing and reopening
GP5 before committing it. The frontend then reloads that revision for display and
playback. **Save GP5** downloads the server's edited song.

Percussion, ties, grace notes, effect-bearing notes and ambiguous mappings are
excluded from this first increment. String changes, adding/deleting notes,
duration changes are not implemented. Track selection changes only
the displayed track; it does not change solo state. Track duplication also reloads
the server score so that the new track can be selected.

**Ctrl+Z** and **Ctrl+Shift+Z** restore fret edits and measure pastes in session order, across tracks. Each
transition uses the same GP5 validation and display/playback reload as a new edit.
New edits discard the redo branch; unchanged values do not create history.
History retains up to 1,000 editing operations and is reset on opening a file or
duplicating a track. Track duplication itself is not undoable in this increment.
The history is temporary, is not embedded in downloaded GP5 files, and is lost
when the backend restarts. History actions are disabled during playback or loading.

Keyboard shortcuts: **Ctrl+Z** undoes and **Ctrl+Shift+Z** redoes a score edit.
When an input is focused, these keys retain the browser's native input undo.
Holding a shortcut does not repeatedly submit history requests.

**Space** toggles playback and pause, retaining the current position when paused.
Shortcuts leave focused inputs and native button activation alone. The compact
top row keeps **Play/Pause**, **Stop**, and **Enter/Exit edit mode** on the left and the
SoundFont controls immediately before the GP file actions on the right. It stays
sticky while the score scrolls. **Duplicate selected track** is shown only in edit
mode. Space remains available alongside the Play/Pause button; Undo/Redo use shortcuts.

The playback cursor sweeps at a constant visual speed within each measure,
using its actual playback duration (including tempo changes and repeats).
It resynchronizes at measure boundaries; different measure widths/durations can
produce different speeds between measures. The cursor can pass between note
positions because notation spacing is not proportional to time. Note highlighting
continues to follow the actual notes. Audio timing and saved GP5 data are unchanged.
Frontend logic checks: `node scripts/check-history-shortcuts.mjs` and
`node scripts/check-bar-cursor.mjs` from `frontend`.

## External SoundFonts

Use **SoundFont**, left of **Open GP file**, to select a local `.sf2` or `.sf3` file. The file is read
directly in the browser and replaces the current bank for all tracks. Playback
stops during replacement; press **Space** once loading finishes. A General MIDI
bank is recommended so the score's instrument programs and drums are available.
Single-instrument banks may leave other tracks silent or use unexpected sounds.

**Default** reloads the bundled `sonivox.sf2`. Failed replacement
attempts restore the previous bank where possible and show an error separately
from the score. SoundFont selection persists across opening scores in the same
page, but refresh returns to the bundled default. SoundFonts are not uploaded to
the backend or embedded in exported GP5 files. No extra dependency is required.

Run `node scripts/check-soundfont.mjs` in `frontend` to verify selection validation,
completion/failure handling, and SF2/SF3 decoding with the installed alphaTab synth.

## Track mixer and instruments

Each track has independent view-selection, **Solo**, **Mute**, and an initial
instrument selector. Solo/Mute can be changed during playback. Instrument changes
require playback to be stopped and reload the score's MIDI through the saved GP5.
Selections use actual SF2/SF3 preset names; banks 0-127 are offered for melodic
tracks and 128-255 for percussion. Larger bank numbers cannot be saved in GP5's
byte-sized bank field and are excluded. Existing in-song instrument changes are
preserved, so they can override the initial instrument later in the score.

GP5/alphaTab route playback by primary and effect MIDI channels. Tracks sharing
either channel are marked **Linked** and their mixer/instrument changes apply
together. New melodic track duplicates now receive their own unused primary and
effect channel pair, so their Solo, Mute and instrument settings are independent.
To repair an existing linked copy, enter edit mode and click **Unlink** on the
track to move to private channels. This preserves its notes and instrument and
does not reassign other tracks. Save GP5 to retain the new routing after reopening.
If no private pair is available in GP5's 64 slots, the operation fails without
changing the score. Percussion slots are reserved; independent drum duplication
and unlinking are not yet supported because alphaTab consolidates percussion to
channel 9 when importing. Those controls are disabled for drum tracks.
Changes to program, bank, Solo and Mute are written to the server model and
validated by GP5 serialization/reopening. They survive fret editing and score
reloads. Undo/Redo currently covers fret edits and measure pastes, not mixer or instrument changes;
an instrument change clears the fret redo branch.

The score is isolated in its own stacking context so alphaTab's internal cursor
layer cannot cover the sticky toolbar. Run `node scripts/check-track-controls.mjs`
to check preset metadata and mixer restoration; backend tests also load exported
track settings into alphaTab and verify generated MIDI program changes. Routing
tests also synthesize audio with only the original enabled, only its copy enabled,
and both muted to verify independent mute behaviour.

## File picker locations and edit mode

In Chrome/Edge on localhost, **Open GP file** and **SoundFont** use distinct File
System Access picker IDs. The browser remembers each button's last-used directory
separately, including across refreshes. Use the same browser profile and origin
(for example, consistently use `http://127.0.0.1:5173`). Clearing browser data or
browser privacy policy can reset these locations. Browsers without
`showOpenFilePicker` use ordinary file inputs; independent directory memory is
not guaranteed there. No absolute file paths are uploaded or stored by the app.

Open a score, then click **Enter edit mode**. A single click on a beat/note selects
its whole measure and shows a dashed outline. **Shift+click** another measure to
select the inclusive range from the original anchor. Further Shift+clicks extend
or shrink that range in either direction. A normal click starts a new selection;
changing tracks starts a separate selection on that track.
**Ctrl+C** captures the selected range's note/rhythm data in the session clipboard.
Select a destination start measure on the same or another track, then **Ctrl+V**.
Paste **overwrites** the same number of existing destination measures starting at
that selection's first measure; it never inserts measures or shifts later ones.
Selecting a larger destination range does not tile/repeat the clipboard.
If there are too few destination measures, nothing is changed. Destination
time signature, repeat markers and other measure-header data stay in place.
Use **Ctrl+Z / Ctrl+Shift+Z** to undo/redo the whole paste in one step. Double-click a note to open
the fret editor. Inputs retain their native text-copy/paste shortcuts.

Measure-range paste works within the current session, with matching
tuning/string count/capo/percussion type and time
signature. Ties, hammer-ons, slides, grace notes, bends and other note effects are
copied intact rather than rejected at copy time. Ties which enter or leave the
pasted range must retain their pitch: the whole affected track is compared after
GP5 serialization, including neighbouring measures. A mismatched tie reports the
track/bar and leaves the score unchanged; include its origin in the copied range
or choose a compatible destination.

Note/rhythm copy excludes source tempo/instrument/mixer changes and reports this
in its result. Destination controller changes are retained at their original
relative ticks. If the copied rhythm has no beat at one of those ticks, paste is
rejected with a specific explanation rather than dropping the controller or moving
it in time. The complete range is checked and GP5-validated before committing.
Operation status and API rejection reasons are shown below the sticky top row.
alphaTab's `Unsupported bend type detected, fallback to custom` warning does not
itself fail a copy request; it indicates that its model uses a custom bend curve.
The app clipboard is a snapshot, does not touch the OS clipboard, and is cleared
when a new file is opened. Editing requires stopped playback; exiting edit mode
hides note/measure editing and track duplication while leaving playback/mixing available.

Checks: `node scripts/check-file-picker.mjs` and
`node scripts/check-measure-shortcuts.mjs`, plus `node scripts/check-measure-selection.mjs`
from `frontend`; run backend pytest
for paste compatibility, rollback, mixed fret/paste history and alphaTab reopening.

If synchronization fails, use **Reload server score** before editing again.
An edit may already be saved in the session even if its response or rendering
fails. Sessions remain temporary and are lost when the backend stops.

Backend checks: `cd backend` then `python -m pytest -q`. With Node.js 26 and the
frontend dependencies installed, these checks also load generated GP5 fixtures
through alphaTab 1.8.4 and verify the note mapping. Frontend check:
`cd frontend` then `npm run build` (use `npm.cmd` in PowerShell if required).
