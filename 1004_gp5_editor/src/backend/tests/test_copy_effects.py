import copy

import guitarpro as gp
import pytest

from app.main import SESSIONS
from app.measure_edit import validate_song
from test_fret import score, state, client, command
from test_measure_paste import copy_bar, paste_bar, reopen, add_measure, undo
from test_measure_range import prepare, copy_range


@pytest.mark.parametrize('effect', ['slide', 'hammer', 'grace', 'bend'])
def test_note_effects_copy_and_paste_without_being_removed(score, effect):
    add_measure(score)
    song = SESSIONS[score]['song']
    voice = song.tracks[0].measures[0].voices[0]
    note = voice.beats[0].notes[0]
    if effect == 'slide':
        note.effect.slides = [gp.SlideType.legatoSlideTo]
    elif effect == 'hammer':
        note.effect.hammer = True
    elif effect == 'grace':
        note.effect.grace = gp.GraceEffect(fret=1, duration=16)
    else:
        note.effect.bend = gp.BendEffect(type=gp.BendType.bend,
            points=[gp.BendPoint(0, 0), gp.BendPoint(4, 2), gp.BendPoint(8, 1), gp.BendPoint(12, 0)])
    following = copy.deepcopy(voice.beats[0], {id(voice): voice})
    following.notes[0].value = 5
    following.notes[0].effect = gp.NoteEffect()
    voice.beats.append(following)
    SESSIONS[score]['song'] = validate_song(song)
    expected = copy.deepcopy(SESSIONS[score]['song'].tracks[0].measures[0].voices[0].beats[0].notes[0].effect)
    copied = copy_bar(score)
    assert copied.status_code == 200, copied.text
    response = paste_bar(score, copied.json()['clipboardId'])
    assert response.status_code == 200, response.text
    assert reopen(score).tracks[0].measures[1].voices[0].beats[0].notes[0].effect == expected
    assert undo(score).status_code == 200
    assert undo(score, 'redo').status_code == 200
    assert reopen(score).tracks[0].measures[1].voices[0].beats[0].notes[0].effect == expected


@pytest.mark.parametrize('effect', ['slide', 'bend', 'harmonic', 'palmMute'])
def test_symbol_note_fret_edit_preserves_effect_and_history(score, effect):
    song = SESSIONS[score]['song']
    note = song.tracks[0].measures[0].voices[0].beats[0].notes[0]
    if effect == 'slide':
        note.effect.slides = [gp.SlideType.shiftSlideTo]
    elif effect == 'bend':
        note.effect.bend = gp.BendEffect(type=gp.BendType.bend,
            points=[gp.BendPoint(0, 0), gp.BendPoint(12, 2)])
    elif effect == 'harmonic':
        note.effect.harmonic = gp.NaturalHarmonic()
    else:
        note.effect.palmMute = True
    SESSIONS[score]['song'] = validate_song(song)
    expected = copy.deepcopy(SESSIONS[score]['song'].tracks[0].measures[0].voices[0].beats[0].notes[0].effect)
    response = client.post(f'/api/sessions/{score}/fret', json=command(score))
    assert response.status_code == 200, response.text
    for direction in [None, 'undo', 'redo']:
        if direction:
            assert undo(score, direction).status_code == 200
        note = reopen(score).tracks[0].measures[0].voices[0].beats[0].notes[0]
        assert note.effect == expected
        assert note.value == (3 if direction == 'undo' else 5)


def test_ties_inside_copied_range_are_preserved(score):
    prepare(score)
    song = SESSIONS[score]['song']
    tie = song.tracks[0].measures[1].voices[0].beats[0].notes[0]
    tie.type, tie.value = gp.NoteType.tie, 3
    copied = copy_range(score, count=2)
    assert copied.status_code == 200, copied.text
    response = paste_bar(score, copied.json()['clipboardId'], bar=2)
    assert response.status_code == 200, response.text
    pasted_tie = reopen(score).tracks[0].measures[3].voices[0].beats[0].notes[0]
    assert pasted_tie.type == gp.NoteType.tie and pasted_tie.value == 3


def test_copy_boundary_tie_succeeds_but_incompatible_destination_does_not_change_pitch(score):
    prepare(score)
    tie = SESSIONS[score]['song'].tracks[0].measures[1].voices[0].beats[0].notes[0]
    tie.type, tie.value = gp.NoteType.tie, 3
    copied = copy_bar(score, bar=1)
    assert copied.status_code == 200
    before = state(score)
    response = paste_bar(score, copied.json()['clipboardId'], bar=3)
    assert response.status_code == 422
    assert 'Tie connection' in response.json()['detail']
    assert state(score) == before


def test_source_controller_changes_are_not_copied_and_destination_changes_survive(score):
    add_measure(score)
    song = SESSIONS[score]['song']
    song.tracks[0].measures[0].voices[0].beats[0].effect.mixTableChange = gp.MixTableChange(
        instrument=gp.MixTableItem(40), volume=gp.MixTableItem(72))
    song.tracks[0].measures[1].voices[0].beats[0].effect.mixTableChange = gp.MixTableChange(
        instrument=gp.MixTableItem(31), volume=gp.MixTableItem(88), tempo=gp.MixTableItem(140))
    SESSIONS[score]['song'] = validate_song(song)
    expected = copy.deepcopy(SESSIONS[score]['song'].tracks[0].measures[1].voices[0].beats[0].effect.mixTableChange)
    copied = copy_bar(score)
    assert copied.status_code == 200, copied.text
    assert copied.json()['excludedControllers'] == 1
    response = paste_bar(score, copied.json()['clipboardId'])
    assert response.status_code == 200, response.text
    result = reopen(score)
    assert result.tracks[0].measures[1].voices[0].beats[0].notes[0].value == 3
    assert result.tracks[0].measures[1].voices[0].beats[0].effect.mixTableChange == expected
    assert result.tracks[0].measures[0].voices[0].beats[0].effect.mixTableChange.instrument.value == 40
