# Deviations from the run plan

Each entry is dated and says what happened, what it touches and what was done about it.

## 2026-11-13 10:30 ET: the tooling session saw the builder's pressure test

The session that wrote the agent loop, prompts, procedure and scorer read the sealed builder session's transcript to report its status. The transcript's last entry was the builder's own adversarial test of the trap set, so that session saw trap descriptions from a version of the case the builder had not yet fixed. It did not open `sealed/`.

What it touches: the plan says the tooling session never sees the key. The owner, who rules blind, has seen nothing.

What was done: the prompts, procedure and scorer were hashed in PRESEAL.txt before the case build began, and all 12 hashes were checked and still match. The tooling session makes no further change to any agent-facing file. Any tool change after the dry run is listed in SEAL.txt as PRESEAL requires.

Remedy, agreed the same morning: the builder moves every trap to a new place and value while applying its pressure-test fixes, so the descriptions the tooling session saw no longer describe the sealed case. The tooling session does not read the builder's transcript again; it asks for status by message, and the builder answers with hashes, pass or fail and counts only.

## 2026-11-14, PROTOCOL.md changed beyond its braces before the seal

PRESEAL.txt says PROTOCOL.md changes only where a name in braces is filled in. Before the seal it also changed in four places, each on the owner's ruling or to keep a ruling: (1) five memo runs in place of ten (steps 15, the count lines, the folder list and limit 1), set by the owner after the dry run on MRA-CMP-07 cost $1.01 for one memo job and one cross-read, with one sentence saying so in the spend line; (2) the model id is named only in manifest.json, so the two places that held {MODEL_ID} now point to it, under the owner's ruling of 2026-11-14 that the content scan exempts that one line; (3) the generator row says how its one hash is formed; (4) the employer-disclosure line points to the README's line without quoting it, for the same scan. The prompts, the procedure, the scorer, the schema, the loop and the gate are unchanged against PRESEAL.txt, and the sealed builder confirmed on 2026-11-14 that every sealed file still matches its hashes.

## 2026-11-14 13:55 ET: the sealed run record still says ten memo runs

Found while checking the seal before intake. The Run record table at the foot of PROTOCOL.md, as sealed in 4039e60, gives "Memo runs | 10". The four changes listed in the entry above set five memo runs in step 15, the count lines, the folder list and limit 1, and manifest.json sets memo_repeats to 4. The table row was missed. PROTOCOL.md cannot change after the seal, so it stays as pushed.

What it touches: nothing the loop reads. Step 15 says the memo runs are "as manifest.json fixes", and the manifest's hash is in SEAL.txt.

What was done: the run follows the manifest, five memo runs in all, and RESULTS.md names the stale row.

## 2026-11-14 15:13 ET: run 01 stopped at step 7 by the owner

The plan job ran once, from 14:44 to 14:48 EST. It ended at the manifest's limit of 60 turns after 60 tool calls and wrote nothing. The ledger shows $1.626723 of the $20 cap, with cached prompt tokens charged at the full input price. The gate found 0 paths changed, and the check page reads "Not ready: plan.md has no milestone rows yet." The loop refused one read, a listing of kit/finding.

The limit of 60 turns is the loop's default, and the manifest kept it. The dry run tested the memo and cross-read jobs on a case of six Markdown files and never ran the plan or covers job. Nobody knows that more turns would have produced a plan. By turn 41 the drafter had opened each of the 22 evidence files at least once. It spent the next 19 turns on kit pages the plan does not need, second looks at evidence and a shipped case, without a write.

What it touches: the first claim, that an agent drafts the plan. On the sealed settings it did not. No void condition occurred. Every seal hash matched, and no read outside the seat got through.

What was done: the owner stopped run 01 with one of its two sittings for steps 6 to 13 unused. The job was not rerun, and the owner wrote no plan row. The owner has read none of the case, none of the transcript's tool results and nothing in key/ or build/. Run 01 is published as stopped before anything else is sealed. SHA-256 of run-01/plan/transcript.jsonl: b9b2c19a63c3b9c834cf41fb680610d75c7a7e976f319198e2fd8ff1ed4294c9. The transcript holds case text, so it is published with the case.

What follows: a pilot of the plan and covers jobs on the shipped case MRA-CMP-07, with its plan rows and cover lines blanked. It runs under the settings run 02 would use and is published as run 02's second dry run. If the pilot's plan job ends with status done, one more run on the same unopened case, run 02, follows under its own seal. It differs from run 01 only in three manifest.json values (run, max_turns_per_job and cap_usd) and in the protocol lines its own PROTOCOL.md lists. Those settings were chosen after this failure, knowing how the drafter behaved on the sealed case. If the pilot's plan job does not finish, run 01 is the final result. There is no run 03 on this case, and the case and key are published after run 02 however it ends.
