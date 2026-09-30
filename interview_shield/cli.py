from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import AppConfig
from .fixtures import ensure_fixture_audio


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Milhy's Interview Shield")
    parser.add_argument("--test", default=None, help="Legacy shortcut for test-file AUDIO_PATH")
    parser.add_argument("--input-mode", default=None, choices=["auto", "mic", "monitor", "dual"], help="Preferred live input mode")
    parser.add_argument("--device", default=None, help="Exact sounddevice input name")
    parser.add_argument("--monitor-device", default=None, help="Exact sounddevice monitor/loopback input name")
    parser.add_argument(
        "--stt-device",
        default=None,
        choices=["auto", "cpu", "cuda"],
        help="Preferred STT device",
    )
    parser.add_argument("--model", default=None, help="faster-whisper model name")
    parser.add_argument(
        "--translation-model",
        default=None,
        help="Translation model repository or directory",
    )
    parser.add_argument(
        "--translation-device",
        default=None,
        choices=["auto", "cpu", "cuda"],
        help="Preferred translation device",
    )
    parser.add_argument(
        "--translation-compute-type",
        default=None,
        choices=["auto", "int8", "float16", "int8_float16", "float32"],
        help="Preferred translation compute type",
    )
    parser.add_argument("--log-dir", default=None, help="Override session log directory")
    parser.add_argument("--artifact-dir", default=None, help="Override debug artifact directory")
    parser.add_argument(
        "--vad",
        dest="vad_enabled",
        action="store_true",
        default=None,
        help="Enable Voice Activity Detection segmentation (default)",
    )
    parser.add_argument(
        "--no-vad",
        dest="vad_enabled",
        action="store_false",
        help="Disable Voice Activity Detection segmentation and use fixed chunks",
    )
    parser.add_argument(
        "--vad-silence-seconds",
        type=float,
        default=None,
        help="Trailing silence duration (seconds) before triggering flush (default: 0.5)",
    )
    parser.add_argument(
        "--vad-max-seconds",
        type=float,
        default=None,
        help="Maximum continuous speech segment duration before forced flush (default: 8.0)",
    )

    subparsers = parser.add_subparsers(dest="command", required=False)
    subparsers.add_parser("run", help="Start live TUI mode")
    subparsers.add_parser("doctor", help="Inspect environment readiness")
    subparsers.add_parser("devices", help="List capture devices")

    test_file = subparsers.add_parser("test-file", help="Run file-based STT and translation")
    test_file.add_argument("audio_path", nargs="?", help="Audio file to transcribe")

    test_mic = subparsers.add_parser("test-live-mic", help="Run simulated microphone E2E")
    test_mic.add_argument("--wav", default=None, help="Explicit WAV fixture path")

    test_monitor = subparsers.add_parser("test-live-monitor", help="Run simulated monitor E2E")
    test_monitor.add_argument("--wav", default=None, help="Explicit WAV fixture path")

    test_dual = subparsers.add_parser("test-live-dual", help="Run simulated dual E2E")
    test_dual.add_argument("--wav", default=None, help="Explicit WAV fixture path")

    subparsers.add_parser("prepare-fixtures", help="Generate deterministic audio fixtures")
    return parser


def apply_overrides(config: AppConfig, args: argparse.Namespace) -> AppConfig:
    changes = {}
    if args.input_mode:
        changes["input_mode"] = args.input_mode
    if args.device:
        changes["device_name"] = args.device
    if getattr(args, "monitor_device", None):
        changes["monitor_device_name"] = args.monitor_device
    # Offline-only mode: force_offline is always True
    changes["force_offline"] = True
    if args.stt_device:
        changes["stt_device"] = args.stt_device
    if args.model:
        changes["stt_model"] = args.model
    if getattr(args, "translation_model", None):
        changes["translation_model"] = args.translation_model
    if getattr(args, "translation_device", None):
        changes["translation_device"] = args.translation_device
    if getattr(args, "translation_compute_type", None):
        changes["translation_compute_type"] = args.translation_compute_type
    if getattr(args, "vad_enabled", None) is not None:
        changes["vad_enabled"] = args.vad_enabled
    if getattr(args, "vad_silence_seconds", None) is not None:
        changes["vad_silence_seconds"] = args.vad_silence_seconds
    if getattr(args, "vad_max_seconds", None) is not None:
        changes["vad_max_seconds"] = args.vad_max_seconds
    if args.log_dir:
        changes["log_dir"] = Path(args.log_dir).expanduser()
    if args.artifact_dir:
        changes["artifacts_dir"] = Path(args.artifact_dir).expanduser()
    if changes:
        config = config.with_changes(**changes)
    config = config.ensure_directories()
    return config


def run_pipeline_command(config: AppConfig, mode: str, wav_path: Path | None = None, audio_path: Path | None = None) -> int:
    from .diagnostics import run_doctor
    from .logging_utils import SessionLogger
    from .pipeline import InterviewShieldPipeline

    logger = SessionLogger(config.log_dir, config.artifacts_dir)
    pipeline = InterviewShieldPipeline(config, logger)
    diagnostics = run_doctor(config, include_audio_devices=False)
    if audio_path is not None:
        result = pipeline.run_file(audio_path)
    else:
        if wav_path is None:
            wav_path = ensure_fixture_audio(config.fixture_dir).wav_path
        result = pipeline.run_simulated_live(wav_path=wav_path, input_mode=mode)
    bundle = logger.export_debug_bundle(
        diagnostics=diagnostics,
        transcripts=result.transcripts,
        status_events=result.status_events,
    )
    summary = {
        "transcripts": [
            {"english": event.english, "czech": event.czech, "backend": event.backend}
            for event in result.transcripts
        ],
        "debug_bundle": str(bundle),
        "session_log": str(logger.session_log),
        "stt_status": {
            "requested": pipeline.transcriber.status.requested_device,
            "actual": pipeline.transcriber.status.actual_device,
            "compute_type": pipeline.transcriber.status.compute_type,
        },
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.test and args.command is None:
        args.command = "test-file"
        args.audio_path = args.test
    config = apply_overrides(AppConfig.from_env(), args)
    command = args.command or "run"

    if command == "doctor":
        from .diagnostics import run_doctor

        print(json.dumps(run_doctor(config, include_audio_devices=True), ensure_ascii=False, indent=2))
        return 0
    if command == "devices":
        from .audio import list_input_devices

        print(
            json.dumps(
                [
                    {
                        "name": device.name,
                        "index": device.index,
                        "max_input_channels": device.max_input_channels,
                        "default_samplerate": device.default_samplerate,
                        "is_monitor_like": device.is_monitor_like,
                    }
                    for device in list_input_devices()
                ],
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    if command == "prepare-fixtures":
        fixtures = ensure_fixture_audio(config.fixture_dir)
        print(json.dumps({"wav": str(fixtures.wav_path), "mp3": str(fixtures.mp3_path)}, indent=2))
        return 0
    if command == "test-file":
        fixtures = ensure_fixture_audio(config.fixture_dir)
        audio_path = Path(args.audio_path) if args.audio_path else fixtures.mp3_path
        return run_pipeline_command(config, mode="file", audio_path=audio_path)
    if command == "test-live-mic":
        fixtures = ensure_fixture_audio(config.fixture_dir)
        wav_path = Path(args.wav) if args.wav else fixtures.wav_path
        return run_pipeline_command(config, mode="mic", wav_path=wav_path)
    if command == "test-live-monitor":
        fixtures = ensure_fixture_audio(config.fixture_dir)
        wav_path = Path(args.wav) if args.wav else fixtures.wav_path
        return run_pipeline_command(config, mode="monitor", wav_path=wav_path)
    if command == "test-live-dual":
        fixtures = ensure_fixture_audio(config.fixture_dir)
        wav_path = Path(args.wav) if args.wav else fixtures.wav_path
        return run_pipeline_command(config, mode="dual", wav_path=wav_path)

    from .tui import InterviewShieldApp

    app = InterviewShieldApp(config)
    app.run()
    return 0
