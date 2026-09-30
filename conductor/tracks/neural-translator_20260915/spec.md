# Specification: Offline Neural Machine Translation via CTranslate2 OPUS-MT

## Overview
Replace the static 80-token map fallback in `interview_shield/translate.py` with an offline neural machine translation (NMT) engine based on CTranslate2 running an English-to-Czech OPUS-MT model (`Helsinki-NLP/opus-mt-en-cs` converted to CTranslate2 / INT8 format). This enables real, fluent sentence translation during live interviews without any external API or cloud dependency.

## Motivation
- Current `LocalFallbackTranslator` only recognizes ~80 common words and translates word-by-word with no grammar, tenses, or context ("*I think we have meeting*" -> "*já myslím my máme schůzka*"). Unrecognized words remain in English.
- For job interviews, accurate contextual comprehension of interviewer questions and technical statements is critical.
- `ctranslate2` (4.8.2) is already installed as part of faster-whisper dependencies.
- OPUS-MT en-cs in CTranslate2 INT8 format is lightweight (~75MB), loads quickly, and translates a sentence in <30ms on CPU or <10ms on GTX 1060.

## Functional Requirements
1. **CTranslate2Translator Implementation**:
   - Implement `CTranslate2Translator` conforming to the `Translator` protocol in `interview_shield/interfaces.py`.
   - Supports translation from English to Czech (`en -> cs`).
   - Uses `tokenizers` / SentencePiece for subword tokenization and `ctranslate2.Translator` for fast beam search / greedy decoding.
2. **Model Storage & Management**:
   - Model directory configurable via `AppConfig.state_dir / "translation_models"`.
   - Automatic download / caching of pre-converted CTranslate2 model from Hugging Face hub (e.g. `michaelfeil/ct2fast-opus-mt-en-cs` or equivalent), respecting offline mode if already downloaded.
3. **Execution Device & Compute Type**:
   - Configurable device: `translation_device: str = "auto"` (choices: auto, cpu, cuda).
   - Configurable compute type: `translation_compute_type: str = "auto"` (int8, float16, etc.).
4. **Resilient Fallback Hierarchy**:
   - If CTranslate2 translation model is not downloaded, cannot load, or fails during inference, automatically fall back to `LocalFallbackTranslator` with warning status event.
   - `HybridTranslator` manages the active backend (`ctranslate2` -> `local_fallback`).
5. **Config & CLI Integration**:
   - Add fields to `AppConfig`: `translation_model: str = "michaelfeil/ct2fast-opus-mt-en-cs"`, `translation_device: str = "auto"`, `translation_compute_type: str = "auto"`.
   - Add CLI options: `--translation-device`, `--translation-model`.
6. **TUI & Logging**:
   - Display active translator backend in TUI status bar ("NMT: ctranslate2 (cuda)" or "NMT: fallback").
   - Record backend used in `TranscriptEvent.backend`.

## Non-Functional Requirements
- **Latency**: Translation of standard sentence (<25 words) must complete in <50ms on CPU, <15ms on GPU.
- **Resource usage**: Memory overhead <200MB RAM / VRAM.
- **Robustness**: Never crash on malformed input, punctuation-only strings, or empty strings.
- **Offline operation**: Zero internet requests when model is cached.

## Acceptance Criteria
- [x] `CTranslate2Translator` implements `Translator` protocol.
- [x] Full sentence "We are looking for a senior DevOps engineer with Linux and Python skills." translates to coherent Czech.
- [x] Fallback to `LocalFallbackTranslator` occurs seamlessly if model is missing or fails.
- [x] Unit tests in `tests/test_neural_translate.py` cover tokenization, translation, device selection, and fallback with 100% pass rate.
- [x] All existing tests continue to pass (`uv run python -m unittest discover -s tests`).
- [x] TUI reflects active translation backend in status.

## Out of Scope
- Online cloud translation APIs (Google, DeepL, OpenAI).
- Real-time text-to-speech (TTS) audio synthesis.
- Multi-target language support (focus is strictly EN -> CS).
