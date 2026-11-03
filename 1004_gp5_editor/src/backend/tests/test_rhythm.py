import copy
import io
import pytest
import guitarpro as gp
from app.main import SESSIONS
from test_fret import score, state, client


def rhythm_edit(session, value=8, dotted=False, tuplet=1, changes=None):
    current = state(session)
    return client.post(f'/api/sessions/{session}/beat-notes', json=dict(
        commandId='rhythm', expectedRevision=current['revision'], beatId=current['beats'][0]['id'],
        changes=changes or [], rhythm=dict(value=value, dotted=dotted, tuplet=tuplet)))


@pytest.mark.parametrize('value,dotted,tuplet', [(1, False, 1), (2, True, 1), (8, False, 3), (16, True, 5), (128, False, 1)])
def test_rhythm_saves_reopens_and_history(score, value, dotted, tuplet):
    before = state(score)
    response = rhythm_edit(score, value, dotted, tuplet)
    assert response.status_code == 200, response.text
    after = response.json()
    assert after['beats'][0]['rhythm'] == dict(value=value, dotted=dotted, tuplet=tuplet)
    assert after['notes'] == before['notes']
    saved = gp.parse(io.BytesIO(client.get(f'/api/sessions/{score}/download').content))
    duration = saved.tracks[0].measures[0].voices[0].beats[0].duration
    assert (duration.value, duration.isDotted, duration.tuplet.enters) == (value, dotted, tuplet)
    for direction, revision, expected in [('undo', 1, before), ('redo', 2, after)]:
        response = client.post(f'/api/sessions/{score}/history/{direction}', json=dict(commandId=direction, expectedRevision=revision))
        assert response.status_code == 200, response.text
        assert response.json()['beats'][0]['rhythm'] == expected['beats'][0]['rhythm']


def test_rhythm_retimes_following_notes_and_preserves_effects(score):
    voice = SESSIONS[score]['song'].tracks[0].measures[0].voices[0]
    voice.beats[0].notes[0].effect.vibrato = True
    following = copy.deepcopy(voice.beats[0], {id(voice): voice})
    following.start = 1920
    voice.beats.append(following)
    response = rhythm_edit(score, changes=[dict(string=6, fret=7)])
    assert response.status_code == 200, response.text
    voice = SESSIONS[score]['song'].tracks[0].measures[0].voices[0]
    assert voice.beats[1].start == voice.measure.start + 480
    assert voice.beats[0].notes[0].value == 7
    assert voice.beats[0].notes[0].effect.vibrato
    assert len(SESSIONS[score]['undo']) == 1


def test_overflow_rejected_atomically(score):
    voice = SESSIONS[score]['song'].tracks[0].measures[0].voices[0]
    for _ in range(3):
        voice.beats.append(copy.deepcopy(voice.beats[0], {id(voice): voice}))
    before = state(score)
    response = rhythm_edit(score, value=2, changes=[dict(string=6, fret=None)])
    assert response.status_code == 422
    assert state(score) == before


def test_rest_duration_edit(score):
    beat = SESSIONS[score]['song'].tracks[0].measures[0].voices[0].beats[0]
    beat.notes = []
    beat.status = gp.BeatStatus.rest
    response = rhythm_edit(score, value=16)
    assert response.status_code == 200, response.text
    assert response.json()['notes'] == []
