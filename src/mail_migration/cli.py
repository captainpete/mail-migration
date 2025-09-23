"""Command-line interface for the mail migration toolkit."""

from __future__ import annotations

import argparse
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mail-migration",
        description="Migrate Apple Mail exports into a Thunderbird local folder.",
    )
    parser.add_argument(
        "source_mbox",
        type=Path,
        help="Path to the Apple Mail exported .mbox bundle to import.",
    )
    parser.add_argument(
        "thunderbird_profile",
        type=Path,
        help="Path to the Thunderbird profile directory where mail is stored.",
    )
    parser.add_argument(
        "local_folder_path",
        type=Path,
        help=(
            "Relative path within the Thunderbird profile for the target local folder, "
            "e.g. 'Mail/Local Folders/Imports'."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Perform validation without writing to the Thunderbird profile.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Increase logging verbosity for troubleshooting.",
    )
    return parser


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.source_mbox = args.source_mbox.resolve()
    args.thunderbird_profile = args.thunderbird_profile.resolve()
    args.local_folder_path = Path(args.local_folder_path)
    if args.local_folder_path.is_absolute():
        parser.error("local_folder_path must be relative to the Thunderbird profile root")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.source_mbox.exists():
        raise FileNotFoundError(f"Apple Mail export not found: {args.source_mbox}")
    if not args.thunderbird_profile.exists():
        raise FileNotFoundError(f"Thunderbird profile not found: {args.thunderbird_profile}")
    # Real implementation will validate folder structure and perform migration steps here.
    return 0


if __name__ == "__main__":  # pragma: no cover - manual execution entry point
    raise SystemExit(main())
