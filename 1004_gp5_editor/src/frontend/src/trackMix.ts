import type { AlphaTabApi } from '@coderline/alphatab'

export type TrackMix = { index: number; isSolo: boolean; isMute: boolean }

export function applyTrackMix(api: AlphaTabApi, tracks: TrackMix[]) {
  const score = api.score
  if (!score) return
  api.changeTrackSolo(score.tracks, false)
  api.changeTrackMute(score.tracks, false)
  for (const info of tracks) {
    const track = score.tracks[info.index]
    if (!track) continue
    track.playbackInfo.isSolo = info.isSolo
    track.playbackInfo.isMute = info.isMute
    if (info.isSolo) api.changeTrackSolo([track], true)
    if (info.isMute) api.changeTrackMute([track], true)
  }
}
