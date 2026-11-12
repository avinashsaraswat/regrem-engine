# Measuring whether it saved time

This page is for whoever at the financial institution will be asked whether RegRem Engine saved the team time. Nobody can answer that yet, because nobody has timed the tool and every case in this repository is invented.

## Time one finding by hand first

Choose a finding the team is closing without the tool and keep a record of what it costs. Book its hours under the four headings `size` prints for the hand side, which are checking claims, status reports, finding signed files and rework. Count days from the letter date to the day internal audit receives the memo. Keep a line for each item internal audit sends back, with who spotted it, and one for each error found after the package went out. This is the only side of the comparison nobody assumed, and any saving claimed later is a difference from it.

## What finding size prints

The `size` command reads one finding folder, or a folder holding several, and writes nothing into either. On Windows it starts `py -I finding\finding.py` instead.

```sh
python3 -I finding/finding.py size finding/cases/MRA-CMP-07
```

For each finding it counts milestones, evidence files, claims on the memo check, rows to rule on and months from the letter to the last committed date. It then turns those counts into hours by hand and with the kit, both marked assumed. By hand, every claim is checked on each of three memo versions. With the kit, someone still reads every claim against its cited page once, rules on each row and types any page the reader cannot read. Both sides count one rework round.

The closing line lists every minute and hour behind those sums. With the shipped values the kit side comes out near half the hand side on both invented cases. That ratio follows from minutes someone chose, so it says nothing about your institution. The rework round is the largest single part, 8.0 of the 11.5 kit hours on IA-CMP-02, which makes rework the first thing to time.

## Replace the assumptions with timed figures

Write each timed figure in a file named `size-assumptions.txt`, one a line, in the words the closing line uses. These five values are invented for this page:

```text
minutes a claim by hand: 14
hours a status report: 1.5
hours a rework round: 5
minutes to read a claim: 6
minutes a ruling: 20
```

The file can sit beside one finding, one folder up, or inside a folder of findings sized together, and a finding's own file wins. A value it leaves out keeps the shipped figure, and a line the tool cannot read stops the run and lists the eleven names it accepts. The file is outside the fingerprint, so adding it leaves a signed folder signed. With those lines beside a copy of MRA-CMP-07, the hours read:

```text
  By hand, assumed: 26.1 hours. Checking claims 9.1, status reports 9.0, finding signed files 3.0, one rework round 5.0.
  With the kit, assumed: 10.1 hours. Reading each claim against its page 1.3, cover lines 1.0, rulings 1.3, status reports 1.5, rework 5.0.
```

The labels still say assumed, and the closing line says that 5 values came from the file. In a folder run, a finding that is not yet ready to size is named and kept out of the totals.

## Book the hours the kit side takes

Every folder the `new` command makes holds `closure/measures.md`. Hours go in one line a month. Each item internal audit returns gets a line too, with `missed by the check` at the end when the check had let it through:

```text
Hours | 2026-10 | 31
Hours | 2026-11 | 6.5
Sent back | 2026-11-03 | Line 12 | asked for the signed register
Sent back | 2026-11-03 | Line 6 | a figure swapped with another on its page | missed by the check
Sent back | 2026-11-09 | Line 14 | a date two documents give differently | missed by the check
```

On a copy of MRA-CMP-07, first checked on 2026-02-10 and checked as of 2026-11-11, the check page then printed:

```text
Measures: 37.5 hours booked, 274 days since the first check, 3 sent back by internal audit, 2 missed by the check.
```

No signature covers this file. Its totals are the kit side of the comparison.

## Write the stop rule before the first live finding

Agree in writing who decides whether the team keeps the tool and what sends it back to the hand method. Name one person at the institution and a date for the comparison, such as ten business days after the first signature. Typical results that end the trial are reviewers checking for as long as the hand record took, or internal audit returning more items than on the hand finding. A miss found after the package left that the check had passed ends it too. If one happens, the team goes back to working by hand and writes down why.

## The honest baseline

The only test beyond the shipped cases used a larger invented finding, 61 files and 173 pages long, held outside this repository. In the first of three trial runs on it, the check working alone found 1 of the 13 planted traps. An AI agent acting as reviewer found all 11 traps that run tested, and the remaining 2 went untested. The same agent had drafted the memo it then reviewed. AI agents ran all three trials, no institution has used the tool, and nobody timed any of it.

So the time baseline is your team's hand record, because the tool has none yet. For catch rate, the `eval` command plants errors in a memo one at a time and lists each miss by line. Treat the check as a floor under a person's reading of each sentence against its cited page.
