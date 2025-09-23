"""Tests for parsing the Apple Mail on-disk store."""

import plistlib
from pathlib import Path

from mail_migration.readers import mail_store


def _write_info_plist(directory: Path, name: str) -> None:
    with (directory / "Info.plist").open("wb") as handle:
        plistlib.dump({"MailboxName": name}, handle)


def _make_emlx(directory: Path, name: str, content: str = "Subject: test\n\nBody") -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_text(content)


def test_summarize_mail_store_counts_messages(tmp_path: Path) -> None:
    store_root = tmp_path / "Mail" / "V10" / "ACCOUNT"
    archive = store_root / "Archive.mbox"
    archive.mkdir(parents=True)
    _write_info_plist(archive, "Archive")
    _make_emlx(archive / "UUID" / "Data" / "0" / "0" / "Messages", "1.emlx")
    _make_emlx(archive / "UUID" / "Data" / "0" / "1" / "Messages", "2.partial.emlx")

    nested = archive / "Subfolder.mbox"
    nested.mkdir()
    _write_info_plist(nested, "Subfolder")
    _make_emlx(nested / "Another" / "Data" / "0" / "0" / "Messages", "3.emlx")

    summaries = mail_store.summarize_mail_store(store_root)

    mapping = {summary.display_path: summary for summary in summaries}
    assert mapping["Archive"].stored_messages == 1
    assert mapping["Archive"].partial_messages == 1
    assert [segment.is_directory for segment in mapping["Archive"].segments] == [False]
    assert mapping["Archive/Subfolder"].stored_messages == 1
    assert mapping["Archive/Subfolder"].partial_messages == 0
    assert [segment.is_directory for segment in mapping["Archive/Subfolder"].segments] == [
        False,
        False,
    ]


def test_mailbox_name_defaults_to_stem(tmp_path: Path) -> None:
    mailbox = tmp_path / "NoInfo.mbox"
    mailbox.mkdir()
    _make_emlx(mailbox / "UUID" / "Data" / "0" / "0" / "Messages", "message.emlx")

    summaries = mail_store.summarize_mail_store(mailbox)

    assert summaries[0].display_path == "NoInfo"
    assert summaries[0].stored_messages == 1


def test_summarize_mail_store_includes_account_prefix(tmp_path: Path) -> None:
    store_root = tmp_path / "Mail" / "V10"

    account_one = store_root / "ACCOUNT-ONE"
    inbox = account_one / "Inbox.mbox"
    inbox.mkdir(parents=True)
    _write_info_plist(inbox, "Inbox")
    _make_emlx(inbox / "UUID" / "Data" / "0" / "0" / "Messages", "1.emlx")

    account_two = store_root / "ACCOUNT-TWO"
    archive = account_two / "Archive.mbox"
    archive.mkdir(parents=True)
    _write_info_plist(archive, "Archive")
    _make_emlx(archive / "UUID" / "Data" / "0" / "0" / "Messages", "2.partial.emlx")

    summaries = mail_store.summarize_mail_store(store_root)

    mapping = {summary.display_path: summary for summary in summaries}
    assert "ACCOUNT-ONE/Inbox" in mapping
    assert mapping["ACCOUNT-ONE/Inbox"].stored_messages == 1
    assert [segment.is_directory for segment in mapping["ACCOUNT-ONE/Inbox"].segments] == [
        True,
        False,
    ]
    assert "ACCOUNT-TWO/Archive" in mapping
    assert mapping["ACCOUNT-TWO/Archive"].partial_messages == 1
    assert [segment.is_directory for segment in mapping["ACCOUNT-TWO/Archive"].segments] == [
        True,
        False,
    ]
