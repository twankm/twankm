import copy
import io
import json
from pathlib import Path
import shutil
import subprocess
import uuid

import guitarpro as gp
import pytest

from app.main import SESSIONS
from test_fret import client, score, state


def add_measure(session_id):
    song = SESSIONS[session_id]['song']
    header = gp.MeasureHeader(number=2, start=4800)
    song.addMeasureHeader(header)
    for track in song.tracks:
        measure = gp.Measure(track, header)
        voice = measure.voices[0]
        beat = gp.Beat(voice, status=gp.BeatStatus.normal, start=4800)
        beat.notes = [gp.Note(beat, string=1, value=9, type=gp.NoteType.normal)]
        voice.beats.append(beat)
        track.measures.append(measure)


def copy_bar(session_id, track=0, bar=0):
    return client.post(f'/api/sessions/{session_id}/measures/copy', json={
        'expectedRevision': state(session_id)['revision'], 'track': track, 'bar': bar})


def paste_bar(session_id, clipboard_id, track=0, bar=1, **overrides):
    return client.post(f'/api/sessions/{session_id}/measures/paste', json={
        'commandId': uuid.uuid4().hex, 'expectedRevision': state(session_id)['revision'],
        'clipboardId': clipboard_id, 'track': track, 'bar': bar, **overrides})


def reopen(session_id):
    response = client.get(f'/api/sessions/{session_id}/download')
    assert response.status_code == 200
    return gp.parse(io.BytesIO(response.content))


def undo(session_id, direction='undo'):
    return client.post(f'/api/sessions/{session_id}/history/{direction}', json={
        'commandId': uuid.uuid4().hex, 'expectedRevision': state(session_id)['revision']})


def test_paste_replaces_notes_preserves_header_and_supports_undo_redo(score):
    add_measure(score)
    song = SESSIONS[score]['song']
    song.measureHeaders[1].marker = gp.Marker('Keep destination marker')
    before = state(score)
    source_ids = [n['id'] for n in before['notes'] if n['bar'] == 0]
    target_ids = [n['id'] for n in before['notes'] if n['bar'] == 1]
    copied = copy_bar(score)
    assert copied.status_code == 200, copied.text
    assert state(score) == before
    result = paste_bar(score, copied.json()['clipboardId'])
    assert result.status_code == 200, result.text
    pasted_ids = [n['id'] for n in result.json()['notes'] if n['bar'] == 1]
    assert not set(source_ids + target_ids).intersection(pasted_ids)
    target = reopen(score).tracks[0].measures[1]
    assert [n.value for n in target.voices[0].beats[0].notes] == [3, 2]
    assert target.marker.title == 'Keep destination marker'
    assert target.voices[0].beats[0].start == target.start
    assert undo(score).status_code == 200
    assert [n['id'] for n in state(score)['notes'] if n['bar'] == 1] == target_ids
    assert reopen(score).tracks[0].measures[1].voices[0].beats[0].notes[0].value == 9
    assert undo(score, 'redo').status_code == 200
    assert [n['id'] for n in state(score)['notes'] if n['bar'] == 1] == pasted_ids


def test_clipboard_snapshot_and_cross_track_paste(score):
    add_measure(score)
    song = SESSIONS[score]['song']
    track = copy.deepcopy(song.tracks[0])
    track.song = song
    track.number = 2
    track.channel.channel, track.channel.effectChannel = 2, 3
    for measure, header in zip(track.measures, song.measureHeaders):
        measure.header = header
    song.tracks.append(track)
    copied = copy_bar(score).json()['clipboardId']
    # A copy captures data, not a live reference to the source.
    song.tracks[0].measures[0].voices[0].beats[0].notes[0].value = 7
    result = paste_bar(score, copied, track=1)
    assert result.status_code == 200, result.text
    parsed = reopen(score)
    assert parsed.tracks[0].measures[0].voices[0].beats[0].notes[0].value == 7
    assert parsed.tracks[1].measures[1].voices[0].beats[0].notes[0].value == 3


@pytest.mark.parametrize('issue', ['tuning', 'meter', 'controller-position'])
def test_incompatible_paste_is_rejected_without_mutation(score, issue):
    add_measure(score)
    token = copy_bar(score).json()['clipboardId']
    song = SESSIONS[score]['song']
    target = song.tracks[0].measures[1]
    if issue == 'tuning':
        song.tracks[0].strings[0].value -= 1
    elif issue == 'meter':
        target.timeSignature.numerator = 3
    else:
        voice = target.voices[0]
        voice.beats[0].duration = gp.Duration(value=8)
        second = copy.deepcopy(voice.beats[0], {id(voice): voice})
        second.effect.mixTableChange = gp.MixTableChange(volume=gp.MixTableItem(72))
        voice.beats.append(second)
    before = state(score)
    assert paste_bar(score, token).status_code == 422
    assert state(score) == before


def test_paste_idempotency_and_expired_clipboard(score):
    add_measure(score)
    token = copy_bar(score).json()['clipboardId']
    response = paste_bar(score, token, commandId='paste-once')
    assert response.status_code == 200, response.text
    assert paste_bar(score, token, commandId='paste-once', expectedRevision=0).json() == response.json()
    copy_bar(score)
    assert paste_bar(score, token).status_code == 409


def test_paste_failure_does_not_commit(score, monkeypatch):
    add_measure(score)
    token = copy_bar(score).json()['clipboardId']
    before = state(score)
    def fail(*args, **kwargs):
        raise ValueError('forced writer failure')
    monkeypatch.setattr(gp, 'write', fail)
    assert paste_bar(score, token).status_code == 422
    assert state(score) == before


def test_fret_and_measure_history_restore_correct_note_ids(score):
    add_measure(score)
    original_id = next(n['id'] for n in state(score)['notes'] if n['bar'] == 1)
    path = f'/api/sessions/{score}/fret'
    first = client.post(path, json={'commandId': 'before-paste', 'expectedRevision': 0, 'noteId': original_id, 'fret': 10})
    assert first.status_code == 200
    token = copy_bar(score).json()['clipboardId']
    pasted = paste_bar(score, token).json()
    pasted_id = next(n['id'] for n in pasted['notes'] if n['bar'] == 1)
    assert client.post(path, json={'commandId': 'after-paste', 'expectedRevision': 2, 'noteId': pasted_id, 'fret': 7}).status_code == 200
    assert undo(score).status_code == 200
    assert undo(score).status_code == 200
    assert undo(score).status_code == 200
    assert reopen(score).tracks[0].measures[1].voices[0].beats[0].notes[0].value == 9
    for _ in range(3):
        assert undo(score, 'redo').status_code == 200
    assert reopen(score).tracks[0].measures[1].voices[0].beats[0].notes[0].value == 7


def test_pasted_notes_map_to_real_alphatab(score, tmp_path):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js required for alphaTab integration')
    add_measure(score)
    token = copy_bar(score).json()['clipboardId']
    response = paste_bar(score, token)
    assert response.status_code == 200, response.text
    gp5 = tmp_path / 'pasted.gp5'
    dto = tmp_path / 'editing.json'
    gp5.write_bytes(client.get(f'/api/sessions/{score}/download').content)
    dto.write_text(json.dumps(state(score)), encoding='utf-8')
    script = Path(__file__).resolve().parents[2] / 'frontend/scripts/check-note-mapping.mjs'
    result = subprocess.run([node, str(script), str(gp5), str(dto)], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_tuplet_rhythm_and_note_effects_survive_paste(score):
    add_measure(score)
    song = SESSIONS[score]['song']
    voice = song.tracks[0].measures[0].voices[0]
    first = voice.beats[0]
    first.duration = gp.Duration(value=8, tuplet=gp.Tuplet(enters=3, times=2))
    first.notes[0].effect.vibrato = True
    for _ in range(2):
        voice.beats.append(copy.deepcopy(first, {id(voice): voice}))
    token = copy_bar(score).json()['clipboardId']
    response = paste_bar(score, token)
    assert response.status_code == 200, response.text
    beats = reopen(score).tracks[0].measures[1].voices[0].beats
    assert len(beats) == 3
    assert all(b.duration.tuplet.enters == 3 and b.duration.tuplet.times == 2 for b in beats)
    assert all(b.notes[0].effect.vibrato for b in beats)
