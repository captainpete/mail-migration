"""Utilities for reading Apple Mail exported .mbox bundles."""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class MailboxSummary:
    """Simple representation of an Apple Mail mailbox and its message counts."""

    display_path: str
    directory: Path
    stored_messages: int
    indexed_messages: int


def discover_mailboxes(export_root: Path) -> Iterable[Path]:
    """Yield mailbox directories inside an Apple Mail export bundle."""
    if not export_root.exists():
        raise FileNotFoundError(f"Export root not found: {export_root}")

    if export_root.is_dir() and export_root.suffix == ".mbox":
        yield export_root

    for path in sorted(export_root.glob("**/*.mbox")):
        if path.is_dir():
            yield path


def summarize_mailboxes(export_root: Path) -> list[MailboxSummary]:
    """Return mailbox summaries for on-disk data and table-of-contents indexes."""
    summaries: list[MailboxSummary] = []
    for mailbox_dir in discover_mailboxes(export_root):
        stored_count = _stored_message_count(mailbox_dir)
        indexed_count = _indexed_message_count(mailbox_dir)
        if stored_count == 0 and indexed_count == 0:
            continue
        display_path = _relative_mailbox_name(mailbox_dir, export_root)
        summaries.append(
            MailboxSummary(
                display_path=display_path,
                directory=mailbox_dir,
                stored_messages=stored_count,
                indexed_messages=indexed_count,
            )
        )
    summaries.sort(key=lambda item: item.display_path.lower())
    return summaries


def _relative_mailbox_name(mailbox_dir: Path, export_root: Path) -> str:
    base = export_root
    if export_root.is_dir() and export_root.suffix == ".mbox":
        base = export_root.parent
    relative = mailbox_dir.relative_to(base)
    parts = [_strip_mbox_suffix(part) for part in relative.parts]
    return "/".join(parts)


def _strip_mbox_suffix(name: str) -> str:
    return name[:-5] if name.endswith(".mbox") else name


def _stored_message_count(mailbox_dir: Path) -> int:
    messages_dir = mailbox_dir / "Messages"
    if messages_dir.exists():
        return sum(1 for _ in messages_dir.rglob("*.emlx"))

    mbox_file = mailbox_dir / "mbox"
    if mbox_file.exists():
        return _count_messages_in_mbox_file(mbox_file)

    return 0


def _count_messages_in_mbox_file(mbox_file: Path) -> int:
    count = 0
    with mbox_file.open("r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            if line.startswith("From "):
                count += 1
    return count


def _indexed_message_count(mailbox_dir: Path) -> int:
    table_path = mailbox_dir / "table_of_contents"
    if not table_path.exists():
        return 0
    data = table_path.read_bytes()
    if len(data) < 8:
        return 0
    _magic, entry_count = struct.unpack_from(">II", data, 0)
    return entry_count
