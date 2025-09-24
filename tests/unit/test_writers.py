"""Tests for Thunderbird local folder helpers."""

import re
from pathlib import Path

import pytest

from mail_migration.writers import thunderbird_local


def test_ensure_local_folder_creates_parent(tmp_path: Path) -> None:
    profile = tmp_path / "Profile"
    profile.mkdir()
    result = thunderbird_local.ensure_local_folder(
        profile_root=profile,
        local_path=Path("Mail/Local Folders/Imports") / "Inbox",
    )
    assert result == profile / "Mail/Local Folders/Imports/Inbox"
    assert result.exists()


def test_ensure_local_folder_rejects_absolute(tmp_path: Path) -> None:
    profile = tmp_path / "Profile"
    profile.mkdir()
    with pytest.raises(ValueError):
        thunderbird_local.ensure_local_folder(profile, tmp_path)


def test_format_mbox_from_line_includes_sender() -> None:
    line = thunderbird_local.format_mbox_from_line(
        "Alice Example <alice@example.com>",
        "Mon, 01 Jan 2001 00:00:00 +0000",
    )
    assert line.endswith("\n")
    assert re.match(r"^From alice@example.com .+\n$", line)


def test_escape_from_lines_quotes_from_sequences() -> None:
    payload = b"From start\nBody\n>From already\n>>From twice\n"
    escaped = thunderbird_local.escape_from_lines(payload)
    lines = escaped.splitlines()
    assert lines[0] == b">From start"
    assert lines[1] == b"Body"
    assert lines[2] == b">>From already"
    assert lines[3] == b">>>From twice"


def test_ensure_mailbox_path_builds_nested_structure(tmp_path: Path) -> None:
    profile = tmp_path / "Profile"
    profile.mkdir()
    base = thunderbird_local.ensure_local_folder(profile, Path("Mail/Local Folders/Imports"))
    mailbox_path = thunderbird_local.ensure_mailbox_path(base, ["Account", "Inbox"])
    expected = profile / "Mail/Local Folders/Imports.sbd/Account.sbd/Inbox"
    assert mailbox_path == expected
    assert mailbox_path.exists()
    assert mailbox_path.parent.name == "Account.sbd"
    assert mailbox_path.parent.parent.name == "Imports.sbd"


def test_append_message_appends_payload(tmp_path: Path) -> None:
    profile = tmp_path / "Profile"
    profile.mkdir()
    base = thunderbird_local.ensure_local_folder(profile, Path("Mail/Local Folders/Imports"))
    mailbox = thunderbird_local.ensure_mailbox_path(base, ["Inbox"])

    payload = b"Subject: Test\n\nFirst body line\nFrom embedded\n"
    thunderbird_local.append_message(
        mailbox,
        from_header="Alice <alice@example.com>",
        date_header="Mon, 01 Jan 2001 00:00:00 +0000",
        payload=payload,
    )
    thunderbird_local.append_message(
        mailbox,
        from_header="Bob <bob@example.com>",
        date_header="Tue, 02 Jan 2001 00:00:00 +0000",
        payload=b"Subject: Second\n\nBody\n",
    )

    contents = mailbox.read_text()
    assert contents.count("From alice@example.com") == 1
    assert contents.count("From bob@example.com") == 1
    assert ">From embedded" in contents


def test_append_message_replaces_status_headers(tmp_path: Path) -> None:
    profile = tmp_path / "Profile"
    profile.mkdir()
    base = thunderbird_local.ensure_local_folder(profile, Path("Mail/Local Folders/Imports"))
    mailbox = thunderbird_local.ensure_mailbox_path(base, ["Inbox"])

    payload = (
        b"X-Mozilla-Status: FFFF\n" b"X-Mozilla-Status2: FFFFFFFF\n" b"Subject: Existing\n\nBody\n"
    )
    thunderbird_local.append_message(
        mailbox,
        from_header="Tester <tester@example.com>",
        date_header="Wed, 03 Jan 2001 00:00:00 +0000",
        payload=payload,
        extra_headers=[
            ("X-Mozilla-Status", "0001"),
            ("X-Mozilla-Status2", "10000000"),
        ],
    )

    contents = mailbox.read_text()
    assert contents.count("X-Mozilla-Status: 0001") == 1
    assert "X-Mozilla-Status: FFFF" not in contents
    assert contents.count("X-Mozilla-Status2: 10000000") == 1
    assert "X-Mozilla-Status2: FFFFFFFF" not in contents
