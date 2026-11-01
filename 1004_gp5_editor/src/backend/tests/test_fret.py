import io
import json
from pathlib import Path
import shutil
import subprocess

import guitarpro as gp
import pytest
from fastapi.testclient import TestClient

from app.main import app, SESSIONS

client = TestClient(app)


@pytest.fixture
def score():
    song = gp.Song()
    song.title = "Fret round trip"
    voice = song.tracks[0].measures[0].voices[0]
    beat = gp.Beat(voice, status=gp.BeatStatus.normal)
    beat.notes = [gp.Note(beat, value=3, string=1, type=gp.NoteType.normal),
                  gp.Note(beat, value=2, string=2, type=gp.NoteType.normal)]
    voice.beats.append(beat)
    stream = io.BytesIO()
    gp.write(song, stream, version=(5, 1, 0))
    response = client.post('/api/sessions', files={'file': ('test.gp5', stream.getvalue())})
    assert response.status_code == 200, response.text
    session_id = response.json()['sessionId']
    yield session_id
    SESSIONS.pop(session_id, None)


def state(session_id):
    response = client.get(f'/api/sessions/{session_id}/editing')
    assert response.status_code == 200
    return response.json()


def command(session_id, **changes):
    current = state(session_id)
    note = next(n for n in current['notes'] if n['fret'] == 3)
    return dict(commandId='edit-1', expectedRevision=current['revision'],
                noteId=note['id'], fret=5) | changes


def test_edit_download_reopen_and_idempotency(score):
    before = state(score)
    request = command(score)
    response = client.post(f'/api/sessions/{score}/fret', json=request)
    assert response.status_code == 200, response.text
    after = response.json()
    assert after['revision'] == 1
    assert [n['id'] for n in after['notes']] == [n['id'] for n in before['notes']]
    assert sorted(n['fret'] for n in after['notes']) == [2, 5]
    assert client.post(f'/api/sessions/{score}/fret', json=request).json() == after
    assert client.post(f'/api/sessions/{score}/fret', json=request | {'fret': 6}).status_code == 409
    download = client.get(f'/api/sessions/{score}/download?revision=1')
    assert download.status_code == 200
    reopened = gp.parse(io.BytesIO(download.content))
    assert reopened.title == 'Fret round trip'
    assert [(n.string, n.value) for n in reopened.tracks[0].measures[0].voices[0].beats[0].notes] == [(1, 5), (2, 2)]
    assert client.get(f'/api/sessions/{score}/download?revision=0').status_code == 409


@pytest.mark.parametrize('changes,status', [({'fret': -1}, 422), ({'fret': 25}, 422),
    ({'fret': 2.5}, 422), ({'fret': True}, 422), ({'expectedRevision': 10}, 409),
    ({'noteId': 'missing'}, 404)])
def test_rejected_edits_do_not_mutate(score, changes, status):
    before = state(score)
    response = client.post(f'/api/sessions/{score}/fret', json=command(score, **changes))
    assert response.status_code == status, response.text
    assert state(score) == before


def test_effects_and_ties_are_not_editable(score):
    song = SESSIONS[score]['song']
    notes = song.tracks[0].measures[0].voices[0].beats[0].notes
    notes[0].effect.bend = gp.BendEffect()
    assert not next(n for n in state(score)['notes'] if n['fret'] == 3)['editable']
    assert client.post(f'/api/sessions/{score}/fret', json=command(score)).status_code == 422
    notes[1].type = gp.NoteType.tie
    assert not any(n['editable'] for n in state(score)['notes'])


def test_serialization_failure_rolls_back(score, monkeypatch):
    before = state(score)
    request = command(score)
    def fail(*args, **kwargs):
        raise ValueError('forced writer failure')
    monkeypatch.setattr(gp, 'write', fail)
    assert client.post(f'/api/sessions/{score}/fret', json=request).status_code == 422
    assert state(score) == before


def test_duplicate_invalidates_old_revision_and_exports(score):
    request = command(score)
    response = client.post(f'/api/sessions/{score}/tracks/0/duplicate', json={})
    assert response.status_code == 200
    assert client.post(f'/api/sessions/{score}/fret', json=request).status_code == 409
    download = client.get(f'/api/sessions/{score}/download')
    assert len(gp.parse(io.BytesIO(download.content)).tracks) == 2


@pytest.mark.parametrize('second_voice', [False, True])
def test_real_alphatab_note_mapping(score, tmp_path, second_voice):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js required for alphaTab integration check')
    song = SESSIONS[score]['song']
    if second_voice:
        # alphaTab compresses voice indexes when the first voice has no beats.
        first, second = song.tracks[0].measures[0].voices
        second.beats = first.beats
        first.beats = []
        for beat in second.beats:
            beat.voice = second
    output = client.get(f'/api/sessions/{score}/download')
    gp5 = tmp_path / 'sample.gp5'
    dto = tmp_path / 'editing.json'
    gp5.write_bytes(output.content)
    dto.write_text(json.dumps(state(score)), encoding='utf-8')
    script = Path(__file__).resolve().parents[2] / 'frontend/scripts/check-note-mapping.mjs'
    result = subprocess.run([node, str(script), str(gp5), str(dto)], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_tie_origin_in_previous_measure_is_not_editable(score):
    song = SESSIONS[score]['song']
    header = gp.MeasureHeader(number=2, start=4800)
    song.measureHeaders.append(header)
    measure = gp.Measure(song.tracks[0], header)
    song.tracks[0].measures.append(measure)
    voice = measure.voices[0]
    beat = gp.Beat(voice, status=gp.BeatStatus.normal)
    beat.notes = [gp.Note(beat, value=3, string=1, type=gp.NoteType.tie)]
    voice.beats.append(beat)
    original = next(n for n in state(score)['notes'] if n['bar'] == 0 and n['fret'] == 3)
    assert not original['editable']


def test_other_note_effect_survives_fret_edit(score):
    notes = SESSIONS[score]['song'].tracks[0].measures[0].voices[0].beats[0].notes
    notes[1].effect.vibrato = True
    response = client.post(f'/api/sessions/{score}/fret', json=command(score))
    assert response.status_code == 200
    saved = gp.parse(io.BytesIO(client.get(f'/api/sessions/{score}/download').content))
    saved_notes = saved.tracks[0].measures[0].voices[0].beats[0].notes
    assert saved_notes[0].value == 5
    assert saved_notes[1].effect.vibrato


@pytest.mark.parametrize('version,suffix', [((3, 0, 0), 'gp3'), ((4, 0, 6), 'gp4')])
def test_legacy_import_still_exports_gp5(score, version, suffix):
    stream = io.BytesIO()
    gp.write(SESSIONS[score]['song'], stream, version=version)
    response = client.post('/api/sessions', files={'file': (f'test.{suffix}', stream.getvalue())})
    assert response.status_code == 200, response.text
    session_id = response.json()['sessionId']
    try:
        edited = client.post(f'/api/sessions/{session_id}/fret', json=command(session_id))
        assert edited.status_code == 200, edited.text
        exported = client.get(f'/api/sessions/{session_id}/download')
        assert gp.parse(io.BytesIO(exported.content)).tracks[0].measures[0].voices[0].beats[0].notes[0].value == 5
    finally:
        SESSIONS.pop(session_id, None)
