"""Tests for Apple Mail mailbox discovery and summarisation utilities."""

import struct
from pathlib import Path

import pytest

from mail_migration.readers import apple_mbox

TOC_MAGIC = 0x000DBBA0


def _make_mailbox(
    root: Path, relative: Path, message_count: int, toc_count: int | None = None
) -> Path:
    mailbox_dir = root / relative
    messages_dir = mailbox_dir / "Messages"
    messages_dir.mkdir(parents=True)
    for idx in range(message_count):
        (messages_dir / f"message-{idx}.emlx").write_text("dummy")
    if toc_count is not None:
        toc_path = mailbox_dir / "table_of_contents"
        toc_path.write_bytes(struct.pack(">II", TOC_MAGIC, toc_count) + b"\x00" * 8)
    return mailbox_dir


def _write_mbox(mailbox_dir: Path, from_lines: int, toc_count: int | None = None) -> None:
    mailbox_dir.mkdir(parents=True, exist_ok=True)
    mbox_file = mailbox_dir / "mbox"
    mbox_contents = "".join([f"From person@example.com {i}\nBody\n" for i in range(from_lines)])
    mbox_file.write_text(mbox_contents)
    if toc_count is not None:
        toc_path = mailbox_dir / "table_of_contents"
        toc_path.write_bytes(struct.pack(">II", TOC_MAGIC, toc_count) + b"\x00" * 8)


def test_summarize_mailboxes_counts_messages(tmp_path: Path) -> None:
    export_root = tmp_path / "Export"
    export_root.mkdir()
    _make_mailbox(export_root, Path("Inbox.mbox"), 3, toc_count=5)
    _make_mailbox(export_root, Path("Archive.mbox") / "Year 2023.mbox", 1, toc_count=1)

    summaries = apple_mbox.summarize_mailboxes(export_root)

    mapping = {summary.display_path: summary for summary in summaries}
    assert set(mapping) == {"Archive/Year 2023", "Inbox"}
    assert mapping["Inbox"].stored_messages == 3
    assert mapping["Inbox"].indexed_messages == 5
    assert mapping["Archive/Year 2023"].stored_messages == 1
    assert mapping["Archive/Year 2023"].indexed_messages == 1


def test_summarize_handles_export_root_that_is_mailbox(tmp_path: Path) -> None:
    export_root = tmp_path / "Inbox.mbox"
    _make_mailbox(tmp_path, Path("Inbox.mbox"), 2, toc_count=2)

    summaries = apple_mbox.summarize_mailboxes(export_root)

    assert [summary.display_path for summary in summaries] == ["Inbox"]
    assert summaries[0].stored_messages == 2
    assert summaries[0].indexed_messages == 2


def test_discover_mailboxes_missing_root_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        list(apple_mbox.discover_mailboxes(tmp_path / "missing"))


def test_count_messages_falls_back_to_mbox_file(tmp_path: Path) -> None:
    mailbox_dir = tmp_path / "Fallback.mbox"
    _write_mbox(mailbox_dir, from_lines=2, toc_count=4)

    summaries = apple_mbox.summarize_mailboxes(mailbox_dir)

    assert summaries[0].stored_messages == 2
    assert summaries[0].indexed_messages == 4
