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
from .measure_edit import measure_at, detached_voices, attach_voices, validate_song, make_clipboard_range, paste_range_candidate
from .track_routing import assign_private_channels, validate_private_channels

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
    """Expose stable note identities with alphaTab string and voice indexes."""
    result = []
    for ti, track in enumerate(session["song"].tracks):
        for mi, measure in enumerate(track.measures):
            rendered_voice = 0
            for vi, voice in enumerate(measure.voices):
                if not voice.beats:
                    continue  # alphaTab omits voices with zero beats.
                voice_shape = [[[len(track.strings) + 1 - x.string, x.value] for x in b.notes] for b in voice.beats]
                for bi, beat in enumerate(voice.beats):
                    for ni, note in enumerate(beat.notes):
                        key = (ti, mi, vi, bi, ni)
                        note_id = session["note_ids"].setdefault(key, uuid.uuid4().hex)
                        editable = (not track.isPercussionTrack
                                    and beat.status == guitarpro.models.BeatStatus.normal
                                    and note.type in {guitarpro.models.NoteType.normal, guitarpro.models.NoteType.tie, guitarpro.models.NoteType.dead}
                                    and 1 <= note.string <= len(track.strings))
                        result.append({"id": note_id, "track": ti, "bar": mi,
                                       "voice": rendered_voice, "beat": bi,
                                       "string": len(track.strings) + 1 - note.string,
                                       "fret": note.value, "maxFret": min(track.fretCount, 99),
                                       "voiceShape": voice_shape,
                                       "kind": "note", "editable": editable, "path": key})
                        if note.effect.grace:
                            result.append({**result[-1], "id": note_id + ':grace', "kind": "grace", "fret": note.effect.grace.fret})
                rendered_voice += 1
    return result


def _editing_state(session):
    notes = []
    voices = {}
    for note in _notes(session):
        voice_key = f'{note["track"]}:{note["bar"]}:{note["voice"]}'
        voices[voice_key] = note["voiceShape"]
        notes.append({k: v for k, v in note.items() if k not in {"path", "voiceShape"}})
    beats = _beats(session)
    for beat in beats:
        voices[f'{beat["track"]}:{beat["bar"]}:{beat["voice"]}'] = beat['voiceShape']
    return {"revision": session["revision"], "notes": notes, "voices": voices,
            "beats": [{k: v for k, v in b.items() if k not in {'path', 'voiceShape'}} for b in beats],
            "canUndo": bool(session["undo"]), "canRedo": bool(session["redo"])}



def _beats(session):
    result = []
    for ti, track in enumerate(session['song'].tracks):
        for mi, measure in enumerate(track.measures):
            rendered = 0
            for vi, voice in enumerate(measure.voices):
                if not voice.beats:
                    continue
                shape = [[[len(track.strings) + 1 - n.string, n.value] for n in b.notes] for b in voice.beats]
                for bi, beat in enumerate(voice.beats):
                    result.append(dict(id=f'beat:{session["revision"]}:{ti}:{mi}:{vi}:{bi}', track=ti,
                                       bar=mi, voice=rendered, beat=bi, stringCount=len(track.strings),
                                       maxFret=min(track.fretCount, 99), path=(ti, mi, vi, bi), voiceShape=shape,
                                       rhythm=dict(value=beat.duration.value, dotted=beat.duration.isDotted,
                                                   tuplet=beat.duration.tuplet.enters),
                                       canAdd=not track.isPercussionTrack and beat.status != guitarpro.models.BeatStatus.empty))
                rendered += 1
    return result


def _commit_note_candidate(session, candidate, track, bars):
    parsed = validate_song(candidate)
    for expected, actual in zip(candidate.tracks[track].measures, parsed.tracks[track].measures):
        if detached_voices(expected) != detached_voices(actual):
            raise HTTPException(422, 'The edit would change other notes or effects when saved as GP5.')
    before_ids = _measure_id_groups(session, track, bars)
    changes = [dict(track=track, bar=bar, beforeVoices=detached_voices(session['song'].tracks[track].measures[bar]),
                    afterVoices=detached_voices(candidate.tracks[track].measures[bar]), beforeIds=before_ids[bar]) for bar in bars]
    # Preserve existing identities even when inserting a note shifts its list index.
    for bar in bars:
        old = session['song'].tracks[track].measures[bar]
        new = candidate.tracks[track].measures[bar]
        for vi, voice in enumerate(old.voices):
            for bi, beat in enumerate(voice.beats):
                identities = {n.string: session['note_ids'].get((track, bar, vi, bi, ni)) for ni, n in enumerate(beat.notes)}
                for path in list(session['note_ids']):
                    if path[:4] == (track, bar, vi, bi):
                        del session['note_ids'][path]
                for ni, note in enumerate(new.voices[vi].beats[bi].notes):
                    session['note_ids'][(track, bar, vi, bi, ni)] = identities.get(note.string) or uuid.uuid4().hex
    session['song'] = candidate
    after_ids = _measure_id_groups(session, track, bars)
    for change in changes:
        change['afterIds'] = after_ids[change['bar']]
    session['undo'].append({'kind': 'measures', 'measures': changes})
    del session['undo'][:-HISTORY_LIMIT]
    session['redo'].clear()
    session['revision'] += 1


class HistoryRequest(BaseModel):
    commandId: str = Field(min_length=1, max_length=100)
    expectedRevision: int = Field(ge=0, strict=True)


class FretRequest(HistoryRequest):
    noteId: str
    fret: int = Field(ge=0, le=99, strict=True)


class AddNoteRequest(HistoryRequest):
    beatId: str
    string: int = Field(ge=1, le=7, strict=True)
    fret: int = Field(ge=0, le=99, strict=True)


class NoteChange(BaseModel):
    kind: Literal['note', 'grace'] = 'note'
    string: int = Field(ge=1, le=7, strict=True)
    fret: int | None = Field(default=None, ge=0, le=99, strict=True)


class RhythmRequest(BaseModel):
    value: Literal[1, 2, 4, 8, 16, 32, 64, 128]
    dotted: bool = Field(strict=True)
    tuplet: Literal[1, 3, 5, 6, 7, 9, 10, 11, 12, 13]


class BeatEditRequest(HistoryRequest):
    beatId: str
    changes: list[NoteChange] = Field(default_factory=list, max_length=14)
    rhythm: RhythmRequest | None = None


@app.post('/api/sessions/{session_id}/beat-notes')
def edit_beat_notes(session_id: str, request: BeatEditRequest):
    with EDIT_LOCK:
        session = SESSIONS.get(session_id)
        if not session:
            raise HTTPException(404, 'Session not found.')
        command = {'operation': 'beat-notes', **request.model_dump()}
        if request.commandId in session['commands']:
            if session['commands'][request.commandId] != command:
                raise HTTPException(409, 'Command ID already used.')
            return _editing_state(session)
        if request.expectedRevision != session['revision']:
            raise HTTPException(409, 'Score changed. Reload before editing.')
        target = next((b for b in _beats(session) if b['id'] == request.beatId), None)
        if not target or not target['canAdd']:
            raise HTTPException(422, 'Select an editable beat.')
        if len({(c.kind, c.string) for c in request.changes}) != len(request.changes):
            raise HTTPException(422, 'Each string can be changed only once.')
        ti, mi, vi, bi = target['path']
        candidate = copy.deepcopy(session['song'])
        beat = candidate.tracks[ti].measures[mi].voices[vi].beats[bi]
        bars = {mi}
        if not request.changes and request.rhythm is None:
            raise HTTPException(422, 'Provide note or rhythm changes.')
        if request.rhythm is not None:
            rhythm = request.rhythm
            old_total = sum(b.duration.time for b in beat.voice.beats if b.status != guitarpro.models.BeatStatus.empty)
            times = dict(guitarpro.models.Tuplet.supportedTuplets)[rhythm.tuplet]
            beat.duration = guitarpro.models.Duration(value=rhythm.value, isDotted=rhythm.dotted,
                                                     tuplet=guitarpro.models.Tuplet(rhythm.tuplet, times))
            new_total = sum(b.duration.time for b in beat.voice.beats if b.status != guitarpro.models.BeatStatus.empty)
            if new_total > max(old_total, beat.voice.measure.header.length):
                raise HTTPException(422, 'This duration exceeds the measure length. Shorten another note first.')
            start = beat.voice.measure.start
            for following in beat.voice.beats:
                following.start = start
                if following.status != guitarpro.models.BeatStatus.empty:
                    start += following.duration.time
        for change in request.changes:
            if change.string > target['stringCount'] or (change.fret is not None and change.fret > target['maxFret']):
                raise HTTPException(422, 'String or fret is outside the track range.')
            string = target['stringCount'] + 1 - change.string
            note = next((n for n in beat.notes if n.string == string), None)
            if change.kind == 'grace':
                if not note or not note.effect.grace:
                    raise HTTPException(422, 'Grace note not found.')
                if change.fret is None:
                    note.effect.grace = None
                else:
                    note.effect.grace.fret = change.fret
            elif change.fret is None:
                if note:
                    chain = [(bar, n) for bar, m in enumerate(candidate.tracks[ti].measures)
                             for b in m.voices[vi].beats for n in b.notes if n.string == string]
                    index = next(i for i, (_, n) in enumerate(chain) if n is note)
                    if index + 1 < len(chain) and chain[index + 1][1].type == guitarpro.models.NoteType.tie:
                        bar, following = chain[index + 1]
                        # Removing an attack must not make the next tied note inherit
                        # the pitch of an unrelated earlier note on this string.
                        following.type = guitarpro.models.NoteType.normal
                        bars.add(bar)
                    beat.notes.remove(note)
            elif note:
                chain = [(bar, n) for bar, m in enumerate(candidate.tracks[ti].measures)
                         for b in m.voices[vi].beats for n in b.notes if n.string == string]
                start = next(i for i, (_, n) in enumerate(chain) if n is note)
                while start > 0 and chain[start][1].type == guitarpro.models.NoteType.tie:
                    start -= 1
                if chain[start][1].type == guitarpro.models.NoteType.tie:
                    raise HTTPException(422, 'This tie has no preceding note.')
                end = start + 1
                while end < len(chain) and chain[end][1].type == guitarpro.models.NoteType.tie:
                    end += 1
                for bar, linked in chain[start:end]:
                    linked.value = change.fret
                    bars.add(bar)
            else:
                beat.notes.append(guitarpro.models.Note(beat, string=string, value=change.fret, type=guitarpro.models.NoteType.normal))
        beat.notes.sort(key=lambda n: n.string)
        beat.status = guitarpro.models.BeatStatus.normal if beat.notes else guitarpro.models.BeatStatus.rest
        _commit_note_candidate(session, candidate, ti, sorted(bars))
        session['commands'][request.commandId] = command
        return _editing_state(session)


@app.post('/api/sessions/{session_id}/notes')
def add_note(session_id: str, request: AddNoteRequest):
    with EDIT_LOCK:
        session = SESSIONS.get(session_id)
        if not session:
            raise HTTPException(404, 'Session not found.')
        command = {'operation': 'add-note', **request.model_dump()}
        if request.commandId in session['commands']:
            if session['commands'][request.commandId] != command:
                raise HTTPException(409, 'Command ID already used.')
            return _editing_state(session)
        if request.expectedRevision != session['revision']:
            raise HTTPException(409, 'Score changed. Reload before editing.')
        target = next((b for b in _beats(session) if b['id'] == request.beatId), None)
        if not target or not target['canAdd'] or request.string > target['stringCount'] or request.fret > target['maxFret']:
            raise HTTPException(422, 'Select a valid beat, string and fret.')
        ti, mi, vi, bi = target['path']
        candidate = copy.deepcopy(session['song'])
        beat = candidate.tracks[ti].measures[mi].voices[vi].beats[bi]
        gp_string = target['stringCount'] + 1 - request.string
        if any(n.string == gp_string for n in beat.notes):
            raise HTTPException(409, 'This string already has a note at the selected beat.')
        beat.notes.append(guitarpro.models.Note(beat, value=request.fret, string=gp_string, type=guitarpro.models.NoteType.normal))
        beat.notes.sort(key=lambda n: n.string)
        beat.status = guitarpro.models.BeatStatus.normal
        _commit_note_candidate(session, candidate, ti, [mi])
        session['commands'][request.commandId] = command
        return _editing_state(session)


class MeasureCopyRequest(BaseModel):
    expectedRevision: int = Field(ge=0, strict=True)
    track: int = Field(ge=0, strict=True)
    bar: int = Field(ge=0, strict=True)
    count: int = Field(default=1, ge=1, strict=True)


class MeasurePasteRequest(HistoryRequest):
    clipboardId: str
    track: int = Field(ge=0, strict=True)
    bar: int = Field(ge=0, strict=True)


def _measure_id_groups(session, track, bars):
    _notes(session)
    groups = {bar: {} for bar in bars}
    for path, note_id in session['note_ids'].items():
        if path[0] == track and path[1] in groups:
            groups[path[1]][path] = note_id
    return groups


@app.post('/api/sessions/{session_id}/measures/copy')
def copy_measure(session_id: str, request: MeasureCopyRequest):
    with EDIT_LOCK:
        session = SESSIONS.get(session_id)
        if not session:
            raise HTTPException(404, 'Session not found.')
        if request.expectedRevision != session['revision']:
            raise HTTPException(409, 'Score changed. Reload before copying.')
        clipboard = make_clipboard_range(session['song'], request.track, request.bar, request.count)
        clipboard['id'] = uuid.uuid4().hex
        session['clipboard'] = clipboard
        return {'clipboardId': clipboard['id'], 'track': request.track, 'bar': request.bar,
                'count': request.count, 'excludedControllers': clipboard['excludedControllers']}


@app.post('/api/sessions/{session_id}/measures/paste')
def paste_measure(session_id: str, request: MeasurePasteRequest):
    with EDIT_LOCK:
        session = SESSIONS.get(session_id)
        if not session:
            raise HTTPException(404, 'Session not found.')
        command = {'operation': 'paste', **request.model_dump()}
        if request.commandId in session['commands']:
            if session['commands'][request.commandId] != command:
                raise HTTPException(409, 'Command ID already used.')
            return _editing_state(session)
        if request.expectedRevision != session['revision']:
            raise HTTPException(409, 'Score changed. Reload before pasting.')
        clipboard = session.get('clipboard')
        if not clipboard or clipboard['id'] != request.clipboardId:
            raise HTTPException(409, 'Clipboard expired. Copy the source measure again.')
        candidate = paste_range_candidate(session['song'], request.track, request.bar, clipboard)
        bars = range(request.bar, request.bar + clipboard.get('count', 1))
        before_ids = _measure_id_groups(session, request.track, bars)
        changes = [{'track': request.track, 'bar': bar,
                    'beforeVoices': detached_voices(measure_at(session['song'], request.track, bar)),
                    'beforeIds': before_ids[bar],
                    'afterVoices': detached_voices(measure_at(candidate, request.track, bar))} for bar in bars]
        session['song'] = candidate
        targets = {(request.track, bar) for bar in bars}
        session['note_ids'] = {p: note_id for p, note_id in session['note_ids'].items() if p[:2] not in targets}
        after_ids = _measure_id_groups(session, request.track, bars)
        for change in changes:
            change['afterIds'] = after_ids[change['bar']]
        session['undo'].append({'kind': 'measures', 'measures': changes})
        del session['undo'][:-HISTORY_LIMIT]
        session['redo'].clear()
        session['revision'] += 1
        session['commands'][request.commandId] = command
        return _editing_state(session)


class TrackSettingsRequest(HistoryRequest):
    instrument: int | None = Field(default=None, ge=0, le=127, strict=True)
    bank: int | None = Field(default=None, ge=0, le=255, strict=True)
    solo: bool | None = Field(default=None, strict=True)
    mute: bool | None = Field(default=None, strict=True)


def _channel_group(song, index):
    """Playback APIs act on both MIDI channels, not on a visual track alone."""
    group = {index}
    channels = set()
    while True:
        for i in group:
            channel = song.tracks[i].channel
            channels.update((channel.channel, channel.effectChannel))
        linked = {i for i, track in enumerate(song.tracks)
                  if channels.intersection((track.channel.channel, track.channel.effectChannel))}
        if linked <= group:
            return sorted(group)
        group.update(linked)


@app.post("/api/sessions/{session_id}/tracks/{track_index}/settings")
def change_track_settings(session_id: str, track_index: int, request: TrackSettingsRequest):
    with EDIT_LOCK:
        session = SESSIONS.get(session_id)
        if not session:
            raise HTTPException(404, "Session not found.")
        song = session["song"]
        if not 0 <= track_index < len(song.tracks):
            raise HTTPException(404, "Track not found.")
        changes = {key: value for key, value in request.model_dump().items()
                   if key in {"instrument", "solo", "mute"} and value is not None}
        if len(changes) != 1:
            raise HTTPException(422, "Change exactly one track setting per request.")
        if request.bank is not None and request.instrument is None:
            raise HTTPException(422, "Bank must be changed together with an instrument.")
        command = {"operation": "track-settings", "track": track_index, **request.model_dump()}
        if request.commandId in session["commands"]:
            if session["commands"][request.commandId] != command:
                raise HTTPException(409, "Command ID already used.")
            return {"song": _song_summary(session["song"], session_id), "editing": _editing_state(session)}
        if request.expectedRevision != session["revision"]:
            raise HTTPException(409, "Score changed. Reload before editing.")
        group = _channel_group(song, track_index)
        if request.instrument is not None and len({song.tracks[i].isPercussionTrack for i in group}) > 1:
            raise HTTPException(422, "A drum track and melodic track share channels; separate their routing before changing instruments.")
        candidate = copy.deepcopy(song)
        key, value = next(iter(changes.items()))
        for i in group:
            track = candidate.tracks[i]
            if key == "instrument":
                track.channel.instrument = value
                if request.bank is not None:
                    track.channel.bank = request.bank
            else:
                setattr(track, "isSolo" if key == "solo" else "isMute", value)
        try:
            stream = io.BytesIO()
            guitarpro.write(candidate, stream, version=(5, 1, 0))
            stream.seek(0)
            reopened = guitarpro.parse(stream)
            for i in group:
                track = reopened.tracks[i]
                actual = track.channel.instrument if key == "instrument" else getattr(track, "isSolo" if key == "solo" else "isMute")
                if actual != value:
                    raise ValueError("Track setting did not survive GP5 serialization")
                if key == "instrument" and request.bank is not None and track.channel.bank != request.bank:
                    raise ValueError("Instrument bank did not survive GP5 serialization")
        except Exception as exc:
            raise HTTPException(422, f"GP5 validation failed: {exc}") from exc
        session["song"] = candidate
        session["revision"] += 1
        if key == "instrument":
            session["redo"].clear()
        session["commands"][request.commandId] = command
        return {"song": _song_summary(candidate, session_id), "editing": _editing_state(session)}


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
        if entry.get('kind') in {'measure', 'measures'}:
            candidate = copy.deepcopy(session['song'])
            prefix = 'before' if direction == 'undo' else 'after'
            changes = entry['measures'] if entry['kind'] == 'measures' else [entry]
            for change in changes:
                attach_voices(measure_at(candidate, change['track'], change['bar']), change[prefix + 'Voices'])
            reopened = validate_song(candidate)
            for change in changes:
                if detached_voices(measure_at(reopened, change['track'], change['bar'])) != detached_voices(measure_at(candidate, change['track'], change['bar'])):
                    raise HTTPException(422, 'Measure history did not survive GP5 serialization.')
            session['song'] = candidate
            targets = {(change['track'], change['bar']) for change in changes}
            ids = {p: note_id for change in changes for p, note_id in change[prefix + 'Ids'].items()}
            session['note_ids'] = {p: note_id for p, note_id in session['note_ids'].items() if p[:2] not in targets} | ids
            source.pop()
            destination.append(entry)
            session['revision'] += 1
            session['commands'][request.commandId] = command
            return _editing_state(session)
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
            raise HTTPException(422, "Select a supported fretted note within the track fret range.")
        if target["fret"] == request.fret:
            session["commands"][request.commandId] = request.model_dump()
            return _editing_state(session)
        candidate = copy.deepcopy(session['song'])
        ti, mi, vi, bi, ni = target['path']
        selected = candidate.tracks[ti].measures[mi].voices[vi].beats[bi].notes[ni]
        bars = {mi}
        if target['kind'] == 'grace':
            selected.effect.grace.fret = request.fret
        else:
            # A tied note inherits pitch from the preceding note on its string.
            chain = [(bar, n) for bar, m in enumerate(candidate.tracks[ti].measures)
                     for b in m.voices[vi].beats for n in b.notes if n.string == selected.string]
            index = next(i for i, (_, n) in enumerate(chain) if n is selected)
            start = index
            while start > 0 and chain[start][1].type == guitarpro.models.NoteType.tie:
                start -= 1
            if chain[start][1].type == guitarpro.models.NoteType.tie:
                raise HTTPException(422, 'This tie has no preceding note.')
            end = start + 1
            while end < len(chain) and chain[end][1].type == guitarpro.models.NoteType.tie:
                end += 1
            for bar, note in chain[start:end]:
                note.value = request.fret
                bars.add(bar)
        _commit_note_candidate(session, candidate, ti, sorted(bars))
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
    shared = _channel_group(track.song, index)
    return {
        "index": index,
        "name": str(getattr(track, "name", f"Track {index + 1}")),
        "measureCount": len(measures),
        "instrument": _safe_int(instrument, -1),
        "bank": _safe_int(channel.bank),
        "primaryChannel": channel.channel,
        "effectChannel": channel.effectChannel,
        "isSolo": any(track.song.tracks[i].isSolo for i in shared),
        "isMute": any(track.song.tracks[i].isMute for i in shared),
        "sharedTracks": shared,
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

        # Work on a candidate so routing exhaustion or GP5 validation cannot
        # leave a partially added track in the editing session.
        candidate = copy.deepcopy(song)
        cloned = copy.deepcopy(candidate.tracks[track_index], {id(candidate): candidate})
        source_name = str(getattr(cloned, "name", f"Track {track_index + 1}"))
        cloned.name = request.new_name or f"{source_name} Copy"

        assign_private_channels(candidate, cloned)
        cloned.song = candidate
        cloned.number = len(candidate.tracks) + 1
        for measure, header in zip(cloned.measures, candidate.measureHeaders):
            measure.header = header
        candidate.tracks.append(cloned)
        validate_private_channels(candidate, len(candidate.tracks) - 1)
        session['song'] = candidate
        # Structural edits are outside this first fret-only history.
        session["undo"].clear()
        session["redo"].clear()
        session["revision"] += 1
        return _song_summary(candidate, session_id)


@app.post('/api/sessions/{session_id}/tracks/{track_index}/unlink')
def unlink_track(session_id: str, track_index: int, request: HistoryRequest):
    with EDIT_LOCK:
        session = SESSIONS.get(session_id)
        if not session:
            raise HTTPException(404, 'Session not found.')
        song = session['song']
        if not 0 <= track_index < len(song.tracks):
            raise HTTPException(404, 'Track not found.')
        command = {'operation': 'unlink', 'track': track_index, **request.model_dump()}
        if request.commandId in session['commands']:
            if session['commands'][request.commandId] != command:
                raise HTTPException(409, 'Command ID already used.')
            return {'song': _song_summary(song, session_id), 'editing': _editing_state(session)}
        if request.expectedRevision != session['revision']:
            raise HTTPException(409, 'Score changed. Reload before unlinking.')
        if len(_channel_group(song, track_index)) > 1:
            candidate = copy.deepcopy(song)
            assign_private_channels(candidate, candidate.tracks[track_index], excluding=track_index)
            validate_private_channels(candidate, track_index)
            session['song'] = candidate
            session['revision'] += 1
        session['commands'][request.commandId] = command
        return {'song': _song_summary(session['song'], session_id), 'editing': _editing_state(session)}


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
