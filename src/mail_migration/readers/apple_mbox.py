"""Utilities for reading Apple Mail exported .mbox bundles."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable


def discover_mailboxes(export_root: Path) -> Iterable[Path]:
    """Yield mailbox directories inside an Apple Mail export bundle."""
    if not export_root.exists():
        raise FileNotFoundError(f"Export root not found: {export_root}")
    for path in export_root.glob("**/*.mbox"):
        if path.is_dir():
            yield path
