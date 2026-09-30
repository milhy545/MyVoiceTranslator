"""
FastAPI Backend for MyVoiceTranslator Chrome Extension
Provides WebSocket endpoint for real-time audio transcription and translation.
"""

from __future__ import annotations

import asyncio
import json
import logging
import signal
import sys
from contextlib import asynccontextmanager
from typing import Any

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

from .config import AppConfig
from .events import StatusEvent, TranscriptEvent
from .logging_utils import SessionLogger
from .pipeline import InterviewShieldPipeline

# Global state for server control
_should_switch_to_tui = False
_server_shutdown_event: asyncio.Event | None = None
_main_loop: asyncio.AbstractEventLoop | None = None


def set_switch_to_tui() -> None:
    """Signal that the server should shut down and switch to TUI mode."""
    global _should_switch_to_tui
    _should_switch_to_tui = True
    if _server_shutdown_event and _main_loop:
        _main_loop.call_soon_threadsafe(_server_shutdown_event.set)


def should_switch_to_tui() -> bool:
    """Check if a switch to TUI has been requested."""
    return _should_switch_to_tui


def reset_switch_flag() -> None:
    """Reset the switch flag for reuse."""
    global _should_switch_to_tui
    _should_switch_to_tui = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    global _server_shutdown_event, _main_loop
    _server_shutdown_event = asyncio.Event()
    _main_loop = asyncio.get_running_loop()
    yield
    # Cleanup on shutdown
    _server_shutdown_event = None
    _main_loop = None


app = FastAPI(
    title="MyVoiceTranslator Server",
    description="Real-time STT and translation backend for Chrome extension",
    version="0.1.0",
    lifespan=lifespan,
)

# Store active WebSocket connections
active_connections: set[WebSocket] = set()

# Pipeline instance (created on first connection)
pipeline: InterviewShieldPipeline | None = None
pipeline_config: AppConfig | None = None
pipeline_logger: SessionLogger | None = None


async def get_or_create_pipeline() -> InterviewShieldPipeline:
    """Get or create the shared pipeline instance."""
    global pipeline, pipeline_config, pipeline_logger
    
    if pipeline is not None:
        return pipeline
    
    # Load config and create pipeline
    pipeline_config = AppConfig.from_env().ensure_directories()
    pipeline_logger = SessionLogger(pipeline_config.log_dir, pipeline_config.artifacts_dir)
    
    # Create pipeline with WebSocket callbacks (sync functions that schedule async work)
    pipeline = InterviewShieldPipeline(
        config=pipeline_config,
        logger=pipeline_logger,
        on_partial_transcript=_on_partial_transcript_sync,
        on_transcript=_on_transcript_sync,
        on_status=_on_status_sync,
        on_audio_state=_on_audio_state_sync,
    )
    
    return pipeline


def _on_partial_transcript_sync(event: TranscriptEvent) -> None:
    """Sync callback for partial transcript - schedules async broadcast."""
    if _main_loop:
        _main_loop.call_soon_threadsafe(
            asyncio.create_task, _broadcast_partial_transcript(event)
        )


def _on_transcript_sync(event: TranscriptEvent) -> None:
    """Sync callback for final transcript - schedules async broadcast."""
    if _main_loop:
        _main_loop.call_soon_threadsafe(
            asyncio.create_task, _broadcast_transcript(event)
        )


def _on_status_sync(event: StatusEvent) -> None:
    """Sync callback for status - schedules async broadcast."""
    if _main_loop:
        _main_loop.call_soon_threadsafe(
            asyncio.create_task, _broadcast_status(event)
        )


def _on_audio_state_sync(state: str) -> None:
    """Sync callback for audio state - schedules async broadcast."""
    if _main_loop:
        _main_loop.call_soon_threadsafe(
            asyncio.create_task, _broadcast_audio_state(state)
        )


async def _broadcast_partial_transcript(event: TranscriptEvent) -> None:
    """Broadcast partial transcript to all connected clients."""
    message = {
        "type": "partial_transcript",
        "english": event.english,
        "input_mode": event.input_mode,
    }
    await _broadcast_to_all(message)


async def _broadcast_transcript(event: TranscriptEvent) -> None:
    """Broadcast final transcript to all connected clients."""
    message = {
        "type": "transcript",
        "english": event.english,
        "czech": event.czech,
        "backend": event.backend,
        "input_mode": event.input_mode,
    }
    await _broadcast_to_all(message)


async def _broadcast_status(event: StatusEvent) -> None:
    """Broadcast status event to all connected clients."""
    message = {
        "type": "status",
        "level": event.level,
        "message": event.message,
    }
    await _broadcast_to_all(message)


async def _broadcast_audio_state(state: str) -> None:
    """Broadcast audio state change to all connected clients."""
    message = {
        "type": "audio_state",
        "state": state,
    }
    await _broadcast_to_all(message)


async def _broadcast_to_all(message: dict[str, Any]) -> None:
    """Send message to all active WebSocket connections."""
    if not active_connections:
        return
    
    data = json.dumps(message, ensure_ascii=False)
    disconnected = set()
    
    for ws in active_connections:
        try:
            await ws.send_text(data)
        except (WebSocketDisconnect, RuntimeError, ConnectionError):
            disconnected.add(ws)
    
    # Clean up disconnected clients
    for ws in disconnected:
        active_connections.discard(ws)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok", "service": "myvoicetranslator-server"}


@app.post("/api/switch-to-tui")
async def switch_to_tui() -> JSONResponse:
    """Endpoint to request server shutdown and switch to TUI mode."""
    set_switch_to_tui()
    return JSONResponse({"status": "switching", "message": "Server will shut down and switch to TUI mode"})


@app.websocket("/transcribe")
async def websocket_transcribe(websocket: WebSocket) -> None:
    """WebSocket endpoint for real-time audio transcription.
    
    Expected protocol:
    - Client sends binary PCM Float32 audio chunks at 16kHz
    - Server responds with JSON events (partial_transcript, transcript, status, audio_state)
    """
    logger = logging.getLogger(__name__)
    await websocket.accept()
    active_connections.add(websocket)
    
    # Get or create pipeline
    pipe = await get_or_create_pipeline()
    
    # Queue for audio chunks from WebSocket
    audio_queue: asyncio.Queue[bytes | None] = asyncio.Queue()
    
    # Task to process audio from queue
    async def process_audio():
        buffer: list[bytes] = []
        frames_in_buffer = 0
        sample_rate = pipe.config.sample_rate
        chunk_seconds = pipe.config.live_chunk_seconds
        frames_per_chunk = int(sample_rate * chunk_seconds)
        
        while True:
            chunk = await audio_queue.get()
            if chunk is None:
                # Flush remaining buffer
                if buffer:
                    await _process_audio_buffer(b"".join(buffer), pipe)
                break
            
            buffer.append(chunk)
            frames_in_buffer += len(chunk) // 4  # Float32 = 4 bytes per sample
            
            if frames_in_buffer >= frames_per_chunk:
                await _process_audio_buffer(b"".join(buffer), pipe)
                buffer = []
                frames_in_buffer = 0
    
    async def _process_audio_buffer(audio_bytes: bytes, pipe: InterviewShieldPipeline) -> None:
        """Process accumulated audio buffer through pipeline."""
        import numpy as np
        
        # Convert bytes to numpy array (Float32)
        audio_data = np.frombuffer(audio_bytes, dtype=np.float32)
        
        # Skip silence
        if len(audio_data) == 0 or np.max(np.abs(audio_data)) < 1e-4:
            return
        
        # Run STT in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        try:
            # Transcribe the audio
            text = await loop.run_in_executor(
                None,
                lambda: pipe.transcriber.normalise_segments(
                    pipe.transcriber.transcribe_samples(audio_data, pipe.config.sample_rate)
                )
            )
            
            if text:
                # Emit partial transcript
                partial_event = TranscriptEvent(
                    english=text,
                    input_mode=pipe.config.input_mode,
                    phase="captured",
                )
                await _broadcast_partial_transcript(partial_event)
                
                # Translate
                translated = pipe.translator.translate(text)
                
                # Emit final transcript
                final_event = TranscriptEvent(
                    english=text,
                    input_mode=pipe.config.input_mode,
                    czech=translated.text or "[translation unavailable]",
                    backend=translated.backend,
                    phase="translated",
                )
                await _broadcast_transcript(final_event)
                
        except (RuntimeError, ValueError, TypeError) as e:
            await _broadcast_status(StatusEvent(level="error", message=f"STT failed: {e}"))
    
    # Start audio processing task
    process_task = asyncio.create_task(process_audio())
    
    try:
        while True:
            # Check if switch to TUI requested
            if should_switch_to_tui():
                await websocket.send_text(json.dumps({
                    "type": "server_shutdown",
                    "message": "Switching to TUI mode"
                }))
                break
            
            # Receive audio data (binary) or control messages (text)
            try:
                message = await asyncio.wait_for(websocket.receive(), timeout=0.1)
            except TimeoutError:
                continue
            
            if "bytes" in message:
                # Binary audio chunk
                await audio_queue.put(message["bytes"])
            elif "text" in message:
                # Text control message
                try:
                    control = json.loads(message["text"])
                    if control.get("type") == "ping":
                        await websocket.send_text(json.dumps({"type": "pong"}))
                    elif control.get("type") == "flush":
                        # Flush current buffer
                        await audio_queue.put(None)
                        # Re-create queue for next segment
                        audio_queue = asyncio.Queue()
                except json.JSONDecodeError:
                    pass
                    
    except WebSocketDisconnect:
        pass
    except (RuntimeError, ValueError, TypeError) as e:
        logger.error("WebSocket error: %s", e)
    finally:
        active_connections.discard(websocket)
        await audio_queue.put(None)
        await process_task


def run_server(args: list[str]) -> int:
    """Run the FastAPI server.
    
    Returns:
        0: Normal shutdown
        10: Switch to TUI mode requested
        Other: Error
    """
    global _should_switch_to_tui
    _should_switch_to_tui = False
    
    # Parse args for host/port
    host = "127.0.0.1"
    port = 8000
    
    i = 0
    while i < len(args):
        if args[i] == "--host" and i + 1 < len(args):
            host = args[i + 1]
            i += 2
        elif args[i] == "--port" and i + 1 < len(args):
            port = int(args[i + 1])
            i += 2
        else:
            i += 1
    
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    
    # Run server
    config = uvicorn.Config(
        app=app,
        host=host,
        port=port,
        log_level="info",
        loop="uvloop",
    )
    server = uvicorn.Server(config)
    
    # Handle signals for graceful shutdown
    def signal_handler(sig, frame):
        global _should_switch_to_tui
        _should_switch_to_tui = True
        server.should_exit = True
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Run in asyncio
    asyncio.run(server.serve())
    
    # Check if we should switch to TUI
    if _should_switch_to_tui:
        return 10
    return 0


if __name__ == "__main__":
    sys.exit(run_server(sys.argv[1:]))