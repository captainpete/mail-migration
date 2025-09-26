"""Command-line interface for the mail migration toolkit."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Callable

from mail_migration import migrate as migration
from mail_migration.readers import apple_mbox, apple_mbox_scan, mail_store, mail_store_scan


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mail-migration",
        description="Migrate Apple Mail data into Thunderbird local folders or inspect mailbox contents.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_mbox_parser = subparsers.add_parser(
        "list-mbox",
        help="List mailboxes within an Apple Mail export and show message counts.",
    )
    list_mbox_parser.add_argument(
        "source_mbox",
        type=Path,
        help="Path to the Apple Mail exported .mbox bundle to inspect.",
    )
    list_mbox_parser.set_defaults(handler=_handle_list_mbox)

    list_store_parser = subparsers.add_parser(
        "list-store",
        help="List mailboxes and message counts directly from the Apple Mail store.",
    )
    list_store_parser.add_argument(
        "store_root",
        type=Path,
        help="Path to the Mail/V10 directory, an account folder, or a specific *.mbox directory.",
    )
    list_store_parser.set_defaults(handler=_handle_list_store)

    migrate_mbox_parser = subparsers.add_parser(
        "migrate-mbox",
        help="Migrate mailboxes from an exported Apple Mail bundle into Thunderbird.",
    )
    migrate_mbox_parser.add_argument(
        "export_root",
        type=Path,
        help="Path to the exported .mbox bundle or containing directory.",
    )
    migrate_mbox_parser.add_argument(
        "thunderbird_profile",
        type=Path,
        help="Path to the Thunderbird profile directory where mail is stored.",
    )
    migrate_mbox_parser.add_argument(
        "local_folder_path",
        type=Path,
        help=(
            "Relative path within the Thunderbird profile for the target local folder, "
            "e.g. 'Mail/Local Folders/Imports'."
        ),
    )
    migrate_mbox_parser.add_argument(
        "--prefix",
        help="Only migrate mailboxes whose path starts with the provided prefix (case-sensitive).",
    )
    migrate_mbox_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Perform validation without writing to the Thunderbird profile.",
    )
    migrate_mbox_parser.add_argument(
        "--no-progress",
        action="store_true",
        help="Disable progress bar output during the migration run.",
    )
    migrate_mbox_parser.add_argument(
        "--verbose",
        action="store_true",
        help="Increase logging verbosity for troubleshooting.",
    )
    migrate_mbox_parser.add_argument(
        "--mail-store-root",
        type=Path,
        help=(
            "Optional path to a live Apple Mail store used to backfill missing "
            "messages that were not exported."
        ),
    )
    migrate_mbox_parser.set_defaults(handler=_handle_migrate_mbox)

    migrate_store_parser = subparsers.add_parser(
        "migrate-store",
        help="Migrate mailboxes from the on-disk Apple Mail store into Thunderbird.",
    )
    migrate_store_parser.add_argument(
        "mail_store_root",
        type=Path,
        help="Path to the Mail/V10 directory or a subdirectory containing Apple Mail mailboxes.",
    )
    migrate_store_parser.add_argument(
        "thunderbird_profile",
        type=Path,
        help="Path to the Thunderbird profile directory where mail is stored.",
    )
    migrate_store_parser.add_argument(
        "local_folder_path",
        type=Path,
        help=(
            "Relative path within the Thunderbird profile for the target local folder, "
            "e.g. 'Mail/Local Folders/Imports'."
        ),
    )
    migrate_store_parser.add_argument(
        "--prefix",
        help="Only migrate mailboxes whose path starts with the provided prefix (case-sensitive).",
    )
    migrate_store_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Perform validation without writing to the Thunderbird profile.",
    )
    migrate_store_parser.add_argument(
        "--no-progress",
        action="store_true",
        help="Disable progress bar output during the migration run.",
    )
    migrate_store_parser.add_argument(
        "--verbose",
        action="store_true",
        help="Increase logging verbosity for troubleshooting.",
    )
    migrate_store_parser.set_defaults(handler=_handle_migrate_store)

    scan_mbox_parser = subparsers.add_parser(
        "scan-mbox",
        help="Scan an exported Apple Mail bundle for partial messages or index gaps.",
    )
    scan_mbox_parser.add_argument(
        "export_root",
        type=Path,
        help="Path to the exported .mbox bundle or containing directory.",
    )
    scan_mbox_parser.add_argument(
        "--report",
        type=Path,
        help="Optional path to write a JSON report describing detected mismatches.",
    )
    scan_mbox_parser.add_argument(
        "--prefix",
        help="Only scan mailboxes whose path starts with the provided prefix (case-sensitive).",
    )
    scan_mbox_parser.add_argument(
        "--no-progress",
        action="store_true",
        help="Disable the progress bar output during the scan.",
    )
    scan_mbox_parser.set_defaults(handler=_handle_scan_mbox)

    scan_store_parser = subparsers.add_parser(
        "scan-store",
        help="Scan the Apple Mail store for partial messages that could be recovered.",
    )
    scan_store_parser.add_argument(
        "mail_store_root",
        type=Path,
        help="Path to the Mail/V10 directory or subset to scan.",
    )
    scan_store_parser.add_argument(
        "--report",
        type=Path,
        help="Optional path to write a JSON report describing partial recovery matches.",
    )
    scan_store_parser.add_argument(
        "--prefix",
        help="Only scan mailboxes whose path starts with the provided prefix (case-sensitive).",
    )
    scan_store_parser.add_argument(
        "--no-progress",
        action="store_true",
        help="Disable the progress bar output during the scan.",
    )
    scan_store_parser.set_defaults(handler=_handle_scan_store)

    return parser


Handler = Callable[[argparse.Namespace], int]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "list-mbox":
        args.source_mbox = args.source_mbox.resolve()
    elif args.command == "list-store":
        args.store_root = args.store_root.resolve()
    elif args.command == "migrate-mbox":
        args.export_root = args.export_root.resolve()
        args.thunderbird_profile = args.thunderbird_profile.resolve()
        args.local_folder_path = Path(args.local_folder_path)
        if args.local_folder_path.is_absolute():
            parser.error("local_folder_path must be relative to the Thunderbird profile root")
        if args.mail_store_root is not None:
            args.mail_store_root = args.mail_store_root.resolve()
    elif args.command == "migrate-store":
        args.mail_store_root = args.mail_store_root.resolve()
        args.thunderbird_profile = args.thunderbird_profile.resolve()
        args.local_folder_path = Path(args.local_folder_path)
        if args.local_folder_path.is_absolute():
            parser.error("local_folder_path must be relative to the Thunderbird profile root")
    elif args.command == "scan-mbox":
        args.export_root = args.export_root.resolve()
        if args.report is not None:
            args.report = args.report.resolve()
    elif args.command == "scan-store":
        args.mail_store_root = args.mail_store_root.resolve()
        if args.report is not None:
            args.report = args.report.resolve()
    else:  # pragma: no cover
        parser.error("Unsupported command")

    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    handler: Handler = args.handler
    return handler(args)


def _handle_list_mbox(args: argparse.Namespace) -> int:
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


def _handle_list_store(args: argparse.Namespace) -> int:
    store_root: Path = args.store_root
    summaries = mail_store.summarize_mail_store(store_root)
    if not summaries:
        print(f"No mailboxes found in {store_root}")
        return 0

    name_width = max(len(summary.display_path) for summary in summaries)
    print(f"Mailboxes discovered in {store_root}:")
    header = f"  {'Name'.ljust(name_width)}  {'Messages':>8}  {'Partial':>8}"
    print(header)
    print("  " + "-" * (len(header) - 2))
    for summary in summaries:
        if summary.segments:
            name_parts = []
            total_parts = len(summary.segments)
            for index, segment in enumerate(summary.segments):
                piece = segment.value
                if index < total_parts - 1:
                    piece = f"{piece}/"
                if segment.is_directory:
                    piece = f"\033[2m{piece}\033[22m"
                name_parts.append(piece)
            name_display = "".join(name_parts)
        else:  # pragma: no cover - defensive, segments always populated
            name_display = summary.display_path

        padding = " " * (name_width - len(summary.display_path))
        print(
            f"  {name_display}{padding}  {summary.stored_messages:8d}  {summary.partial_messages:8d}"
        )
    return 0


def _handle_migrate_mbox(args: argparse.Namespace) -> int:
    stats = migration.migrate_mbox_export(
        export_root=args.export_root,
        profile_root=args.thunderbird_profile,
        local_folder_path=args.local_folder_path,
        prefix=args.prefix,
        mail_store_root=args.mail_store_root,
        dry_run=args.dry_run,
        show_progress=not args.no_progress,
    )

    outcome = "Dry run" if stats.dry_run else "Migration"
    print(
        f"{outcome} complete: {stats.migrated_messages} messages across "
        f"{stats.migrated_mailboxes} mailboxes."
    )
    if stats.unresolved_partials:
        print(f"  Skipped {stats.unresolved_partials} partial messages.")
    if stats.recovered_missing:
        print(
            "  Recovered "
            f"{stats.recovered_missing} message{'s' if stats.recovered_missing != 1 else ''} "
            "from the mail store."
        )
    if stats.skipped_by_prefix:
        print(f"  {stats.skipped_by_prefix} mailboxes excluded by prefix filter.")
    return 0


def _handle_migrate_store(args: argparse.Namespace) -> int:
    stats = migration.migrate_mail_store(
        store_root=args.mail_store_root,
        profile_root=args.thunderbird_profile,
        local_folder_path=args.local_folder_path,
        prefix=args.prefix,
        dry_run=args.dry_run,
        show_progress=not args.no_progress,
    )

    outcome = "Dry run" if stats.dry_run else "Migration"
    print(
        f"{outcome} complete: {stats.migrated_messages} messages across "
        f"{stats.migrated_mailboxes} mailboxes."
    )
    if stats.recovered_partials:
        print(f"  Recovered {stats.recovered_partials} partial messages.")
    if stats.unresolved_partials:
        print(f"  Skipped {stats.unresolved_partials} partial messages.")
    if stats.skipped_by_prefix:
        print(f"  {stats.skipped_by_prefix} mailboxes excluded by prefix filter.")
    return 0


def _handle_scan_mbox(args: argparse.Namespace) -> int:
    report = apple_mbox_scan.scan_export(
        args.export_root,
        show_progress=not args.no_progress,
        prefix=args.prefix,
    )

    print(
        "Scan complete: "
        f"{report.total_full_messages} full messages, "
        f"{report.total_partial_messages} partial messages, "
        f"{report.total_missing_messages} missing from index."
    )
    if report.mismatched_mailboxes:
        name_width = max(len(mismatch.display_path) for mismatch in report.mismatched_mailboxes)
        print("Mailboxes with discrepancies:")
        header = (
            f"  {'Name'.ljust(name_width)}  {'Full':>6}  {'Indexed':>7}  "
            f"{'Partial':>7}  {'Missing':>7}"
        )
        print(header)
        print("  " + "-" * (len(header) - 2))
        for mismatch in report.mismatched_mailboxes:
            name = mismatch.display_path.ljust(name_width)
            print(
                f"  {name}  {mismatch.full_messages:6d}  {mismatch.indexed_messages:7d}  "
                f"{mismatch.partial_messages:7d}  {mismatch.missing_messages:7d}"
            )
    else:
        print("No discrepancies detected between stored and indexed messages.")

    if args.report is not None:
        apple_mbox_scan.write_report(args.report, report, args.export_root)
        print(f"Report written to {args.report}")

    return 0


def _handle_scan_store(args: argparse.Namespace) -> int:
    report = mail_store_scan.scan_mail_store(
        args.mail_store_root,
        show_progress=not args.no_progress,
        prefix=args.prefix,
    )

    print(
        "Scan complete: "
        f"{report.total_full_messages} full messages, "
        f"{report.total_partial_messages} partial messages."
    )
    print(
        f"Resolved partials: {report.resolved_partials}; "
        f"Unresolved: {report.unresolved_partials}."
    )
    if report.duplicate_keys:
        print(
            f"Duplicate keys: {report.duplicate_keys} "
            f"({report.duplicate_messages} additional copies)."
        )
    if report.mismatched_size_keys:
        print(f"Warning: {report.mismatched_size_keys} duplicate keys have differing sizes.")

    if args.report is not None:
        mail_store_scan.write_report(args.report, report, args.mail_store_root)
        print(f"Report written to {args.report}")

    return 0


if __name__ == "__main__":  # pragma: no cover - manual execution entry point
    raise SystemExit(main())
