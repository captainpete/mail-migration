# mail-migration

This repo is a snapshot of a once-off migration I ran to rescue a very large and partially broken Apple Mail archive and move it into Thunderbird. The code exists here so future travellers (or their AI copilots) can see what worked for me without having to rediscover every corner case from scratch. It is **not** a supported or actively maintained project.

## What it does
- Reads both the live Apple Mail store (`~/Library/Mail/V10`) and exported `.mbox` bundles.
- Migrates those messages into Thunderbird local folders, trying hard to preserve payloads, dates, and known Apple Mail status flags when the source data makes that possible.
- Scans exports for gaps between the on-disk payloads and the `table_of_contents` index so you can decide whether a re-export is needed.

Along the way it recovers many “partial” `.emlx` files by stitching them back together from the live store, and it prints progress so you know which mailboxes still need attention.

## What it does **not** do
- **No deduplication.** Thunderbird (or another downstream tool) needs to clean up any duplicates produced by multiple migration passes.
- **No guarantees on metadata.** Exported `.mbox` bundles lose read/reply status, so Thunderbird will treat those imports as unread. Other Apple Mail metadata may also be missing depending on the source.
- **No polishing for re-use.** Error handling and reporting were scoped to the data I had; your mailbox tree may expose edge cases I never saw.

## Why the code lives here
- I wanted a record of what finally worked after weeks of trial-and-error with half-downloaded mailboxes.
- Sharing it publicly adds another data point for anyone who needs to recover similar archives in the future.
- AI tooling was a big help during the build, and I’m hoping it can use this repository as a shortcut next time.

## Maintenance status
This repository is archived in spirit: I don’t plan to evolve the code or provide support. Feel free to fork, adapt, or tear it apart for your own migrations, but expect to own whatever changes you need.
