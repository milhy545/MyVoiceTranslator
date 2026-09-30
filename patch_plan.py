with open("conductor/tracks/fix-stt-blocking-and-tech-debt_20260915/plan.md", "r") as f:
    content = f.read()

content = content.replace("- [ ] Task: In `interview_shield/pipeline.py`", "- [x] Task: In `interview_shield/pipeline.py`")
content = content.replace("- [ ] Task: Ensure `_flush_buffer` places", "- [x] Task: Ensure `_flush_buffer` places")
content = content.replace("- [ ] Task: Create a worker loop", "- [x] Task: Create a worker loop")
content = content.replace("- [ ] Task: Update the `tests/test_pipeline.py`", "- [x] Task: Update the `tests/test_pipeline.py`")

content = content.replace("- [ ] Task: In `interview_shield/stt.py`", "- [x] Task: In `interview_shield/stt.py`")
content = content.replace("- [ ] Task: In `interview_shield/audio.py`", "- [x] Task: In `interview_shield/audio.py`")
content = content.replace("- [ ] Task: Ensure TUI calls `close()`", "- [x] Task: Ensure TUI calls `close()`")

with open("conductor/tracks/fix-stt-blocking-and-tech-debt_20260915/plan.md", "w") as f:
    f.write(content)
