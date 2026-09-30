import numpy as np

from interview_shield.stt import WhisperTranscriber


def test_stt_benchmark(benchmark):
    # Initialize transcriber (this will take time, but benchmark function runs it later)
    # We will use CPU and int8 to simulate the fallback.
    transcriber = WhisperTranscriber(model_name="tiny.en", requested_device="cpu", compute_type="int8")
    
    # Generate 3 seconds of dummy audio at 16kHz
    audio = np.zeros(16000 * 3, dtype=np.float32)
    
    def run_stt():
        return transcriber.transcribe_samples(audio)

    result = benchmark(run_stt)
    assert result is not None
