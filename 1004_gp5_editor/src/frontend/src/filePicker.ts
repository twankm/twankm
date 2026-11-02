type PickerKind = 'score' | 'soundfont'
type FileHandle = { getFile(): Promise<File> }
type PickerOptions = {
  id: string; multiple: boolean; startIn?: FileHandle
  types: { description: string; accept: Record<string, string[]> }[]
}
type PickerWindow = Window & { showOpenFilePicker?: (options: PickerOptions) => Promise<FileHandle[]> }
const lastHandles: Partial<Record<PickerKind, FileHandle>> = {}

// The browser remembers a distinct last-used directory per id, including across
// page reloads. A remembered file handle also supplies startIn in this page.
export async function pickFile(kind: PickerKind, fallback: () => void, host = window as PickerWindow): Promise<File | null> {
  if (!host.showOpenFilePicker) { fallback(); return null }
  const options: PickerOptions = {
    id: kind === 'score' ? 'gp5-editor-score' : 'gp5-editor-soundfont',
    multiple: false,
    types: [{ description: kind === 'score' ? 'Guitar Pro files' : 'SoundFont banks',
      accept: { 'application/octet-stream': kind === 'score' ? ['.gp3', '.gp4', '.gp5'] : ['.sf2', '.sf3'] } }]
  }
  if (lastHandles[kind]) options.startIn = lastHandles[kind]
  try {
    const [handle] = await host.showOpenFilePicker(options)
    if (!handle) return null
    const file = await handle.getFile()
    lastHandles[kind] = handle
    return file
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') return null
    throw error
  }
}
