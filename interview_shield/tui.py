from __future__ import annotations

import threading

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import (
    Button,
    Footer,
    Header,
    Label,
    RichLog,
    Select,
    Static,
    Switch,
)

from .audio import (
    AudioDeviceInfo,
    invalidate_device_cache,
    list_input_devices,
    resolve_input_device_name,
)
from .config import AppConfig
from .diagnostics import run_doctor
from .events import StatusEvent, TranscriptEvent
from .logging_utils import SessionLogger
from .pipeline import InterviewShieldPipeline
from .stt import WhisperTranscriber
from .translate import HybridTranslator


class InterviewShieldApp(App[None]):  # pragma: no cover - interactive UI
    CSS = """
    Screen {
        layout: vertical;
        background: rgb(16, 18, 24);
        color: rgb(231, 235, 240);
    }

    #status-bar {
        height: 3;
        content-align: center middle;
        background: rgb(18, 32, 58);
        color: rgb(245, 247, 250);
        text-style: bold;
    }

    #body {
        height: 1fr;
    }

    #main-pane {
        width: 3fr;
        min-width: 60;
    }

    #live-windows {
        height: 18;
        min-height: 12;
        margin-bottom: 1;
    }

    #en-window {
        width: 1fr;
        border: round rgb(45, 212, 191);
        padding: 1 2;
        background: rgb(8, 28, 30);
        color: rgb(224, 242, 254);
        margin-right: 1;
    }

    #cz-window {
        width: 1fr;
        border: round rgb(250, 204, 21);
        padding: 1 2;
        background: rgb(38, 30, 6);
        color: rgb(255, 248, 196);
        text-style: bold;
    }

    #debug {
        height: 14;
        border: round rgb(245, 158, 11);
        padding: 0 1;
    }

    #history {
        height: 1fr;
        min-height: 10;
        margin-bottom: 1;
    }

    #history-columns {
        height: 1fr;
    }

    #history-en,
    #history-cz {
        width: 1fr;
        border: round rgb(71, 85, 105);
        padding: 1 2;
        background: rgb(15, 23, 42);
    }

    #history-en {
        margin-right: 1;
    }

    #history-en-content,
    #history-cz-content {
        color: rgb(203, 213, 225);
    }

    #control-pane {
        width: 42;
        min-width: 36;
        border: round rgb(59, 130, 246);
        padding: 1 2;
        background: rgb(11, 16, 28);
    }

    .section-title {
        color: rgb(147, 197, 253);
        text-style: bold;
        margin: 1 0 0 0;
    }

    .control-label {
        margin: 1 0 0 0;
        color: rgb(191, 219, 254);
    }

    Select {
        width: 100%;
        margin: 0 0 1 0;
    }

    Switch {
        margin: 0 0 1 0;
    }

    .button-row {
        height: auto;
        margin: 1 0 0 0;
    }

    .button-row Button {
        width: 1fr;
        margin-right: 1;
    }

    .button-row Button:last-child {
        margin-right: 0;
    }

    #device-hint {
        color: rgb(148, 163, 184);
        margin: 0 0 1 0;
    }

    #doctor-summary {
        color: rgb(203, 213, 225);
        margin-top: 1;
    }
    """

    AUTO_DEVICE_VALUE = "__auto__"
    INPUT_MODE_OPTIONS = [
        ("Auto", "auto"),
        ("Microphone", "mic"),
        ("Internal Audio / Monitor", "monitor"),
        ("Dual (Mic + System)", "dual"),
    ]
    STT_DEVICE_OPTIONS = [
        ("Auto", "auto"),
        ("CPU", "cpu"),
        ("CUDA", "cuda"),
    ]
    COMPUTE_TYPE_OPTIONS = [
        ("Auto", "auto"),
        ("Int8 (CPU/GPU)", "int8"),
        ("Float16 (GPU)", "float16"),
        ("Int8-Float16 (GPU)", "int8_float16"),
    ]
    ONLINE_BACKEND_OPTIONS = [
        ("Google", "google"),
        ("Disabled / local only", "disabled"),
    ]
    MODEL_OPTIONS = [
        ("tiny.en", "tiny.en"),
        ("base.en", "base.en"),
        ("small.en", "small.en"),
        ("medium.en", "medium.en"),
        ("large-v3", "large-v3"),
    ]
    MODEL_METADATA = {
        "tiny.en": {"multilingual": False, "size_mb": 39},
        "base.en": {"multilingual": False, "size_mb": 74},
        "small.en": {"multilingual": False, "size_mb": 244},
        "medium.en": {"multilingual": False, "size_mb": 769},
        "large-v3": {"multilingual": True, "size_mb": 1550},
    }

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("r", "restart_capture", "Apply + restart"),
        ("s", "stop_capture", "Stop capture"),
        ("f", "refresh_devices", "Refresh devices"),
        ("o", "toggle_offline", "Toggle offline"),
        ("d", "export_debug", "Export debug bundle"),
        ("c", "clear_translation_window", "Clear translation"),
        ("l", "toggle_log_panel", "Hide / show log"),
        ("h", "toggle_history_panel", "Hide / show history"),
        ("t", "toggle_settings_panel", "Hide / show settings"),
        ("p", "run_doctor_snapshot", "Doctor snapshot"),
        ("x", "switch_to_server", "Switch to Server Mode"),
    ]

    def __init__(self, config: AppConfig) -> None:
        super().__init__()
        self.config = config
        self.logger = SessionLogger(config.log_dir, config.artifacts_dir)
        self.pipeline: InterviewShieldPipeline | None = None
        self.available_devices: list[AudioDeviceInfo] = []
        self.capture_running = False
        self.capture_state = "booting"
        self.pending_restart = False
        self.controls_dirty = False
        self._pending_changes: dict[str, object] = {}
        self.control_events_enabled = False
        self.capture_stop_event = threading.Event()
        self.session_transcripts: list[TranscriptEvent] = []
        self.session_status_events: list[StatusEvent] = []
        self.last_doctor_snapshot: dict[str, object] | None = None
        self.log_visible = True
        self.history_visible = True
        self.settings_visible = True
        self.current_transcript_event: TranscriptEvent | None = None
        self.en_history_items: list[str] = []
        self.cz_history_items: list[str] = []
        self._shared_transcriber: WhisperTranscriber | None = None
        self._shared_translator: HybridTranslator | None = None
        self._status_refresh_pending = False
        self.audio_state: str = "Listening"
        self._switch_to_server = False

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("Booting…", id="status-bar")
        with Horizontal(id="body"):
            with Vertical(id="main-pane"):
                with Horizontal(id="live-windows"):
                    yield Static("ENG\n\nWaiting for captured English text…", id="en-window")
                    yield Static("CZE\n\nTranslation will appear after it is received", id="cz-window")
                with VerticalScroll(id="history"):
                    with Horizontal(id="history-columns"):
                        with Vertical(id="history-en"):
                            yield Static("EN HISTORY", classes="section-title")
                            yield Static("No previous English sentences yet.", id="history-en-content")
                        with Vertical(id="history-cz"):
                            yield Static("CZ HISTORY", classes="section-title")
                            yield Static("No previous Czech translations yet.", id="history-cz-content")
                yield RichLog(id="debug", markup=True, wrap=True)
            with VerticalScroll(id="control-pane"):
                yield Static("Live Controls", classes="section-title")
                yield Label("Input mode", classes="control-label")
                yield Select(
                    self.INPUT_MODE_OPTIONS,
                    value=self.config.input_mode,
                    allow_blank=False,
                    id="input-mode-select",
                )
                yield Label("Input device", classes="control-label", id="device-label")
                yield Select(
                    [("Auto / default", self.AUTO_DEVICE_VALUE)],
                    value=self.AUTO_DEVICE_VALUE,
                    allow_blank=False,
                    id="device-select",
                )
                yield Label("Monitor device", classes="control-label", id="monitor-device-label")
                yield Select(
                    [("Auto / default monitor", self.AUTO_DEVICE_VALUE)],
                    value=self.AUTO_DEVICE_VALUE,
                    allow_blank=False,
                    id="monitor-device-select",
                )
                yield Static("", id="device-hint")
                yield Label("STT device", classes="control-label")
                yield Select(
                    self.STT_DEVICE_OPTIONS,
                    value=self.config.stt_device,
                    allow_blank=False,
                    id="stt-device-select",
                )
                yield Label("Whisper model", classes="control-label")
                yield Select(
                    self.MODEL_OPTIONS,
                    value=self.config.stt_model,
                    allow_blank=False,
                    id="model-select",
                )
                yield Label("Compute type", classes="control-label")
                yield Select(
                    self.COMPUTE_TYPE_OPTIONS,
                    value=self.config.stt_compute_type,
                    allow_blank=False,
                    id="compute-type-select",
                )
                yield Label("Online backend", classes="control-label")
                yield Select(
                    self.ONLINE_BACKEND_OPTIONS,
                    value=self.config.online_backend
                    if self.config.online_backend in {value for _, value in self.ONLINE_BACKEND_OPTIONS}
                    else "disabled",
                    allow_blank=False,
                    id="online-backend-select",
                )
                yield Label("Force offline fallback", classes="control-label")
                yield Switch(value=self.config.force_offline, id="force-offline-switch")
                with Horizontal(classes="button-row"):
                    yield Button("Apply + Restart", id="apply-button", variant="primary")
                    yield Button("Stop", id="stop-button", variant="warning")
                with Horizontal(classes="button-row"):
                    yield Button("Refresh Devices", id="refresh-button")
                    yield Button("Doctor", id="doctor-button")
                with Horizontal(classes="button-row"):
                    yield Button("Clear Window", id="clear-translation-button")
                    yield Button("Hide Log", id="toggle-log-button")
                with Horizontal(classes="button-row"):
                    yield Button("Hide History", id="toggle-history-button")
                    yield Button("Hide Settings", id="toggle-settings-button")
                with Horizontal(classes="button-row"):
                    yield Button("Export Debug", id="export-button", variant="success")
                yield Static("", id="doctor-summary")
        yield Footer()

    def on_mount(self) -> None:
        self.history = self.query_one("#history", VerticalScroll)
        self.debug_log = self.query_one("#debug", RichLog)
        self.control_pane = self.query_one("#control-pane", VerticalScroll)
        self.current_en = self.query_one("#en-window", Static)
        self.current_cz = self.query_one("#cz-window", Static)
        self.en_history_content = self.query_one("#history-en-content", Static)
        self.cz_history_content = self.query_one("#history-cz-content", Static)
        self.device_hint = self.query_one("#device-hint", Static)
        self.doctor_summary = self.query_one("#doctor-summary", Static)
        self.input_mode_select = self.query_one("#input-mode-select", Select)
        self.device_select = self.query_one("#device-select", Select)
        self.monitor_device_label = self.query_one("#monitor-device-label", Label)
        self.monitor_device_select = self.query_one("#monitor-device-select", Select)
        self.stt_device_select = self.query_one("#stt-device-select", Select)
        self.model_select = self.query_one("#model-select", Select)
        self.online_backend_select = self.query_one("#online-backend-select", Select)
        self.force_offline_switch = self.query_one("#force-offline-switch", Switch)
        self._load_devices()
        self._sync_controls_from_config()
        self._run_doctor_snapshot(write_debug=False)
        self._refresh_status()
        self._start_capture()

    def _device_options(self) -> list[tuple[str, str]]:
        options = [("Auto / default", self.AUTO_DEVICE_VALUE)]
        for device in self.available_devices:
            tags: list[str] = []
            if device.is_monitor_like:
                tags.append("monitor")
            if device.name.lower() in {"pipewire", "pulse", "default"}:
                tags.append("virtual")
            suffix = f" [{' / '.join(tags)}]" if tags else ""
            label = f"{device.name}{suffix}"
            options.append((label, device.name))
        return options

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

    def _sync_controls_from_config(self) -> None:
        self.control_events_enabled = False
        self.input_mode_select.value = self.config.input_mode
        self.stt_device_select.value = self.config.stt_device
        self.model_select.value = self.config.stt_model
        self.compute_type_select = self.query_one("#compute-type-select", Select)
        self.compute_type_select.value = self.config.stt_compute_type
        online_value = (
            self.config.online_backend
            if self.config.online_backend in {value for _, value in self.ONLINE_BACKEND_OPTIONS}
            else "disabled"
        )
        self.online_backend_select.value = online_value
        self.force_offline_switch.value = self.config.force_offline
        self.device_select.value = self.config.device_name or self.AUTO_DEVICE_VALUE
        self.monitor_device_select.value = self.config.monitor_device_name or self.AUTO_DEVICE_VALUE
        is_dual = (self.config.input_mode == "dual")
        self.monitor_device_label.display = is_dual
        self.monitor_device_select.display = is_dual
        self.control_events_enabled = True
        self._update_device_hint()

    def _build_pipeline(self) -> InterviewShieldPipeline:
        return InterviewShieldPipeline(
            self.config,
            self.logger,
            on_partial_transcript=self._queue_partial_transcript_event,
            on_transcript=self._queue_transcript_event,
            on_status=self._queue_status_event,
            on_audio_state=self._queue_audio_state_event,
            transcriber=self._shared_transcriber,
            translator=self._shared_translator,
        )

    def _queue_audio_state_event(self, state: str) -> None:
        self.call_from_thread(self._update_audio_state, state)

    def _update_audio_state(self, state: str) -> None:
        old_state = self.audio_state
        self.audio_state = state
        if old_state != state:
            event = StatusEvent(level="info", message=f"Audio state: {state}")
            self.session_status_events.append(event)
            self.debug_log.write(f"[dim]AUDIO:[/] {state}")
        self._refresh_status()

    def _queue_partial_transcript_event(self, event: TranscriptEvent) -> None:
        self.call_from_thread(self._append_partial_transcript_to_ui, event)

    def _queue_transcript_event(self, event: TranscriptEvent) -> None:
        self.session_transcripts.append(event)
        self.call_from_thread(self._append_transcript_to_ui, event)

    def _queue_status_event(self, event: StatusEvent) -> None:
        self.session_status_events.append(event)
        self.call_from_thread(self._append_status_to_ui, event)

    def _append_transcript_to_ui(self, event: TranscriptEvent) -> None:
        self.current_transcript_event = event
        self.current_en.update(f"ENG\n{event.english}")
        self.current_cz.update(f"CZE / {event.backend}\n\n{event.czech}")
        self._refresh_status()

    def _append_partial_transcript_to_ui(self, event: TranscriptEvent) -> None:
        if self.current_transcript_event is not None:
            self._archive_current_transcript(self.current_transcript_event)
            self.current_transcript_event = None
        self.current_en.update(f"ENG\n{event.english}")
        self.current_cz.update("CZE\n\nWaiting for translation…")
        self._refresh_status()

    def _archive_current_transcript(self, event: TranscriptEvent) -> None:
        self.en_history_items.insert(0, event.english)
        self.cz_history_items.insert(0, event.czech)
        self._render_history_columns()

    def _render_history_columns(self) -> None:
        en_text = "\n\n".join(self.en_history_items) if self.en_history_items else "No previous English sentences yet."
        cz_text = "\n\n".join(self.cz_history_items) if self.cz_history_items else "No previous Czech translations yet."
        self.en_history_content.update(en_text)
        self.cz_history_content.update(cz_text)

    def _append_status_to_ui(self, event: StatusEvent) -> None:
        level_map = {
            "info": "cyan",
            "warning": "yellow",
            "error": "red",
        }
        colour = level_map.get(event.level, "white")
        self.debug_log.write(f"[{colour}]{event.level.upper()}:[/] {event.message}")
        self._refresh_status()

    def _refresh_status(self) -> None:
        if self._status_refresh_pending:
            return
        self._status_refresh_pending = True
        self.set_timer(0.1, self._do_refresh_status)

    def _do_refresh_status(self) -> None:
        self._status_refresh_pending = False
        if self.config.input_mode == "dual":
            requested_mic = self.config.device_name or "auto"
            resolved_mic = resolve_input_device_name(
                requested_name=self.config.device_name,
                input_mode="mic",
                devices=self.available_devices,
            )
            mic_label = resolved_mic or "system mic"
            if requested_mic != "auto" and requested_mic != mic_label:
                mic_label = f"{requested_mic}->{mic_label}"

            requested_mon = self.config.monitor_device_name or "auto"
            resolved_mon = resolve_input_device_name(
                requested_name=self.config.monitor_device_name,
                input_mode="monitor",
                devices=self.available_devices,
            )
            mon_label = resolved_mon or "system monitor"
            if requested_mon != "auto" and requested_mon != mon_label:
                mon_label = f"{requested_mon}->{mon_label}"

            device_info_str = f"Mic={mic_label} | Mon={mon_label}"
        else:
            requested_device = self.config.device_name or "auto"
            resolved_device = resolve_input_device_name(
                requested_name=self.config.device_name,
                input_mode=self.config.input_mode,
                devices=self.available_devices,
            )
            device_label = resolved_device or "system default"
            if requested_device != "auto" and requested_device != device_label:
                device_label = f"{requested_device} -> {device_label}"
            device_info_str = f"Device={device_label}"

        if self.pipeline is not None:
            stt_label = (
                f"{self.pipeline.transcriber.status.requested_device}"
                f"->{self.pipeline.transcriber.status.actual_device}"
            )
        else:
            stt_label = self.config.stt_device

        pending_text = "yes" if self.controls_dirty else "no"
        panels = (
            f"history={'on' if self.history_visible else 'off'}, "
            f"log={'on' if self.log_visible else 'off'}, "
            f"settings={'on' if self.settings_visible else 'off'}"
        )
        
        # Multilingual model warning
        model_meta = self.MODEL_METADATA.get(self.config.stt_model, {})
        multilingual_warning = ""
        if model_meta.get("multilingual", False) and self.config.stt_language == "en":
            multilingual_warning = " | [yellow]⚠ Multilingual model with English-only STT language[/]"
        
        active_translator = None
        if self.pipeline is not None:
            active_translator = self.pipeline.translator
        elif self._shared_translator is not None:
            active_translator = self._shared_translator

        if active_translator is not None and hasattr(active_translator, "active_backend_name"):
            backend_name = active_translator.active_backend_name
            if backend_name == "ctranslate2":
                nmt_device = getattr(getattr(active_translator, "nmt_backend", None), "device", "unknown")
                nmt_label = f"NMT=ctranslate2 ({nmt_device})"
            else:
                nmt_label = "NMT=fallback"
        else:
            nmt_label = f"NMT={self.config.translation_model.split('/')[-1]}"

        audio_badges = {
            "Listening": "[cyan]● Listening[/]",
            "Speaking": "[bold green]🎤 Speaking[/]",
            "Transcribing": "[bold yellow]⚡ Transcribing[/]",
        }
        audio_badge = audio_badges.get(self.audio_state, f"[{self.audio_state}]")
        vad_info = f"VAD=on ({self.config.vad_silence_seconds}s)" if self.config.vad_enabled else "VAD=off"

        status_message = (
            f"Audio={audio_badge} | {vad_info} | Capture={self.capture_state} | Mode={self.config.input_mode} | {device_info_str} | "
            f"STT={stt_label} | {nmt_label} | Model={self.config.stt_model} | Compute={self.config.stt_compute_type} | "
            f"Online={self.config.online_backend} | Offline={self.config.offline_backend} | "
            f"ForceOffline={self.config.force_offline} | Pending={pending_text} | {panels}"
            f"{multilingual_warning}"
        )
        self.query_one("#status-bar", Static).update(status_message)
        self._update_device_hint()

    def _update_device_hint(self) -> None:
        if self.config.input_mode == "dual":
            resolved_mic = resolve_input_device_name(
                requested_name=self.config.device_name,
                input_mode="mic",
                devices=self.available_devices,
            )
            resolved_mon = resolve_input_device_name(
                requested_name=self.config.monitor_device_name,
                input_mode="monitor",
                devices=self.available_devices,
            )
            self.device_hint.update(f"Dual: Mic=[{resolved_mic or 'default'}], Mon=[{resolved_mon or 'default'}]")
        else:
            resolved_device = resolve_input_device_name(
                requested_name=self.config.device_name,
                input_mode=self.config.input_mode,
                devices=self.available_devices,
            )
            if self.config.device_name:
                self.device_hint.update(f"Requested device: {self.config.device_name}")
            else:
                self.device_hint.update(f"Auto-resolved device: {resolved_device or 'system default'}")

    def _run_doctor_snapshot(self, write_debug: bool = True) -> None:
        self.last_doctor_snapshot = run_doctor(self.config, include_audio_devices=False)
        runtime = self.last_doctor_snapshot["runtime_checks"]
        google_state = "ok" if runtime["google_dns"]["ok"] else "offline"
        ffmpeg_state = "ok" if runtime["ffmpeg"]["ok"] else "missing"
        gpu_state = "ok" if runtime["nvidia-smi"]["ok"] else "cpu-only"
        summary = f"Doctor: ffmpeg={ffmpeg_state}, dns={google_state}, gpu={gpu_state}"
        self.doctor_summary.update(summary)
        if write_debug:
            self.debug_log.write(f"[bold]Doctor snapshot:[/] {summary}")

    def _start_capture(self) -> None:
        if self.capture_running:
            return
        self.capture_stop_event = threading.Event()
        self.capture_running = True
        self.capture_state = "starting"
        self._refresh_status()
        self.run_worker(self._bootstrap_live, thread=True)

    def _bootstrap_live(self) -> None:
        try:
            self.pipeline = self._build_pipeline()
            # Cache transcriber/translator for reuse on restart
            if self._shared_transcriber is None:
                self._shared_transcriber = self.pipeline.transcriber
            if self._shared_translator is None:
                self._shared_translator = self.pipeline.translator
            self.call_from_thread(self._set_capture_state, "running")
            self.pipeline.run_live(stop_event=self.capture_stop_event)
        except KeyboardInterrupt:
            self.call_from_thread(self.debug_log.write, "[yellow]Live capture stopped by user.[/]")
        except Exception as exc:
            self.call_from_thread(self.debug_log.write, f"[red]Live failure:[/] {exc}")
            self.call_from_thread(self._set_capture_state, "error")
        finally:
            self.call_from_thread(self._handle_capture_finished)

    def _set_capture_state(self, state: str) -> None:
        self.capture_state = state
        self._refresh_status()

    def _handle_capture_finished(self) -> None:
        self.capture_running = False
        if self.pending_restart:
            self.pending_restart = False
            self.capture_state = "restarting"
            self._refresh_status()
            self._start_capture()
            return
        if self.capture_state != "error":
            self.capture_state = "stopped"
        self._refresh_status()

    def _mark_controls_dirty(self, message: str) -> None:
        self.controls_dirty = True
        self.debug_log.write(f"[yellow]Config changed:[/] {message}")
        self._refresh_status()

    def _queue_change(self, key: str, value: object) -> None:
        """Queue a config change for atomic application on restart."""
        self._pending_changes[key] = value
        self.controls_dirty = True

    def _apply_and_restart(self) -> None:
        # Apply pending changes atomically using immutable config
        if self._pending_changes:
            new_config = self.config.with_changes(**self._pending_changes).ensure_directories()
            self.config = new_config
            self._pending_changes.clear()
        
        self.controls_dirty = False
        
        # Check if STT config changed (requires full app restart)
        stt_changed = False
        if self._shared_transcriber is not None:
            if (self.config.stt_model != self._shared_transcriber.model_name or
                self.config.stt_device != self._shared_transcriber.requested_device or
                self.config.stt_compute_type != getattr(self._shared_transcriber, 'compute_type', 'auto')):
                stt_changed = True
        
        if stt_changed:
            self.debug_log.write("[yellow]STT config changed. Restarting Transcriber (this may take a moment to load the model).[/]")
            if self._shared_transcriber is not None:
                self._shared_transcriber.close()
                self._shared_transcriber = None
        else:
            self.debug_log.write("[cyan]Applying configuration and restarting capture (reusing transcriber).[/]")
        
        if self.capture_running:
            self.pending_restart = True
            self.capture_state = "restarting"
            self.capture_stop_event.set()
            self._refresh_status()
        else:
            self._start_capture()

    def on_select_changed(self, event: Select.Changed) -> None:
        if not self.control_events_enabled:
            return
        value = str(event.value)
        if event.select.id == "input-mode-select":
            self._queue_change("input_mode", value)
            is_dual = (value == "dual")
            self.monitor_device_label.display = is_dual
            self.monitor_device_select.display = is_dual
        elif event.select.id == "device-select":
            self._queue_change("device_name", None if value == self.AUTO_DEVICE_VALUE else value)
        elif event.select.id == "monitor-device-select":
            self._queue_change("monitor_device_name", None if value == self.AUTO_DEVICE_VALUE else value)
        elif event.select.id == "stt-device-select":
            self._queue_change("stt_device", value)
        elif event.select.id == "model-select":
            self._queue_change("stt_model", value)
        elif event.select.id == "compute-type-select":
            self._queue_change("stt_compute_type", value)
        elif event.select.id == "online-backend-select":
            self._queue_change("online_backend", value)
        self._refresh_status()

    def on_switch_changed(self, event: Switch.Changed) -> None:
        if not self.control_events_enabled:
            return
        if event.switch.id == "force-offline-switch":
            self._queue_change("force_offline", event.value)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id == "apply-button":
            self._apply_and_restart()
        elif button_id == "stop-button":
            self.action_stop_capture()
        elif button_id == "refresh-button":
            self.action_refresh_devices()
        elif button_id == "doctor-button":
            self.action_run_doctor_snapshot()
        elif button_id == "clear-translation-button":
            self.action_clear_translation_window()
        elif button_id == "toggle-log-button":
            self.action_toggle_log_panel()
        elif button_id == "toggle-history-button":
            self.action_toggle_history_panel()
        elif button_id == "toggle-settings-button":
            self.action_toggle_settings_panel()
        elif button_id == "export-button":
            self.action_export_debug()

    def action_restart_capture(self) -> None:
        self._apply_and_restart()

    def action_stop_capture(self) -> None:
        if not self.capture_running:
            self.debug_log.write("[yellow]Capture is already stopped.[/]")
            return
        self.pending_restart = False
        self.capture_state = "stopping"
        self.capture_stop_event.set()
        self.debug_log.write("[yellow]Stopping live capture…[/]")
        self._refresh_status()

    def action_refresh_devices(self) -> None:
        current_device = self.config.device_name
        invalidate_device_cache()
        self._load_devices()
        if current_device and all(device.name != current_device for device in self.available_devices):
            self.config = self.config.with_changes(device_name=None)
            self.debug_log.write(
                f"[yellow]Previously selected device disappeared:[/] {current_device}. Falling back to auto."
            )
        self._sync_controls_from_config()
        self._refresh_status()

    def action_toggle_offline(self) -> None:
        self.force_offline_switch.value = not self.force_offline_switch.value

    def action_clear_translation_window(self) -> None:
        self.current_transcript_event = None
        self.current_en.update("ENG\n")
        self.current_cz.update("CZE\n")
        self.debug_log.write("[cyan]EN and CZE live windows cleared.[/]")

    def action_toggle_log_panel(self) -> None:
        self.log_visible = not self.log_visible
        self.debug_log.display = self.log_visible
        toggle_button = self.query_one("#toggle-log-button", Button)
        toggle_button.label = "Hide Log" if self.log_visible else "Show Log"
        if self.log_visible:
            self.debug_log.write("[cyan]Log panel shown.[/]")
        self._refresh_status()

    def action_toggle_history_panel(self) -> None:
        self.history_visible = not self.history_visible
        self.history.display = self.history_visible
        toggle_button = self.query_one("#toggle-history-button", Button)
        toggle_button.label = "Hide History" if self.history_visible else "Show History"
        if self.log_visible:
            self.debug_log.write(
                "[cyan]History panel shown.[/]" if self.history_visible else "[cyan]History panel hidden.[/]"
            )
        self._refresh_status()

    def action_toggle_settings_panel(self) -> None:
        self.settings_visible = not self.settings_visible
        self.control_pane.display = self.settings_visible
        toggle_button = self.query_one("#toggle-settings-button", Button)
        toggle_button.label = "Hide Settings" if self.settings_visible else "Show Settings"
        if self.log_visible:
            self.debug_log.write(
                "[cyan]Settings panel shown.[/]" if self.settings_visible else "[cyan]Settings panel hidden.[/]"
            )
        self._refresh_status()

    def action_run_doctor_snapshot(self) -> None:
        self._run_doctor_snapshot(write_debug=True)

    def action_export_debug(self) -> None:
        diagnostics = self.last_doctor_snapshot or run_doctor(self.config)
        bundle = self.logger.export_debug_bundle(
            diagnostics=diagnostics,
            transcripts=self.session_transcripts,
            status_events=self.session_status_events,
        )
        self.debug_log.write(f"[green]Debug bundle exported:[/] {bundle}")

    def action_switch_to_server(self) -> None:
        """Signal to exit TUI and switch to server mode."""
        self._switch_to_server = True
        self.debug_log.write("[yellow]Switching to Server Mode...[/]")
        self.action_stop_capture()
        # Exit with special code to signal mode switch
        self.exit(10)  # type: ignore[arg-type]
