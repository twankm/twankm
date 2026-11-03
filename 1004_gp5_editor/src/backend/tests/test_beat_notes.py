import io
import guitarpro as gp
from app.main import SESSIONS
from test_fret import score, state, client
from test_measure_paste import add_measure


def edit(session, changes, command='batch'):
    current = state(session)
    return client.post(f'/api/sessions/{session}/beat-notes', json=dict(
        commandId=command, expectedRevision=current['revision'], beatId=current['beats'][0]['id'], changes=changes))


def test_delete_change_add_is_one_history_entry(score):
    before = state(score)
    response = edit(score, [dict(string=6, fret=None), dict(string=5, fret=7), dict(string=1, fret=0)])
    assert response.status_code == 200, response.text
    after = response.json()
    assert sorted((n['string'], n['fret']) for n in after['notes']) == [(1, 0), (5, 7)]
    retained = next(n for n in before['notes'] if n['string'] == 5)
    assert next(n for n in after['notes'] if n['string'] == 5)['id'] == retained['id']
    assert len(SESSIONS[score]['undo']) == 1
    for direction, revision, expected in [('undo', 1, before['notes']), ('redo', 2, after['notes'])]:
        response = client.post(f'/api/sessions/{score}/history/{direction}', json=dict(commandId=direction, expectedRevision=revision))
        assert response.status_code == 200, response.text
        assert response.json()['notes'] == expected


def test_last_note_deletion_becomes_rest_and_reopens(score):
    duration = SESSIONS[score]['song'].tracks[0].measures[0].voices[0].beats[0].duration
    response = edit(score, [dict(string=6, fret=None), dict(string=5, fret=None)])
    assert response.status_code == 200, response.text
    saved = gp.parse(io.BytesIO(client.get(f'/api/sessions/{score}/download').content))
    beat = saved.tracks[0].measures[0].voices[0].beats[0]
    assert beat.status == gp.BeatStatus.rest and not beat.notes and beat.duration == duration
    assert edit(score, [dict(string=3, fret=4)], 'add-back').status_code == 200


def test_invalid_batch_does_not_partially_delete(score):
    before = state(score)
    response = edit(score, [dict(string=6, fret=None), dict(string=5, fret=99)])
    assert response.status_code == 422
    assert state(score) == before


def test_grace_can_be_deleted_without_deleting_main_note(score):
    SESSIONS[score]['song'].tracks[0].measures[0].voices[0].beats[0].notes[0].effect.grace = gp.GraceEffect(fret=1)
    response = edit(score, [dict(kind='grace', string=6, fret=None)])
    assert response.status_code == 200, response.text
    assert len(response.json()['notes']) == 2
    note = SESSIONS[score]['song'].tracks[0].measures[0].voices[0].beats[0].notes[0]
    assert note.value == 3 and note.effect.grace is None


def test_delete_tie_origin_preserves_following_pitch_and_undo(score):
    add_measure(score)
    tied = SESSIONS[score]['song'].tracks[0].measures[1].voices[0].beats[0].notes[0]
    tied.type, tied.value = gp.NoteType.tie, 3
    response = edit(score, [dict(string=6, fret=None)])
    assert response.status_code == 200, response.text
    saved = gp.parse(io.BytesIO(client.get(f'/api/sessions/{score}/download').content))
    following = saved.tracks[0].measures[1].voices[0].beats[0].notes[0]
    assert following.value == 3 and following.type == gp.NoteType.normal
    response = client.post(f'/api/sessions/{score}/history/undo', json=dict(commandId='undo', expectedRevision=1))
    assert response.status_code == 200, response.text
    assert SESSIONS[score]['song'].tracks[0].measures[1].voices[0].beats[0].notes[0].type == gp.NoteType.tie
