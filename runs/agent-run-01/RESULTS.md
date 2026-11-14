# Agent run 01 stopped at step 7

Run 01 stopped before any memo existed, so it counts nothing and supports no claim about the check, the cross-reader or the owner. On the sealed settings, the drafter did not produce a plan.

## What happened

The seal went out on 2026-11-14 in commit 4039e60. Before intake, every hash in SEAL.txt for a pushed file matched its file, and the case archive matched its hash. Intake, step 6, made the finding folder from the kit at release 0.7.1 on 2026-11-14 at 13:52 EST.

Step 7, the plan job, ran once in the drafter seat from 14:44 to 14:48 EST, on the machine's date.

| Item | Value |
|---|---|
| How it ended | at the manifest's limit of 60 turns |
| Turns and tool calls | 60 and 60, one call a turn |
| Writes | none; the gate found 0 paths changed |
| Reads the loop refused | 1, a listing of kit/finding |
| Writes the gate stopped | 0 |
| Final check page | "Not ready: plan.md has no milestone rows yet." |
| Spend on the ledger | $1.626723 of the $20 cap |
| Time | 262 seconds |

The ledger charges cached prompt tokens at the full input price, so it overstates the bill. About 92 percent of the job's prompt tokens were reported as cached.

By turn 41 the drafter had opened each of the case's 22 evidence files at least once, most of them a page per call. It spent the next 19 turns on kit pages the plan does not need, second looks at evidence and a shipped case, and wrote nothing. The limit of 60 turns was the loop's default. The dry run tried the memo and cross-read jobs on a six-file case, and never the plan or covers job.

## Why it stopped there

The owner stopped the run at 15:13 EST, with one of the two sittings for steps 6 to 13 unused. No void condition occurred. A rerun under the same settings could repeat the same path, and the covers job alone needs more than 60 calls to write 22 covers. DEVIATIONS.md gives the full entry.

## What is published now and later

Published now: this page, DEVIATIONS.md, run-01/RUN-LOG.md and the final check page, run-01/plan/check-final.txt.

The plan job's transcript, its summary and the spend ledger hold case text, so they are published after run 02 with the case, the key, the generator and the dry run. The transcript's SHA-256 is b9b2c19a63c3b9c834cf41fb680610d75c7a7e976f319198e2fd8ff1ed4294c9.

## What follows

A pilot of the plan and covers jobs runs first, on the shipped case MRA-CMP-07 with its plan rows and cover lines blanked, under the settings run 02 would use. If the pilot's plan job finishes, run 02 follows on the same unopened case under its own seal. It changes the turn limit and the spend cap, and those settings were chosen after this failure. If the pilot's plan job does not finish, this page is the final result. There is no run 03 on this case.

The owner's employer disclosure is the one-line disclosure in the kit's README.md.
