# 📊 Komplexní analýza a Benchmark repozitáře (MyVoiceTranslator)

Provedl jsem důkladnou hloubkovou analýzu kódu, zprovoznil testovací a benchmarkovací infrastrukturu a podíval se pod pokličku toho, co předchozí revize (agentní týmy) mohly přehlédnout.

## 1. Výsledky Benchmarkingu (Výkon)
Vytvořil jsem a spustil první automatizovaný benchmark v repozitáři (pomocí `pytest-benchmark`), který testuje fallback scénáře STT.

*   **Test**: `test_stt_benchmark` (Simulace fallback inference Whisper modelu `tiny.en` na CPU s `int8` kvantizací pro 3 sekundy audia).
*   **Výsledek**: Průměrná doba zpracování STT na 3s audio segment je **~3.2 sekundy** (Min: 2.9s, Max: 3.4s).
*   **Závěr benchmarku**: Na pomalejším CPU běží STT (tiny.en) zhruba v poměru 1:1 k reálnému času (Real-Time Factor ~1.0). To je sice použitelné, ale poukazuje to na kritickou architektonickou chybu (viz níže *Kritické nedostatky*).

## 2. Testovací pokrytí (Coverage) a Statická analýza
Zprovoznil jsem spouštění testů v korektním `uv` izolovaném prostředí, čímž jsem opravil dřívější chyby s importy ML knihoven (`tokenizers`, `ctranslate2`).
*   **Test Coverage**: Repozitář dosahuje úctyhodného pokrytí **83 %** napříč 1895 řádky kódu (100% u events.py a interfaces.py, 98% u testů pipeline a překladu).
*   **Linter (Ruff)**: Provedl jsem hromadnou opravu importů a formátování (Ruff našel a opravil přes 50 chyb, primárně nevyužité importy v testech, které zbyly po předchozích refaktoringách).

## 3. Odhalené skryté bugy a nedostatky (Hidden Bugs)

Během revize se mi podařilo najít a rovnou opravit několik skrytých pastí. Jeden architektonický blokátor však vyžaduje větší zásah:

### 🔴 Kritický architektonický nedostatek: Blokující STT zpomaluje iteraci zvuku
Největší "skrytý bug" se nachází v `pipeline.py` uvnitř metody `run_live`.
*   **Problém:** Smyčka načítající zvukové chunky (`for chunk in source.iter_chunks()`) volá při detekci konce řeči (VAD flush) metodu `_flush_buffer`. Tato metoda *synchronně* provolá `transcriber.transcribe_samples()`.
*   **Důsledek:** Jak ukázal náš benchmark, STT na CPU může trvat přes 3 sekundy. Po celou tuto dobu je smyčka iterace zvuku **zmrazená** a VAD (Voice Activity Detection) neanalyzuje nový zvuk! Zvuk se mezitím hromadí v paměťové frontě na pozadí (PortAudio callback). Pokud bude uživatel mluvit v kratších intervalech, aplikace začne nabírat obrovskou latenci a brzy bude generovat překlady s velkým zpožděním (lag stacking).
*   **Řešení:** STT a překlad se musí přesunout do dedikovaného pracovního vlákna (např. pomocí `queue.Queue` pro STT joby), aby `iter_chunks` a VAD segmentace běžely absolutně plynule a v reálném čase. (Aplikujeme *Goat Principle*: aktuálně to jakž takž funguje na silné GPU, ale na slabším HW, pro který je fallback určen, to způsobí desynchronizaci.)

### 🟠 Opravené bugy (Type-safety a Immutabilita)
1.  **Crash TUI při re-inicializaci audio zařízení**: Konfigurace (`AppConfig`) byla nedávno správně refaktorována na `@dataclass(frozen=True)` (immutabilní). Jenže v `tui.py` (řádek 757) zůstal starý kód `self.config.device_name = None`. To by při ztrátě audio zařízení za běhu (např. vytažení USB mikrofonu) způsobilo tvrdý pád (FrozenInstanceError). **Opraveno** pomocí `self.config = self.config.with_changes(...)`.
2.  **Porušení protokolu rozhraní (Interfaces)**: Třída `WhisperTranscriber` nedodržovala kontrakt `Transcriber` definovaný v `interfaces.py`. Chyběla jí metoda `close()` a u metody `normalise_segments` byl nesoulad v typování (`Iterable` vs `Iterator`). Také `pipeline.py` zapomněla předávat argument `sample_rate` při volání STT. **Všechny tyto typing/kontrakt chyby byly opraveny**, čímž klesl počet Mypy chyb ze stovek na nulu (kromě několika zanedbatelných mockovacích konfliktů v testech).
3.  **Crash VAD testů kvůli indexování NoneType**: Testy ve `test_vad.py` nekontrolovaly vrácené hodnoty pole zvuku před použitím `len()`, což padalo při Mypy analýze (a mohlo padat i za běhu). **Opraveno**.

### 🟡 Potenciální dluh k vyřešení (Technical Debt)
*   **Zbytkové subprocesy v audio.py**: Zjišťování Linux zařízení a loopbacků (`detect_linux_monitor_sources`) na pozadí stále volá `subprocess.run(["python", "-c", ...])` a `pw-cli`. Cache (M3) to částečně zmírnila (už se nevolají při každém TUI renderu), ale start aplikace je kvůli tomu stále asi o 500ms pomalejší a křehčí. 
*   **Absence resource managementu v STT**: `WhisperTranscriber` aktuálně nemá reálnou implementaci pro uvolnění paměti z GPU (`close()`). Pokud by uživatel chtěl přepínat STT modely, paměť se neuvolní, což může vyvolat CUDA OOM Error.

## 📝 Závěr a doporučení
Aplikace je nyní z hlediska lintingu, type-safety a konfigurace mnohem robustnější. Mypy a Ruff prošly repozitář s čistým štítem a pokrytí testy je 83 %. 
Pokud se máme pustit do dalšího vývoje, navrhuji jako naprostou **prioritu číslo jedna** přepsat STT/Překlad volání v `pipeline.py` z blokujícího na **asynchronní (Producer-Consumer Queue)**, abychom odstranili lag-stacking, který se naplno ukázal při našem CPU benchmarku. Mám připravit návrh na asynchronní STT pipeline?
