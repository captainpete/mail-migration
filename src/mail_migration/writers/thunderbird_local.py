"""Helpers for writing mail content into Thunderbird local folders."""

from __future__ import annotations

from pathlib import Path


def ensure_local_folder(profile_root: Path, local_path: Path) -> Path:
    """Return an absolute path to the Thunderbird local folder, creating parent directories."""
    if local_path.is_absolute():
        raise ValueError("local_path must be relative to the Thunderbird profile root")
    target = profile_root / local_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.touch(exist_ok=True)
    return target
