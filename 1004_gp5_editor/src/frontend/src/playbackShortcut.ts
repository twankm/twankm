export function isPlaybackShortcut(event: Pick<KeyboardEvent, 'code' | 'key' | 'ctrlKey' | 'shiftKey' | 'altKey' | 'metaKey' | 'isComposing'>): boolean {
  return !event.ctrlKey && !event.shiftKey && !event.altKey && !event.metaKey && !event.isComposing &&
    (event.code === 'Space' || event.key === ' ')
}
