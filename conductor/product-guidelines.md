# Product Guidelines: MyVoiceTranslator

## UX Principles
- **Keyboard-first**: All TUI actions accessible via keybindings (q/r/s/f/o/d/c/l/h/t/p)
- **Visual clarity**: Color-coded windows (ENG teal, CZE gold, debug amber, history slate)
- **Transparency**: Status bar shows all active config at a glance
- **Recoverable**: Apply+Restart pattern with dirty-state indication
- **Observable**: Debug log, history panels, doctor snapshot, export debug bundle

## Visual
- Dark theme: backgrounds 16-24 range, text 231-250
- Accent colors: teal (ENG), gold (CZE), blue (controls), amber (debug), red (errors)
- Rounded borders on all panels
- Markdown session logs for human readability

## Content
- Language: English UI, Czech translations
- Timestamps: HH:MM:SS in logs
- Backend labels: "local" for fallback, "google" removed (offline-only)

## Safety
- No network calls in default configuration
- Audio device access via sounddevice (PortAudio)
- No sudo or privileged operations
- Config via env vars and CLI, no secrets in code

## Performance
- Live chunk: 1.0s (low latency feel)
- STT accumulation: 8.0s (context for accuracy)
- Target: first transcript <3s after speech starts
- GPU memory: stable across restarts (no leak)