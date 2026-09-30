from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Pre-converted OPUS-MT en-cs models on Hugging Face Hub
MODEL_CANDIDATES: dict[str, list[str]] = {
    "michaelfeil/ct2fast-opus-mt-en-cs": [
        "michaelfeil/ct2fast-opus-mt-en-cs",
        "manancode/opus-mt-en-cs-ctranslate2-android",
    ],
}

TOKENIZER_REPO_FALLBACK = "Xenova/opus-mt-en-cs"


def _sanitize_tokenizer_json(tok_path: Path) -> None:
    """Ensure tokenizer.json does not have null precompiled_charsmap which causes tokenizers panic."""
    try:
        with open(tok_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        modified = False
        normalizer = data.get("normalizer")
        if isinstance(normalizer, dict) and normalizer.get("type") == "Precompiled":
            if normalizer.get("precompiled_charsmap") is None:
                data["normalizer"] = None
                modified = True
        if modified:
            with open(tok_path, "w", encoding="utf-8") as f:
                json.dump(data, f)
    except Exception as exc:
        logger.debug("Failed to sanitize tokenizer.json: %s", exc)


def _ensure_tokenizer_file(model_dir: Path, cache_dir: Path, force_offline: bool) -> bool:
    """Ensure model_dir contains a working tokenizer.json file."""
    tok_path = model_dir / "tokenizer.json"
    if tok_path.is_file():
        _sanitize_tokenizer_json(tok_path)
        return True

    # Try to fetch tokenizer.json from known compatible repo
    try:
        from huggingface_hub import hf_hub_download

        downloaded_tok = hf_hub_download(
            repo_id=TOKENIZER_REPO_FALLBACK,
            filename="tokenizer.json",
            cache_dir=cache_dir,
            local_files_only=force_offline,
        )
        with open(downloaded_tok, "r", encoding="utf-8") as f:
            tok_data = json.load(f)
        if tok_data.get("normalizer", {}).get("precompiled_charsmap") is None:
            tok_data["normalizer"] = None
        with open(tok_path, "w", encoding="utf-8") as f:
            json.dump(tok_data, f)
        return True
    except Exception as exc:
        logger.debug("Could not obtain tokenizer.json: %s", exc)
        return False


def resolve_translation_model(
    model_name: str,
    cache_dir: Path,
    force_offline: bool = False,
) -> Path | None:
    """Resolve or download a CTranslate2 translation model directory.

    Args:
        model_name: Hugging Face repo ID or local directory path.
        cache_dir: Directory used for local caching.
        force_offline: If True, only use local cached files without network calls.

    Returns:
        Path to the resolved model directory containing model.bin, or None if unavailable.
    """
    # 1. Local path check
    local_path = Path(model_name)
    if local_path.is_dir() and (local_path / "model.bin").is_file():
        _ensure_tokenizer_file(local_path, cache_dir=cache_dir, force_offline=force_offline)
        return local_path

    # 2. Hugging Face snapshot download
    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        logger.warning("huggingface_hub is not installed")
        return None

    cache_dir.mkdir(parents=True, exist_ok=True)
    candidates = MODEL_CANDIDATES.get(model_name, [model_name])

    for candidate in candidates:
        try:
            downloaded = snapshot_download(
                repo_id=candidate,
                cache_dir=cache_dir,
                local_files_only=force_offline,
            )
            candidate_dir = Path(downloaded)
            if (candidate_dir / "model.bin").is_file():
                _ensure_tokenizer_file(candidate_dir, cache_dir=cache_dir, force_offline=force_offline)
                return candidate_dir
        except Exception as exc:
            logger.debug("Failed resolving candidate %s: %s", candidate, exc)
            continue

    return None
