# mail-migration

Utilities for migrating Apple Mail stores into Thunderbird local folders using Python 3.10+.

## Project Layout
- `src/mail_migration/`: main package with CLI (`cli.py`), readers, and writers.
- `src/lib/`: shared helper utilities for future connectors.
- `bin/mail-migration`: executable shim that invokes the CLI.
- `tests/`: pytest suite mirroring the source layout; sample exports live in `tests/fixtures/`.

## Getting Started
```bash
make setup
source .venv/bin/activate
```

Inspect the live Apple Mail store (`~/Library/Mail/V10`) and review mailbox counts:
```bash
bin/mail-migration list-store ~/Library/Mail/V10
# => Name, Messages (fully downloaded .emlx), Partial (.partial.emlx placeholders)
```

Migrate from the on-disk Apple Mail store into a Thunderbird profile (use `--dry-run` first):
```bash
bin/mail-migration migrate-store ~/Library/Mail/V10 \
  ~/Library/Thunderbird/Profiles/xyz.default \
  "Mail/Local Folders/Imports" --dry-run
```
`Mail/Local Folders/Imports` is specified relative to the profile root and can be adjusted as needed. Omit `--dry-run` to perform the actual migration.

Scan the store for partial messages and optionally emit a JSON report:
```bash
bin/mail-migration scan-store ~/Library/Mail/V10 --report scan.json --no-progress
```

> Export-based (`.mbox`) commands are temporarily unavailable while the pipeline is being refreshed. They will return in a future release.

## Development Commands
```bash
make lint    # ruff + black
make test    # pytest
make format  # auto-fix lint findings
```

Enable the git hooks after the first setup:
```bash
pre-commit install
```

## Testing Strategy
- Use `pytest` for unit and integration coverage.
- Temporary directories (`tmp_path`) keep filesystem interactions isolated.
- Add representative `.mbox` fixtures under `tests/fixtures/` for regression coverage.
