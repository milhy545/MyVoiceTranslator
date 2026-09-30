with open("conductor/tracks/fix-stt-blocking-and-tech-debt_20260915/plan.md", "r") as f:
    content = f.read()

content = content.replace("- [ ] Task: Run full test suite", "- [x] Task: Run full test suite")
content = content.replace("- [ ] Task: Run type checks and linter", "- [x] Task: Run type checks and linter")
content = content.replace("- [ ] Task: Run STT benchmark", "- [x] Task: Run STT benchmark")
content = content.replace("- [ ] Acceptance criteria verified", "- [x] Acceptance criteria verified")
content = content.replace("- [ ] Required project completion gate passed", "- [x] Required project completion gate passed")

with open("conductor/tracks/fix-stt-blocking-and-tech-debt_20260915/plan.md", "w") as f:
    f.write(content)
