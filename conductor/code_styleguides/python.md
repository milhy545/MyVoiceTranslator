# Python Code Style Guide

## Formatting
- Indent: 4 spaces (no tabs)
- Line length: 100 chars (soft), 120 hard
- Imports: stdlib → third-party → local, grouped with blank line
- Trailing commas in multiline collections

## Typing
- Type hints on all public functions/classes
- Use `from __future__ import annotations` for forward refs
- Prefer `list[T]`, `dict[K, V]`, `tuple[T, ...]` over `List`, `Dict`, `Tuple`
- `Protocol` for interfaces, `@dataclass(slots=True)` for data
- `frozen=True` for immutable config objects

## Naming
- `snake_case`: functions, variables, modules, files
- `PascalCase`: classes, exceptions, protocols
- `UPPER_SNAKE_CASE`: constants
- Single leading `_` for module-private, double `__` for class-private

## Patterns
- Early returns, guard clauses
- No mutable defaults (`= []`, `= {}`)
- Context managers for resources (`with`, `__enter__`/`__exit__`)
- `pathlib.Path` over `os.path`
- `subprocess.run` with `capture_output=True`, `text=True`
- Structured logging via stdlib `logging` (JSONL for machines, markdown for humans)

## Testing
- `unittest` for unit tests, `pytest` only for integration
- Test file: `tests/test_<module>.py`
- Test class: `<Module>Test` or `<Feature>Test`
- Fixtures in `tests/` or `test_audio/`
- Mock at boundaries (I/O, network, time), not internals

## Error Handling
- Typed exceptions for expected failures
- No bare `except:`
- `RuntimeError` for unrecoverable internal errors
- Return `Result[T, E]` or `Option[T]` for expected failures (consider `typing_extensions`)

## Async/Threading
- `threading` for audio callback → queue → consumer pattern
- `textual` workers for TUI background tasks
- No `asyncio` in current architecture (keep simple)