"""Tests for ``lib.emlx`` helpers."""

import plistlib
from pathlib import Path

from lib import emlx


def test_read_emlx_parses_payload_and_metadata(tmp_path: Path) -> None:
    payload = b"Subject: Sample\n\nBody\n"
    metadata = {"flags": 42}
    data = plistlib.dumps(metadata, fmt=plistlib.FMT_BINARY)
    target = tmp_path / "message.emlx"
    target.write_bytes(str(len(payload)).encode("ascii") + b"\n" + payload + b"\n" + data)

    record = emlx.read_emlx(target)
    assert record.payload == payload
    assert record.metadata == metadata


def test_read_emlx_handles_missing_metadata(tmp_path: Path) -> None:
    payload = b"Subject: Sample\n\nBody\n"
    target = tmp_path / "message.emlx"
    target.write_bytes(str(len(payload)).encode("ascii") + b"\n" + payload)

    record = emlx.read_emlx(target)
    assert record.payload == payload
    assert record.metadata is None
