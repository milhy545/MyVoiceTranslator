# E2E and Debugging Workflow

## 1. Pre-flight

```bash
source .venv/bin/activate
python shield.py doctor
python shield.py devices
```

Sleduj hlavně:

- `runtime_checks.google_dns`
- `runtime_checks.nvidia-smi`
- `runtime_checks.nvidia_device_nodes`
- `runtime_checks.kernel_lockdown`
- `imports.faster_whisper`
- `paths.log_dir`
- `audio_devices`

## 2. Deterministic fixtures

```bash
source .venv/bin/activate
python shield.py prepare-fixtures
```

Tohle vygeneruje:

- `test_audio/fixture_voice.wav`
- `test_audio/fixture_voice.mp3`
- a doplní legacy soubory `test_audio.wav` a `sample.mp3`, pokud byly prázdné

## 3. CPU-first acceptance

```bash
source .venv/bin/activate
python shield.py --offline --stt-device cpu test-file
python shield.py --offline --stt-device cpu test-live-mic
python shield.py --offline --stt-device cpu test-live-monitor
python -m unittest -v tests.test_e2e
python scripts/run_final_verification.py
```

Zelený stav znamená:

- transcript obsahuje očekávané tokeny
- session log existuje
- debug bundle existuje
- simulated mic a monitor workflow doběhnou bez pádu

## 4. Online troubleshooting

Pokud `test-file` bez `--offline` skončí local backendem:

1. zkontroluj `doctor`
2. pokud `google_dns.ok == false`, problém je DNS/síť
3. pokud DNS funguje a stále padá online překlad, podívej se do debug bundle na `warning` status event

## 5. GPU troubleshooting

Základ:

```bash
source .venv/bin/activate
python shield.py doctor
python shield.py --stt-device cuda test-file
```

Když CUDA neprojde:

1. ověř, že host má `nvidia-smi`
2. ověř device nodes `/dev/nvidia*`
3. ověř `doctor.runtime_checks.kernel_lockdown`
4. ověř CUDA runtime knihovny a kompatibilitu driveru
5. pokud to stále padá, vrať se na `--stt-device cpu`; aplikace tím nekončí

## Host result on this machine

Mimo sandbox bylo ověřeno:

- DNS pro Google překlad funguje
- online Google backend je zelený
- audio devices se správně enumerují
- GPU není dostupná kvůli kernel lockdownu: `/sys/kernel/security/lockdown` obsahuje `none [integrity] confidentiality`
- `modprobe nvidia` končí `Key was rejected by service`

Tohle je host boot / kernel policy problém, ne chyba projektu.

## 6. Kde hledat artefakty

- session log:
  `~/logs/interview_YYYYMMDD.md`
  nebo fallback `./logs/interview_YYYYMMDD.md`
- debug bundle:
  `~/.local/state/myvoicetranslator/artifacts/debug-*.json`
  nebo fallback `./.runtime/artifacts/debug-*.json`

## 7. Co dělá debug bundle

Bundle obsahuje:

- doctor snapshot
- transcript events
- status events
- odkaz na session log

Je to primární artefakt pro post-mortem debugging bez nutnosti znovu reprodukovat běh.
