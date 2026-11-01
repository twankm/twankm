import type { AlphaTabApi } from '@coderline/alphatab'

export const DEFAULT_SOUND_FONT = '/soundfont/sonivox.sf2'
export const DEFAULT_SOUND_FONT_NAME = 'Default (sonivox.sf2)'

export async function readSoundFont(file: File): Promise<Uint8Array> {
  if (!/\.sf[23]$/i.test(file.name)) throw new Error('Select a .sf2 or .sf3 SoundFont file.')
  const header = new Uint8Array(await file.slice(0, 12).arrayBuffer())
  const text = new TextDecoder('ascii').decode(header)
  if (header.length !== 12 || text.slice(0, 4) !== 'RIFF' || text.slice(8, 12) !== 'sfbk') {
    throw new Error('This file is not a SoundFont bank.')
  }
  return new Uint8Array(await file.arrayBuffer())
}

// loadSoundFont's boolean reports acceptance, not successful decoding. Wait for
// completion and, when a score exists, for its presets to be ready for playback.
export function replaceSoundFont(api: AlphaTabApi, data: Uint8Array | string, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal.aborted) { reject(new Error('SoundFont loading cancelled.')); return }
    const player = api.player
    if (!player) { reject(new Error('Audio player is not initialized.')); return }
    let loaded = false
    let settled = false
    const unregister: (() => void)[] = []
    const finish = (error?: Error) => {
      if (settled) return
      settled = true
      clearTimeout(timeout)
      unregister.forEach(remove => remove())
      signal.removeEventListener('abort', abort)
      if (error) reject(error)
      else resolve()
    }
    const abort = () => finish(new Error('SoundFont loading cancelled.'))
    const timeout = setTimeout(() => finish(new Error('SoundFont loading timed out.')), 120000)
    signal.addEventListener('abort', abort, { once: true })
    unregister.push(api.soundFontLoaded.on(() => {
      loaded = true
      if (!api.score) finish()
    }))
    unregister.push(api.playerReady.on(() => { if (loaded) finish() }))
    unregister.push(player.soundFontLoadFailed.on(error => finish(error instanceof Error ? error : new Error(String(error)))))
    try {
      if (!api.loadSoundFont(data, false)) finish(new Error('SoundFont loading could not start.'))
    } catch (error) {
      finish(error instanceof Error ? error : new Error(String(error)))
    }
  })
}
