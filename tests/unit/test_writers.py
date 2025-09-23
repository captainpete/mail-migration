"""Tests for Thunderbird local folder helpers."""

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
