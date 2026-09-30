from interview_shield.translate import LocalFallbackTranslator


def test_local_fallback_translation(benchmark):
    translator = LocalFallbackTranslator()
    text = "Hello, world! I am looking for a senior Python developer with automation skills."
    
    def run_translation():
        return translator.translate(text)

    result = benchmark(run_translation)
    assert result.text != ""
