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


def setting(session_id, track=0, **change):
    return client.post(f'/api/sessions/{session_id}/tracks/{track}/settings', json={
        'commandId': uuid.uuid4().hex, 'expectedRevision': state(session_id)['revision'], **change})


def saved(session_id):
    response = client.get(f'/api/sessions/{session_id}/download')
    assert response.status_code == 200
    return gp.parse(io.BytesIO(response.content))


def add_track(session_id, shared=False):
    song = SESSIONS[session_id]['song']
    track = gp.Track(song, number=2, name='Second')
    if not shared:
        track.channel.channel, track.channel.effectChannel = 2, 3
    song.tracks.append(track)


def test_solo_mute_are_independent_and_roundtrip(score):
    add_track(score)
    assert setting(score, solo=True).status_code == 200
    assert setting(score, track=1, mute=True).status_code == 200
    tracks = saved(score).tracks
    assert tracks[0].isSolo and not tracks[0].isMute
    assert tracks[1].isMute and not tracks[1].isSolo
    assert setting(score, solo=False).status_code == 200
    assert not saved(score).tracks[0].isSolo


def test_instrument_bank_roundtrip_leaves_other_track_and_notes_unchanged(score):
    add_track(score)
    response = setting(score, instrument=40, bank=8)
    assert response.status_code == 200, response.text
    tracks = saved(score).tracks
    assert tracks[0].channel.instrument == 40
    assert tracks[0].channel.bank == 8
    assert tracks[1].channel.instrument == 25
    assert tracks[0].measures[0].voices[0].beats[0].notes[0].value == 3
    assert response.json()['song']['tracks'][0]['bank'] == 8


def test_shared_channel_buttons_and_instrument_change_together(score):
    add_track(score, shared=True)
    response = setting(score, solo=True)
    assert response.status_code == 200
    assert all(t['isSolo'] for t in response.json()['song']['tracks'])
    assert response.json()['song']['tracks'][0]['sharedTracks'] == [0, 1]
    assert setting(score, track=1, instrument=30, bank=1).status_code == 200
    assert all(t.channel.instrument == 30 and t.channel.bank == 1 for t in saved(score).tracks)
    assert setting(score, track=1, solo=False).status_code == 200
    assert not any(t.isSolo for t in saved(score).tracks)


@pytest.mark.parametrize('change', [{'instrument': -1}, {'instrument': 128}, {'instrument': True},
    {'bank': 3}, {'instrument': 3, 'bank': 256}, {'solo': 'yes'}, {'solo': True, 'mute': True}, {}])
def test_invalid_settings_leave_score_unchanged(score, change):
    before = state(score)
    assert setting(score, **change).status_code == 422
    assert state(score) == before
    assert saved(score).tracks[0].channel.instrument == 25


def test_stale_revision_and_duplicate_commands(score):
    request = {'commandId': 'settings-once', 'expectedRevision': 0, 'instrument': 40, 'bank': 0}
    path = f'/api/sessions/{score}/tracks/0/settings'
    first = client.post(path, json=request)
    assert first.status_code == 200
    assert client.post(path, json=request).json() == first.json()
    assert client.post(path, json=request | {'instrument': 41}).status_code == 409
    assert setting(score, expectedRevision=0, mute=True).status_code == 409


def test_writer_failure_does_not_commit_track_change(score, monkeypatch):
    before = state(score)
    def fail(*args, **kwargs):
        raise ValueError('forced writer failure')
    monkeypatch.setattr(gp, 'write', fail)
    assert setting(score, instrument=40).status_code == 422
    assert state(score) == before
    assert SESSIONS[score]['song'].tracks[0].channel.instrument == 25


def test_fret_undo_preserves_instrument_and_mix(score):
    current = state(score)
    client.post(f'/api/sessions/{score}/fret', json={'commandId': 'fret', 'expectedRevision': 0,
                'noteId': current['notes'][0]['id'], 'fret': 5})
    assert setting(score, instrument=40, bank=8).status_code == 200
    assert setting(score, mute=True).status_code == 200
    response = client.post(f'/api/sessions/{score}/history/undo', json={'commandId': 'undo', 'expectedRevision': 3})
    assert response.status_code == 200
    track = saved(score).tracks[0]
    assert track.measures[0].voices[0].beats[0].notes[0].value == 3
    assert track.channel.instrument == 40 and track.channel.bank == 8 and track.isMute


@pytest.mark.parametrize('program', [0, 8])
def test_drum_kit_bank_roundtrip(score, program):
    track = SESSIONS[score]['song'].tracks[0]
    track.isPercussionTrack = True
    track.channel.channel = track.channel.effectChannel = 9
    response = setting(score, instrument=program, bank=128)
    assert response.status_code == 200, response.text
    assert saved(score).tracks[0].channel.bank == 128
    assert saved(score).tracks[0].channel.instrument == program


def test_alphatab_reads_saved_track_settings_and_generates_program_change(score, tmp_path):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js required for alphaTab integration')
    setting(score, instrument=40, bank=8)
    setting(score, solo=True)
    setting(score, mute=True)
    gp5 = tmp_path / 'track.gp5'
    expected = tmp_path / 'expected.json'
    gp5.write_bytes(client.get(f'/api/sessions/{score}/download').content)
    expected.write_text(json.dumps({'instrument': 40, 'bank': 8, 'isSolo': True, 'isMute': True}), encoding='utf-8')
    script = Path(__file__).resolve().parents[2] / 'frontend/scripts/check-track-roundtrip.mjs'
    result = subprocess.run([node, str(script), str(gp5), str(expected)], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
