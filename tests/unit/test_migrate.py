"""Tests for migrating Apple Mail content into Thunderbird."""

import plistlib
import struct
from pathlib import Path

import pytest

from mail_migration import migrate
from mail_migration.readers import mail_store_scan

TOC_MAGIC = 0x000DBBA0


def _write_info_plist(directory: Path, name: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "Info.plist").open("wb") as handle:
        plistlib.dump({"MailboxName": name}, handle)


def _write_emlx(
    target: Path,
    headers: dict[str, str],
    body: str,
    *,
    metadata: dict[str, object] | None = None,
) -> None:
    payload_lines = [f"{key}: {value}" for key, value in headers.items()]
    payload = ("\n".join(payload_lines) + "\n\n" + body + "\n").encode("utf-8")
    target.parent.mkdir(parents=True, exist_ok=True)
    trailer = b""
    if metadata:
        plist = plistlib.dumps(metadata, fmt=plistlib.FMT_BINARY)
        trailer = b"\n" + plist
    target.write_bytes(str(len(payload)).encode("ascii") + b"\n" + payload + trailer)


def _write_mbox_messages(mailbox_dir: Path, subjects: list[str]) -> None:
    mailbox_dir.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    for index, subject in enumerate(subjects):
        lines.append(f"From sender@example.com {index}\n")
        lines.append("From: Sender <sender@example.com>\n")
        lines.append("Date: Fri, 05 Jan 2001 12:00:00 +0000\n")
        lines.append(f"Subject: {subject}\n\n")
        lines.append(f"Body {index}\n\n")
    (mailbox_dir / "mbox").write_text("".join(lines))


def _write_table_of_contents(mailbox_dir: Path, count: int) -> None:
    mailbox_dir.mkdir(parents=True, exist_ok=True)
    payload = struct.pack(">II", TOC_MAGIC, count) + b"\x00" * 8
    (mailbox_dir / "table_of_contents").write_bytes(payload)


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
        metadata={"flags": (1 << 0) | (0x3F << 10)},
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
    assert stats.recovered_missing == 0
    assert stats.unresolved_partials == 1
    mailbox_path = profile_root / "Mail/Local Folders/Imports.sbd/ACCOUNT-ONE.sbd/Inbox"
    contents = mailbox_path.read_text()
    assert "Migrated Message" in contents
    assert contents.startswith("From alice@example.com ")
    assert "X-Mozilla-Status: 0001" in contents
    assert "X-Mozilla-Status2: 00000000" in contents


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
    assert stats.recovered_missing == 0
    assert stats.unresolved_partials == 0
    assert stats.skipped_by_prefix >= 1
    target = profile_root / "Mail/Local Folders/Imports.sbd/ACCOUNT.sbd/Inbox"
    assert not target.exists()


def test_status_headers_ignore_attachment_sentinel() -> None:
    headers = migrate._derive_status_headers({"flags": (0x3F << 10)})
    assert ("X-Mozilla-Status", "0000") in headers
    assert ("X-Mozilla-Status2", "00000000") in headers


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
        metadata={"flags": (1 << 0) | (1 << 8) | (2 << 10)},
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
    assert stats.recovered_missing == 0
    assert stats.unresolved_partials == 0

    mailbox_path = profile_root / "Mail/Local Folders/Imports.sbd/ACCOUNT-PARTIAL.sbd/Inbox"
    contents = mailbox_path.read_text()
    assert "Recovered Message" in contents
    assert "Full body with attachments" in contents
    assert "X-Mozilla-Status: 1001" in contents
    assert "X-Mozilla-Status2: 10000000" in contents


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


def test_migrate_mbox_export_transfers_messages(tmp_path: Path) -> None:
    export_root = tmp_path / "Export"
    mailbox_dir = export_root / "Inbox.mbox"
    messages = mailbox_dir / "Messages"
    _write_emlx(
        messages / "1.emlx",
        {
            "From": "Export <export@example.com>",
            "Date": "Fri, 05 Jan 2001 12:00:00 +0000",
            "Subject": "Export Message",
        },
        "Export body",
        metadata={"flags": (1 << 0)},
    )
    _write_emlx(
        messages / "2.partial.emlx",
        {
            "From": "Partial <partial@example.com>",
            "Subject": "Partial Export",
        },
        "",
    )

    profile_root = tmp_path / "Profile"
    profile_root.mkdir()

    stats = migrate.migrate_mbox_export(
        export_root,
        profile_root,
        Path("Mail/Local Folders/Imports"),
    )

    assert stats.migrated_messages == 1
    assert stats.unresolved_partials == 1
    assert stats.recovered_partials == 0
    assert stats.recovered_missing == 0
    mailbox_path = profile_root / "Mail/Local Folders/Imports.sbd/Inbox"
    contents = mailbox_path.read_text()
    assert "Export Message" in contents
    assert "X-Mozilla-Status: 0001" in contents


def test_migrate_mbox_export_respects_prefix_and_dry_run(tmp_path: Path) -> None:
    export_root = tmp_path / "Export"
    inbox_dir = export_root / "Inbox.mbox"
    archive_dir = export_root / "Archive.mbox" / "Year 2023.mbox"
    _write_emlx(
        (inbox_dir / "Messages" / "1.emlx"),
        {
            "From": "Inbox <inbox@example.com>",
            "Date": "Sat, 06 Jan 2001 12:00:00 +0000",
            "Subject": "Inbox message",
        },
        "Inbox body",
    )
    _write_emlx(
        (archive_dir / "Messages" / "1.emlx"),
        {
            "From": "Archive <archive@example.com>",
            "Date": "Sat, 06 Jan 2001 12:00:00 +0000",
            "Subject": "Archive message",
        },
        "Archive body",
    )

    profile_root = tmp_path / "Profile"
    profile_root.mkdir()

    stats = migrate.migrate_mbox_export(
        export_root,
        profile_root,
        Path("Mail/Local Folders/Imports"),
        prefix="Archive",
        dry_run=True,
    )

    assert stats.dry_run is True
    assert stats.processed_mailboxes == 1
    assert stats.migrated_messages == 1
    assert stats.unresolved_partials == 0
    assert stats.recovered_missing == 0
    assert stats.skipped_by_prefix >= 1
    target = profile_root / "Mail/Local Folders/Imports.sbd/Archive.sbd/Year 2023"
    assert not target.exists()


def test_migrate_mbox_export_handles_mbox_file(tmp_path: Path) -> None:
    export_root = tmp_path / "Export"
    mailbox_dir = export_root / "Inbox.mbox"
    _write_mbox_messages(mailbox_dir, ["First", "Second"])

    profile_root = tmp_path / "Profile"
    profile_root.mkdir()

    stats = migrate.migrate_mbox_export(
        export_root,
        profile_root,
        Path("Mail/Local Folders/Imports"),
    )

    assert stats.migrated_messages == 2
    assert stats.recovered_missing == 0
    mailbox_path = profile_root / "Mail/Local Folders/Imports.sbd/Inbox"
    contents = mailbox_path.read_text()
    assert "Subject: First" in contents
    assert "Subject: Second" in contents


def test_migrate_mbox_export_backfills_from_mail_store(tmp_path: Path) -> None:
    export_root = tmp_path / "Export"
    mailbox_dir = export_root / "Inbox.mbox"
    _write_table_of_contents(mailbox_dir, 1)

    store_root = tmp_path / "Mail" / "V10"
    store_mailbox = store_root / "Inbox.mbox"
    _write_emlx(
        store_mailbox / "Messages" / "1.emlx",
        {
            "From": "Recovered <recovered@example.com>",
            "Date": "Sun, 07 Jan 2001 12:00:00 +0000",
            "Subject": "Recovered from Store",
            "Message-ID": "<recovered@example.com>",
        },
        "Recovered body",
    )

    profile_root = tmp_path / "Profile"
    profile_root.mkdir()

    stats = migrate.migrate_mbox_export(
        export_root,
        profile_root,
        Path("Mail/Local Folders/Imports"),
        mail_store_root=store_root,
    )

    assert stats.migrated_messages == 1
    assert stats.recovered_partials == 0
    assert stats.recovered_missing == 1
    assert stats.unresolved_partials == 0
    mailbox_path = profile_root / "Mail/Local Folders/Imports.sbd/Inbox"
    contents = mailbox_path.read_text()
    assert "Recovered from Store" in contents
