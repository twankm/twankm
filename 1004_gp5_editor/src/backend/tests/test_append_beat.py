import copy
import io
import guitarpro as gp
from app.main import SESSIONS
from test_fret import score, state, client


def prepare(session):
    voice = SESSIONS[session]['song'].tracks[0].measures[0].voices[0]
    template = voice.beats[0]
    voice.beats = []
    start = voice.measure.start
    for value, dotted in [(8, False), (8, False), (8, False), (4, False), (8, True)]:
        beat = copy.deepcopy(template, {id(voice): voice})
        beat.duration = gp.Duration(value=value, isDotted=dotted)
        beat.start = start
        start += beat.duration.time
        voice.beats.append(beat)


def append(session, value=8, dotted=True):
    current = state(session)
    return client.post(f'/api/sessions/{session}/beat-notes', json=dict(
        commandId='append', expectedRevision=current['revision'], beatId=current['beats'][-1]['id'],
        append=True, rhythm=dict(value=value, dotted=dotted, tuplet=1), changes=[dict(string=6, fret=7)]))


def test_three_eighths_quarter_dotted_eighth_can_add_dotted_eighth(score):
    prepare(score)
    before = state(score)
    assert before['beats'][0]['remainingTicks'] == 720
    response = append(score)
    assert response.status_code == 200, response.text
    after = response.json()
    assert len(after['beats']) == 6
    assert after['beats'][-1]['remainingTicks'] == 0
    assert after['notes'][:-1] == before['notes']
    saved = gp.parse(io.BytesIO(client.get(f'/api/sessions/{score}/download').content))
    voice = saved.tracks[0].measures[0].voices[0]
    assert sum(b.duration.time for b in voice.beats) == 3840
    assert voice.beats[-1].start == voice.measure.start + 3120
    assert voice.beats[-1].notes[0].value == 7
    for direction, revision, expected in [('undo', 1, before), ('redo', 2, after)]:
        response = client.post(f'/api/sessions/{score}/history/{direction}', json=dict(commandId=direction, expectedRevision=revision))
        assert response.status_code == 200, response.text
        assert response.json()['notes'] == expected['notes']
        assert len(response.json()['beats']) == len(expected['beats'])


def test_append_overflow_does_not_change_existing_notes(score):
    prepare(score)
    before = state(score)
    response = append(score, value=4, dotted=False)
    assert response.status_code == 422
    assert state(score) == before
