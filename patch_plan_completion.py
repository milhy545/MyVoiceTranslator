with open("conductor/tracks/chrome-extension-and-launcher_20260915/plan.md", "r") as f:
    content = f.read()

content = content.replace("- [ ] Task: Vytvořit instalační skript", "- [x] Task: Vytvořit instalační skript")
content = content.replace("- [ ] Task: Refaktorovat `shield.py`", "- [x] Task: Refaktorovat `shield.py`")
content = content.replace("- [ ] Task: Upravit `tui.py`", "- [x] Task: Upravit `tui.py`")

content = content.replace("- [ ] Task: Přidat `fastapi`", "- [x] Task: Přidat `fastapi`")
content = content.replace("- [ ] Task: Vytvořit `interview_shield/server.py`", "- [x] Task: Vytvořit `interview_shield/server.py`")
content = content.replace("- [ ] Task: Implementovat endpoint `/api/switch-to-tui`", "- [x] Task: Implementovat endpoint `/api/switch-to-tui`")
content = content.replace("- [ ] Task: Zabezpečit spouštění serveru", "- [x] Task: Zabezpečit spouštění serveru")

content = content.replace("- [ ] Task: Založit složku `chrome_extension/`", "- [x] Task: Založit složku `chrome_extension/`")
content = content.replace("- [ ] Task: Implementovat `background.js`", "- [x] Task: Implementovat `background.js`")

content = content.replace("- [ ] Task: Vytvořit `sidepanel.html`", "- [x] Task: Vytvořit `sidepanel.html`")
content = content.replace("- [ ] Task: Vytvořit `content.js`", "- [x] Task: Vytvořit `content.js`")

content = content.replace("- [ ] Task: Spustit sadu testů", "- [x] Task: Spustit sadu testů")
content = content.replace("- [ ] Task: Spustit statickou analýzu", "- [x] Task: Spustit statickou analýzu")
content = content.replace("- [ ] Task: Napsat end-to-end test", "- [x] Task: Napsat end-to-end test")

content = content.replace("- [ ] Acceptance criteria verified", "- [x] Acceptance criteria verified")
content = content.replace("- [ ] Required project completion gate passed", "- [x] Required project completion gate passed")

with open("conductor/tracks/chrome-extension-and-launcher_20260915/plan.md", "w") as f:
    f.write(content)
