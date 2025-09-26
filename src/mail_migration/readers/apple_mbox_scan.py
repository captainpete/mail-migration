"""Scanning utilities for Apple Mail exported .mbox bundles."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from tqdm import tqdm

from mail_migration.readers import apple_mbox


@dataclass(frozen=True)
class MailboxMismatch:
    """Details about an export mailbox with potential inconsistencies."""

    display_path: str
    full_messages: int
    indexed_messages: int
    partial_messages: int
    missing_messages: int


@dataclass(frozen=True)
class ExportScanReport:
    """Aggregate results from scanning an exported Apple Mail bundle."""

    total_mailboxes: int
    total_full_messages: int
    total_partial_messages: int
    total_indexed_messages: int
    total_missing_messages: int
    mismatched_mailboxes: list[MailboxMismatch]


def scan_export(
    export_root: Path,
    *,
    show_progress: bool = True,
    prefix: str | None = None,
) -> ExportScanReport:
    """Inspect ``export_root`` for partial messages or index mismatches."""

    summaries = apple_mbox.summarize_mailboxes(export_root)
    if prefix:
        summaries = [s for s in summaries if s.display_path.startswith(prefix)]

    total_messages = sum(summary.stored_messages for summary in summaries)
    progress = None
    if show_progress and total_messages:
        progress = tqdm(total=total_messages, desc="Scanning Export", unit="msg")

    mismatches: list[MailboxMismatch] = []
    total_full = 0
    total_partial = 0
    total_missing = 0
    total_indexed = 0

    for summary in summaries:
        partial = _count_partial_messages(summary.directory)
        full_messages = max(summary.stored_messages - partial, 0)
        missing_messages = max(summary.indexed_messages - full_messages, 0)

        if progress:
            progress.update(summary.stored_messages)

        if partial or missing_messages or full_messages != summary.indexed_messages:
            mismatches.append(
                MailboxMismatch(
                    display_path=summary.display_path,
                    full_messages=full_messages,
                    indexed_messages=summary.indexed_messages,
                    partial_messages=partial,
                    missing_messages=missing_messages,
                )
            )

        total_full += full_messages
        total_partial += partial
        total_missing += missing_messages
        total_indexed += summary.indexed_messages

    if progress:
        progress.close()

    return ExportScanReport(
        total_mailboxes=len(summaries),
        total_full_messages=total_full,
        total_partial_messages=total_partial,
        total_indexed_messages=total_indexed,
        total_missing_messages=total_missing,
        mismatched_mailboxes=mismatches,
    )


def write_report(path: Path, report: ExportScanReport, export_root: Path) -> None:
    """Serialize ``report`` to ``path`` in JSON format."""

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "export_root": str(export_root),
        "summary": {
            "total_mailboxes": report.total_mailboxes,
            "total_full_messages": report.total_full_messages,
            "total_partial_messages": report.total_partial_messages,
            "total_indexed_messages": report.total_indexed_messages,
            "total_missing_messages": report.total_missing_messages,
        },
        "mailboxes": [
            {
                "path": mismatch.display_path,
                "full_messages": mismatch.full_messages,
                "indexed_messages": mismatch.indexed_messages,
                "partial_messages": mismatch.partial_messages,
                "missing_messages": mismatch.missing_messages,
            }
            for mismatch in report.mismatched_mailboxes
        ],
    }

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))


def _count_partial_messages(mailbox_dir: Path) -> int:
    messages_dir = mailbox_dir / "Messages"
    if not messages_dir.exists():
        return 0
    return sum(1 for _ in messages_dir.rglob("*.partial.emlx"))


__all__ = [
    "ExportScanReport",
    "MailboxMismatch",
    "scan_export",
    "write_report",
]
