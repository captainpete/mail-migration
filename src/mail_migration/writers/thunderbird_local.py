"""Helpers for writing mail content into Thunderbird local folders."""

from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parseaddr, parsedate_to_datetime
from pathlib import Path
from typing import Iterable


def _resolve_sender(from_header: str | None) -> str:
    name, address = parseaddr(from_header or "")
    if address:
        return address
    if from_header:
        return from_header.strip()
    return "MAILER-DAEMON"


def _resolve_timestamp(date_header: str | None) -> datetime:
    if date_header:
        try:
            parsed = parsedate_to_datetime(date_header)
            if parsed is not None:
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                return parsed.astimezone()
        except (TypeError, ValueError):
            pass
    return datetime.now(timezone.utc).astimezone()


def format_mbox_from_line(from_header: str | None, date_header: str | None) -> str:
    """Return an mbox-compatible ``From `` separator line."""

    sender = _resolve_sender(from_header)
    timestamp = _resolve_timestamp(date_header)
    formatted = timestamp.strftime("%a %b %d %H:%M:%S %Y")
    return f"From {sender} {formatted}\n"


def escape_from_lines(message: bytes) -> bytes:
    """Escape ``From `` lines within a message payload for mbox storage."""

    lines = message.splitlines(keepends=True)
    escaped: list[bytes] = []
    for line in lines:
        newline = b""
        content = line
        if line.endswith(b"\r\n"):
            content = line[:-2]
            newline = b"\r\n"
        elif line.endswith(b"\n"):
            content = line[:-1]
            newline = b"\n"

        stripped = content.lstrip(b">")
        if stripped.startswith(b"From "):
            content = b">" + content

        escaped.append(content + newline)

    return b"".join(escaped)


def ensure_local_folder(profile_root: Path, local_path: Path) -> Path:
    """Return an absolute path to the Thunderbird local folder, creating parent directories."""
    if local_path.is_absolute():
        raise ValueError("local_path must be relative to the Thunderbird profile root")
    target = profile_root / local_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.touch(exist_ok=True)
    return target


def ensure_mailbox_path(base_mailbox: Path, segments: Iterable[str]) -> Path:
    """Return the Thunderbird mbox path for ``segments`` beneath ``base_mailbox``."""

    current = base_mailbox
    for segment in segments:
        container = current.with_name(current.name + ".sbd")
        container.mkdir(parents=True, exist_ok=True)
        current = container / segment
        current.touch(exist_ok=True)
    return current


def append_message(
    target: Path,
    *,
    from_header: str | None,
    date_header: str | None,
    payload: bytes,
) -> None:
    """Append a message payload to the provided Thunderbird mbox file."""

    separator = format_mbox_from_line(from_header, date_header).encode("utf-8")
    body = escape_from_lines(payload)
    if not body.endswith(b"\n"):
        body += b"\n"

    with target.open("ab") as handle:
        handle.write(separator)
        handle.write(body)
        handle.write(b"\n")


__all__ = [
    "append_message",
    "ensure_local_folder",
    "ensure_mailbox_path",
    "escape_from_lines",
    "format_mbox_from_line",
]
