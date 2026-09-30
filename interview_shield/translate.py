from __future__ import annotations

import json
import logging
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    import ctranslate2
except ImportError:  # pragma: no cover
    ctranslate2 = None

try:
    from tokenizers import Tokenizer
except ImportError:  # pragma: no cover
    Tokenizer = None


LOCAL_TOKEN_MAP = {
    # Original
    "good": "dobré",
    "morning": "ráno",
    "python": "python",
    "automation": "automatizace",
    "works": "funguje",
    "offline": "offline",
    "online": "online",
    "and": "a",
    # Greetings
    "hello": "ahoj",
    "hi": "ahoj",
    "hey": "ahoj",
    "bye": "nashledanou",
    "goodbye": "nashledanou",
    # Common responses
    "yes": "ano",
    "no": "ne",
    "ok": "ok",
    "okay": "ok",
    "sure": "jasně",
    "please": "prosím",
    "thanks": "děkuji",
    "thank": "děkuji",
    # Pronouns
    "i": "já",
    "you": "vy",
    "he": "on",
    "she": "ona",
    "we": "my",
    "they": "oni",
    "me": "mě",
    "him": "ho",
    "her": "ji",
    "us": "nás",
    "them": "je",
    # Verbs - present
    "am": "jsem",
    "is": "je",
    "are": "jsou",
    "have": "mám",
    "has": "má",
    "do": "dělám",
    "does": "dělá",
    "go": "jdu",
    "goes": "jde",
    "come": "přijdu",
    "comes": "přijde",
    "see": "vidím",
    "sees": "vidí",
    "know": "vím",
    "knows": "ví",
    "think": "myslím",
    "thinks": "myslí",
    "want": "chci",
    "wants": "chce",
    "need": "potřebuji",
    "needs": "potřebuje",
    "like": "mám rád",
    "likes": "má rád",
    "love": "miluju",
    "loves": "miluje",
    # Verbs - past
    "was": "byl",
    "were": "byli",
    "had": "měl",
    "did": "udělal",
    "went": "šel",
    "came": "přišel",
    "saw": "viděl",
    "knew": "věděl",
    "thought": "myslel",
    # Verbs - future/conditional
    "will": "budu",
    "would": "bych",
    "could": "mohl",
    "should": "měl",
    "must": "musím",
    "can": "mohu",
    # Time
    "today": "dnes",
    "tomorrow": "zítra",
    "yesterday": "včera",
    "now": "teď",
    "later": "později",
    "soon": "brzy",
    "time": "čas",
    "day": "den",
    "night": "noc",
    "morning": "ráno",
    "evening": "večer",
    # Work/meeting
    "meeting": "schůzka",
    "call": "hovor",
    "interview": "pohovor",
    "question": "otázka",
    "answer": "odpověď",
    "problem": "problém",
    "solution": "řešení",
    "test": "test",
    "code": "kód",
    "bug": "chyba",
    "fix": "oprava",
    "deploy": "nasazení",
    "build": "build",
    "run": "spustit",
    "work": "práce",
    "project": "projekt",
    "task": "úkol",
    # Tech
    "python": "python",
    "server": "server",
    "client": "klient",
    "api": "api",
    "database": "databáze",
    "config": "config",
    "script": "skript",
    "automation": "automatizace",
    # Articles/prepositions (empty for Czech)
    "the": "",
    "a": "",
    "an": "",
    "in": "v",
    "on": "na",
    "at": "u",
    "to": "do",
    "for": "pro",
    "with": "s",
    "from": "z",
    "by": "od",
    "of": "",
}


def _strip_diacritics(text: str) -> str:
    """Remove diacritics from text for case-insensitive map lookup."""
    return "".join(
        c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn"
    )


@dataclass(slots=True)
class TranslationResult:
    text: str
    backend: str
    online_ok: bool
    error: str | None = None


class LocalFallbackTranslator:
    backend_name = "local"

    def translate(self, text: str) -> TranslationResult:
        # Split on word boundaries, keep punctuation attached to preceding word
        tokens = re.findall(r"\w+(?:[.,!?;:]*)|[.,!?;:]+", text, flags=re.UNICODE)
        translated_tokens = []
        for token in tokens:
            # Separate word from trailing punctuation
            match = re.match(r"^(\w+)([.,!?;:]*)$", token, flags=re.UNICODE)
            if match:
                word, punct = match.groups()
                # Diacritic-insensitive lookup
                word_key = _strip_diacritics(word).lower()
                translated = LOCAL_TOKEN_MAP.get(word_key, word)
                translated_tokens.append(translated + punct)
            else:
                translated_tokens.append(token)

        # Join with spaces, but don't add space before punctuation
        translated = ""
        for i, token in enumerate(translated_tokens):
            if i == 0:
                translated = token
            elif re.match(r"^[.,!?;:]+$", token):
                translated += token
            else:
                translated += " " + token

        return TranslationResult(text=translated, backend=self.backend_name, online_ok=False)


class CTranslate2Translator:
    backend_name = "ctranslate2"

    def __init__(
        self,
        model_dir: Path,
        device: str = "auto",
        compute_type: str = "auto",
    ) -> None:
        if ctranslate2 is None:
            raise RuntimeError("ctranslate2 is not installed in the active environment")
        if Tokenizer is None:
            raise RuntimeError("tokenizers is not installed in the active environment")

        self.model_dir = Path(model_dir)
        if not self.model_dir.is_dir():
            raise FileNotFoundError(f"Translation model directory does not exist: {model_dir}")

        # Device resolution: auto -> cuda if available else cpu
        if device == "auto":
            try:
                has_cuda = ctranslate2.get_cuda_device_count() > 0
            except Exception:
                has_cuda = False
            self.device = "cuda" if has_cuda else "cpu"
        else:
            self.device = device

        # Compute type resolution
        if compute_type == "auto":
            self.compute_type = "int8"
        else:
            self.compute_type = compute_type

        # Initialize ctranslate2.Translator with fallback to CPU if CUDA fails
        try:
            self.translator = ctranslate2.Translator(
                str(self.model_dir),
                device=self.device,
                compute_type=self.compute_type,
            )
        except Exception as exc:
            if self.device != "cpu":
                logger.warning(
                    "Failed initializing CTranslate2 on %s (%s); falling back to CPU int8",
                    self.device,
                    exc,
                )
                self.device = "cpu"
                self.compute_type = "int8"
                self.translator = ctranslate2.Translator(
                    str(self.model_dir),
                    device="cpu",
                    compute_type="int8",
                )
            else:
                raise

        # Load tokenizer
        tokenizer_file = self.model_dir / "tokenizer.json"
        if not tokenizer_file.is_file():
            raise FileNotFoundError(f"Missing tokenizer.json in model directory: {self.model_dir}")

        self.tokenizer = self._load_tokenizer(tokenizer_file)

    @staticmethod
    def _load_tokenizer(tok_path: Path) -> Tokenizer:
        try:
            return Tokenizer.from_file(str(tok_path))
        except Exception:
            # Handle possible null precompiled_charsmap panic
            with open(tok_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("normalizer", {}).get("precompiled_charsmap") is None:
                data["normalizer"] = None
            return Tokenizer.from_str(json.dumps(data))

    def translate(self, text: str) -> TranslationResult:
        stripped = text.strip()
        if not stripped:
            return TranslationResult(text="", backend=self.backend_name, online_ok=False)

        try:
            encoded = self.tokenizer.encode(stripped)
            tokens = list(encoded.tokens)
            if not tokens or tokens == ["</s>"]:
                return TranslationResult(text="", backend=self.backend_name, online_ok=False)

            if tokens[-1] != "</s>":
                tokens.append("</s>")

            results = self.translator.translate_batch([tokens])
            target_tokens = results[0].hypotheses[0]

            target_ids = [
                self.tokenizer.token_to_id(t)
                for t in target_tokens
                if self.tokenizer.token_to_id(t) is not None
            ]
            decoded = self.tokenizer.decode(target_ids)
            if not decoded and target_tokens:
                decoded = "".join(target_tokens).replace("\u2581", " ").strip()

            return TranslationResult(text=decoded, backend=self.backend_name, online_ok=False)
        except Exception as exc:
            return TranslationResult(
                text="",
                backend=self.backend_name,
                online_ok=False,
                error=str(exc),
            )


class HybridTranslator:
    def __init__(
        self,
        online_backend: str = "disabled",
        force_offline: bool = True,
        model_name: str | None = None,
        cache_dir: Path | None = None,
        device: str = "auto",
        compute_type: str = "auto",
        nmt_translator: Translator | None = None,
    ) -> None:
        self.force_offline = force_offline
        self.online_backend = online_backend
        self.local_backend = LocalFallbackTranslator()
        self.online = None  # Offline-only mode
        self.nmt_backend: Translator | None = nmt_translator
        self.nmt_error: str | None = None

        if self.nmt_backend is None and model_name is not None:
            try:
                from .nmt_model import resolve_translation_model

                resolved_path = resolve_translation_model(
                    model_name=model_name,
                    cache_dir=cache_dir
                    or (Path.home() / ".local" / "state" / "myvoicetranslator" / "translation_models"),
                    force_offline=force_offline,
                )
                if resolved_path is not None:
                    self.nmt_backend = CTranslate2Translator(
                        model_dir=resolved_path,
                        device=device,
                        compute_type=compute_type,
                    )
                else:
                    self.nmt_error = f"Translation model '{model_name}' could not be resolved or found."
            except Exception as exc:
                self.nmt_error = f"Failed to initialize neural translator: {exc}"

    @property
    def active_backend_name(self) -> str:
        if self.nmt_backend is not None:
            return getattr(self.nmt_backend, "backend_name", "ctranslate2")
        return self.local_backend.backend_name

    def translate(self, text: str) -> TranslationResult:
        if self.nmt_backend is not None:
            res = self.nmt_backend.translate(text)
            if not res.error:
                return res
            # Fall back on inference error
            fallback = self.local_backend.translate(text)
            return TranslationResult(
                text=fallback.text,
                backend=fallback.backend,
                online_ok=False,
                error=f"NMT inference failed ({res.error}), used fallback",
            )

        fallback = self.local_backend.translate(text)
        if self.nmt_error:
            return TranslationResult(
                text=fallback.text,
                backend=fallback.backend,
                online_ok=False,
                error=self.nmt_error,
            )
        return fallback