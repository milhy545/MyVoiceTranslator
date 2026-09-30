# Přehled Benchmarkingů

Benchmarky běží pomocí `pytest-benchmark`. Spuštění benchmarků:

```bash
PYTHONPATH=. uv run pytest benchmarks/
```

Aktuální benchmarky:
- `test_stt_benchmark.py`: Testuje fallback inference na CPU (`tiny.en` přes `int8`).
