"""Helpers for reading Apple Mail ``.emlx`` message files."""

from __future__ import annotations

import plistlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True)
class EmlxRecord:
    """Container for an ``.emlx`` message payload and optional metadata."""

    payload: bytes
    metadata: Mapping[str, Any] | None


def read_emlx(path: Path) -> EmlxRecord:
    """Return the message payload and trailing metadata stored in ``path``."""

    with path.open("rb") as handle:
        header = handle.readline()
        try:
            expected_length = int(header.strip() or 0)
        except ValueError:  # fall back if the count line is malformed
            expected_length = 0

        payload = handle.read(expected_length) if expected_length else handle.read()
        remainder = handle.read()

    metadata = None
    if remainder:
        metadata = _load_metadata(remainder)

    return EmlxRecord(payload=payload, metadata=metadata)


def _load_metadata(raw: bytes) -> Mapping[str, Any] | None:
    data = raw.lstrip(b"\r\n")
    if not data:
        return None
    try:
        return plistlib.loads(data)
    except Exception:
        return None


__all__ = ["EmlxRecord", "read_emlx"]
