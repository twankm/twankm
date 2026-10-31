# Roadmap

## 0.1 — foundation
- [x] API health endpoint
- [x] GP3/4/5 upload and parse
- [x] Song/track metadata
- [x] Track deep-copy command
- [x] GP5 download endpoint
- [x] alphaTab viewer/player integration scaffold
- [x] Browser print-to-PDF scaffold

## 0.2 — editing core
- [ ] Define stable internal score DTO and stable IDs for tracks/bars/beats/notes
- [ ] Track copy/paste with explicit MIDI channel conflict policy
- [ ] Measure-range copy/paste
- [ ] Note fret/string/duration edit commands
- [ ] Undo/redo command history
- [ ] Re-render alphaTab after edits (serialize internal model to supported format or update renderer)

## 0.3 — fidelity and output
- [ ] Round-trip corpus: GP5 files with repeats, alternate endings, bends, slides, tuplets, drums
- [ ] Compare parsed model before/after save
- [ ] PDF page layout settings and page-break tests
- [ ] Offline bundled fonts and SoundFont

## 0.4 — distribution
- [ ] Tauri 2 shell and local backend lifecycle
- [ ] Windows installer
- [ ] Web deployment with authentication, storage quotas, session expiry
