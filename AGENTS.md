# Repository Guidelines

## Project Structure & Module Organization
- Core logic lives in `src/mail_migration/`; keep providers in `readers/` and Thunderbird adapters in `writers/`.
- Shared helpers belong in `src/lib/`; add modules when functionality is reused across readers and writers.
- CLI entry lives in `src/mail_migration/cli.py` with an executable shim in `bin/mail-migration`.
- Tests reside in `tests/`, mirroring `src/`; add fixtures under `tests/fixtures/` when you need canned mailbox exports.
- Versioning and tool configuration sit in `pyproject.toml`; update it when dependencies shift.

## Build, Test, and Development Commands
- `make setup` creates/updates `.venv` and installs project + dev extras.
- `make lint` runs formatters and static analysis (`ruff`, `black`) over `src/` and `tests/`.
- `make test` executes the pytest suite with the repository on `PYTHONPATH`.
- `bin/mail-migration list <export.mbox>` shows each mailbox with Stored (on-disk) and Indexed (Apple Mail table-of-contents) message counts.
- `bin/mail-migration list-store <Mail/V10>` enumerates the Mail store directly, reporting fully downloaded and partial `.emlx` counts per mailbox.
- `bin/mail-migration migrate <export.mbox> <profile> "Mail/Local Folders/Imports"` performs the local migration (use `--dry-run` for validation).

## Coding Style & Naming Conventions
- Use 4-space indentation for Python and adhere to `ruff`/`black` defaults.
- Modules expose functions/classes via `snake_case`/`PascalCase`; keep CLI-only helpers private (`_helper`).
- Prefer small, composable functions; route filesystem interactions through adapters for testability.
- Run `pre-commit run --all-files` before pushing to ensure consistent formatting.

## Testing Guidelines
- Write unit tests with `pytest`; integration scenarios should target realistic mbox samples under `tests/fixtures/`.
- Name test files `test_<subject>.py` and group scenario-specific tests with parametrization.
- Keep coverage ≥90% for `src/mail_migration/`; note exceptions in PR descriptions.
- Use temporary directories (`tmp_path`) when touching filesystem paths inside tests.

## Commit & Pull Request Guidelines
- Follow Conventional Commits (`feat:`, `fix:`, `chore:`) and keep messages focused and present-tense.
- Reference migration tickets or GitHub issues; outline rollback or manual verification steps when relevant.
- Include CLI transcripts or diff snippets when behavior changes.
- Request review from someone comfortable with Thunderbird internals when modifying writers.
