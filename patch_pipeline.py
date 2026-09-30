import re

with open("interview_shield/pipeline.py", "r") as f:
    content = f.read()

# Add imports
if "from concurrent.futures import ThreadPoolExecutor" not in content:
    content = content.replace("import threading", "import threading\nfrom concurrent.futures import ThreadPoolExecutor")

# Rename _flush_buffer to _queue_audio for clarity in the class, or just keep _flush_buffer and make it submit to executor
flush_code = """
    def _flush_buffer(self, buffer: list[np.ndarray] | np.ndarray, input_mode: str) -> None:
        if isinstance(buffer, np.ndarray):
            joined = buffer
        elif not buffer:
            return
        else:
            joined = np.concatenate(buffer)

        if len(joined) == 0:
            return

        # Drop pure background silence buffers to avoid running Whisper STT on silence
        if np.max(np.abs(joined)) < 1e-4:
            return

        # Submit to executor if it exists, otherwise process synchronously
        if hasattr(self, "_executor") and self._executor is not None:
            self._executor.submit(self._process_audio_task, joined, input_mode)
        else:
            self._process_audio_task(joined, input_mode)

    def _process_audio_task(self, joined: np.ndarray, input_mode: str) -> None:
        self._set_audio_state("Transcribing")
        try:
            text = self.transcriber.normalise_segments(self.transcriber.transcribe_samples(joined, self.config.sample_rate))
            if text:
                self._emit_transcript(text, input_mode=input_mode)
        finally:
            self._set_audio_state("Listening")
"""

content = re.sub(r'    def _flush_buffer\(self, buffer: list\[np\.ndarray\] \| np\.ndarray, input_mode: str\) -> None:.*?        finally:\n            self\._set_audio_state\("Listening"\)', flush_code.strip(), content, flags=re.DOTALL)

# Update run_simulated_live
sim_live = """    def run_simulated_live(self, wav_path: Path, input_mode: str) -> PipelineRun:
        self._status("info", f"Simulated live input: {input_mode} from {wav_path}")
        self._executor = ThreadPoolExecutor(max_workers=1)
        try:
"""
content = content.replace('    def run_simulated_live(self, wav_path: Path, input_mode: str) -> PipelineRun:\n        self._status("info", f"Simulated live input: {input_mode} from {wav_path}")', sim_live)
content = content.replace('        return PipelineRun(self.transcripts, self.status_events)\n\n    def _flush_buffer', '        finally:\n            self._executor.shutdown(wait=True)\n            self._executor = None\n\n        return PipelineRun(self.transcripts, self.status_events)\n\n    def _flush_buffer')

# Update run_live
run_live = """    def run_live(
        self,
        stop_event: threading.Event | None = None,
    ) -> PipelineRun:  # pragma: no cover - interactive mode
        self._executor = ThreadPoolExecutor(max_workers=1)
        try:
            source: AudioSource
"""
content = content.replace('    def run_live(\n        self,\n        stop_event: threading.Event | None = None,\n    ) -> PipelineRun:  # pragma: no cover - interactive mode\n        source: AudioSource', run_live)
content = content.replace('        self._status("info", "Live capture stopped.")\n        return PipelineRun(self.transcripts, self.status_events)', '        self._status("info", "Live capture stopped.")\n        finally:\n            self._executor.shutdown(wait=True)\n            self._executor = None\n\n        return PipelineRun(self.transcripts, self.status_events)')

with open("interview_shield/pipeline.py", "w") as f:
    f.write(content)
