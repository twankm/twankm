import io
import shutil
import subprocess
from pathlib import Path
import pytest
import guitarpro as gp
from app.main import SESSIONS
from test_fret import score, state, client


@pytest.mark.parametrize('index', [0, 1, 2])
def test_delete_track_preserves_remaining_score_and_undo(score, index):
    for name in ['Second', 'Third']:
        response = client.post(f'/api/sessions/{score}/tracks/0/duplicate', json={'new_name': name})
        assert response.status_code == 200, response.text
    before = state(score)
    names = [t.name for t in SESSIONS[score]['song'].tracks]
    channels = [(t.channel.channel, t.channel.effectChannel) for t in SESSIONS[score]['song'].tracks]
    request = dict(commandId='delete', expectedRevision=before['revision'])
    response = client.post(f'/api/sessions/{score}/tracks/{index}/delete', json=request)
    assert response.status_code == 200, response.text
    assert client.post(f'/api/sessions/{score}/tracks/{index}/delete', json=request).json() == response.json()
    after = response.json()['editing']
    saved = gp.parse(io.BytesIO(client.get(f'/api/sessions/{score}/download').content))
    assert [t.name for t in saved.tracks] == names[:index] + names[index + 1:]
    assert [t.number for t in saved.tracks] == [1, 2]
    assert [(t.channel.channel, t.channel.effectChannel) for t in saved.tracks] == channels[:index] + channels[index + 1:]
    assert {n['id'] for n in after['notes']} == {n['id'] for n in before['notes'] if n['track'] != index}
    for direction, expected, revision in [('undo', before, after['revision']), ('redo', after, after['revision'] + 1)]:
        response = client.post(f'/api/sessions/{score}/history/{direction}', json=dict(commandId=direction, expectedRevision=revision))
        assert response.status_code == 200, response.text
        assert response.json()['notes'] == expected['notes']


def test_last_track_and_stale_revision_cannot_be_deleted(score):
    before = state(score)
    for revision, status in [(0, 422), (1, 409)]:
        response = client.post(f'/api/sessions/{score}/tracks/0/delete', json=dict(commandId='delete', expectedRevision=revision))
        assert response.status_code == status, response.text
        assert state(score) == before


def test_frontend_score_replacement_cancels_stale_track_bounds(score, tmp_path):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js required for score replacement regression check')
    assert client.post(f'/api/sessions/{score}/tracks/0/duplicate', json={}).status_code == 200
    before = tmp_path / 'before.gp5'
    after = tmp_path / 'after.gp5'
    before.write_bytes(client.get(f'/api/sessions/{score}/download').content)
    response = client.post(f'/api/sessions/{score}/tracks/1/delete', json=dict(commandId='delete', expectedRevision=state(score)['revision']))
    assert response.status_code == 200, response.text
    after.write_bytes(client.get(f'/api/sessions/{score}/download').content)
    script = Path(__file__).resolve().parents[2] / 'frontend/scripts/check-score-replacement.mjs'
    result = subprocess.run([node, str(script), str(before), str(after)], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
