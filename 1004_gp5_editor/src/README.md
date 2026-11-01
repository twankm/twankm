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
Click an ordinary TAB note, enter a fret number, and click **Apply fret** while
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

**Undo** and **Redo** restore fret edits in session order, across tracks. Each
transition uses the same GP5 validation and display/playback reload as a new edit.
New edits discard the redo branch; unchanged values do not create history.
History retains up to 1,000 fret changes and is reset on opening a file or
duplicating a track. Track duplication itself is not undoable in this increment.
The history is temporary, is not embedded in downloaded GP5 files, and is lost
when the backend restarts. History actions are disabled during playback or loading.

Keyboard shortcuts: **Ctrl+Z** undoes and **Ctrl+Shift+Z** redoes a score edit.
When an input is focused, these keys retain the browser's native input undo.
Holding a shortcut does not repeatedly submit history requests.

The playback cursor sweeps at a constant visual speed within each measure,
using its actual playback duration (including tempo changes and repeats).
It resynchronizes at measure boundaries; different measure widths/durations can
produce different speeds between measures. The cursor can pass between note
positions because notation spacing is not proportional to time. Note highlighting
continues to follow the actual notes. Audio timing and saved GP5 data are unchanged.
Frontend logic checks: `node scripts/check-history-shortcuts.mjs` and
`node scripts/check-bar-cursor.mjs` from `frontend`.

## External SoundFonts

Use **Load SoundFont** to select a local `.sf2` or `.sf3` file. The file is read
directly in the browser and replaces the current bank for all tracks. Playback
stops during replacement; press **Play** once loading finishes. A General MIDI
bank is recommended so the score's instrument programs and drums are available.
Single-instrument banks may leave other tracks silent or use unexpected sounds.

**Use default SoundFont** reloads the bundled `sonivox.sf2`. Failed replacement
attempts restore the previous bank where possible and show an error separately
from the score. SoundFont selection persists across opening scores in the same
page, but refresh returns to the bundled default. SoundFonts are not uploaded to
the backend or embedded in exported GP5 files. No extra dependency is required.

Run `node scripts/check-soundfont.mjs` in `frontend` to verify selection validation,
completion/failure handling, and SF2/SF3 decoding with the installed alphaTab synth.

If synchronization fails, use **Reload server score** before editing again.
An edit may already be saved in the session even if its response or rendering
fails. Sessions remain temporary and are lost when the backend stops.

Backend checks: `cd backend` then `python -m pytest -q`. With Node.js 26 and the
frontend dependencies installed, these checks also load generated GP5 fixtures
through alphaTab 1.8.4 and verify the note mapping. Frontend check:
`cd frontend` then `npm run build` (use `npm.cmd` in PowerShell if required).
