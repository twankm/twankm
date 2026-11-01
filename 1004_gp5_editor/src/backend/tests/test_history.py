import io
import uuid

import guitarpro as gp
import pytest

from app.main import SESSIONS
from test_fret import client, score, state


def edit(session_id, fret):
    current = state(session_id)
    return client.post(f'/api/sessions/{session_id}/fret', json={
        'commandId': uuid.uuid4().hex, 'expectedRevision': current['revision'],
        'noteId': current['notes'][0]['id'], 'fret': fret})


def history(session_id, direction, **overrides):
    return client.post(f'/api/sessions/{session_id}/history/{direction}', json={
        'commandId': uuid.uuid4().hex, 'expectedRevision': state(session_id)['revision'], **overrides})


def exported_fret(session_id):
    response = client.get(f'/api/sessions/{session_id}/download')
    assert response.status_code == 200
    song = gp.parse(io.BytesIO(response.content))
    return song.tracks[0].measures[0].voices[0].beats[0].notes[0].value


def test_multiple_undo_redo_exports_and_stable_ids(score):
    before = state(score)
    ids = [n['id'] for n in before['notes']]
    assert not before['canUndo'] and not before['canRedo']
    assert edit(score, 5).status_code == 200
    assert edit(score, 7).status_code == 200
    for direction, fret, revision in [('undo', 5, 3), ('undo', 3, 4), ('redo', 5, 5), ('redo', 7, 6)]:
        response = history(score, direction)
        assert response.status_code == 200, response.text
        current = response.json()
        assert current['revision'] == revision
        assert [n['id'] for n in current['notes']] == ids
        assert current['notes'][0]['fret'] == exported_fret(score) == fret
        assert current['notes'][1]['fret'] == 2
    assert state(score)['canUndo'] and not state(score)['canRedo']


def test_new_edit_after_undo_discards_redo(score):
    edit(score, 5)
    history(score, 'undo')
    assert state(score)['canRedo']
    assert edit(score, 8).status_code == 200
    assert not state(score)['canRedo']
    assert history(score, 'redo').status_code == 409
    assert history(score, 'undo').json()['notes'][0]['fret'] == 3


@pytest.mark.parametrize('direction', ['undo', 'redo'])
def test_empty_history_does_not_mutate(score, direction):
    before = state(score)
    assert history(score, direction).status_code == 409
    assert state(score) == before


def test_retries_and_revision_conflicts(score):
    edit(score, 5)
    response = history(score, 'undo', commandId='undo-once')
    assert response.status_code == 200
    after = response.json()
    assert history(score, 'undo', commandId='undo-once', expectedRevision=1).json() == after
    assert history(score, 'redo', commandId='undo-once', expectedRevision=1).status_code == 409
    assert history(score, 'redo', expectedRevision=1).status_code == 409
    assert state(score) == after


@pytest.mark.parametrize('direction', ['undo', 'redo'])
def test_writer_failure_keeps_history_and_score(score, monkeypatch, direction):
    edit(score, 5)
    if direction == 'redo':
        history(score, 'undo')
    before = state(score)
    def fail(*args, **kwargs):
        raise ValueError('forced validation failure')
    monkeypatch.setattr(gp, 'write', fail)
    assert history(score, direction).status_code == 422
    assert state(score) == before


def test_noop_keeps_redo_and_revision(score):
    edit(score, 5)
    history(score, 'undo')
    before = state(score)
    assert edit(score, 3).json() == before
    assert history(score, 'redo').status_code == 200


def test_structural_edit_clears_fret_history(score):
    edit(score, 5)
    history(score, 'undo')
    assert client.post(f'/api/sessions/{score}/tracks/0/duplicate', json={}).status_code == 200
    current = state(score)
    assert not current['canUndo'] and not current['canRedo']
    assert history(score, 'redo').status_code == 409


def test_reopening_file_starts_new_history(score):
    edit(score, 5)
    download = client.get(f'/api/sessions/{score}/download')
    opened = client.post('/api/sessions', files={'file': ('reopen.gp5', download.content)})
    new_id = opened.json()['sessionId']
    try:
        current = state(new_id)
        assert current['revision'] == 0
        assert not current['canUndo'] and not current['canRedo']
        assert exported_fret(new_id) == 5
        assert state(score)['canUndo']
    finally:
        SESSIONS.pop(new_id, None)


def test_history_limit(score, monkeypatch):
    monkeypatch.setattr('app.main.HISTORY_LIMIT', 2)
    for fret in [5, 7, 9]:
        assert edit(score, fret).status_code == 200
    assert history(score, 'undo').json()['notes'][0]['fret'] == 7
    assert history(score, 'undo').json()['notes'][0]['fret'] == 5
    assert history(score, 'undo').status_code == 409
