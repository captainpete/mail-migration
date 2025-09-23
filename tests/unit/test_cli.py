"""Basic smoke tests for the mail migration CLI argument parsing."""

from pathlib import Path

import pytest

from mail_migration import cli


def test_parse_args_resolves_paths(tmp_path: Path) -> None:
    source = tmp_path / "export.mbox"
    source.write_text("dummy")
    profile = tmp_path / "Profile.test"
    profile.mkdir()
    args = cli.parse_args([
        str(source),
        str(profile),
        "Mail/Local Folders/Imports",
    ])
    assert args.source_mbox == source
    assert args.thunderbird_profile == profile
    assert args.local_folder_path == Path("Mail/Local Folders/Imports")


def test_parse_args_rejects_absolute_local_folder(tmp_path: Path) -> None:
    source = tmp_path / "export.mbox"
    source.write_text("dummy")
    profile = tmp_path / "Profile.test"
    profile.mkdir()
    absolute_local = tmp_path / "absolute"
    with pytest.raises(SystemExit):
        cli.parse_args([str(source), str(profile), str(absolute_local)])


def test_main_raises_file_not_found(tmp_path: Path) -> None:
    profile = tmp_path / "Profile"
    profile.mkdir()
    with pytest.raises(FileNotFoundError):
        cli.main([
            str(tmp_path / "missing.mbox"),
            str(profile),
            "Mail/Local Folders/Imports",
        ])
