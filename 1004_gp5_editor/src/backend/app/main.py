from __future__ import annotations

import copy
import os
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import guitarpro
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
from pydantic import BaseModel

app = FastAPI(title="GP5 Editor API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Prototype-only in-memory sessions. Production should use managed temp storage
# with quotas, expiry, and per-user isolation.
SESSIONS: dict[str, dict[str, Any]] = {}
ALLOWED_SUFFIXES = {".gp3", ".gp4", ".gp5"}


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _track_summary(track: Any, index: int) -> dict[str, Any]:
    measures = getattr(track, "measures", []) or []
    channel = getattr(track, "channel", None)
    instrument = getattr(channel, "instrument", None)
    return {
        "index": index,
        "name": str(getattr(track, "name", f"Track {index + 1}")),
        "measureCount": len(measures),
        "instrument": _safe_int(instrument, -1),
        "isPercussionTrack": bool(getattr(track, "isPercussionTrack", False)),
        "tuning": [getattr(string, "value", None) for string in (getattr(track, "strings", []) or [])],
    }


def _song_summary(song: Any, session_id: str) -> dict[str, Any]:
    tracks = list(getattr(song, "tracks", []) or [])
    tempo = getattr(song, "tempo", None)
    return {
        "sessionId": session_id,
        "title": str(getattr(song, "title", "") or "Untitled"),
        "subtitle": str(getattr(song, "subtitle", "") or ""),
        "artist": str(getattr(song, "artist", "") or ""),
        "album": str(getattr(song, "album", "") or ""),
        "tempo": _safe_int(tempo, 120),
        "trackCount": len(tracks),
        "tracks": [_track_summary(track, i) for i, track in enumerate(tracks)],
    }


class DuplicateTrackRequest(BaseModel):
    new_name: str | None = None


@app.get("/api/health")
def health():
    return {"ok": True, "service": "gp5-editor-api", "version": "0.1.0"}


@app.post("/api/sessions")
async def create_session(file: UploadFile = File(...)):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(415, "Please upload a .gp3, .gp4, or .gp5 file.")

    data = await file.read()
    if not data:
        raise HTTPException(400, "The uploaded file is empty.")
    if len(data) > 30 * 1024 * 1024:
        raise HTTPException(413, "Prototype upload limit is 30 MB.")

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    temp_path = Path(tmp.name)
    try:
        tmp.write(data)
        tmp.close()
        try:
            song = guitarpro.parse(str(temp_path))
        except Exception as exc:
            raise HTTPException(422, f"Could not parse Guitar Pro file: {exc}") from exc
    finally:
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            pass

    session_id = uuid.uuid4().hex
    SESSIONS[session_id] = {
        "song": song,
        "original_bytes": data,
        "filename": file.filename or f"score{suffix}",
    }
    return _song_summary(song, session_id)


@app.get("/api/sessions/{session_id}")
def get_session(session_id: str):
    session = SESSIONS.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found. Upload the file again.")
    return _song_summary(session["song"], session_id)


@app.post("/api/sessions/{session_id}/tracks/{track_index}/duplicate")
def duplicate_track(session_id: str, track_index: int, request: DuplicateTrackRequest):
    session = SESSIONS.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found.")
    song = session["song"]
    tracks = getattr(song, "tracks", None)
    if tracks is None or track_index < 0 or track_index >= len(tracks):
        raise HTTPException(404, "Track index not found.")

    cloned = copy.deepcopy(tracks[track_index])
    source_name = str(getattr(cloned, "name", f"Track {track_index + 1}"))
    cloned.name = request.new_name or f"{source_name} Copy"

    # Do not silently allocate a new MIDI channel here: GP5 channel routing,
    # percussion channel 9, and shared channels need a deliberate policy.
    # The clone keeps source routing until the user explicitly changes it.
    tracks.append(cloned)
    return _song_summary(song, session_id)


@app.get("/api/sessions/{session_id}/download")
def download_session(session_id: str, format: str = "gp5"):
    session = SESSIONS.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found.")
    if format.lower() != "gp5":
        raise HTTPException(400, "Only GP5 output is currently exposed.")

    fd, output_name = tempfile.mkstemp(suffix=".gp5")
    os.close(fd)
    output_path = Path(output_name)
    try:
        try:
            guitarpro.write(session["song"], str(output_path), version=(5, 1, 0))
        except TypeError:
            # Some PyGuitarPro releases infer the output version from the
            # requested format or use a slightly different writer signature.
            guitarpro.write(session["song"], str(output_path))
        except Exception as exc:
            output_path.unlink(missing_ok=True)
            raise HTTPException(422, f"Could not serialize GP5: {exc}") from exc
    except Exception:
        output_path.unlink(missing_ok=True)
        raise

    original = Path(session["filename"]).stem or "score"
    return FileResponse(
        output_path,
        media_type="application/octet-stream",
        filename=f"{original}_edited.gp5",
        background=BackgroundTask(output_path.unlink, missing_ok=True),
    )
