from __future__ import annotations

import unittest

from interview_shield.translate import (
    HybridTranslator,
    LocalFallbackTranslator,
)


class LocalFallbackTranslatorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.translator = LocalFallbackTranslator()

    def test_known_words(self) -> None:
        result = self.translator.translate("good morning python")
        self.assertEqual(result.text, "dobré ráno python")
        self.assertEqual(result.backend, "local")
        self.assertFalse(result.online_ok)

    def test_unknown_words_passthrough(self) -> None:
        result = self.translator.translate("hello world")
        # hello -> ahoj, world not in map
        self.assertEqual(result.text, "ahoj world")
        self.assertEqual(result.backend, "local")

    def test_punctuation_handling(self) -> None:
        result = self.translator.translate("good morning!")
        self.assertEqual(result.text, "dobré ráno!")

    def test_comma_handling(self) -> None:
        result = self.translator.translate("good, morning")
        self.assertEqual(result.text, "dobré, ráno")

    def test_question_mark(self) -> None:
        result = self.translator.translate("how are you?")
        # how -> how, are -> jsou, you -> vy
        self.assertEqual(result.text, "how jsou vy?")

    def test_multiple_punctuation(self) -> None:
        result = self.translator.translate("hello! world? yes.")
        # hello -> ahoj, world not in map, yes -> ano
        self.assertEqual(result.text, "ahoj! world? ano.")

    def test_diacritics_in_input(self) -> None:
        # Czech diacritics should be stripped for lookup
        result = self.translator.translate("dobré ráno")
        self.assertEqual(result.text, "dobré ráno")

    def test_mixed_known_unknown(self) -> None:
        result = self.translator.translate("good python world")
        self.assertEqual(result.text, "dobré python world")

    def test_case_insensitive(self) -> None:
        result = self.translator.translate("GOOD MORNING")
        self.assertEqual(result.text, "dobré ráno")

    def test_empty_string(self) -> None:
        result = self.translator.translate("")
        self.assertEqual(result.text, "")

    def test_only_punctuation(self) -> None:
        result = self.translator.translate("!!!")
        self.assertEqual(result.text, "!!!")


class HybridTranslatorTest(unittest.TestCase):
    def test_force_offline_uses_local(self) -> None:
        translator = HybridTranslator(force_offline=True)
        result = translator.translate("good morning")
        self.assertEqual(result.backend, "local")
        self.assertFalse(result.online_ok)

    def test_force_offline_true_by_default(self) -> None:
        translator = HybridTranslator()
        self.assertTrue(translator.force_offline)
        self.assertIsNone(translator.online)

    def test_local_backend_attribute(self) -> None:
        translator = HybridTranslator()
        self.assertIsNotNone(translator.local_backend)
        self.assertEqual(translator.local_backend.backend_name, "local")


if __name__ == "__main__":
    unittest.main()