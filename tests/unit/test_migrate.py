"""Tests for migrating from Apple Mail stores into Thunderbird."""

import plistlib
from pathlib import Path

import pytest

from mail_migration import migrate
from mail_migration.readers import mail_store_scan


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
    assert stats.recovered_partials == 0
    assert stats.unresolved_partials == 1
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
    assert stats.recovered_partials == 0
    assert stats.unresolved_partials == 0
    assert stats.skipped_by_prefix >= 1
    target = profile_root / "Mail/Local Folders/Imports.sbd/ACCOUNT.sbd/Inbox"
    assert not target.exists()


def test_migrate_mail_store_recovers_partial(tmp_path: Path) -> None:
    store_root = tmp_path / "Mail" / "V10"

    full_mailbox = store_root / "ACCOUNT-FULL" / "Archive.mbox"
    partial_mailbox = store_root / "ACCOUNT-PARTIAL" / "Inbox.mbox"
    _write_info_plist(full_mailbox, "Archive")
    _write_info_plist(partial_mailbox, "Inbox")

    headers = {
        "From": "Recover Me <recover@example.com>",
        "To": "peter@example.com",
        "Date": "Wed, 03 Jan 2001 12:00:00 +0000",
        "Subject": "Recovered Message",
        "Message-ID": "<recover@example.com>",
    }

    body_full = "Full body with attachments"
    body_partial = ""

    _write_emlx(
        full_mailbox / "UUID" / "Data" / "0" / "0" / "Messages" / "10.emlx",
        headers,
        body_full,
    )
    _write_emlx(
        partial_mailbox / "UUID" / "Data" / "0" / "0" / "Messages" / "20.partial.emlx",
        headers,
        body_partial,
    )

    profile_root = tmp_path / "Profile"
    profile_root.mkdir()

    stats = migrate.migrate_mail_store(
        store_root,
        profile_root,
        Path("Mail/Local Folders/Imports"),
    )

    assert stats.migrated_messages == 2
    assert stats.recovered_partials == 1
    assert stats.unresolved_partials == 0

    mailbox_path = profile_root / "Mail/Local Folders/Imports.sbd/ACCOUNT-PARTIAL.sbd/Inbox"
    contents = mailbox_path.read_text()
    assert "Recovered Message" in contents
    assert "Full body with attachments" in contents


def test_migrate_mail_store_recovery_missing_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    store_root = tmp_path / "Mail" / "V10"
    mailbox_dir = store_root / "ACCOUNT" / "Inbox.mbox"
    _write_info_plist(mailbox_dir, "Inbox")

    headers = {
        "From": "Missing <missing@example.com>",
        "To": "peter@example.com",
        "Date": "Thu, 04 Jan 2001 12:00:00 +0000",
        "Subject": "Missing File",
        "Message-ID": "<missing@example.com>",
    }

    partial_path = mailbox_dir / "UUID" / "Data" / "0" / "0" / "Messages" / "1.partial.emlx"
    _write_emlx(partial_path, headers, "")

    fake_resolved = tmp_path / "nonexistent.emlx"

    partial_entry = mail_store_scan.PartialEntry(
        key=(
            headers["Message-ID"],
            headers["Date"],
            headers["From"],
            headers["To"],
            headers["Subject"],
        ),
        path=partial_path.resolve(),
        mailbox="ACCOUNT/Inbox",
        resolved_path=fake_resolved,
        duplicate_count=0,
        size_mismatch=False,
    )
    fake_report = mail_store_scan.ScanReport(
        total_full_messages=0,
        total_partial_messages=1,
        resolved_partials=1,
        unresolved_partials=0,
        duplicate_keys=0,
        duplicate_messages=0,
        mismatched_size_keys=0,
        partial_entries=[partial_entry],
    )

    monkeypatch.setattr(
        mail_store_scan,
        "scan_mail_store",
        lambda *args, **kwargs: fake_report,
    )

    profile_root = tmp_path / "Profile"
    profile_root.mkdir()

    with pytest.raises(FileNotFoundError):
        migrate.migrate_mail_store(
            store_root,
            profile_root,
            Path("Mail/Local Folders/Imports"),
        )
