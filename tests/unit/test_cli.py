"""Tests for the mail migration CLI argument parsing and commands."""

import plistlib
import struct
from pathlib import Path

import pytest

from mail_migration import cli


def _write_info_plist(directory: Path, name: str) -> None:
    with (directory / "Info.plist").open("wb") as handle:
        plistlib.dump({"MailboxName": name}, handle)


def _write_emlx(directory: Path, name: str, *, subject: str) -> None:
    payload = (
        f"From: Alice <alice@example.com>\n"
        f"To: Bob <bob@example.com>\n"
        f"Date: Mon, 01 Jan 2001 12:00:00 +0000\n"
        f"Subject: {subject}\n\n"
        "Body\n"
    ).encode("utf-8")
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_bytes(str(len(payload)).encode("ascii") + b"\n" + payload)


TOC_MAGIC = 0x000DBBA0


def _write_table_of_contents(mailbox_dir: Path, count: int) -> None:
    toc_path = mailbox_dir / "table_of_contents"
    toc_path.write_bytes(struct.pack(">II", TOC_MAGIC, count) + b"\x00" * 8)


def test_parse_args_resolves_paths_for_migrate(tmp_path: Path) -> None:
    source = tmp_path / "Mail" / "V10"
    source.mkdir(parents=True)
    profile = tmp_path / "Profile.test"
    profile.mkdir()
    args = cli.parse_args(
        [
            "migrate",
            str(source),
            str(profile),
            "Mail/Local Folders/Imports",
        ]
    )
    assert args.command == "migrate"
    assert args.mail_store_root == source
    assert args.thunderbird_profile == profile
    assert args.local_folder_path == Path("Mail/Local Folders/Imports")
    assert args.prefix is None


def test_parse_args_rejects_absolute_local_folder(tmp_path: Path) -> None:
    source = tmp_path / "Mail" / "V10"
    source.mkdir(parents=True)
    profile = tmp_path / "Profile.test"
    profile.mkdir()
    absolute_local = tmp_path / "absolute"
    with pytest.raises(SystemExit):
        cli.parse_args(
            [
                "migrate",
                str(source),
                str(profile),
                str(absolute_local),
            ]
        )


def test_main_migrate_raises_file_not_found(tmp_path: Path) -> None:
    profile = tmp_path / "Profile"
    profile.mkdir()
    with pytest.raises(FileNotFoundError):
        cli.main(
            [
                "migrate",
                str(tmp_path / "missing-store"),
                str(profile),
                "Mail/Local Folders/Imports",
            ]
        )


def test_migrate_command_dry_run(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    store_root = tmp_path / "Mail" / "V10" / "Account" / "Inbox.mbox"
    store_root.mkdir(parents=True)
    _write_info_plist(store_root, "Inbox")
    messages = store_root / "UUID" / "Data" / "0" / "0" / "Messages"
    _write_emlx(messages, "1.emlx", subject="Test Migration")

    profile = tmp_path / "Profile"
    profile.mkdir()

    exit_code = cli.main(
        [
            "migrate",
            str(tmp_path / "Mail" / "V10"),
            str(profile),
            "Mail/Local Folders/Imports",
            "--dry-run",
        ]
    )

    captured = capsys.readouterr().out
    assert exit_code == 0
    assert "Dry run complete" in captured
    assert "messages across" in captured
    target = profile / "Mail/Local Folders/Imports.sbd/Account.sbd/Inbox"
    assert not target.exists()


def test_list_command_outputs_counts(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    export_root = tmp_path / "Export"
    mailbox_dir = export_root / "Inbox.mbox"
    messages_dir = mailbox_dir / "Messages"
    messages_dir.mkdir(parents=True)
    for idx in range(2):
        (messages_dir / f"{idx}.emlx").write_text("dummy")
    _write_table_of_contents(mailbox_dir, count=5)

    exit_code = cli.main(["list", str(export_root)])

    captured = capsys.readouterr().out
    assert exit_code == 0
    assert "Mailboxes discovered" in captured
    assert "Stored" in captured
    assert "Indexed" in captured
    assert "Inbox" in captured
    assert "2" in captured and "5" in captured


def test_list_command_missing_source() -> None:
    with pytest.raises(FileNotFoundError):
        cli.main(["list", "/nonexistent/path/export.mbox"])


def test_list_store_command_outputs_counts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    store_root = tmp_path / "Mail" / "V10" / "Account"
    mailbox = store_root / "Inbox.mbox"
    mailbox.mkdir(parents=True)
    _write_info_plist(mailbox, "Inbox")
    messages = mailbox / "UUID" / "Data" / "0" / "0" / "Messages"
    messages.mkdir(parents=True)
    (messages / "1.emlx").write_text("Subject: Hello\n\nBody")
    (messages / "2.partial.emlx").write_text("Subject: Partial\n\nBody")

    exit_code = cli.main(["list-store", str(store_root)])

    captured = capsys.readouterr().out
    assert exit_code == 0
    assert "Mailboxes discovered" in captured
    inbox_line = next(line for line in captured.splitlines() if "Inbox" in line)
    columns = inbox_line.split()
    assert columns[0] == "Inbox"
    assert columns[-2:] == ["1", "1"]
