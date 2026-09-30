# Architecture

## Entry points

- [`shield.py`](/home/milhy777/Develop/MyVoiceTranslator/shield.py) je tenký CLI wrapper.
- [`interview_shield/cli.py`](/home/milhy777/Develop/MyVoiceTranslator/interview_shield/cli.py) řeší parser, command routing a JSON summary výstupy.

## Core modules

- [`interview_shield/config.py`](/home/milhy777/Develop/MyVoiceTranslator/interview_shield/config.py)
  řeší runtime konfiguraci, env overrides a safe fallback adresáře.
- [`interview_shield/pipeline.py`](/home/milhy777/Develop/MyVoiceTranslator/interview_shield/pipeline.py)
  skládá STT, překlad a logging do jednoho orchestrátoru.
- [`interview_shield/stt.py`](/home/milhy777/Develop/MyVoiceTranslator/interview_shield/stt.py)
  obaluje `faster-whisper` a řeší CPU/CUDA výběr.
- [`interview_shield/translate.py`](/home/milhy777/Develop/MyVoiceTranslator/interview_shield/translate.py)
  drží hybridní překlad: online Google -> local fallback.
- [`interview_shield/audio.py`](/home/milhy777/Develop/MyVoiceTranslator/interview_shield/audio.py)
  obsahuje safe device discovery, WAV chunk source a live `sounddevice` source.
- [`interview_shield/logging_utils.py`](/home/milhy777/Develop/MyVoiceTranslator/interview_shield/logging_utils.py)
  zapisuje session markdown log a debug bundle JSON.
- [`interview_shield/diagnostics.py`](/home/milhy777/Develop/MyVoiceTranslator/interview_shield/diagnostics.py)
  generuje doctor report bez toho, aby při file/simulated testech blokoval audio stack.
- [`interview_shield/fixtures.py`](/home/milhy777/Develop/MyVoiceTranslator/interview_shield/fixtures.py)
  generuje deterministické audio fixture přes `espeak-ng` a `ffmpeg`.
- [`interview_shield/tui.py`](/home/milhy777/Develop/MyVoiceTranslator/interview_shield/tui.py)
  drží Textual rozhraní.

## Data flow

1. CLI vytvoří `AppConfig` a zajistí writable directories.
2. Pipeline inicializuje `WhisperTranscriber`.
3. Pipeline transkribuje audio z file/live source.
4. Každý segment projde přes `HybridTranslator`.
5. Výstup se zapíše do session logu a debug bundlu.
6. TUI jen zobrazuje stav a transcript events; obchodní logiku nedrží.

## Fallback model

- STT:
  `auto` -> zkus CUDA -> při selhání CPU `int8`
- Translation:
  online Google -> při chybě local fallback
- Paths:
  home/XDG -> při blokaci workspace fallback
- Audio discovery:
  safe subprocess probe s timeoutem místo nekonečného visení

## Intentional trade-offs

- Local translation fallback je deterministic emergency path, ne plnohodnotný NMT.
- Simulated live E2E používá WAV chunk streaming místo skutečného PipeWire loopbacku, aby šel unattended test pustit i v omezeném prostředí.
- Host audio/GPU readiness se diagnostikuje explicitně přes `doctor`, ale core file/simulated pipeline na ně není existenčně závislá.
