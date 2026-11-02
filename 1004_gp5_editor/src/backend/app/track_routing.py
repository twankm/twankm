"""Allocate private GP5 primary/effect channel pairs for melodic tracks."""
import copy

from fastapi import HTTPException

from .measure_edit import validate_song


def assign_private_channels(song, track, excluding=None):
    if track.isPercussionTrack:
        # alphaTab 1.8.4 consolidates all percussion tracks to channel 9 on import.
        raise HTTPException(422, 'Independent drum-track routing is not supported yet; alphaTab uses a shared percussion channel.')
    used = {channel for i, other in enumerate(song.tracks) if i != excluding
            for channel in (other.channel.channel, other.channel.effectChannel)}
    # GP5 stores 64 channel slots; every port's percussion slot is reserved.
    free = [channel for channel in range(64) if channel % 16 != 9 and channel not in used]
    if len(free) < 2:
        raise HTTPException(409, 'No free GP5 primary/effect channel pair is available. No tracks were changed.')
    track.channel = copy.deepcopy(track.channel)
    track.channel.channel, track.channel.effectChannel = free[:2]


def validate_private_channels(candidate, index):
    reopened = validate_song(candidate)
    for original, saved in zip(candidate.tracks, reopened.tracks):
        if (original.channel.channel, original.channel.effectChannel, original.channel.instrument, original.channel.bank) != (
                saved.channel.channel, saved.channel.effectChannel, saved.channel.instrument, saved.channel.bank):
            raise HTTPException(422, 'Track routing or instrument did not survive GP5 serialization.')
    track = reopened.tracks[index]
    channels = {track.channel.channel, track.channel.effectChannel}
    if any(channels.intersection((other.channel.channel, other.channel.effectChannel))
           for i, other in enumerate(reopened.tracks) if i != index):
        raise HTTPException(422, 'Could not isolate the selected track channels.')
