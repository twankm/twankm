export type SoundFontPreset = { name: string; bank: number; program: number }

// SF2 and SF3 share the RIFF/pdta/phdr preset header format. Only read chunk
// headers and preset records; sample data stays with alphaTab's own decoder.
export function soundFontPresets(bytes: Uint8Array): SoundFontPreset[] {
  const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength)
  const ascii = new TextDecoder('windows-1252')
  const text = (start: number, size: number) => ascii.decode(bytes.subarray(start, start + size))
  if (bytes.length < 12 || text(0, 4) !== 'RIFF' || text(8, 4) !== 'sfbk') throw new Error('Invalid SoundFont RIFF header.')
  const end = view.getUint32(4, true) + 8
  if (end > bytes.length || end < 12) throw new Error('Truncated SoundFont bank.')
  for (let offset = 12; offset + 8 <= end;) {
    const size = view.getUint32(offset + 4, true)
    const chunkEnd = offset + 8 + size
    if (chunkEnd > end) throw new Error('Truncated SoundFont chunk.')
    if (text(offset, 4) === 'LIST' && size >= 4 && text(offset + 8, 4) === 'pdta') {
      for (let item = offset + 12; item + 8 <= chunkEnd;) {
        const length = view.getUint32(item + 4, true)
        const itemEnd = item + 8 + length
        if (itemEnd > chunkEnd) throw new Error('Truncated preset chunk.')
        if (text(item, 4) === 'phdr') {
          if (length < 38 || length % 38 !== 0) throw new Error('Invalid SoundFont preset table.')
          const presets: SoundFontPreset[] = []
          // Final phdr record is the mandatory EOP sentinel, not an instrument.
          for (let record = item + 8; record + 38 < itemEnd; record += 38) {
            presets.push({ name: text(record, 20).split('\0')[0].trim(),
              program: view.getUint16(record + 20, true), bank: view.getUint16(record + 22, true) })
          }
          if (!presets.length) throw new Error('SoundFont contains no instruments.')
          // Synth lookup prefers the last matching bank/program entry.
          return [...new Map(presets.map(p => [`${p.bank}:${p.program}`, p])).values()]
            .sort((a, b) => a.bank - b.bank || a.program - b.program)
        }
        item = itemEnd + (length & 1)
      }
    }
    offset = chunkEnd + (size & 1)
  }
  throw new Error('SoundFont preset table was not found.')
}

export function trackPresets(presets: SoundFontPreset[], percussion: boolean): SoundFontPreset[] {
  // GP5 persists a byte-sized bank. alphaTab treats SF banks 128+ as drum kits.
  return presets.filter(p => p.program <= 127 && p.bank <= 255 && (percussion ? p.bank >= 128 : p.bank < 128))
}
