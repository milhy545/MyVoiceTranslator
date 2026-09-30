from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from interview_shield.interfaces import Translator
from interview_shield.nmt_model import (
    _sanitize_tokenizer_json,
    resolve_translation_model,
)
from interview_shield.translate import (
    CTranslate2Translator,
    HybridTranslator,
    TranslationResult,
)


class ModelResolutionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.cache_dir = Path(self.temp_dir.name)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_local_directory_with_model_bin(self) -> None:
        model_dir = self.cache_dir / "my_local_model"
        model_dir.mkdir(parents=True)
        (model_dir / "model.bin").write_bytes(b"dummy model weights")
        (model_dir / "tokenizer.json").write_text('{"normalizer": null}', encoding="utf-8")

        resolved = resolve_translation_model(str(model_dir), cache_dir=self.cache_dir)
        self.assertEqual(resolved, model_dir)

    def test_offline_not_found_returns_none(self) -> None:
        resolved = resolve_translation_model(
            "nonexistent/remote-model-xyz",
            cache_dir=self.cache_dir,
            force_offline=True,
        )
        self.assertIsNone(resolved)

    @patch("huggingface_hub.snapshot_download")
    def test_snapshot_download_success(self, mock_download: MagicMock) -> None:
        fake_download_dir = self.cache_dir / "downloaded_model"
        fake_download_dir.mkdir(parents=True)
        (fake_download_dir / "model.bin").write_bytes(b"fake model")
        (fake_download_dir / "tokenizer.json").write_text("{}", encoding="utf-8")
        mock_download.return_value = str(fake_download_dir)

        resolved = resolve_translation_model(
            "custom/model",
            cache_dir=self.cache_dir,
            force_offline=False,
        )
        self.assertEqual(resolved, fake_download_dir)
        mock_download.assert_called_once()

    @patch("huggingface_hub.snapshot_download")
    def test_fallback_candidate_when_primary_fails(self, mock_download: MagicMock) -> None:
        fake_download_dir = self.cache_dir / "fallback_model"
        fake_download_dir.mkdir(parents=True)
        (fake_download_dir / "model.bin").write_bytes(b"fallback model")
        (fake_download_dir / "tokenizer.json").write_text("{}", encoding="utf-8")

        # First candidate fails, second candidate succeeds
        mock_download.side_effect = [
            RuntimeError("Repo not found"),
            str(fake_download_dir),
        ]

        resolved = resolve_translation_model(
            "michaelfeil/ct2fast-opus-mt-en-cs",
            cache_dir=self.cache_dir,
            force_offline=False,
        )
        self.assertEqual(resolved, fake_download_dir)
        self.assertEqual(mock_download.call_count, 2)

    def test_sanitize_tokenizer_json(self) -> None:
        tok_file = self.cache_dir / "tokenizer.json"
        tok_file.write_text(
            json.dumps({
                "version": "1.0",
                "normalizer": {"type": "Precompiled", "precompiled_charsmap": None},
            }),
            encoding="utf-8",
        )
        _sanitize_tokenizer_json(tok_file)

        with open(tok_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertIsNone(data["normalizer"])


class DeviceAndComputeSelectionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.model_dir = Path(self.temp_dir.name)
        (self.model_dir / "model.bin").write_bytes(b"fake weights")
        (self.model_dir / "tokenizer.json").write_text('{"normalizer": null}', encoding="utf-8")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    @patch("interview_shield.translate.ctranslate2.Translator")
    @patch("interview_shield.translate.ctranslate2.get_cuda_device_count", return_value=1)
    @patch("interview_shield.translate.Tokenizer.from_file")
    def test_auto_device_selects_cuda_when_available(
        self, mock_tok: MagicMock, mock_cuda_count: MagicMock, mock_trans_cls: MagicMock
    ) -> None:
        translator = CTranslate2Translator(model_dir=self.model_dir, device="auto", compute_type="auto")
        self.assertEqual(translator.device, "cuda")
        self.assertEqual(translator.compute_type, "int8")
        mock_trans_cls.assert_called_with(str(self.model_dir), device="cuda", compute_type="int8")

    @patch("interview_shield.translate.ctranslate2.Translator")
    @patch("interview_shield.translate.ctranslate2.get_cuda_device_count", return_value=0)
    @patch("interview_shield.translate.Tokenizer.from_file")
    def test_auto_device_selects_cpu_when_no_cuda(
        self, mock_tok: MagicMock, mock_cuda_count: MagicMock, mock_trans_cls: MagicMock
    ) -> None:
        translator = CTranslate2Translator(model_dir=self.model_dir, device="auto", compute_type="auto")
        self.assertEqual(translator.device, "cpu")
        self.assertEqual(translator.compute_type, "int8")
        mock_trans_cls.assert_called_with(str(self.model_dir), device="cpu", compute_type="int8")

    @patch("interview_shield.translate.ctranslate2.Translator")
    @patch("interview_shield.translate.Tokenizer.from_file")
    def test_explicit_device_and_compute_type(
        self, mock_tok: MagicMock, mock_trans_cls: MagicMock
    ) -> None:
        translator = CTranslate2Translator(model_dir=self.model_dir, device="cpu", compute_type="float32")
        self.assertEqual(translator.device, "cpu")
        self.assertEqual(translator.compute_type, "float32")
        mock_trans_cls.assert_called_with(str(self.model_dir), device="cpu", compute_type="float32")

    @patch("interview_shield.translate.ctranslate2.Translator")
    @patch("interview_shield.translate.ctranslate2.get_cuda_device_count", return_value=1)
    @patch("interview_shield.translate.Tokenizer.from_file")
    def test_cuda_failure_falls_back_to_cpu(
        self, mock_tok: MagicMock, mock_cuda_count: MagicMock, mock_trans_cls: MagicMock
    ) -> None:
        # CUDA call raises, CPU fallback succeeds
        mock_trans_cls.side_effect = [RuntimeError("CUDA OOM"), MagicMock()]
        translator = CTranslate2Translator(model_dir=self.model_dir, device="cuda", compute_type="float16")
        self.assertEqual(translator.device, "cpu")
        self.assertEqual(translator.compute_type, "int8")


class CTranslate2TranslatorLogicTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.model_dir = Path(self.temp_dir.name)
        (self.model_dir / "model.bin").write_bytes(b"fake weights")
        (self.model_dir / "tokenizer.json").write_text('{"normalizer": null}', encoding="utf-8")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    @patch("interview_shield.translate.ctranslate2.Translator")
    @patch("interview_shield.translate.Tokenizer.from_file")
    def test_protocol_adherence(self, mock_tok: MagicMock, mock_trans_cls: MagicMock) -> None:
        translator = CTranslate2Translator(model_dir=self.model_dir, device="cpu")
        self.assertIsInstance(translator, Translator)

    @patch("interview_shield.translate.ctranslate2.Translator")
    @patch("interview_shield.translate.Tokenizer.from_file")
    def test_empty_and_whitespace_input(
        self, mock_tok: MagicMock, mock_trans_cls: MagicMock
    ) -> None:
        translator = CTranslate2Translator(model_dir=self.model_dir, device="cpu")
        res_empty = translator.translate("")
        self.assertEqual(res_empty.text, "")
        self.assertEqual(res_empty.backend, "ctranslate2")
        self.assertFalse(res_empty.online_ok)

        res_spaces = translator.translate("   \n\t  ")
        self.assertEqual(res_spaces.text, "")
        self.assertEqual(res_spaces.backend, "ctranslate2")

    @patch("interview_shield.translate.ctranslate2.Translator")
    @patch("interview_shield.translate.Tokenizer.from_file")
    def test_successful_translation(
        self, mock_tok_from_file: MagicMock, mock_trans_cls: MagicMock
    ) -> None:
        mock_tok = MagicMock()
        mock_tok_from_file.return_value = mock_tok
        mock_encoding = MagicMock()
        mock_encoding.tokens = [" Hello", " world"]
        mock_tok.encode.return_value = mock_encoding
        mock_tok.token_to_id.side_effect = lambda t: 10
        mock_tok.decode.return_value = "Ahoj světe"

        mock_backend_trans = MagicMock()
        mock_trans_cls.return_value = mock_backend_trans
        hypothesis = MagicMock()
        hypothesis.hypotheses = [[" Ahoj", " světe"]]
        mock_backend_trans.translate_batch.return_value = [hypothesis]

        translator = CTranslate2Translator(model_dir=self.model_dir, device="cpu")
        result = translator.translate("Hello world")

        self.assertEqual(result.text, "Ahoj světe")
        self.assertEqual(result.backend, "ctranslate2")
        self.assertFalse(result.online_ok)
        self.assertIsNone(result.error)

    @patch("interview_shield.translate.ctranslate2.Translator")
    @patch("interview_shield.translate.Tokenizer.from_file")
    def test_inference_exception_captured_gracefully(
        self, mock_tok_from_file: MagicMock, mock_trans_cls: MagicMock
    ) -> None:
        mock_tok = MagicMock()
        mock_tok_from_file.return_value = mock_tok
        mock_encoding = MagicMock()
        mock_encoding.tokens = [" Hello"]
        mock_tok.encode.return_value = mock_encoding

        mock_backend_trans = MagicMock()
        mock_trans_cls.return_value = mock_backend_trans
        mock_backend_trans.translate_batch.side_effect = RuntimeError("Inference crash")

        translator = CTranslate2Translator(model_dir=self.model_dir, device="cpu")
        result = translator.translate("Hello")

        self.assertEqual(result.text, "")
        self.assertEqual(result.backend, "ctranslate2")
        self.assertIsNotNone(result.error)
        self.assertIn("Inference crash", result.error)


class HybridTranslatorFallbackTest(unittest.TestCase):
    def test_fallback_when_nmt_none(self) -> None:
        hybrid = HybridTranslator(nmt_translator=None)
        self.assertEqual(hybrid.active_backend_name, "local")
        result = hybrid.translate("good morning")
        self.assertEqual(result.backend, "local")
        self.assertEqual(result.text, "dobré ráno")

    def test_prioritizes_nmt_when_available(self) -> None:
        mock_nmt = MagicMock()
        mock_nmt.backend_name = "ctranslate2"
        mock_nmt.translate.return_value = TranslationResult(
            text="Dobré ráno z NMT",
            backend="ctranslate2",
            online_ok=False,
        )

        hybrid = HybridTranslator(nmt_translator=mock_nmt)
        self.assertEqual(hybrid.active_backend_name, "ctranslate2")
        result = hybrid.translate("good morning")
        self.assertEqual(result.backend, "ctranslate2")
        self.assertEqual(result.text, "Dobré ráno z NMT")

    def test_falls_back_to_local_when_nmt_returns_error(self) -> None:
        mock_nmt = MagicMock()
        mock_nmt.backend_name = "ctranslate2"
        mock_nmt.translate.return_value = TranslationResult(
            text="",
            backend="ctranslate2",
            online_ok=False,
            error="CUDA crash",
        )

        hybrid = HybridTranslator(nmt_translator=mock_nmt)
        result = hybrid.translate("good morning")
        self.assertEqual(result.backend, "local")
        self.assertEqual(result.text, "dobré ráno")
        self.assertIsNotNone(result.error)
        self.assertIn("NMT inference failed", result.error)


class LiveNeuralTranslationFixtureTest(unittest.TestCase):
    """Verifies real NMT output against the acceptance criteria if model is cached."""

    def test_acceptance_criteria_sentence(self) -> None:
        cache_dir = Path.home() / ".local" / "state" / "myvoicetranslator" / "translation_models"
        resolved = resolve_translation_model(
            "michaelfeil/ct2fast-opus-mt-en-cs",
            cache_dir=cache_dir,
            force_offline=True,
        )
        if resolved is None:
            self.skipTest("CTranslate2 OPUS-MT model not cached on host")

        translator = CTranslate2Translator(model_dir=resolved, device="auto")
        sentence = "We are looking for a senior DevOps engineer with Linux and Python skills."
        result = translator.translate(sentence)

        self.assertEqual(result.backend, "ctranslate2")
        self.assertIsNone(result.error)
        # Verify sentence translated meaningfully to Czech
        text_lower = result.text.lower()
        self.assertTrue(
            any(word in text_lower for word in ["hledáme", "inženýr", "devops", "linux", "python"]),
            f"Translation did not contain expected terms: {result.text}",
        )


if __name__ == "__main__":
    unittest.main()
