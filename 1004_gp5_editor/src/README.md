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
- `GET /api/health`
- `POST /api/sessions` — multipart upload of a Guitar Pro file
- `GET /api/sessions/{id}` — song and track metadata
- `POST /api/sessions/{id}/tracks/{track_index}/duplicate`
- `GET /api/sessions/{id}/download?format=gp5`

Sessions are held in memory and disappear when the backend restarts. Do not use this prototype as a permanent file store.
