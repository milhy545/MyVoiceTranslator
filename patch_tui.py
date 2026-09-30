import re

with open("interview_shield/tui.py", "r") as f:
    content = f.read()

# Replace _load_devices to use run_worker
new_load_devices = """
    def _load_devices(self) -> None:
        self.run_worker(self._async_load_devices, thread=True)

    def _async_load_devices(self) -> None:
        devices = list_input_devices(force_refresh=True)
        self.call_from_thread(self._apply_loaded_devices, devices)

    def _apply_loaded_devices(self, devices) -> None:
        self.available_devices = devices
        opts = self._device_options()
        self.device_select.set_options(opts)
        self.monitor_device_select.set_options(opts)
        self._update_device_hint()
        self.debug_log.write(f"[cyan]Devices refreshed:[/] {len(self.available_devices)} input candidates")
"""

content = re.sub(r'    def _load_devices\(self\) -> None:.*?        self\.debug_log\.write\(f"\[cyan\]Devices refreshed:\[/\] {len\(self\.available_devices\)} input candidates"\)', new_load_devices.strip('\n'), content, flags=re.DOTALL)

with open("interview_shield/tui.py", "w") as f:
    f.write(content)
