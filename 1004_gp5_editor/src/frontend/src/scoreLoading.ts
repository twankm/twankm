import { importer, type AlphaTabApi } from '@coderline/alphatab'

// alphaTab 1.8.x worker results resolve beat coordinates against api.score.
// A result queued for the old score can refer to a track removed from the new
// score. Replace the renderer through the public settings API before swapping
// scores; the synthesizer and its loaded SoundFont remain in place.
export function loadScoreSafely(api: AlphaTabApi, bytes: Uint8Array, requestedTrack: number): number {
  const score = importer.ScoreLoader.loadScoreFromBytes(bytes, api.settings)
  if (!score.tracks.length) throw new Error('The score contains no tracks.')
  const track = Number.isInteger(requestedTrack)
    ? Math.max(0, Math.min(requestedTrack, score.tracks.length - 1)) : 0
  if (api.score && api.settings.core.useWorkers) {
    api.settings.core.useWorkers = false
    try {
      api.updateSettings()
    } finally {
      api.settings.core.useWorkers = true
      api.updateSettings()
    }
  }
  if (!api.load(score, [track])) throw new Error('alphaTab rejected the file data.')
  return track
}
