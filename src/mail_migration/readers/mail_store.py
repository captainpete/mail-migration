"""Helpers for reading Apple Mail's on-disk mail store (~/Library/Mail/V10)."""

from __future__ import annotations

import os
import plistlib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Tuple

_SKIP_DIRECTORIES = {
    "Attachments",
    "Attachments.noindex",
    "Data",
    "Info.plist",
    "Messages",
    "Resources",
    "MailData",
}


@dataclass(frozen=True)
class MailStoreNameSegment:
    value: str
    is_directory: bool


@dataclass(frozen=True)
class MailStoreSummary:
    """Mail store mailbox summary with message statistics."""

    display_path: str
    mailbox_dir: Path
    stored_messages: int
    partial_messages: int
    segments: Tuple[MailStoreNameSegment, ...]


def summarize_mail_store(store_root: Path) -> list[MailStoreSummary]:
    """Return summaries for each mailbox beneath ``store_root``.

    The ``store_root`` may point at the ``Mail/V10`` directory, an account
    subdirectory, or an individual ``*.mbox`` folder.
    """

    root = store_root.resolve()
    if not root.exists():
        raise FileNotFoundError(f"Mail store not found: {root}")

    summaries: list[MailStoreSummary] = []
    for mailbox_dir, name_parts in _iter_mailboxes(root):
        stored, partial = _count_messages(mailbox_dir)
        display_path = "/".join(part.value for part in name_parts)
        summaries.append(
            MailStoreSummary(
                display_path=display_path,
                mailbox_dir=mailbox_dir,
                stored_messages=stored,
                partial_messages=partial,
                segments=name_parts,
            )
        )
    summaries.sort(key=lambda summary: summary.display_path.lower())
    return summaries


def _should_include_directory_names(root: Path) -> bool:
    try:
        for child in root.iterdir():
            if not child.is_dir():
                continue
            if child.name in _SKIP_DIRECTORIES:
                continue
            if not child.name.endswith(".mbox"):
                return True
    except FileNotFoundError:
        return False
    return False


def _iter_mailboxes(root: Path) -> Iterator[Tuple[Path, Tuple[MailStoreNameSegment, ...]]]:
    if root.name.endswith(".mbox") and root.is_dir():
        name = _mailbox_display_name(root)
        parts = (MailStoreNameSegment(name, False),)
        yield root, parts
        yield from _walk_child_mailboxes(root, parts, include_directory_names=False)
    else:
        include_directory_names = _should_include_directory_names(root)
        yield from _walk_child_mailboxes(root, (), include_directory_names)


def _walk_child_mailboxes(
    directory: Path,
    parent_parts: Tuple[MailStoreNameSegment, ...],
    include_directory_names: bool,
) -> Iterator[Tuple[Path, Tuple[MailStoreNameSegment, ...]]]:
    try:
        children = sorted(directory.iterdir(), key=lambda item: item.name.lower())
    except FileNotFoundError:
        return

    for child in children:
        if not child.is_dir():
            continue
        name = child.name
        if name.endswith(".mbox"):
            mailbox_name = _mailbox_display_name(child)
            parts = parent_parts + (MailStoreNameSegment(mailbox_name, False),)
            yield child, parts
            yield from _walk_child_mailboxes(child, parts, include_directory_names)
        else:
            # Only descend further if we have not yet entered a mailbox hierarchy.
            if parent_parts:
                continue
            if name in _SKIP_DIRECTORIES:
                continue
            next_parts = parent_parts
            if include_directory_names:
                next_parts = parent_parts + (MailStoreNameSegment(name, True),)
            yield from _walk_child_mailboxes(child, next_parts, include_directory_names)


def _mailbox_display_name(mailbox_dir: Path) -> str:
    info_path = mailbox_dir / "Info.plist"
    if info_path.exists():
        try:
            with info_path.open("rb") as handle:
                info = plistlib.load(handle)
            name = info.get("MailboxName")
            if isinstance(name, str) and name.strip():
                return name.strip()
        except Exception:
            pass
    return mailbox_dir.stem


def _count_messages(mailbox_dir: Path) -> Tuple[int, int]:
    stored = 0
    partial = 0
    for root, dirs, files in os.walk(mailbox_dir):
        # Prevent descending into nested mailbox directories so counts remain scoped.
        dirs[:] = [d for d in dirs if not (Path(root) / d).name.endswith(".mbox")]
        root_path = Path(root)
        if "Messages" not in root_path.parts:
            continue
        for filename in files:
            if filename.endswith(".partial.emlx"):
                partial += 1
            elif filename.endswith(".emlx"):
                stored += 1
    return stored, partial


__all__ = ["MailStoreNameSegment", "MailStoreSummary", "summarize_mail_store"]
