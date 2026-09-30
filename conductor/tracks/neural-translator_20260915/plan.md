# Implementation Plan: Offline Neural Machine Translation via CTranslate2 OPUS-MT

## Phase 1: Core Engine & Model Management

- [x] **Task: Model downloader and cache resolver** (interview_shield/nmt_model.py, tests/test_neural_translate.py)
  - [x] Implement `resolve_translation_model(model_name: str, cache_dir: Path) -> Path` using `huggingface_hub.snapshot_download` with offline check
  - [x] Add unit test verifying directory layout and cache hit without internet

- [x] **Task: Implement CTranslate2Translator** (interview_shield/translate.py, tests/test_neural_translate.py)
  - [x] Implement tokenization using `tokenizers` or Hugging Face tokenizer files (spm / bpe)
  - [x] Wrap `ctranslate2.Translator` with device and compute_type resolution (auto -> cuda if available else cpu)
  - [x] Return `TranslationResult(text=..., backend="ctranslate2", online_ok=False)`
  - [x] Add unit tests with mocked Translator and test sentence fixtures

## Phase 2: Pipeline & Fallback Wiring

- [x] **Task: Update HybridTranslator with fallback chain** (interview_shield/translate.py, interview_shield/pipeline.py)
  - [x] Attempt loading `CTranslate2Translator` if enabled; fall back to `LocalFallbackTranslator` on missing model or load error
  - [x] Expose active backend name and error states cleanly
  - [x] Update `InterviewShieldPipeline` to report translation status

- [x] **Task: Extend AppConfig and CLI** (interview_shield/config.py, interview_shield/cli.py)
  - [x] Add `translation_model`, `translation_device`, `translation_compute_type` to `AppConfig`
  - [x] Wire CLI arguments `--translation-model`, `--translation-device`, `--translation-compute-type`
  - [x] Add environment variable overrides `MVT_TRANSLATION_MODEL`, `MVT_TRANSLATION_DEVICE`

## Phase 3: TUI Integration & Verification

- [x] **Task: TUI backend display and controls** (interview_shield/tui.py)
  - [x] Show active translation model and engine in TUI status bar
  - [x] Ensure model is reused across TUI reconfigurations without memory leak

- [x] **Task: End-to-end and regression testing** (tests/test_translate.py, tests/test_neural_translate.py)
  - [x] Run full test suite: `uv run python -m unittest discover -s tests`
  - [x] Validate deterministic translation output on interview questions fixture
