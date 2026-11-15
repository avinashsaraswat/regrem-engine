# Results table

Scored by `tools/score.py` with the match rule in `tools/SCHEMA.md`. No model call.
Case: MRA-PAM-05. Traps: 12 (9 listed, 3 unlisted). Decoys: 3. Traps whose claim the memo cites: 12 of 12.

## Inputs

| Input | File | SHA-256 |
|---|---|---|
| traps | key/traps.json | 4e287ea5d1f12e48befdc95e7a97e4ae5d032435cd1bbb9813722011355ea8cb |
| memo | results/floor/floor-memo.md | 2dfa156d435c5888838e83a0f22af8b2fff5a690a2d8e03cc264c0094f13dd8c |
| floor | key/floor.tsv | 87e567f11a4b0c4760c48a0aa53042cf466b96b01f44e7f285ce2d2c089f58d0 |
| rulings | run-01/trap-rulings.tsv | a6d9cacfc4f9e3dbb0522deed851f1650e2d68f312c975b67ca9db0d54068eee |

## Each trap

yes: at least one finding in that layer matches the trap. -: no file was given for that layer. Tried: the memo cites a page listed for the trap's claim. Check by design is the floor file, the check's rows on a memo that carries every trap as fact, so it has no tried count. Any is the check, the cross-reader or the owner.

| Trap | Kind | List | Tried | Check by design |
|---|---|---|---|---|
| T01 | figure carried from another document with two digits transposed | listed | yes | yes |
| T02 | date carried from another document a month off | listed | yes | yes |
| T03 | quotation reworded in another document, changing the rule | listed | yes | yes |
| T04 | figure carried from another document with one digit changed | listed | yes | yes |
| T05 | two dates on one page swapped, seeded by a status report | listed | yes | no |
| T06 | two documents disagree on the date of an approval | listed | yes | no |
| T07 | a later version in force than the version the institution approved | listed | yes | no |
| T08 | work done before the training meant to precede it | listed | yes | no |
| T09 | a status report claiming more than its evidence supports | listed | yes | no |
| T10 | evidence taken from a test environment, offered as live operation | unlisted | yes | no |
| T11 | an exception relied on after it lapsed | unlisted | yes | no |
| T12 | a measure that counts something narrower than the rule it reports on | unlisted | yes | no |

## Counts

Each count is out of the total in its column heading.

| Layer | Traps caught, of 12 | Listed caught, of 9 | Unlisted caught, of 3 | Tried caught, of 12 | Decoys flagged, of 3 | Findings | Matching no trap | Lines not read |
|---|---|---|---|---|---|---|---|---|
| Check by design | 4 | 4 | 0 | - | 0 | 5 | 0 | 0 |

## Untried traps

Untried: 0 of 12. The memo cites a listed page for every trap's claim.

## Decoys flagged

A decoy looks wrong and is fine, so a finding that matches one is a false alarm.

| Decoy | Kind | Check by design |
|---|---|---|
| D01 | an early estimate that looks to disagree with the later count | no |
| D02 | an exception that looks lapsed but covered the whole review | no |
| D03 | a running total that looks short of the status report's figure but stops at an earlier date | no |

## Scripted matches

Each finding the script matched to a trap or a decoy, for the owner to rule.

| Entry | Layer | Finding | Memo line | Cite | Value seen | Problem |
|---|---|---|---|---|---|---|
| T01 | Check by design | key/floor.tsv:4 | 7 | EV-05 p3 | 348 | 348 is cited to EV-05 p3, and the page does not hold it; the nearest figures on the page are 371, 380 and 384. |
| T02 | Check by design | key/floor.tsv:5 | 18 | EV-11 p2 | 2026-03-02 | 2026-03-02 is cited to EV-11 p2, and the page does not hold it; the dates on the page are 2026-03-31 and 2026-04-02. |
| T03 | Check by design | key/floor.tsv:2 | 4 | EV-01 p6 | "every orphaned account is removed or given a named owner within 90 days" | "every orphaned account is removed or given a named owner within 90 days" is cited to EV-01 p6, and the page does not hold "every orphaned account is removed or given a named owner within 90 days". |
| T03 | Check by design | key/floor.tsv:3 | 4 | EV-01 p6 | 90 | 90 is cited to EV-01 p6, and the page does not hold it; the nearest figures on the page are 120, 8 and 6.3. |
| T04 | Check by design | key/floor.tsv:6 | 23 | EV-17 p1 | 54 | 54 is cited to EV-17 p1, and the page does not hold it; the nearest figures on the page are 64 and 90. |

## Findings that match no trap

No trap or decoy matches these by the match rule. The owner rules each one from the first run.

None.

## Lines not read

A line of a layer's file that is not in the findings form. It matches nothing and is counted here.

None.

## After the owner's rulings

Traps ruled real: 8 of 12. Ruled trivial: 4 of 12. Ruled wrong: 0 of 12. Not ruled: 0 of 12.
A scripted match the owner ruled no is dropped. A finding that matched no trap and that the owner ruled a match is added. A scripted match with no ruling stands.

| Layer | Traps caught, of 12 | Caught among traps ruled real, of 8 | Decoys flagged, of 3 | Scripted matches ruled no | Unmatched ruled a match | Unmatched ruled a real problem | Unmatched ruled a false alarm | Unmatched not ruled |
|---|---|---|---|---|---|---|---|---|
| Check by design | 4 | 1 | 0 | 0 | 0 | 0 | 0 | 0 |

| Trap | Ruling | Check by design |
|---|---|---|
| T01 | trivial | yes |
| T02 | trivial | yes |
| T03 | real | yes |
| T04 | trivial | yes |
| T05 | real | no |
| T06 | trivial | no |
| T07 | real | no |
| T08 | real | no |
| T09 | real | no |
| T10 | real | no |
| T11 | real | no |
| T12 | real | no |
