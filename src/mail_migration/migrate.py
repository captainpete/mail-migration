"""High-level workflows for migrating Apple Mail stores into Thunderbird."""

from __future__ import annotations

from dataclasses import dataclass
from email import policy
from email.parser import BytesHeaderParser
from pathlib import Path
from typing import Iterable, Sequence

from mail_migration.readers import mail_store, mail_store_scan
from mail_migration.writers import thunderbird_local


@dataclass(frozen=True)
class MigrationStats:
    """Summary information produced by a migration run."""

    processed_mailboxes: int
    migrated_mailboxes: int
    migrated_messages: int
    recovered_partials: int
    unresolved_partials: int
    skipped_by_prefix: int
    dry_run: bool


def migrate_mail_store(
    store_root: Path,
    profile_root: Path,
    local_folder_path: Path,
    *,
    prefix: str | None = None,
    dry_run: bool = False,
) -> MigrationStats:
    """Migrate messages from ``store_root`` into a Thunderbird local folder."""

    if not store_root.exists():
        raise FileNotFoundError(f"Mail store not found: {store_root}")
    if not profile_root.exists():
        raise FileNotFoundError(f"Thunderbird profile not found: {profile_root}")
    if local_folder_path.is_absolute():
        raise ValueError("local_folder_path must be relative to the Thunderbird profile root")

    summaries = mail_store.summarize_mail_store(store_root)

    header_parser = BytesHeaderParser(policy=policy.default)

    recovery_report = mail_store_scan.scan_mail_store(
        store_root,
        show_progress=False,
    )
    recovery_by_path = {
        entry.path.resolve(): entry
        for entry in recovery_report.partial_entries
        if entry.resolved_path is not None
    }

    base_mailbox_path = profile_root / local_folder_path
    if not dry_run:
        base_mailbox_path = thunderbird_local.ensure_local_folder(profile_root, local_folder_path)

    processed = 0
    migrated_mailboxes = 0
    migrated_messages = 0
    recovered_partials = 0
    unresolved_partials = 0
    skipped_by_prefix = 0

    for summary in summaries:
        if prefix and not summary.display_path.startswith(prefix):
            skipped_by_prefix += 1
            continue

        processed += 1

        segment_names = _segment_values(summary.segments)
        if dry_run:
            mailbox_path = _compute_mailbox_path(base_mailbox_path, segment_names)
        else:
            mailbox_path = thunderbird_local.ensure_mailbox_path(base_mailbox_path, segment_names)

        mailbox_messages = 0
        for message in mail_store.iter_mailbox_messages(summary):
            payload_path = message.message_path

            if message.is_partial:
                entry = recovery_by_path.get(message.message_path.resolve())
                if entry is None or entry.resolved_path is None:
                    unresolved_partials += 1
                    continue
                resolved_path = entry.resolved_path
                if not resolved_path.exists():
                    raise FileNotFoundError(f"Recovered message not found: {resolved_path}")
                payload_path = resolved_path
                recovered_partials += 1

            payload = _read_emlx_payload(payload_path)
            if not payload:
                continue
            headers = header_parser.parsebytes(payload)
            from_header = headers.get("From")
            date_header = headers.get("Date")

            if not dry_run:
                thunderbird_local.append_message(
                    mailbox_path,
                    from_header=from_header,
                    date_header=date_header,
                    payload=payload,
                )

            mailbox_messages += 1
            migrated_messages += 1

        if mailbox_messages > 0 or not dry_run:
            migrated_mailboxes += 1

    return MigrationStats(
        processed_mailboxes=processed,
        migrated_mailboxes=migrated_mailboxes,
        migrated_messages=migrated_messages,
        recovered_partials=recovered_partials,
        unresolved_partials=unresolved_partials,
        skipped_by_prefix=skipped_by_prefix,
        dry_run=dry_run,
    )


def _read_emlx_payload(path: Path) -> bytes:
    with path.open("rb") as handle:
        handle.readline()  # leading byte-count header
        payload = handle.read()
    return payload


def _segment_values(segments: Sequence[mail_store.MailStoreNameSegment]) -> Iterable[str]:
    return [segment.value for segment in segments]


def _compute_mailbox_path(base_mailbox: Path, segments: Iterable[str]) -> Path:
    current = base_mailbox
    for segment in segments:
        current = current.with_name(current.name + ".sbd") / segment
    return current


__all__ = ["MigrationStats", "migrate_mail_store"]
