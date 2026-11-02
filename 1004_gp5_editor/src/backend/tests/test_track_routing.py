import copy
from pathlib import Path
import shutil
import subprocess

import guitarpro as gp
import pytest

from app.main import SESSIONS
from test_fret import client, score, state
from test_track_settings import setting, saved


def duplicate(session_id):
    return client.post(f'/api/sessions/{session_id}/tracks/0/duplicate', json={})


def legacy_clone(session_id):
    song = SESSIONS[session_id]['song']
    clone = copy.deepcopy(song.tracks[0], {id(song): song})
    clone.number = 2
    for measure, header in zip(clone.measures, song.measureHeaders):
        measure.header = header
    song.tracks.append(clone)


def unlink(session_id, **overrides):
    return client.post(f'/api/sessions/{session_id}/tracks/1/unlink', json={
        'commandId': 'unlink-once', 'expectedRevision': state(session_id)['revision'], **overrides})


def test_duplicate_mute_solo_and_instrument_are_independent(score):
    response = duplicate(score)
    assert response.status_code == 200, response.text
    assert [t['sharedTracks'] for t in response.json()['tracks']] == [[0], [1]]
    assert setting(score, mute=True).status_code == 200
    assert setting(score, track=1, solo=True).status_code == 200
    assert setting(score, track=1, instrument=40, bank=8).status_code == 200
    source, clone = saved(score).tracks
    assert source.isMute and not clone.isMute
    assert clone.isSolo and not source.isSolo
    assert source.channel.instrument == 25 and clone.channel.instrument == 40
    assert source.channel.bank == 0 and clone.channel.bank == 8
    assert not {source.channel.channel, source.channel.effectChannel}.intersection((clone.channel.channel, clone.channel.effectChannel))
    assert source.measures[0].voices[0].beats[0].notes[0].value == clone.measures[0].voices[0].beats[0].notes[0].value == 3


def test_unlink_existing_copy_preserves_original_and_is_idempotent(score):
    legacy_clone(score)
    source_channel = copy.deepcopy(SESSIONS[score]['song'].tracks[0].channel)
    response = unlink(score)
    assert response.status_code == 200, response.text
    assert response.json()['song']['tracks'][1]['sharedTracks'] == [1]
    assert unlink(score, expectedRevision=0).json() == response.json()
    assert saved(score).tracks[0].channel == source_channel
    assert setting(score, track=1, mute=True).status_code == 200
    assert not saved(score).tracks[0].isMute and saved(score).tracks[1].isMute


def test_multiple_copies_use_distinct_nonpercussion_channel_pairs(score):
    for _ in range(10):
        assert duplicate(score).status_code == 200
    channels = [c for track in saved(score).tracks for c in (track.channel.channel, track.channel.effectChannel)]
    assert len(channels) == len(set(channels))
    assert all(c % 16 != 9 for c in channels)


def test_channel_exhaustion_does_not_add_a_linked_copy(score):
    song = SESSIONS[score]['song']
    for channel in range(2, 64):
        track = gp.Track(song, number=len(song.tracks) + 1)
        track.channel.channel = track.channel.effectChannel = channel
        song.tracks.append(track)
    before = state(score)
    count = len(song.tracks)
    response = duplicate(score)
    assert response.status_code == 409
    assert len(SESSIONS[score]['song'].tracks) == count
    assert state(score) == before


@pytest.mark.parametrize('action', ['duplicate', 'unlink'])
def test_routing_validation_failure_rolls_back(score, monkeypatch, action):
    if action == 'unlink':
        legacy_clone(score)
    before = state(score)
    tracks_before = copy.deepcopy(SESSIONS[score]['song'].tracks)
    def fail(*args, **kwargs):
        raise ValueError('forced serialization failure')
    monkeypatch.setattr(gp, 'write', fail)
    response = duplicate(score) if action == 'duplicate' else unlink(score)
    assert response.status_code == 422
    assert state(score) == before
    assert [t.channel for t in SESSIONS[score]['song'].tracks] == [t.channel for t in tracks_before]


def test_percussion_not_silently_reassigned_to_melodic_channels(score):
    track = SESSIONS[score]['song'].tracks[0]
    track.isPercussionTrack = True
    track.channel.channel = track.channel.effectChannel = 9
    assert duplicate(score).status_code == 422
    assert len(SESSIONS[score]['song'].tracks) == 1


def test_real_synth_can_mute_either_duplicate_independently(score, tmp_path):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js required for alphaTab synth integration')
    assert duplicate(score).status_code == 200
    gp5 = tmp_path / 'independent.gp5'
    gp5.write_bytes(client.get(f'/api/sessions/{score}/download').content)
    script = Path(__file__).resolve().parents[2] / 'frontend/scripts/check-independent-tracks.mjs'
    result = subprocess.run([node, str(script), str(gp5)], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
