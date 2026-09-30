# Workflow: MyVoiceTranslator

## Branching
- `main` branch only (no feature branches needed for solo dev)
- Direct commits to main with conventional commit messages
- Format: `<type>(<scope>): <subject>` — e.g., `fix(stt): remove hardcoded cache path`

## Testing Policy
- **TDD for new logic**: Write failing unit test → implement → refactor
- **Unit tests**: Run on every change (`python3 -m unittest discover -s tests -v`)
- **Integration tests**: Opt-in only (`MVT_RUN_INTEGRATION=1 python3 -m pytest tests/test_e2e.py -v`)
- **Syntax check**: `python3 -m py_compile interview_shield/*.py shield.py` before commit
- **Coverage target**: New modules ≥80% line coverage

## Completion Gates (per track)
1. All unit tests pass
2. Syntax check passes
3. CLI file mode produces valid JSON output
4. TUI smoke test: mount → capture → restart ×5 → no GPU memory growth
5. Acceptance criteria from spec verified

## Commits
- Atomic, single-logical-change per commit
- Conventional commit format
- No "WIP" or "fixup" commits in final history
- Rebase/squash before push if needed

## Code Style
- PEP 8, 4-space indent
- Type hints on all public functions/classes
- `snake_case` functions/variables, `PascalCase` classes
- Dataclasses with `slots=True` for performance
- Protocol interfaces for swappable components
- Immutable config (`frozen=True` dataclasses)

## Documentation
- Update `README.md` for user-facing changes
- Docstrings on all public classes/methods
- `REVIEW_REPORT.md`, `MASTER_STITCH_PLAN.md`, `CLEAN_CONTEXT_REVIEW.md` preserved as review artifacts
- `EXECUTION_GUIDE.md` updated with latest verified steps

## Deployment
- Local only: `pip install -e .` → `myvoice` command
- No CI/CD pipeline, no container, no cloud