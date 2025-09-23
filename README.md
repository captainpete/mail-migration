# mail-migration

Utilities for migrating Apple Mail exports into Thunderbird local folders using Python 3.10+.

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

List mailboxes within an Apple Mail export and see both on-disk and indexed counts:
```bash
bin/mail-migration list /path/to/export.mbox
# => Name, Stored (actual .emlx/.mbox messages), Indexed (Apple Mail table_of_contents)
```

Run the migration dry-run once you have an Apple Mail export (`.mbox` bundle) and a Thunderbird profile:
```bash
bin/mail-migration migrate /path/to/export.mbox \
  ~/Library/Thunderbird/Profiles/xyz.default \
  "Mail/Local Folders/Imports" --dry-run
```
`Mail/Local Folders/Imports` is stored relative to the profile root and can be adjusted as needed.

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
