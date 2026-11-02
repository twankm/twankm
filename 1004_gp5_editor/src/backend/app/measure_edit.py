"""Detached measure-range note/rhythm snapshots; destination headers stay in place."""
import copy
import io

import guitarpro as gp
from fastapi import HTTPException


def measure_at(song, track, bar):
    if not 0 <= track < len(song.tracks) or not 0 <= bar < len(song.tracks[track].measures):
        raise HTTPException(404, 'Track or measure not found.')
    return song.tracks[track].measures[bar]


def detached_voices(measure):
    # Avoid copying the parent Song graph into each clipboard/history entry.
    return copy.deepcopy(measure.voices, {id(measure): None})


def attach_voices(measure, voices):
    measure.voices = copy.deepcopy(voices)
    for voice in measure.voices:
        voice.measure = measure
        start = measure.start
        for beat in voice.beats:
            beat.voice = voice
            beat.start = start
            for note in beat.notes:
                note.beat = beat
            if beat.status != gp.BeatStatus.empty:
                start += beat.duration.time


def validate_song(song):
    try:
        stream = io.BytesIO()
        gp.write(song, stream, version=(5, 1, 0))
        stream.seek(0)
        return gp.parse(stream)
    except Exception as exc:
        raise HTTPException(422, f'GP5 validation failed: {exc}') from exc


def timed_beats(voices):
    for index, voice in enumerate(voices):
        tick = 0
        for beat in voice.beats:
            yield index, tick, beat
            if beat.status != gp.BeatStatus.empty:
                tick += beat.duration.time


def preserve_destination_controls(original, destination):
    beats = list(timed_beats(destination.voices))
    for voice, tick, beat in timed_beats(original.voices):
        change = beat.effect.mixTableChange
        if change is None:
            continue
        matches = [(index, target) for index, offset, target in beats if offset == tick and target.effect.mixTableChange is None]
        matches.sort(key=lambda item: item[0] != voice)
        if not matches:
            raise HTTPException(422, f'Destination bar {original.number} has a tempo/instrument/mixer change at tick {tick} that cannot be kept with the copied rhythm. No measures were changed.')
        matches[0][1].effect.mixTableChange = copy.deepcopy(change)


def make_clipboard(song, track, bar):
    measure = measure_at(song, track, bar)
    source_track = song.tracks[track]
    voices = detached_voices(measure)
    excluded = 0
    for _, _, beat in timed_beats(voices):
        if beat.effect.mixTableChange is not None:
            excluded += 1
            # Note/rhythm paste must not change the destination instrument,
            # tempo or track mixer. Note effects themselves are left intact.
            beat.effect.mixTableChange = None
    return {'voices': voices, 'excludedControllers': excluded,
            'tuning': [(s.number, s.value) for s in source_track.strings],
            'percussion': source_track.isPercussionTrack, 'offset': source_track.offset,
            'signature': (measure.timeSignature.numerator, measure.timeSignature.denominator.value),
            'sourceTrack': track, 'sourceBar': bar}


def _check_target(song, track, bar, clipboard):
    target = measure_at(song, track, bar)
    target_track = song.tracks[track]
    if (clipboard['percussion'] != target_track.isPercussionTrack or
            clipboard['tuning'] != [(s.number, s.value) for s in target_track.strings] or
            clipboard['offset'] != target_track.offset):
        raise HTTPException(422, 'Tracks must have matching percussion type, tuning, string count and capo for this paste.')
    signature = (target.timeSignature.numerator, target.timeSignature.denominator.value)
    if signature != clipboard['signature']:
        raise HTTPException(422, 'Source and destination time signatures must match.')
    for voice in clipboard['voices']:
        duration = sum(b.duration.time for b in voice.beats if b.status != gp.BeatStatus.empty)
        if duration > target.length:
            raise HTTPException(422, 'Copied rhythm exceeds the destination measure duration.')
        if any(n.string < 1 or n.string > len(target_track.strings) or
               (not target_track.isPercussionTrack and n.value > target_track.fretCount)
               for b in voice.beats for n in b.notes):
            raise HTTPException(422, 'Copied notes exceed the destination string/fret range.')


def make_clipboard_range(song, track, bar, count):
    measure_at(song, track, bar)
    if count < 1 or bar + count > len(song.tracks[track].measures):
        raise HTTPException(422, 'Selected measure range exceeds the source track.')
    measures = [make_clipboard(song, track, i) for i in range(bar, bar + count)]
    return {'measures': measures, 'sourceTrack': track, 'sourceBar': bar, 'count': count,
            'excludedControllers': sum(m['excludedControllers'] for m in measures)}


def paste_range_candidate(song, track, bar, clipboard):
    measure_at(song, track, bar)
    measures = clipboard.get('measures', [clipboard])
    if bar + len(measures) > len(song.tracks[track].measures):
        raise HTTPException(422, 'Not enough destination measures to overwrite the copied range. No measures were changed.')
    # Validate the whole destination before applying anything. Overlapping paste
    # reads detached clipboard snapshots, never the partially modified song.
    for offset, source in enumerate(measures):
        _check_target(song, track, bar + offset, source)
    candidate = copy.deepcopy(song)
    for offset, source in enumerate(measures):
        destination = measure_at(candidate, track, bar + offset)
        attach_voices(destination, source['voices'])
        preserve_destination_controls(measure_at(song, track, bar + offset), destination)
    parsed = validate_song(candidate)
    # Tied-note values are resolved by the GP5 reader using preceding notes.
    # Check the whole affected track, including ties outside the pasted region,
    # instead of refusing every measure which happens to contain a tie/slide.
    for index, (written, reopened) in enumerate(zip(candidate.tracks[track].measures, parsed.tracks[track].measures)):
        if detached_voices(reopened) != detached_voices(written):
            if any(note.type == gp.NoteType.tie for voice in written.voices for beat in voice.beats for note in beat.notes):
                raise HTTPException(422, f'Tie connection would change at track {track + 1}, bar {index + 1}. Include the tied origin in the copied range or choose a destination with matching preceding notes. No measures were changed.')
            raise HTTPException(422, f'Notes/effects in track {track + 1}, bar {index + 1} did not survive GP5 serialization unchanged. No measures were changed.')
    return candidate


def paste_candidate(song, track, bar, clipboard):
    return paste_range_candidate(song, track, bar, clipboard)
