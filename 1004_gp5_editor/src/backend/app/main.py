from __future__ import annotations

import copy
import io
import os
import tempfile
import uuid
from threading import RLock
from pathlib import Path
from typing import Any, Literal

import guitarpro
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
from pydantic import BaseModel, Field

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
EDIT_LOCK = RLock()
HISTORY_LIMIT = 1000


def _notes(session):
    """Session IDs stay stable while this first editor only changes frets."""
    result = []
    for ti, track in enumerate(session["song"].tracks):
        tied = set()
        previous = {}
        for mi, measure in enumerate(track.measures):
            for vi, voice in enumerate(measure.voices):
                for bi, beat in enumerate(voice.beats):
                    for ni, note in enumerate(beat.notes):
                        key = (ti, mi, vi, bi, ni)
                        if note.type == guitarpro.models.NoteType.tie:
                            tied.add(key)
                            if (vi, note.string) in previous:
                                tied.add(previous[(vi, note.string)])
                        previous[(vi, note.string)] = key
        for mi, measure in enumerate(track.measures):
            rendered_voice = 0
            for vi, voice in enumerate(measure.voices):
                if not voice.beats:
                    continue  # alphaTab omits voices with zero beats.
                unsafe = any(n.type == guitarpro.models.NoteType.tie or n.effect.grace
                             for b in voice.beats for n in b.notes)
                voice_shape = [[[len(track.strings) + 1 - x.string, x.value] for x in b.notes] for b in voice.beats]
                for bi, beat in enumerate(voice.beats):
                    for ni, note in enumerate(beat.notes):
                        key = (ti, mi, vi, bi, ni)
                        note_id = session["note_ids"].setdefault(key, uuid.uuid4().hex)
                        editable = (not track.isPercussionTrack and not unsafe and key not in tied
                                    and beat.status == guitarpro.models.BeatStatus.normal
                                    and note.type == guitarpro.models.NoteType.normal
                                    and note.effect == guitarpro.models.NoteEffect()
                                    and beat.effect == guitarpro.models.BeatEffect()
                                    and 1 <= note.string <= len(track.strings))
                        result.append({"id": note_id, "track": ti, "bar": mi,
                                       "voice": rendered_voice, "beat": bi,
                                       "string": len(track.strings) + 1 - note.string,
                                       "fret": note.value, "maxFret": min(track.fretCount, 99),
                                       "voiceShape": voice_shape,
                                       "editable": editable, "path": key})
                rendered_voice += 1
    return result


def _editing_state(session):
    notes = []
    voices = {}
    for note in _notes(session):
        voice_key = f'{note["track"]}:{note["bar"]}:{note["voice"]}'
        voices[voice_key] = note["voiceShape"]
        notes.append({k: v for k, v in note.items() if k not in {"path", "voiceShape"}})
    return {"revision": session["revision"], "notes": notes, "voices": voices,
            "canUndo": bool(session["undo"]), "canRedo": bool(session["redo"])}



class HistoryRequest(BaseModel):
    commandId: str = Field(min_length=1, max_length=100)
    expectedRevision: int = Field(ge=0, strict=True)


class FretRequest(HistoryRequest):
    noteId: str
    fret: int = Field(ge=0, le=99, strict=True)


def _validated_fret_song(song, path, fret):
    """Validate before committing either a new edit or a history transition."""
    candidate = copy.deepcopy(song)
    ti, mi, vi, bi, ni = path
    candidate.tracks[ti].measures[mi].voices[vi].beats[bi].notes[ni].value = fret
    try:
        stream = io.BytesIO()
        guitarpro.write(candidate, stream, version=(5, 1, 0))
        stream.seek(0)
        parsed = guitarpro.parse(stream)
        if parsed.tracks[ti].measures[mi].voices[vi].beats[bi].notes[ni].value != fret:
            raise ValueError("Fret did not survive GP5 serialization")
    except Exception as exc:
        raise HTTPException(422, f"GP5 validation failed: {exc}") from exc
    return candidate


@app.post("/api/sessions/{session_id}/history/{direction}")
def change_history(session_id: str, direction: Literal["undo", "redo"], request: HistoryRequest):
    with EDIT_LOCK:
        session = SESSIONS.get(session_id)
        if not session:
            raise HTTPException(404, "Session not found.")
        command = {"operation": direction, **request.model_dump()}
        if request.commandId in session["commands"]:
            if session["commands"][request.commandId] != command:
                raise HTTPException(409, "Command ID already used.")
            return _editing_state(session)
        if request.expectedRevision != session["revision"]:
            raise HTTPException(409, "Score changed. Reload before editing.")
        source, destination = (session["undo"], session["redo"]) if direction == "undo" else (session["redo"], session["undo"])
        if not source:
            raise HTTPException(409, f"Nothing to {direction}.")
        entry = source[-1]
        target = next((n for n in _notes(session) if n["id"] == entry["noteId"]), None)
        expected = entry["after"] if direction == "undo" else entry["before"]
        fret = entry["before"] if direction == "undo" else entry["after"]
        if not target or target["path"] != entry["path"] or target["fret"] != expected:
            raise HTTPException(409, "History no longer matches the score.")
        candidate = _validated_fret_song(session["song"], entry["path"], fret)
        session["song"] = candidate
        source.pop()
        destination.append(entry)
        session["revision"] += 1
        session["commands"][request.commandId] = command
        return _editing_state(session)


@app.get("/api/sessions/{session_id}/editing")
def editing_state(session_id: str):
    with EDIT_LOCK:
        if session_id not in SESSIONS:
            raise HTTPException(404, "Session not found.")
        return _editing_state(SESSIONS[session_id])


@app.post("/api/sessions/{session_id}/fret")
def edit_fret(session_id: str, request: FretRequest):
    with EDIT_LOCK:
        session = SESSIONS.get(session_id)
        if not session:
            raise HTTPException(404, "Session not found.")
        if request.commandId in session["commands"]:
            if session["commands"][request.commandId] != request.model_dump():
                raise HTTPException(409, "Command ID already used.")
            return _editing_state(session)
        if request.expectedRevision != session["revision"]:
            raise HTTPException(409, "Score changed. Reload before editing.")
        target = next((n for n in _notes(session) if n["id"] == request.noteId), None)
        if not target:
            raise HTTPException(404, "Note not found.")
        if not target["editable"] or request.fret > target["maxFret"]:
            raise HTTPException(422, "Only ordinary notes within the track fret range can be edited.")
        if target["fret"] == request.fret:
            session["commands"][request.commandId] = request.model_dump()
            return _editing_state(session)
        candidate = _validated_fret_song(session["song"], target["path"], request.fret)
        session["song"] = candidate
        session["undo"].append({"noteId": target["id"], "path": target["path"],
                                "before": target["fret"], "after": request.fret})
        del session["undo"][:-HISTORY_LIMIT]
        session["redo"].clear()
        session["revision"] += 1
        session["commands"][request.commandId] = request.model_dump()
        return _editing_state(session)


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
        "revision": 0,
        "note_ids": {},
        "commands": {},
        "undo": [],
        "redo": [],
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
    with EDIT_LOCK:
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
        # A deep copied track must point back to the active song.
        cloned.song = song
        cloned.number = len(tracks) + 1
        for measure, header in zip(cloned.measures, song.measureHeaders):
            measure.header = header
        tracks.append(cloned)
        # Structural edits are outside this first fret-only history.
        session["undo"].clear()
        session["redo"].clear()
        session["revision"] += 1
        return _song_summary(song, session_id)


@app.get("/api/sessions/{session_id}/download")
def download_session(session_id: str, format: str = "gp5", revision: int | None = None):
    with EDIT_LOCK:
        session = SESSIONS.get(session_id)
        if not session:
            raise HTTPException(404, "Session not found.")
        if revision is not None and revision != session["revision"]:
            raise HTTPException(409, "Score changed. Reload before editing.")
        snapshot = copy.deepcopy(session["song"])
        filename = session["filename"]
    if format.lower() != "gp5":
        raise HTTPException(400, "Only GP5 output is currently exposed.")

    fd, output_name = tempfile.mkstemp(suffix=".gp5")
    os.close(fd)
    output_path = Path(output_name)
    try:
        try:
            guitarpro.write(snapshot, str(output_path), version=(5, 1, 0))
        except TypeError:
            # Some PyGuitarPro releases infer the output version from the
            # requested format or use a slightly different writer signature.
            guitarpro.write(snapshot, str(output_path))
        except Exception as exc:
            output_path.unlink(missing_ok=True)
            raise HTTPException(422, f"Could not serialize GP5: {exc}") from exc
    except Exception:
        output_path.unlink(missing_ok=True)
        raise

    original = Path(filename).stem or "score"
    return FileResponse(
        output_path,
        media_type="application/octet-stream",
        filename=f"{original}_edited.gp5",
        background=BackgroundTask(output_path.unlink, missing_ok=True),
    )
