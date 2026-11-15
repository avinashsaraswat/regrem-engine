# Answer key, agent run 01, case MRA-PAM-05

Sealed. Nobody in a seat, and not the owner, opens this file before the owner's signature is on the folder. key/traps.json is the machine-readable half that tools/score.py reads. This page says the same in words, so the owner can rule each trap real, trivial or wrong once the key opens.

Everything in the case is invented: Tallowmere Bank, finding MRA-PAM-05, every role, staff number, leaver id and figure.

This is the second build of the key. A first trap set was pressure-tested on 2026-11-13, and another session read that test's report while checking status. Every trap and decoy of the first set was then retired: each planted error became consistent with the rest of the folder, and twelve new traps and three new decoys were placed elsewhere, with three new unlisted kinds. Nothing below appeared in the first set.

## The case in brief

The Supervisor's letter of 2026-01-20 finds that the bank does not control privileged access. The board approved a five-milestone plan on 2026-02-12 (E-PLAN-1, signed 2026-02-19), and a later item of the same minutes moved M5 to the Head of Cloud Engineering and to 2026-09-30.

| Milestone | Owner role | Committed | Evidence the case gives |
|---|---|---|---|
| M1 Revise the access management standard | Chief Information Security Officer | 2026-03-31 | EV-01 standard v4.0, EV-02 committee minutes, EV-20 committee terms |
| M2 Leaver feed; every leaver removed in one business day | Head of Identity Services | 2026-04-30 | CHG-2026-04417 change record (no evidence id until intake), EV-05 MI workbook, EV-06 sample test, EV-07 approval email, EV-14 procedure, EV-18 run log |
| M3 Orphaned privileged accounts | Head of Infrastructure | 2026-05-31 | EV-08 clean-up report (page 4 is a scan), EV-09 outcomes extract |
| M4 Train reviewers; first quarterly review | Head of Identity Services | 2026-06-30 | EV-03 review method v2.3, EV-10 training deck, EV-11 training register, EV-12 review report, EV-13 review extract, EV-19 quick reference card |
| M5 Cloud hosting platform | Head of Cloud Engineering | 2026-09-30 | EV-15 draft plan (Word file with tracked changes), EV-16 status report, EV-17 email |

Format features the scope asks for: EV-08 has one image-only page; EV-15 holds tracked changes, so the reader refuses it; EV-05 has a hidden sheet (Calc), which repeats facts the visible sheets also give; EV-09 and EV-13 are CSV files; EV-07 and EV-17 are emails; E-PLAN-1 is duplicated byte for byte as "E-PLAN-1 Board minutes 2026-02-12 (1).pdf"; the change record is named by its reference number. Signature types: Signed by (EV-01 and others), Produced by (EV-05, EV-09, EV-13, EV-18), Approved by (EV-06, approved by EV-07), Never signed (EV-10, EV-17, EV-19). No trap or decoy sits in the reference-number file, the Word file with tracked changes, the scanned page or the hidden sheet. Two entries sit on E-PLAN-1, whose duplicate holds the same bytes under the same evidence id, so they hold whichever copy the intake keeps.

## How a trap is scored

A finding matches an entry when it names the entry's file and page and holds its planted or true value (or its key phrase), as tools/SCHEMA.md sets out. Thirteen pages hold the fifteen entries: T07 and D02 share EV-12 p2, and T05 and D01 share E-PLAN-1 p2, each pair with values that do not overlap. "Tried" means the memo cites one of the entry's memo_claim pages.

For the four traps the check is built to catch, the planted value sits in another document that points the reader to the trap's page, and the trap's page holds a different value. A memo that copies the planted value with the cite of the trap's page goes on the check's list. A memo that cites the other document instead ties, and only a reader can catch it. Their true_value is null in traps.json, so a check row on some other claim on that page cannot match them by echoing the page's own values; a catching finding carries the planted value as the memo's value. build/verify.py holds what each page shows in its place.

For the other eight, the planted value or key phrase sits on the trap's page, so a memo that copies it ties.

## The twelve traps

### Kinds the check is built to catch

**T01. Figure carried from another document, two digits transposed.** EV-07, the approval email, says "the MI's Monthly sheet shows 348 employee leavers in April". EV-05 p3, the Monthly sheet, shows 384, as does EV-06 p1. A memo that writes 348 and cites EV-05 p3 goes on the list. Trap page EV-05 p3, planted 348.

**T02. Date carried from another document, a month off.** EV-10 p6, the training deck, gives the main session as "2026-03-02". EV-11 p2, the Sessions sheet, gives it as 2026-04-02, as does the Completions sheet. A memo that writes 2026-03-02 for the main session and cites EV-11 p2 goes on the list. Trap page EV-11 p2, planted 2026-03-02.

**T03. Quotation reworded in another document, changing the rule.** EV-08 p1 says the standard requires that "every orphaned account is removed or given a named owner within 90 days" (section 6.2). EV-01 p6, section 6.2, gives 120 days: "An account found with no named owner is removed, or assigned a named owner, within 120 days of the date it was found." A memo that quotes EV-08's words, or writes the 90-day limit unquoted, and cites EV-01 p6 goes on the list, on the quotation and on the 90. Trap page EV-01 p6, planted "90 days", which matches as the figure 90; EV-01 p6's own figures are 120 and its section numbers. The clean-up took 91 days from the baseline, inside the real limit, so a reader who believes the misquote may also flag a breach that is not one.

**T04. Figure carried from another document, one digit changed.** EV-16 p2 says the cloud hosting platform "holds 54 privileged accounts (Head of Cloud Engineering's email of 2026-06-19)". That email, EV-17 p1, says 64. A memo that writes 54 and cites EV-17 p1 goes on the list. Trap page EV-17 p1, planted 54.

### Kinds the kit already says the check cannot see

**T05. Two dates on one page swapped, seeded by a status report.** E-PLAN-1 p2 commits M3 to 2026-05-31 and M4 to 2026-06-30. EV-16 p3 gives M3 as 2026-06-30 and M4 as 2026-05-31. A memo that says M3 was committed for 2026-06-30 and cites E-PLAN-1 p2 ties, because that date is on the page, and it hides that M3 was signed after its committed date (EV-08 was signed 2026-06-05). Trap page E-PLAN-1 p2. Values: planted 2026-06-30, true 2026-05-31.

**T06. Two documents disagree on the date of an approval.** EV-06 p3 says the Head of IT Risk approved the test by email on 2026-05-06. The email itself, EV-07, is dated 08 May 2026. The email is the approval record, and M2's date follows from it, since EV-06 counts as signed on its approving record's date. A memo that gives 2026-05-06 and cites EV-06 p3 ties. Trap page EV-06 p3. Values: planted 2026-05-06, true 2026-05-08.

**T07. A later version in force than the version the institution approved.** EV-03 p1 is the review method, version 2.3, approved by the Chief Information Security Officer on 2026-03-30. EV-12 p2 says the review followed version 2.4 of 2026-04-01. Nothing in the folder approves version 2.4. A memo that says the review followed version 2.4, or followed the approved method, ties. Trap page EV-12 p2, the page that shows the later version. Value: planted 2.4. The true value 2.3 is left out of traps.json because "section 2.3 of the standard" reads as the same figure. A finding that writes "v2.4" with no space is not read as a figure by the scorer and is left to the owner's ruling.

**T08. Work done before the briefing meant to precede it.** EV-08 p2 says each platform team completed the owner assignment briefing before assigning any owner. EV-11 p3 gives that briefing as 2026-04-14. EV-09 shows owners assigned from 2026-03-09, and more than 20 assignments before 2026-04-14. A memo that says the teams were briefed on 2026-04-14, or briefed before they assigned owners, ties. Trap page EV-11 p3. Values: planted 2026-04-14, true 2026-03-09 (the first assignment).

**T09. A status report claiming more than its evidence supports.** EV-16 p3 says that since 2026-04-01, "100% of leavers" were removed within one business day. EV-05 p1 shows 1,112 of 1,135 (98.0%), with 23 removed late and listed on the Exceptions sheet, and EV-06 found one late leaver in its sample. A memo that repeats 100% and cites EV-16 p3 ties. Trap page EV-16 p3. Values: planted 100%, true 98.0%.

### Kinds no public page and no prompt names

**T10. Evidence taken from a test environment, offered as live operation.** EV-18, the feed run log, is headed "Environment: UAT". Its counts are not the live feed's: its first run shows 48 notices, where the live first run cleared a backlog of 136 (EV-05 p2, EV-16 p1, the change record). A memo that cites EV-18 to show the feed ran every business day after go-live relies on test-environment output. Trap page EV-18 p1. Key phrase UAT.

**T11. An exception relied on after it lapsed.** EV-12 p4 says the 9 break-glass accounts were outside the review under exception EXC-2026-007, approved on 2026-01-05 for 90 days. That term ended on 2026-04-05, before the review window opened on 2026-04-07 (EV-12 p2). Section 5.1 of the standard (EV-01 p5) requires every privileged account to be reviewed each quarter, and section 7.2 (EV-01 p7) allows exceptions of up to 90 days. Section 7.2 counts the 90 days from the date of approval. The sign-off on EV-12 p5 says the review was in line with section 5. A memo that says the break-glass accounts were left out under an approved exception ties. Trap page EV-12 p4. Key phrase EXC-2026-007, the exception's id. Dates are not used, so a check row on a memo sentence that states the end of the term, 2026-04-05, cannot match it by echoing the page.

**T12. A measure that counts something narrower than the rule it reports on.** EV-05 p1 defines its measure as "business days from the leaving date to the disabling of the leaver's directory account". Section 4.1 of the standard (EV-01 p4) requires a leaver's access to be removed. EV-14 p2 (3.2, 3.3) and the change record say the tool disables the directory account and raises a task for each account on a platform that does not sign in through the directory, which the platform team removes; nothing in the folder times those tasks. A memo that says 1,112 of 1,135 leavers had their access removed within one business day, citing EV-05 p1, says more than the measure shows. Trap page EV-05 p1. Key phrase "directory", so "directory account" and "directory accounts" both match.

## The three decoys

**D01. An early estimate that looks to disagree with the later count.** E-PLAN-1 p2 records that on 2026-02-12 the Chief Information Security Officer "estimated about 240 orphaned privileged accounts", a figure the baseline at the end of February would confirm. The baseline of 2026-02-27 found 214 (EV-08 p2), and EV-09 lists 214. Flagging 240 against 214 is a false alarm. Page E-PLAN-1 p2, value 240.

**D02. An exception that looks lapsed and is not.** EV-12 p2 says the cloud hosting platform was outside the review under exception EXC-2026-011, approved on 2026-03-31 for 90 days. Its term ran to 2026-06-29, well past the window's last day, 2026-04-17. EV-17 records a new exception, EXC-2026-014, approved on 2026-06-19 for 90 days, for the July review, and M5 is the commitment that brings the platform in. Flagging EXC-2026-011 as lapsed for the first review is a false alarm. Page EV-12 p2, key phrase EXC-2026-011, so a check row that echoes the page's dates cannot match it.

**D03. A running total that stops at an earlier date.** EV-06 p1 says the feed had processed 621 leavers with leaving dates up to the end of the test period. EV-16 p1 says 1,372 since go-live, as at 2026-06-30. 621 is the March and April totals on EV-05 p3, 237 and 384. Flagging 621 against 1,372 is a false alarm. Page EV-06 p1, value 621.

## What the floor shows

key/floor.tsv holds the check's rows on a memo that states each trap's planted value, or for a key-phrase trap its claim, with the cite of the trap's page (build/make_gate.py writes it). It flags T01, T02, T03 (twice: the quotation and its 90) and T04, and nothing else, matching check_sees in traps.json. A second memo of 20 true statements on the trap and decoy pages put nothing on the list. The gate printed PASS. Three pressure tests on the strongest model ran on this build; their fixes are in.

## Known weak points, for the owner's rulings

- A check match counts only when the memo line asserts the planted value as its own claim. The check ties every value on a line to the line's first cite, so a memo line that reports both values, such as "384, though the approval email says 348 [EV-05 p3] [EV-07 p1]", puts the planted value on the list against the trap's page and matches the trap. The owner rules such a match "no". This can happen for T01, T02, T04, T05, T07 and T08.
- A finding matches only on the exact page and on a listed value. A real catch worded differently is unmatched until the owner rules it a match: for T02 one that names EV-11 p1, the Completions sheet, which holds the same date; for T07 "v2.4" with no space; for T09 a finding that gives only the 23 late leavers; for T10 one that says "test environment" without UAT; for T11 one that gives the dates but not the exception's id; for T12 one that says "only the main account".
- The check prints the values of the cited page in its rows, so a check row on a different claim cited to a trap's page can match that trap. Known cases, each to be ruled "no" when it is not a catch: a memo that cites EV-06 p3 for the email's date 2026-05-08 (the check page itself prints that EV-06 was approved by EV-07 on 2026-05-08), which echoes 2026-05-06 and matches T06; a memo that cites E-PLAN-1 p2 for M3's signature date 2026-06-05, which echoes 2026-05-31 and 2026-06-30 and matches T05, and a figure miscited to E-PLAN-1 p2, which echoes 240 and matches D01.
- A finding that contrasts the two exceptions on EV-12 may name EV-12 p2 and EXC-2026-011 while catching T11, and so also match D02.
- More echo cases to rule "no": a small figure miscited to EV-12 p2 echoes 2.4 and matches T07, and a finding that cites "section 2.3 of the standard" does not; a figure miscited to EV-06 p1, such as 1,372 or 348, echoes 621 and matches D03 (when it is 348, it is the check catching T01's planted value on a page that also holds 384); a near-verbatim quotation cited to EV-12 p4 or EV-05 p1 gives a check row that holds EXC-2026-007 or "directory" and matches T11 or T12.
- A reader fooled by T03's misquote ("91 days, over the 90 days of section 6.2 [EV-01 p6]") matches T03. The owner rules whether the finding saw the misquote.
- A memo that cites the seed page of a check trap (EV-07, EV-10 p6, EV-08 p1, EV-16 p2) ties there, so the check's catches on a real memo can be fewer than the floor's four.
- The memo may avoid a trap by citing the right page with the right value. The trap is then tried and nothing in the memo is wrong, so no layer can catch it on that memo.
- E-PLAN-1 p2 holds T05 and D01. A finding about M3's lateness that names that page and 2026-05-31 matches T05, which is the same problem seen from the other side.
- A finding that names the duplicate minutes by its full file name, "E-PLAN-1 Board minutes 2026-02-12 (1).pdf", does not match T05 or D01; one that names E-PLAN-1 does.
