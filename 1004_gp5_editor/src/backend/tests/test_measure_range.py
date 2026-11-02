import copy
import json
from pathlib import Path
import shutil
import subprocess
import uuid

import guitarpro as gp
import pytest

from app.main import SESSIONS
from test_fret import client, score, state
from test_measure_paste import paste_bar, reopen, undo


def prepare(session_id):
    song = SESSIONS[session_id]['song']
    for value in [5, 7, 9, 11]:
        previous = song.measureHeaders[-1]
        header = gp.MeasureHeader(number=len(song.measureHeaders) + 1, start=previous.start + previous.length)
        song.addMeasureHeader(header)
        measure = gp.Measure(song.tracks[0], header)
        voice = measure.voices[0]
        beat = gp.Beat(voice, status=gp.BeatStatus.normal, start=header.start)
        beat.notes = [gp.Note(beat, value=value, string=1, type=gp.NoteType.normal)]
        voice.beats.append(beat)
        song.tracks[0].measures.append(measure)


def copy_range(session_id, bar=0, count=2):
    return client.post(f'/api/sessions/{session_id}/measures/copy', json={
        'expectedRevision': state(session_id)['revision'], 'track': 0, 'bar': bar, 'count': count})


def frets(song, track=0):
    return [m.voices[0].beats[0].notes[0].value for m in song.tracks[track].measures]


def test_cross_track_range_overwrites_existing_bars_and_is_one_undo(score, tmp_path):
    prepare(score)
    song = SESSIONS[score]['song']
    target = copy.deepcopy(song.tracks[0], {id(song): song})
    target.number = 2
    target.channel.channel, target.channel.effectChannel = 2, 3
    for measure, header in zip(target.measures, song.measureHeaders):
        measure.header = header
    song.tracks.append(target)
    song.measureHeaders[2].marker = gp.Marker('Keep destination marker')
    before = state(score)
    before_ids = [n['id'] for n in before['notes']]
    copied = copy_range(score)
    assert copied.status_code == 200
    assert copied.json()['count'] == 2
    response = paste_bar(score, copied.json()['clipboardId'], track=1, bar=2)
    assert response.status_code == 200, response.text
    parsed = reopen(score)
    assert len(parsed.tracks[1].measures) == 5
    assert frets(parsed, 0) == [3, 5, 7, 9, 11]
    assert frets(parsed, 1) == [3, 5, 3, 5, 11]
    assert parsed.tracks[1].measures[2].marker.title == 'Keep destination marker'
    assert state(score)['revision'] == 1
    node = shutil.which('node')
    if node:
        gp5 = tmp_path / 'range.gp5'
        dto = tmp_path / 'editing.json'
        gp5.write_bytes(client.get(f'/api/sessions/{score}/download').content)
        dto.write_text(json.dumps(state(score)), encoding='utf-8')
        script = Path(__file__).resolve().parents[2] / 'frontend/scripts/check-note-mapping.mjs'
        result = subprocess.run([node, str(script), str(gp5), str(dto)], capture_output=True, text=True)
        assert result.returncode == 0, result.stdout + result.stderr
    assert undo(score).status_code == 200
    assert [n['id'] for n in state(score)['notes']] == before_ids
    assert frets(reopen(score), 1) == [3, 5, 7, 9, 11]
    assert not state(score)['canUndo']
    assert undo(score, 'redo').status_code == 200
    assert frets(reopen(score), 1) == [3, 5, 3, 5, 11]


def test_overlapping_range_paste_uses_clipboard_snapshot(score):
    prepare(score)
    token = copy_range(score, count=3).json()['clipboardId']
    response = paste_bar(score, token, bar=1)
    assert response.status_code == 200, response.text
    assert frets(reopen(score)) == [3, 3, 5, 7, 11]


@pytest.mark.parametrize('problem', ['end-of-track', 'later-meter', 'later-tie'])
def test_range_rejection_is_atomic(score, problem):
    prepare(score)
    token = copy_range(score).json()['clipboardId']
    song = SESSIONS[score]['song']
    start = 4 if problem == 'end-of-track' else 2
    if problem == 'later-meter':
        song.measureHeaders[3].timeSignature.numerator = 3
    elif problem == 'later-tie':
        # Existing tie after the overwritten range must keep its original pitch.
        outside = song.tracks[0].measures[4].voices[0].beats[0].notes[0]
        outside.type = gp.NoteType.tie
        outside.value = 9
    before = state(score)
    before_values = frets(song)
    assert paste_bar(score, token, bar=start).status_code == 422
    assert state(score) == before
    assert frets(SESSIONS[score]['song']) == before_values


@pytest.mark.parametrize('count', [0, -1, True, 1.5, 6])
def test_invalid_copy_range_rejected(score, count):
    prepare(score)
    assert copy_range(score, count=count).status_code == 422


def test_range_paste_failure_and_history_failure_preserve_all_bars(score, monkeypatch):
    prepare(score)
    token = copy_range(score).json()['clipboardId']
    before = state(score)
    original_write = gp.write
    def fail(*args, **kwargs):
        raise ValueError('forced writer failure')
    monkeypatch.setattr(gp, 'write', fail)
    assert paste_bar(score, token, bar=2).status_code == 422
    assert state(score) == before
    monkeypatch.setattr(gp, 'write', original_write)
    assert paste_bar(score, token, bar=2).status_code == 200
    pasted = state(score)
    monkeypatch.setattr(gp, 'write', fail)
    assert undo(score).status_code == 422
    assert state(score) == pasted


def test_fret_after_range_paste_and_history_ids(score):
    prepare(score)
    token = copy_range(score).json()['clipboardId']
    assert paste_bar(score, token, bar=2).status_code == 200
    pasted = state(score)
    note = next(n for n in pasted['notes'] if n['bar'] == 3)
    assert client.post(f'/api/sessions/{score}/fret', json={
        'commandId': uuid.uuid4().hex, 'expectedRevision': 1, 'noteId': note['id'], 'fret': 12}).status_code == 200
    assert undo(score).status_code == 200
    assert undo(score).status_code == 200
    assert frets(reopen(score)) == [3, 5, 7, 9, 11]
    assert undo(score, 'redo').status_code == 200
    assert undo(score, 'redo').status_code == 200
    assert frets(reopen(score)) == [3, 5, 3, 12, 11]
