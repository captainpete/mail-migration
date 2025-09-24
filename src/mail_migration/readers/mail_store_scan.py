"""Utilities for scanning the Apple Mail store for partial message recovery."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from email import policy
from email.parser import BytesHeaderParser
from pathlib import Path
from typing import Tuple

from tqdm import tqdm

from mail_migration.readers import mail_store

CompositeKey = Tuple[str, str, str, str, str]


def _normalize_header(value: str | None) -> str:
    if value is None:
        return ""
    if not isinstance(value, str):
        value = str(value)
    return sys.intern(value.strip())


def _composite_key(headers) -> CompositeKey:
    return (
        _normalize_header(headers.get("Message-ID")),
        _normalize_header(headers.get("Date")),
        _normalize_header(headers.get("From")),
        _normalize_header(headers.get("To")),
        _normalize_header(headers.get("Subject")),
    )


@dataclass(slots=True)
class FullEntry:
    key: CompositeKey
    path: Path
    mailbox: str
    size: int
    duplicate_count: int = 0
    mismatched_size: bool = False


@dataclass(slots=True)
class PartialEntry:
    key: CompositeKey
    path: Path
    mailbox: str
    resolved_path: Path | None = None
    duplicate_count: int = 0
    size_mismatch: bool = False


@dataclass(slots=True)
class ScanReport:
    total_full_messages: int
    total_partial_messages: int
    resolved_partials: int
    unresolved_partials: int
    duplicate_keys: int
    duplicate_messages: int
    mismatched_size_keys: int
    partial_entries: list[PartialEntry]


def scan_mail_store(
    store_root: Path,
    *,
    show_progress: bool = True,
    prefix: str | None = None,
) -> ScanReport:
    """Scan ``store_root`` to index full messages and locate partial recovery options."""

    summaries = mail_store.summarize_mail_store(store_root)
    if prefix:
        summaries = [s for s in summaries if s.display_path.startswith(prefix)]
    total_items = sum(s.stored_messages + s.partial_messages for s in summaries)
    header_parser = BytesHeaderParser(policy=policy.compat32)

    progress = tqdm(
        total=total_items,
        disable=not show_progress,
        unit="msg",
        desc="Scanning Mail Store",
    )

    full_index: dict[CompositeKey, FullEntry] = {}
    partial_entries: list[PartialEntry] = []

    total_full = 0
    total_partial = 0

    for summary in summaries:
        for message in mail_store.iter_mailbox_messages(summary):
            try:
                with message.message_path.open("rb") as handle:
                    handle.readline()  # skip byte-count header
                    headers = header_parser.parse(handle, headersonly=True)
            except Exception as exc:  # pragma: no cover - defensive logging for malformed files
                print(
                    f"[scan] Failed to parse headers for {message.message_path}: {exc}",
                    file=sys.stdout,
                )
                progress.update(1)
                continue

            try:
                key = _composite_key(headers)
            except Exception as exc:  # pragma: no cover - unexpected header parsing failure
                print(
                    f"[scan] Failed to build composite key for {message.message_path}: {exc}",
                    file=sys.stdout,
                )
                progress.update(1)
                continue

            size = message.message_path.stat().st_size

            if message.is_partial:
                total_partial += 1
                partial_entries.append(
                    PartialEntry(
                        key=key,
                        path=message.message_path,
                        mailbox=summary.display_path,
                    )
                )
            else:
                total_full += 1
                existing = full_index.get(key)
                if existing is None:
                    full_index[key] = FullEntry(
                        key=key,
                        path=message.message_path,
                        mailbox=summary.display_path,
                        size=size,
                    )
                else:
                    existing.duplicate_count += 1
                    if existing.size != size:
                        existing.mismatched_size = True
                        if size > existing.size:
                            existing.path = message.message_path
                            existing.mailbox = summary.display_path
                            existing.size = size

            progress.update(1)

    progress.close()

    resolved = 0
    mismatched_size_keys = 0
    duplicate_keys = 0
    duplicate_messages = 0

    for entry in full_index.values():
        if entry.duplicate_count:
            duplicate_keys += 1
            duplicate_messages += entry.duplicate_count
            if entry.mismatched_size:
                mismatched_size_keys += 1

    for partial in partial_entries:
        match = full_index.get(partial.key)
        if match is None:
            continue
        partial.resolved_path = match.path
        partial.duplicate_count = match.duplicate_count
        partial.size_mismatch = match.mismatched_size
        resolved += 1

    unresolved = len(partial_entries) - resolved

    return ScanReport(
        total_full_messages=total_full,
        total_partial_messages=total_partial,
        resolved_partials=resolved,
        unresolved_partials=unresolved,
        duplicate_keys=duplicate_keys,
        duplicate_messages=duplicate_messages,
        mismatched_size_keys=mismatched_size_keys,
        partial_entries=partial_entries,
    )


def report_to_dict(report: ScanReport, store_root: Path) -> dict:
    timestamp = datetime.now(timezone.utc).isoformat()
    return {
        "generated_at": timestamp,
        "store_root": str(store_root),
        "summary": {
            "total_full_messages": report.total_full_messages,
            "total_partial_messages": report.total_partial_messages,
            "resolved_partials": report.resolved_partials,
            "unresolved_partials": report.unresolved_partials,
            "duplicate_keys": report.duplicate_keys,
            "duplicate_messages": report.duplicate_messages,
            "mismatched_size_keys": report.mismatched_size_keys,
        },
        "partials": [
            {
                "mailbox": entry.mailbox,
                "path": str(entry.path),
                "resolved_path": str(entry.resolved_path) if entry.resolved_path else None,
                "duplicate_count": entry.duplicate_count,
                "size_mismatch": entry.size_mismatch,
                "key": list(entry.key),
            }
            for entry in report.partial_entries
        ],
    }


def write_report(report_path: Path, report: ScanReport, store_root: Path) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    data = report_to_dict(report, store_root)
    report_path.write_text(json.dumps(data, indent=2), encoding="utf-8")


__all__ = [
    "CompositeKey",
    "PartialEntry",
    "FullEntry",
    "ScanReport",
    "scan_mail_store",
    "write_report",
    "report_to_dict",
]
