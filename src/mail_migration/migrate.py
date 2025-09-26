"""High-level workflows for migrating Apple Mail content into Thunderbird."""

from __future__ import annotations

from dataclasses import dataclass
from email import policy
from email.parser import BytesHeaderParser
from pathlib import Path
from typing import Iterable, Iterator, Mapping, Sequence

from tqdm import tqdm

from lib import emlx
from mail_migration.readers import apple_mbox, mail_store, mail_store_scan
from mail_migration.writers import thunderbird_local


@dataclass(frozen=True)
class MigrationStats:
    """Summary information produced by a migration run."""

    processed_mailboxes: int
    migrated_mailboxes: int
    migrated_messages: int
    recovered_partials: int
    recovered_missing: int
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
    show_progress: bool = False,
) -> MigrationStats:
    """Migrate messages from ``store_root`` into a Thunderbird local folder."""

    if not store_root.exists():
        raise FileNotFoundError(f"Mail store not found: {store_root}")
    if not profile_root.exists():
        raise FileNotFoundError(f"Thunderbird profile not found: {profile_root}")
    if local_folder_path.is_absolute():
        raise ValueError("local_folder_path must be relative to the Thunderbird profile root")

    summaries = mail_store.summarize_mail_store(store_root)
    if prefix:
        target_summaries = [s for s in summaries if s.display_path.startswith(prefix)]
        skipped_by_prefix = len(summaries) - len(target_summaries)
    else:
        target_summaries = list(summaries)
        skipped_by_prefix = 0

    header_parser = BytesHeaderParser(policy=policy.compat32)

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

    total_messages = sum(
        summary.stored_messages + summary.partial_messages for summary in target_summaries
    )
    progress = None
    if show_progress and total_messages:
        progress = tqdm(total=total_messages, desc="Migrating Mail", unit="msg")

    for summary in target_summaries:
        processed += 1

        if progress:
            progress.set_postfix_str(summary.display_path, refresh=False)

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
                    if progress:
                        progress.update(1)
                    continue
                resolved_path = entry.resolved_path
                if not resolved_path.exists():
                    raise FileNotFoundError(f"Recovered message not found: {resolved_path}")
                payload_path = resolved_path
                recovered_partials += 1

            record = emlx.read_emlx(payload_path)
            payload = record.payload
            if not payload:
                if progress:
                    progress.update(1)
                continue
            headers = header_parser.parsebytes(payload)
            from_header = headers.get("From")
            date_header = headers.get("Date")
            status_headers = _derive_status_headers(record.metadata)

            if not dry_run:
                thunderbird_local.append_message(
                    mailbox_path,
                    from_header=from_header,
                    date_header=date_header,
                    payload=payload,
                    extra_headers=status_headers,
                )

            mailbox_messages += 1
            migrated_messages += 1
            if progress:
                progress.update(1)

        if mailbox_messages > 0 or not dry_run:
            migrated_mailboxes += 1

    if progress:
        progress.close()

    return MigrationStats(
        processed_mailboxes=processed,
        migrated_mailboxes=migrated_mailboxes,
        migrated_messages=migrated_messages,
        recovered_partials=recovered_partials,
        recovered_missing=0,
        unresolved_partials=unresolved_partials,
        skipped_by_prefix=skipped_by_prefix,
        dry_run=dry_run,
    )


@dataclass(frozen=True)
class ExportMessage:
    """Representation of a message discovered inside an exported mailbox."""

    payload: bytes
    metadata: Mapping[str, object] | None
    is_partial: bool


def migrate_mbox_export(
    export_root: Path,
    profile_root: Path,
    local_folder_path: Path,
    *,
    prefix: str | None = None,
    mail_store_root: Path | None = None,
    dry_run: bool = False,
    show_progress: bool = False,
) -> MigrationStats:
    """Migrate messages from an exported Apple Mail ``.mbox`` bundle."""

    if not export_root.exists():
        raise FileNotFoundError(f"Apple Mail export not found: {export_root}")
    if not profile_root.exists():
        raise FileNotFoundError(f"Thunderbird profile not found: {profile_root}")
    if local_folder_path.is_absolute():
        raise ValueError("local_folder_path must be relative to the Thunderbird profile root")

    summaries = apple_mbox.summarize_mailboxes(export_root)
    if prefix:
        target_summaries = [s for s in summaries if s.display_path.startswith(prefix)]
        skipped_by_prefix = len(summaries) - len(target_summaries)
    else:
        target_summaries = list(summaries)
        skipped_by_prefix = 0

    header_parser = BytesHeaderParser(policy=policy.compat32)

    store_index: dict[str, mail_store.MailStoreSummary] = {}
    store_key_cache: dict[str, dict[CompositeKey, Path]] = {}
    if mail_store_root is not None:
        store_summaries = mail_store.summarize_mail_store(mail_store_root)
        store_index = {summary.display_path: summary for summary in store_summaries}

    base_mailbox_path = profile_root / local_folder_path
    if not dry_run:
        base_mailbox_path = thunderbird_local.ensure_local_folder(profile_root, local_folder_path)

    processed = 0
    migrated_mailboxes = 0
    migrated_messages = 0
    recovered_partials = 0
    recovered_missing = 0
    unresolved_partials = 0

    total_messages = sum(
        max(summary.stored_messages, summary.indexed_messages) for summary in target_summaries
    )
    progress = None
    if show_progress and total_messages:
        progress = tqdm(total=total_messages, desc="Migrating Export", unit="msg")

    for summary in target_summaries:
        processed += 1

        if progress:
            progress.set_postfix_str(summary.display_path, refresh=False)

        segments = _export_segments(summary.display_path)
        if dry_run:
            mailbox_path = _compute_mailbox_path(base_mailbox_path, segments)
        else:
            mailbox_path = thunderbird_local.ensure_mailbox_path(base_mailbox_path, segments)

        mailbox_messages = 0
        mailbox_keys: set[CompositeKey] = set()
        for export_message in _iter_export_messages(summary.directory):
            if progress:
                progress.update(1)

            if export_message.is_partial:
                unresolved_partials += 1
                continue

            payload = export_message.payload
            if not payload:
                continue

            headers = header_parser.parsebytes(payload)
            from_header = headers.get("From")
            date_header = headers.get("Date")
            status_headers = _derive_status_headers(export_message.metadata)
            key = _composite_key(headers)
            if key is not None:
                mailbox_keys.add(key)

            if not dry_run:
                thunderbird_local.append_message(
                    mailbox_path,
                    from_header=from_header,
                    date_header=date_header,
                    payload=payload,
                    extra_headers=status_headers,
                )

            mailbox_messages += 1
            migrated_messages += 1

        missing_target = max(summary.indexed_messages - mailbox_messages, 0)
        if mail_store_root is not None and missing_target > 0:
            store_summary = store_index.get(summary.display_path)
            if store_summary is not None:
                key_map = store_key_cache.get(summary.display_path)
                if key_map is None:
                    key_map = _build_store_key_map(store_summary, header_parser)
                    store_key_cache[summary.display_path] = key_map
                for key, payload_path in key_map.items():
                    if key in mailbox_keys:
                        continue
                    record = emlx.read_emlx(payload_path)
                    payload = record.payload
                    if not payload:
                        continue
                    headers = header_parser.parsebytes(payload)
                    from_header = headers.get("From")
                    date_header = headers.get("Date")
                    status_headers = _derive_status_headers(record.metadata)
                    if not dry_run:
                        thunderbird_local.append_message(
                            mailbox_path,
                            from_header=from_header,
                            date_header=date_header,
                            payload=payload,
                            extra_headers=status_headers,
                        )
                    mailbox_keys.add(key)
                    mailbox_messages += 1
                    migrated_messages += 1
                    recovered_missing += 1
                    if progress:
                        progress.update(1)
                    if mailbox_messages >= summary.indexed_messages:
                        break

        if mailbox_messages > 0 or not dry_run:
            migrated_mailboxes += 1

    if progress:
        progress.close()

    return MigrationStats(
        processed_mailboxes=processed,
        migrated_mailboxes=migrated_mailboxes,
        migrated_messages=migrated_messages,
        recovered_partials=recovered_partials,
        recovered_missing=recovered_missing,
        unresolved_partials=unresolved_partials,
        skipped_by_prefix=skipped_by_prefix,
        dry_run=dry_run,
    )


def _segment_values(segments: Sequence[mail_store.MailStoreNameSegment]) -> Iterable[str]:
    return [segment.value for segment in segments]


def _compute_mailbox_path(base_mailbox: Path, segments: Iterable[str]) -> Path:
    current = base_mailbox
    for segment in segments:
        current = current.with_name(current.name + ".sbd") / segment
    return current


def _export_segments(display_path: str) -> Iterable[str]:
    if not display_path:
        return []
    return display_path.split("/")


def _iter_export_messages(mailbox_dir: Path) -> Iterator[ExportMessage]:
    messages_dir = mailbox_dir / "Messages"
    if messages_dir.exists():
        for path in sorted(messages_dir.rglob("*.emlx")):
            record = emlx.read_emlx(path)
            is_partial = path.name.endswith(".partial.emlx") or not record.payload
            yield ExportMessage(
                payload=record.payload,
                metadata=record.metadata,
                is_partial=is_partial,
            )
        return

    mbox_file = mailbox_dir / "mbox"
    if mbox_file.exists():
        for payload in _iter_mbox_payloads(mbox_file):
            yield ExportMessage(payload=payload, metadata=None, is_partial=False)


def _iter_mbox_payloads(mbox_file: Path) -> Iterator[bytes]:
    with mbox_file.open("rb") as handle:
        buffer: list[bytes] = []
        for line in handle:
            if line.startswith(b"From "):
                if buffer:
                    yield b"".join(buffer)
                    buffer = []
                continue
            buffer.append(line)
        if buffer:
            yield b"".join(buffer)


CompositeKey = tuple[str, str, str, str, str]


def _build_store_key_map(
    summary: mail_store.MailStoreSummary,
    header_parser: BytesHeaderParser,
) -> dict[CompositeKey, Path]:
    key_map: dict[CompositeKey, Path] = {}
    for message in mail_store.iter_mailbox_messages(summary):
        if message.is_partial:
            continue
        record = emlx.read_emlx(message.message_path)
        payload = record.payload
        if not payload:
            continue
        headers = header_parser.parsebytes(payload)
        key = _composite_key(headers)
        if key is None or key in key_map:
            continue
        key_map[key] = message.message_path
    return key_map


def _composite_key(headers) -> CompositeKey | None:
    values = tuple(
        _normalized_header(headers.get(name))
        for name in ("Message-ID", "Date", "From", "To", "Subject")
    )
    if any(values):
        return values
    return None


def _normalized_header(value) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        value = str(value)
    return value.strip()


def _derive_status_headers(
    metadata: Mapping[str, object] | None,
) -> list[tuple[str, str]]:
    apple_flags = _extract_flags(metadata)
    status, status2 = _convert_flags(apple_flags)

    formatted_status = f"{status:04X}"
    formatted_status2 = f"{status2:08X}"

    return [
        ("X-Mozilla-Status", formatted_status),
        ("X-Mozilla-Status2", formatted_status2),
    ]


def _extract_flags(metadata: Mapping[str, object] | None) -> int:
    if not metadata:
        return 0

    candidate = metadata.get("flags") or metadata.get("Flags")
    if isinstance(candidate, bool):
        return int(candidate)
    if isinstance(candidate, (int, float)):
        return int(candidate)
    if isinstance(candidate, (bytes, bytearray)):
        try:
            return int(candidate.decode("ascii"), 0)
        except (UnicodeDecodeError, ValueError):
            return 0
    if isinstance(candidate, str):
        try:
            return int(candidate, 0)
        except ValueError:
            return 0
    return 0


def _convert_flags(apple_flags: int) -> tuple[int, int]:
    status = 0
    status2 = 0

    mappings = (
        (1 << 0, 0x00000001),  # read
        (1 << 2, 0x00000002),  # replied
        (1 << 4, 0x00000004),  # flagged/starred
        (1 << 8, 0x00001000),  # forwarded
        (1 << 9, 0x00002000),  # redirected
    )

    for apple_bit, mozilla_flag in mappings:
        if apple_flags & apple_bit:
            if mozilla_flag <= 0xFFFF:
                status |= mozilla_flag
            else:
                status2 |= mozilla_flag

    attachment_count = (apple_flags >> 10) & 0x3F
    if attachment_count and attachment_count != 0x3F:
        status2 |= 0x10000000

    return status, status2


__all__ = [
    "MigrationStats",
    "migrate_mail_store",
    "migrate_mbox_export",
]
