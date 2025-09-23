"""Command-line interface for the mail migration toolkit."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Callable

from mail_migration.readers import apple_mbox


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mail-migration",
        description="Migrate Apple Mail exports into Thunderbird local folders or inspect mailbox contents.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser(
        "list",
        help="List mailboxes within an Apple Mail export and show message counts.",
    )
    list_parser.add_argument(
        "source_mbox",
        type=Path,
        help="Path to the Apple Mail exported .mbox bundle to inspect.",
    )
    list_parser.set_defaults(handler=_handle_list)

    migrate_parser = subparsers.add_parser(
        "migrate",
        help="Migrate Apple Mail exports into a Thunderbird local folder.",
    )
    migrate_parser.add_argument(
        "source_mbox",
        type=Path,
        help="Path to the Apple Mail exported .mbox bundle to import.",
    )
    migrate_parser.add_argument(
        "thunderbird_profile",
        type=Path,
        help="Path to the Thunderbird profile directory where mail is stored.",
    )
    migrate_parser.add_argument(
        "local_folder_path",
        type=Path,
        help=(
            "Relative path within the Thunderbird profile for the target local folder, "
            "e.g. 'Mail/Local Folders/Imports'."
        ),
    )
    migrate_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Perform validation without writing to the Thunderbird profile.",
    )
    migrate_parser.add_argument(
        "--verbose",
        action="store_true",
        help="Increase logging verbosity for troubleshooting.",
    )
    migrate_parser.set_defaults(handler=_handle_migrate)

    return parser


Handler = Callable[[argparse.Namespace], int]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "list":
        args.source_mbox = args.source_mbox.resolve()
    elif args.command == "migrate":
        args.source_mbox = args.source_mbox.resolve()
        args.thunderbird_profile = args.thunderbird_profile.resolve()
        args.local_folder_path = Path(args.local_folder_path)
        if args.local_folder_path.is_absolute():
            parser.error("local_folder_path must be relative to the Thunderbird profile root")
    else:  # pragma: no cover - safeguarded by argparse required=True
        parser.error("Unsupported command")

    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    handler: Handler = args.handler
    return handler(args)


def _handle_list(args: argparse.Namespace) -> int:
    source_mbox: Path = args.source_mbox
    if not source_mbox.exists():
        raise FileNotFoundError(f"Apple Mail export not found: {source_mbox}")

    summaries = apple_mbox.summarize_mailboxes(source_mbox)
    if not summaries:
        print(f"No mailboxes found in {source_mbox}")
        return 0

    name_width = max(len(summary.display_path) for summary in summaries)
    print(f"Mailboxes discovered in {source_mbox}:")
    header = f"  {'Name'.ljust(name_width)}  {'Stored':>6}  {'Indexed':>7}"
    print(header)
    print("  " + "-" * (len(header) - 2))
    for summary in summaries:
        name = summary.display_path.ljust(name_width)
        print(f"  {name}  {summary.stored_messages:6d}  {summary.indexed_messages:7d}")
    return 0


def _handle_migrate(args: argparse.Namespace) -> int:
    source_mbox: Path = args.source_mbox
    profile: Path = args.thunderbird_profile

    if not source_mbox.exists():
        raise FileNotFoundError(f"Apple Mail export not found: {source_mbox}")
    if not profile.exists():
        raise FileNotFoundError(f"Thunderbird profile not found: {profile}")
    # Real implementation will validate folder structure and perform migration steps here.
    return 0


if __name__ == "__main__":  # pragma: no cover - manual execution entry point
    raise SystemExit(main())
