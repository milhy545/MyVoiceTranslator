import re

with open("interview_shield/tui.py", "r") as f:
    content = f.read()

old_logic = """        if stt_changed:
            self.debug_log.write("[red]STT config changed (model/device). Full app restart required for changes to take effect.[/]")
            self.debug_log.write("[yellow]Reusing existing transcriber; changes will apply on next full restart.[/]")
        else:
            self.debug_log.write("[cyan]Applying configuration and restarting capture (reusing transcriber).[/]")"""

new_logic = """        if stt_changed:
            self.debug_log.write("[yellow]STT config changed. Restarting Transcriber (this may take a moment to load the model).[/]")
            if self._shared_transcriber is not None:
                self._shared_transcriber.close()
                self._shared_transcriber = None
        else:
            self.debug_log.write("[cyan]Applying configuration and restarting capture (reusing transcriber).[/]")"""

content = content.replace(old_logic, new_logic)

with open("interview_shield/tui.py", "w") as f:
    f.write(content)
