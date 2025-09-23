# Repository Guidelines

## Project Structure & Module Organization
- Place migration logic under `src/` using subfolders per provider (e.g., `src/google_workspace/`).
- Keep reusable connectors and helpers inside `src/lib/` with clear module boundaries.
- Store configuration samples in `config/` and redact any secrets before committing.
- Write automated tests under `tests/` mirroring the `src/` hierarchy; fixtures belong in `tests/fixtures/`.
- Save command-line entry points in `bin/`, marking executables with the correct shebang and `chmod +x`.

## Build, Test, and Development Commands
- `make setup` installs toolchain dependencies (Python env, Node tooling) and prepares local `.env` templates.
- `make lint` runs formatters and static analysis across Python (`ruff`) and JavaScript (`eslint`).
- `make test` executes the full automated suite, including integration shims in `tests/integration/`.
- `python -m src.cli migrate --dry-run` exercises the default end-to-end path without mutating mailboxes.

## Coding Style & Naming Conventions
- Follow 4-space indentation for Python modules and 2-space indentation for JavaScript tooling scripts.
- Adopt `snake_case` for functions, `PascalCase` for classes, and prefix async helpers with `async_`.
- Keep modules small (<300 lines) and favor dependency injection over global state.
- Run `pre-commit run --all-files` before pushing; hooks enforce formatting (`black`, `ruff`, `eslint`).

## Testing Guidelines
- Use `pytest` for unit tests and `pytest -m integration` for slower provider-backed scenarios.
- Name test files `test_<subject>.py` and parameterize cross-provider cases for coverage clarity.
- Target ≥90% line coverage for core modules; surface gaps in the PR checklist if below threshold.
- Record credentials-sensitive fixtures in `.git-crypt`; never commit live tokens.

## Commit & Pull Request Guidelines
- Prefer Conventional Commit prefixes (`feat:`, `fix:`, `chore:`) to signal intent; squash minor fixups locally.
- Include screenshots or terminal transcripts for UI/CLI changes affecting output formatting.
