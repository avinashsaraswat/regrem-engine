# Running a finding week to week

This page is for the preparer who keeps a live finding's folder, the reviewer who reads its memo and the owner who rules and signs. It follows the invented case MRA-CMP-07 through the week of Monday 2026-11-16, with a board pack due on Thursday 2026-11-19.

Commands run from the kit root. On Windows, `py -I finding\finding.py` replaces `finding/finding` and File Explorer does the copies. The examples pass `--today` so your screen matches, and a live folder leaves it off so the check uses the machine's date. To follow along, copy the case outside the kit:

```sh
mkdir -p ../findings
cp -R finding/cases/MRA-CMP-07 ../findings/MRA-CMP-07
mkdir ../findings/MRA-CMP-07/closure/pages
```

## Monday: check, and keep the page

The preparer confirms the release, then saves the check's page under the day's date:

```sh
finding/finding --version
finding/finding check ../findings/MRA-CMP-07 --today 2026-11-16 > ../findings/MRA-CMP-07/closure/pages/2026-11-16.txt
```

The first command should end `Every file matches this release.` A page saved in closure/pages/ changes neither later pages nor the folder's fingerprint. The check exits 1 while anything waits on a person.

The page's last block, Needs a person, sorts the open work by role for the status call. This Monday it gives M2 and three list rows to the Head of Complaints, M3 to the Complaints QA lead and M4 to the Head of Digital. On the list sit a figure typed as 1,248 where page 2 of EV-07 says 1,284, a draft quality review, and a sample that starts before its fix.

## Tuesday: the owner rules

A ruling line gives the memo line, the text the row prints after "To rule, name:", one of `cleared`, `fix the memo` or `fix the evidence`, the owner role, a date and a reason:

```text
Line 8 | 1,248 #972adb19 | fix the memo | Head of Complaints | 2026-11-17 | The page says 1,284.
Line 16 | sample period for M2 #106ddd50 | cleared | Head of Complaints | 2026-11-17 | The owner drew this sample across the fix date to compare error rates.
```

The owner, or the preparer on the owner's word, appends these to closure/rulings.md. A ruling dated after the check that reads it counts for nothing. Only `cleared` takes a row off the list, and the check accepts it on any row that prints a name. So the owner never clears a wrong figure, which the memo has to fix. Clearing the draft row would leave M3 unsigned, so it waits for the QA lead's signature. An AI assistant may draft proposals into closure/proposed-rulings.md, a file the check ignores.

## Wednesday: fixes land

The preparer edits line 8 of closure/memo.md to read 1,284. That changes the sentence, so the March 2026 row on that line returns under a new mark, `March 2026 #ffa37a3f`, and the page says `Ruling at rulings.md line 4 names no row` about the old ruling. While a sentence and its cite stay the same, a ruling follows its claim to any line, so the owner need not wait for the memo to settle. This sentence changed, so the owner rules on the new mark:

```text
Line 8 | March 2026 #ffa37a3f | cleared | Head of Complaints | 2026-11-18 | Page 2 gives the period as January to March, in plan year 2026.
```

Someone who has seen the QA lead's signature changes the EV-12 cover to `Signed by: Complaints QA lead, 2026-11-18` and `Status: FINAL`. An assistant never types either line. After any real change to the memo, run the eval:

```sh
finding/finding eval ../findings/MRA-CMP-07
```

It plants errors in memory and lists each one the check let through. This week it caught 26 of 31, and one miss reads `Line 10: 31 changed to 240 still ties.` The reviewer starts from that list.

## Thursday: the board cutoff

The preparer checks again, saves the page and compares it with Monday's. On Windows, `fc` compares two files.

```sh
finding/finding check ../findings/MRA-CMP-07 --today 2026-11-19 > ../findings/MRA-CMP-07/closure/pages/2026-11-19.txt
diff ../findings/MRA-CMP-07/closure/pages/2026-11-16.txt ../findings/MRA-CMP-07/closure/pages/2026-11-19.txt
```

The list is now empty, and the board summary reports the late signature on M3:

```text
Flagged commitments: M2 slipped 249 days, M3 signed 202 days after its commitment, M4 slipped 142 days.
Memo check: 13 claims, 12 tie, 0 on the list, 2 cleared.
```

Anything still under Needs a person at the cutoff goes to the role it names. The board summary is a draft, and the finding owner decides what reaches the pack.

## Friday: measures

The preparer records this week's booked hours in closure/measures.md, plus one line per item internal audit returned. The next page counts both on its Measures line.

```text
Hours | 2026-11 | 6.5
Sent back | 2026-11-20 | Line 10 | the memo still called the review a draft | missed by the check
```

## How a slipped milestone shows

Below signed, a milestone reads AT RISK in the 14 days before its committed date and SLIPPED after it, with a day count. Signed board minutes freeze the committed dates. Move M4 to 2026-12-31 in plan.md and the page still counts from the approved date, and asks the board to approve the change:

```text
committed 2026-06-30, moved to 2026-12-31 in plan.md after the board approved the plan. Not started. SLIPPED by 142 days.
```

Once the minutes are signed again with a later date, the new date counts. The board summary keeps a note that M4 moved after 2026-06-30 had passed, so re-dating never hides a slip.

## Who acts on what

- The preparer runs the check on Monday and Thursday, runs `finding/finding covers` the day a file arrives, fixes memo rows, types accepted rulings and keeps measures.md.
- Each milestone owner named under Needs a person gets the file signed, or signed again after a revision.
- The finding owner rules on every row, decides what goes to the board and signs last.
- The reviewer is someone who wrote no part of the memo. Before the pack, they compare every sentence with its cited page, then read every Cleared line, the eval's misses, the `Not checked:` lines and any typed page.

## Limits

With the list empty, every claim the check reads sits on its cited page or carries the owner's ruling. The check holds no AI model, so one folder checked as of one date gives the same page on every run. It reads each claim against its own cite only. Two documents can disagree and both pass, and a wrong figure that also appears on the cited page ties. On this Thursday, memo line 10 still said the review "is still a draft and carries no signature", and the page raised nothing. The check does not judge whether the fix works. Internal audit tests that, and only the issuer closes the finding. Every case here is invented, and the tool has never run on a real finding.
