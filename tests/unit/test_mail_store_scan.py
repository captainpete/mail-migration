"""Tests for scanning the Apple Mail store for partial recovery."""

import json
import plistlib
from pathlib import Path

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


def test_scan_mail_store_indexes_partials(tmp_path: Path) -> None:
    store_root = tmp_path / "Mail" / "V10"

    headers = {
        "Message-ID": "<test@example.com>",
        "Date": "Mon, 01 Jan 2001 00:00:00 +0000",
        "From": "Alice <alice@example.com>",
        "To": "Bob <bob@example.com>",
        "Subject": "Greetings",
    }

    full_mailbox = store_root / "Account" / "Inbox.mbox"
    _write_info_plist(full_mailbox, "Inbox")
    _write_emlx(
        full_mailbox / "UUID" / "Data" / "0" / "0" / "Messages" / "1.emlx",
        headers,
        "Hello",
    )

    duplicate_mailbox = store_root / "Account" / "Duplicate.mbox"
    _write_info_plist(duplicate_mailbox, "Duplicate")
    _write_emlx(
        duplicate_mailbox / "UUID" / "Data" / "0" / "0" / "Messages" / "2.emlx",
        headers,
        "Hello again",
    )

    partial_mailbox = store_root / "Account" / "Archive.mbox"
    _write_info_plist(partial_mailbox, "Archive")
    _write_emlx(
        partial_mailbox / "UUID" / "Data" / "0" / "0" / "Messages" / "3.partial.emlx",
        headers,
        "Partial",
    )

    unmatched_headers = {
        "Message-ID": "<unmatched@example.com>",
        "Date": "Tue, 02 Jan 2001 00:00:00 +0000",
        "From": "Carol <carol@example.com>",
        "To": "Bob <bob@example.com>",
        "Subject": "Different",
    }
    _write_emlx(
        partial_mailbox / "UUID" / "Data" / "0" / "0" / "Messages" / "4.partial.emlx",
        unmatched_headers,
        "Partial",
    )

    report = mail_store_scan.scan_mail_store(store_root, show_progress=False)

    assert report.total_full_messages == 2
    assert report.total_partial_messages == 2
    assert report.resolved_partials == 1
    assert report.unresolved_partials == 1
    assert report.duplicate_keys == 1
    assert report.duplicate_messages == 1

    partial_map = {entry.path.name: entry for entry in report.partial_entries}
    assert partial_map["3.partial.emlx"].resolved_path is not None
    assert partial_map["3.partial.emlx"].resolved_path.name == "2.emlx"
    assert partial_map["3.partial.emlx"].duplicate_count == 1
    assert partial_map["3.partial.emlx"].size_mismatch is True
    assert partial_map["4.partial.emlx"].resolved_path is None

    report_path = tmp_path / "report.json"
    mail_store_scan.write_report(report_path, report, store_root)
    data = json.loads(report_path.read_text())
    assert data["summary"]["resolved_partials"] == 1
    assert len(data["partials"]) == 2
    resolved_entry = next(
        item for item in data["partials"] if item["path"].endswith("3.partial.emlx")
    )
    assert resolved_entry["resolved_path"].endswith("2.emlx")
    assert resolved_entry["size_mismatch"] is True
