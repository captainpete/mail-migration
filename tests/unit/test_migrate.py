"""Tests for migrating from Apple Mail stores into Thunderbird."""

import plistlib
from pathlib import Path

from mail_migration import migrate


def _write_info_plist(directory: Path, name: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "Info.plist").open("wb") as handle:
        plistlib.dump({"MailboxName": name}, handle)


def _write_emlx(target: Path, headers: dict[str, str], body: str) -> None:
    payload_lines = [f"{key}: {value}" for key, value in headers.items()]
    payload = ("\n".join(payload_lines) + "\n\n" + body + "\n").encode("utf-8")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(str(len(payload)).encode("ascii") + b"\n" + payload)


def test_migrate_mail_store_transfers_messages(tmp_path: Path) -> None:
    store_root = tmp_path / "Mail" / "V10"
    mailbox_dir = store_root / "ACCOUNT-ONE" / "Inbox.mbox"
    _write_info_plist(mailbox_dir, "Inbox")
    _write_emlx(
        mailbox_dir / "UUID" / "Data" / "0" / "0" / "Messages" / "1.emlx",
        {
            "From": "Alice <alice@example.com>",
            "To": "peter@example.com",
            "Date": "Mon, 01 Jan 2001 12:00:00 +0000",
            "Subject": "Migrated Message",
        },
        "Hello from Apple Mail",
    )
    _write_emlx(
        mailbox_dir / "UUID" / "Data" / "0" / "0" / "Messages" / "2.partial.emlx",
        {
            "From": "Partial <partial@example.com>",
            "Subject": "Partial",
        },
        "",
    )

    profile_root = tmp_path / "Profile"
    profile_root.mkdir()

    stats = migrate.migrate_mail_store(
        store_root,
        profile_root,
        Path("Mail/Local Folders/Imports"),
    )

    assert stats.migrated_messages == 1
    assert stats.skipped_partials == 1
    mailbox_path = profile_root / "Mail/Local Folders/Imports.sbd/ACCOUNT-ONE.sbd/Inbox"
    contents = mailbox_path.read_text()
    assert "Migrated Message" in contents
    assert contents.startswith("From alice@example.com ")


def test_migrate_mail_store_respects_prefix_and_dry_run(tmp_path: Path) -> None:
    store_root = tmp_path / "Mail" / "V10"
    inbox_dir = store_root / "ACCOUNT" / "Inbox.mbox"
    archive_dir = store_root / "ACCOUNT" / "Archive.mbox"
    _write_info_plist(inbox_dir, "Inbox")
    _write_info_plist(archive_dir, "Archive")
    _write_emlx(
        inbox_dir / "UUID" / "Data" / "0" / "0" / "Messages" / "1.emlx",
        {
            "From": "Test <test@example.com>",
            "Date": "Tue, 02 Jan 2001 12:00:00 +0000",
            "Subject": "Inbox",
        },
        "Inbox body",
    )
    _write_emlx(
        archive_dir / "UUID" / "Data" / "0" / "0" / "Messages" / "1.emlx",
        {
            "From": "Archive <archive@example.com>",
            "Date": "Tue, 02 Jan 2001 12:00:00 +0000",
            "Subject": "Archive",
        },
        "Archive body",
    )

    profile_root = tmp_path / "Profile"
    profile_root.mkdir()

    stats = migrate.migrate_mail_store(
        store_root,
        profile_root,
        Path("Mail/Local Folders/Imports"),
        prefix="ACCOUNT/Inbox",
        dry_run=True,
    )

    assert stats.dry_run is True
    assert stats.processed_mailboxes == 1
    assert stats.migrated_messages == 1
    assert stats.skipped_by_prefix >= 1
    target = profile_root / "Mail/Local Folders/Imports.sbd/ACCOUNT.sbd/Inbox"
    assert not target.exists()
