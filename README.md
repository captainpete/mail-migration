# mail-migration

Utilities for migrating Apple Mail stores or exported `.mbox` bundles into Thunderbird local folders using Python 3.10+.

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

## Inspect Apple Mail Data
List mailboxes from the live on-disk store (`~/Library/Mail/V10`) and review mailbox counts:
```bash
bin/mail-migration list-store ~/Library/Mail/V10
# => Name, Stored (fully downloaded .emlx), Partial (.partial.emlx placeholders)
```

List mailboxes from an exported Apple Mail `.mbox` bundle:
```bash
bin/mail-migration list-mbox ~/Desktop/MailExport
# => Name, Stored (messages on disk), Indexed (table_of_contents entries)
```

## Migrate Into Thunderbird
Migrate directly from the on-disk Apple Mail store (use `--dry-run` first):
```bash
bin/mail-migration migrate-store ~/Library/Mail/V10 \
  ~/Library/Thunderbird/Profiles/xyz.default \
  "Mail/Local Folders/Imports" --dry-run
```
`Mail/Local Folders/Imports` is specified relative to the profile root and can be adjusted as needed. Omit `--dry-run` to perform the actual migration.

Migrate from an exported `.mbox` bundle:
```bash
bin/mail-migration migrate-mbox ~/Desktop/MailExport \
  ~/Library/Thunderbird/Profiles/xyz.default \
  "Mail/Local Folders/Imports" --dry-run
```
Use `--prefix <path>` to limit migration to mailboxes whose display path starts with the provided value. `--mail-store-root ~/Library/Mail/V10` lets the migrator backfill messages that were indexed but left out of the export. `--no-progress` hides the progress bar and `--verbose` enables additional logging.

> Note: Apple Mail export bundles do not retain per-message read/replied flags. When migrating with `migrate-mbox`, Thunderbird will mark imported messages as unread even if they were read in Apple Mail.

## Scan For Issues
Scan the live store for partial messages and optionally emit a JSON report:
```bash
bin/mail-migration scan-store ~/Library/Mail/V10 --report scan.json --no-progress
```

Scan an exported `.mbox` bundle for discrepancies between on-disk and indexed counts:
```bash
bin/mail-migration scan-mbox ~/Desktop/MailExport --report scan-export.json --no-progress
```

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
