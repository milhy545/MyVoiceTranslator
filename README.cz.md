# MyVoiceTranslator — Milhy's Interview Shield

[![Platform: Linux](https://img.shields.io/badge/Platform-Linux-orange.svg)](https://www.kernel.org/)
[![UI: Textual TUI](https://img.shields.io/badge/UI-Textual%20TUI-blue.svg)](https://github.com/Textualize/textual)
[![Audio: PipeWire](https://img.shields.io/badge/Audio-PipeWire%20%2F%20Pulse-green.svg)](https://pipewire.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)  
[🇬🇧 English version available here](./README.md)

**Milhy's Interview Shield** je nízkonákladový Python TUI nástroj pro real-time převod řeči na text (STT) a okamžitý překlad z angličtiny do češtiny s přísnou **CPU-first fallback strategií**.

Byl navržen a v praxi prověřen jako spolehlivý pomocník při britských technických online pohovorech a odborných školeních, kde odbourává jazykovou bariéru v reálném čase přímo v terminálu.

---

## 🎯 Proč tento nástroj vznikl (The Backstory)

Při technických pohovorech v UK a odborných certifikačních kurzech je potřeba vnímat složité architektonické otázky v plné přesnosti. Běžné cloudové překladače jsou těžkopádné, vyžadují přepínání oken prohlížeče a selhávají při výpadku spojení.

*Interview Shield* vznikl původně jako rychlý CLI prototyp, který se osvědčil natolik, že byl přepsán do profesionálního terminálového rozhraní (Textual TUI) s přímým napojením na zvukový server PipeWire.

---

## 💡 Architektura a funkce

- **Textual TUI rozhraní:** Žádný těžký Electron ani webový prohlížeč – běží čistě a bleskově v terminálu.
- **PipeWire / PulseAudio směrování:** Dokáže souběžně snímat jak mikrofon, tak interní zvuk protistrany (loopback) bez hardwarového mixážního pultu.
- **CPU-First Fallback:** Zaručená funkčnost na procesoru i bez dostupných NVIDIA ovladačů.
- **Auditní logování:** Ukládá kompletní strukturovaný přepis relace do Markdownu pro zpětnou analýzu (`~/logs/interview_YYYYMMDD.md`).
- **Uživatelský instalátor:** Nasazení jedním příkazem přímo do `~/.local/bin/myvoice` včetně integrace do systémového menu Linuxu.

---

## 🚀 Rychlý start

```bash
# Instalace
bash scripts/install_myvoice.sh

# Diagnostika prostředí
myvoice doctor

# Spuštění štítu
myvoice run
```
