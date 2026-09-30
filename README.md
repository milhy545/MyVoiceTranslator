# MyVoiceTranslator — Milhy's Interview Shield

[![Platform: Linux](https://img.shields.io/badge/Platform-Linux-orange.svg)](https://www.kernel.org/)
[![UI: Textual TUI](https://img.shields.io/badge/UI-Textual%20TUI-blue.svg)](https://github.com/Textualize/textual)
[![Audio: PipeWire](https://img.shields.io/badge/Audio-PipeWire%20%2F%20Pulse-green.svg)](https://pipewire.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)  
[🇨🇿 Kompletní česká verze dokumentace zde](./README.cz.md)

**Milhy's Interview Shield** is a lightweight, low-hardware Python TUI for real-time Speech-to-Text (STT) and English-to-Czech translation with a strict **CPU-first fallback strategy**.

Designed as a mission-critical utility for live technical interviews, webinars, and English online training on constrained workstation hardware.

---

## 🎯 The Problem

During live remote technical interviews and online trainings in the UK, cognitive load is high: understanding complex architectural questions while managing speech latency and audio devices. Cloud-based translation tools introduce latency, high resource overhead, or unreliability when connectivity fluctuates.

---

## 💡 The Architecture & Features

- **Interactive Textual TUI:** Full terminal user interface with zero browser or electron overhead.
- **Real-Time PipeWire Audio Routing:** Captures live microphone and internal system audio loopback without external cables or hardware mixers.
- **CPU-First Fallback:** Deterministic offline execution prioritizing CPU-based local whisper models, falling back gracefully if GPU drivers are unavailable.
- **Session Audit Logging:** Automatically exports timestamped Markdown session logs (`~/logs/interview_YYYYMMDD.md`) for post-interview review and learning.
- **Single-Command User Installer:** Deploys directly to `~/.local/bin/myvoice` with desktop application menu integration.

---

## 🚀 Quick Start

```bash
# Standard user installation
bash scripts/install_myvoice.sh

# Run health diagnostics
myvoice doctor

# Launch the live interview shield
myvoice run
```

---

## 🧪 Unattended Scenarios & Diagnostics

```bash
# Run self-contained verification
python shield.py prepare-fixtures
python shield.py --offline --stt-device cpu test-file
python scripts/run_final_verification.py
```
