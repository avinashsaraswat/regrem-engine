# finding: one folder per finding

When your bank tells the board and the Supervisor that a finding is fixed, code has checked every figure and date written in digits, every quotation and every document in the closure package against its evidence. Whatever did not check sits on a one-page list with a role against it. The finding owner signs, internal audit tests the fix, the issuer closes, internal audit for its own findings and the Supervisor for its own, and nothing about the finding leaves the bank.

Everything in `cases/` is invented.

## The folder

```
MRA-CMP-07/
  finding.md           the Supervisor's letter
  plan.md              one row per milestone
  evidence/            one file per piece
  closure/memo.md      the closure memo
  closure/rulings.md   rulings on the list
  closure/record.md    board approval, signature, closers
  closure/measures.md  hours booked, and what internal audit sent back
  closure/finding-log.jsonl   one line for each corrected paste or restarted record
  .finding-state.json  hashes, deny list, signature
```

Copy a folder with `cp -R folder copy`. `cp -R folder/* copy` drops the dot file, and with it the record of signed files.

`new` takes a path whose last part is the finding's id, makes the folder there and writes the templates, with no SYNTHETIC line to delete. It refuses a path inside the kit's own folders, so a bank's finding never lands in the kit. An evidence file opens with four lines:

```
What: EV-07 Complaint intake procedure
For: M2 EV-07
Signed by: Head of Complaints, 2026-03-14
Status: FINAL
```

The lines may sit in any order, together at the top of the file, and a blank line ends them. `Revised: YYYY-MM-DD` records a later change, `Source:` says where the text came from, and `Checked by:` names a second person who compared a typed page. `finding covers` also writes a Source line and a comment.

Signed by is one of four signature lines, and a person types the one that fits the file:

- `Signed by: Head of Complaints, 2026-03-14` for a document a person signs, such as a procedure, minutes, an attestation or a report a person issues.
- `Produced by: case manager aging report, 2026-04-30` for system output, such as an MI workbook or a data extract, on the as-at date a person confirmed.
- `Approved by: EV-29` for a document the bank approved by a separate record, such as a method approved by email, naming that record's evidence id.
- `Never signed: training deck` for material banks never sign, such as a quick reference card. Its ties count, and it never counts toward a milestone.

System output, such as a monthly MI workbook, a system aging report or a data extract, comes from a system as at a date. Its cover gives that system or report and the as-at date a person confirmed, in place of the Signed by line:

```
Produced by: case manager aging report, 2026-04-30
```

A bank often approves a document by a separate record, such as a QA method approved by email, a lookback method approved on a signed sheet or an MI pack accepted in a resolved minute. The document's cover then names that record's evidence id in place of the Signed by line, and the record gets its own cover, signed by the role that approved:

```
Approved by: EV-29
```

The document counts as signed on the record's date once the record is present and signed by a person. A record that is missing, unsigned or changed leaves the document unsigned with that reason, as in `EV-26 is approved by EV-29, which is missing.` So does a Revised line dated after the approval. A record that is system output, never signed or approved in its turn by another record carries no signature, so it approves nothing.

Training decks, quick reference cards, board MI packs, file copies of letters and most emails carry no signature by nature. The cover of such a file says so with a few words of what it is, in place of the Signed by line, and its Status is FINAL:

```
Never signed: training deck
```

Its ties count, and it puts no draft row on the list. It never counts toward a milestone, so listed beside signed files it neither signs the milestone nor holds it up. A milestone that lists only such files stays unsigned, with a reason that asks for the file that shows the milestone done.

A Signed by line that names a role wins over a Produced by, Approved by or Never signed line in the same cover, so a document someone should sign still needs its signature.

plan.md holds one row per milestone, and its Evidence cell lists every file that shows the milestone done. List the file that completes it, such as a lookback's final report, before that file exists, under an evidence id kept for it, such as EV-61. The check keeps the milestone unsigned while that file is missing, as in `Present, unsigned: EV-61 is missing.`, so a lookback two-thirds done never reads as signed on its methodology and approval alone. Mark the file that completes the milestone with `(done)` after its id, as in `EV-27, EV-28 (done)`, and reserve the id with its mark before the file exists. The milestone's date, and so its lateness, is then that file's signature or as-at date, and every other file the row lists still has to be present and signed, apart from a file never signed. A row with no mark keeps the newest date among its files. A row with two marks stops the check, which names its line.

The board's approval of the plan is an evidence file too, holding the minutes. Its `For:` line ends `E-PLAN-1`, as in `For: PLAN E-PLAN-1`, and it is FINAL and signed by the role that keeps the minutes, such as `Signed by: Company Secretary, 2026-02-10`. No milestone lists it. Until it counts as signed, every committed date reads `proposed`, the page asks the board for its approval of the plan and sign refuses. When the minutes are there and do not count, the Plan approval line gives the reason, such as `E-PLAN-1 changed since it was signed`. Once they count, the committed dates freeze. A date changed in plan.md afterwards shows as moved, lateness counts from the approved date, and the board is asked to approve the change. An added milestone asks the same, and neither stops the signature. A milestone taken out of plan.md afterwards does stop the signature, and sign gives the reason. Minutes signed again with a later date approve the plan as it then stands. The page keeps the date the board first approved beside each date it moved. The board summary flags a move only when the approval that first carried the new date came after the old date had passed, and the flag stays after later approvals.

Evidence arrives under the bank's own file names. Copy each file into evidence/, start its name with its evidence id and keep the bank's name after the id, as in `EV-07 TM Alert Backlog MI - Mar 2026 v2 FINAL.xlsx`, then run `finding covers`. The id is one plan.md lists, E-PLAN-1 for the board's minutes, or an EV id. A file whose name starts with the bank's own reference number, such as CHG-2026-03952, gets no draft cover. Nor do two files under one id, such as a signed PDF beside the text file that already carries its id. The covers screen names each one with what to do.

A document sits behind a cover: `EV-07-procedure.pdf` has `EV-07-procedure.pdf.md` beside it, holding the four lines. `finding covers` reads each document and drafts its cover. The check reads a PDF with a text layer, a Word file, an Excel workbook (one page per visible sheet), a CSV, a saved .eml or a plain text file itself. It has no reader for any other file type, such as an Outlook .msg, so each cited page of one is typed into its cover as a scan's is, and `finding covers` drafts that cover saying so. A file the reader refuses, such as a Word file that still holds tracked changes, is typed the same way. The Source line of its draft cover says the check did not read it and why. The covers screen counts the words a reader cannot see that the reader left out of a page, and a row on that page gives the same count. The screen names up to five of them, as in `1 word a reader cannot see left out on page 1: "tial"`. A word on the deny list is counted and never printed. The reader leaves a Word file's comments out of its page, so the covers screen counts each comment that holds words on that file's line, as in `3 comments not read`. A page with no text, such as a scan, is typed into the cover under `## Page 7`, and the screen counts every tie that rests on typed text. Typing a page leaves the document's signature as it was. The signature covers the document and the cover's header lines other than Source and Checked by, and the cover's `Checked by:` line answers for the typed pages. A page typed or changed after a check has seen the cover is a change, and the check that first sees it keeps its date. The ties on the typed pages wait until the Checked by line carries that date or a later one. A change to the document itself, or to another header line, still needs a fresh signature date. The reader does no optical character recognition and reads no encrypted PDF. An Excel date reads as its serial number and a percent as its fraction, so those figures go on the list for a person.

## The verbs

From the kit root, where `finding/finding` is a two-line wrapper that runs `python3 -I finding/finding.py`:

```
finding/finding new ../findings/MRA-CMP-08
finding/finding check ../findings/MRA-CMP-08
finding/finding sign ../findings/MRA-CMP-08
```

Three more help around them, and `finding/finding --version` checks the files against the release:

```
finding/finding covers ../findings/MRA-CMP-08
finding/finding eval ../findings/MRA-CMP-08
finding/finding eval --library
finding/finding size ../findings/MRA-CMP-08
```

On Windows, type `py -I finding\finding.py` instead of `finding/finding`.

## Kinds of matter

finding.md names one of three kinds. A supervisory finding is one the Supervisor wrote, and only the Supervisor closes it. Internal audit closes an internal audit finding. A self-identified issue is a weakness the bank found on its own, and the bank's issue-management owner closes it, on the three `Issue closure` lines in closure/record.md. Internal audit tests the fix for all three. The issuer and the kind of matter freeze at the first check, so relabelling a finding afterwards is refused. A wrong kind at the very first check is caught only where the issuer names the Supervisor.

## Check

The check ties each figure, date and quotation to its cited page, and it does not compare documents with each other. So a list with no rows still leaves a reviewer to read for these:

- A version in force that is later than the one approved.
- Figures that disagree between documents.
- A scanned page that differs from the bank's other records.
- Work dated before the control that should come first, such as people working before their training.
- A status report that says more than its evidence.

Each milestone is not started, unsigned with the reason, or signed. A file counts as signed when it is FINAL, names a role and a date, and is unchanged since. A system output file counts the same way on its as-at date, for its milestone, for lateness and for sign, and its ties count like a signed file's. The milestone line names each one as produced by its system on that date, with no signature, so internal audit sees the difference, and a change to the file after that date unsigns it. A document approved by a separate record counts on that record's date, and the milestone line names the record, as in `EV-26 was approved by EV-29 on 2026-04-24.`, so internal audit can follow the chain. A change to the document after that date unsigns it. The line also names each listed file never signed, as in `Never signed: EV-30 (training deck).` The board's minutes need a signature of their own. A milestone below signed is SLIPPED once its date passes and AT RISK in the 14 days before. A milestone signed after its committed date is flagged on the board summary with how many days late, counted from the date of the file plan.md marks done, as in `Present on 2026-05-15, the date of EV-28, which plan.md marks done.` With no mark it counts from the newest signature or as-at date among the files, so a routine re-signature flags too. The quarterly progress starts at the quarter of the first committed date. Two evidence files with the same bytes, such as a scan saved under a second name, are named for the team under Needs a person, and `finding covers` names them too. Sign goes ahead with them. The board summary, commitment table and closure state follow. It refuses if the letter or the owner role changes after the first check, or if it would print a name on the deny list. A line that says the finding itself is closed, written before the closer's record exists, goes on the list as `closed in plan.md` or `closed in closure/memo.md`, and the rest of the page prints. That row stops the signature, and no ruling clears it, so the line has to be reworded. Any other use of the word closed, such as accounts closed in error, goes on the list the same way for the owner to rule on. A use is no row when the two words before closed and the two after it stand in that order in finding.md, as when the plan copies the letter's alerts closed without escalation. A line that says the finding itself is closed stays a row all the same. Every such row stays off the list once the closer's record exists. A wrong paste of the letter is corrected with `finding/finding check <folder> --repaste`, which keeps the evidence record, the deny list and the signature, and says so on every later page and in the log.

Each entry in closure/record.md, internal audit's, a closer's or the board's, counts once its reference, date and role each have a real form. A placeholder such as TBD, to follow or XXX counts for nothing, and so do a value under three characters, a reference with no digit and a date after the check. An entry dated before the first check counts, and its line says the check cannot see when it was made. A role is taken as written, such as Company Secretary or Head of Regulatory Relations. A name typed there prints as written, unless it is on the deny list, which stops the page.

In the memo, a cite such as `[EV-12 p2]` names page 2 of the file whose `For:` line ends `EV-12`. A heading such as `## Page 2` starts a page, and a file without one is one page. The kit's tie-out engine reads the cited page for each figure, date and quotation. A cite answers for its own sentence, even across a wrapped line, and a list item after a bullet or a list number is a sentence of its own. A quotation is read in double quote marks, or in single marks when it holds three words or more, and one with a bracketed insertion or an ellipsis goes on the list for a person. A cite written another way, such as `[EV-12, p2]`, `[ EV-12 p2 ]`, `[EV-12 pp. 1-2]` or `[EV-12 p2, EV-13 p1]`, is no cite, its page numbers are no claims, and its row names the form the check reads. A claim that does not tie goes on the list, as does a missing cite or one to a missing file, or to a file no milestone lists that is not signed. A draft cover has one row for the claims that match its pages and they count as no ties, and a claim that does not match keeps its own row. A heading's figures count, a number that opens it included, except a section number and a number that labels a part, such as Part 3 or Appendix 1. A number straight after version, v or Rev., such as version 3.1, v2 or Rev. 4, is a label anywhere in the memo, and no claim. A section number is written as `2.`, `2)`, `(2)`, `2:` or `2 -`, or as `2.1` before a capitalised word, or is `1` or the number after the last heading's, as `## 3 Findings` after `## 2 Method`. A list number is no figure when it is 1 or the next in its list, so a figure such as `(12)` opening a line counts. So do the dates on a `Fix effective:` or `Sample period:` line. A sample period that starts before its control's `Fix effective:` date is a row too, which sits on the list without being one of the claims. A figure written in words, a number read as a year and a date with a two-digit year, such as 1-Jul-26, are no claims, and the page names each on a `Not checked:` line. A date ties at the precision written. A month or a quarter ties a page that shows the same period or a date inside it, however many such dates the page holds. The figures in its sentence are checked as before. On an evidence page, a day, month and year split by one line break read as one date, unless a figure stands before the day, as in a table row or Page 1 of 3, or a label such as Table 3, Page 2 or Section 4 does. Excel's Aug-26 and Aug-2026 read as August 2026, in the memo and on a page. On the page of a saved email with a Date line, a day and month with no year take the year that puts them nearest that date. So 29 January in an email dated 21 Oct 2026 reads as 2027-01-29. Anywhere else such a date is not read. The time and zone on an email's Date line, such as 20:05:33 +0000, are no figures, and its date still reads as a date. A page the memo cites that has no text and nothing typed is named on the page, and a page it does not cite is not. The tool never changes the memo.

A row leaves the list when a line in closure/rulings.md clears it with the owner role, a date no later than the check and a reason, and the page prints each cleared row. A ruling clears one row. The second cell is what the row prints after "To rule, name:", the claim and a short mark for its cite and sentence, so a ruling cannot clear a different claim:

```
Line 8 | March 2026 #f2ba27f8 | cleared | Head of Complaints | 2026-11-04 | The page says January to March.
```

If the memo moves, a cleared ruling follows its claim to the new line while the memo holds that claim, cite and sentence once. Change the sentence or the cite and the row returns to the list under a new mark. The page then says the old ruling names no row and gives the row that prints its claim, as in `Ruling at rulings.md line 5 names no row: the row on line 8 prints EV-12 draft #30243f6b.` The owner rules again under the new mark. A ruling dated before its cited file was signed again stops counting, and the page says why. A ruling of `fix the memo` or `fix the evidence` gets the same line while a row prints its claim under another mark. Once no row does, it stays in the file without a word.

## Sign

`sign` runs only at a terminal, which stops a script by accident and proves nobody's identity. The bank's access controls supply that. A real finding is signed on the machine's date. `--today` works on sign only while the first line of finding.md is a shipped case's SYNTHETIC line, word for word. `finding new` writes no SYNTHETIC line, and on any other first line `sign` refuses `--today` with "drop --today". A typed date shows on the page and in record.md beside the machine's own date. It refuses while a row is on the list, the memo is empty, a tie rests on a page typed into a cover with no Checked by line, or with one dated before the check that first saw that page change, a milestone is below signed, the plan is still proposed, a milestone was taken out of plan.md after the board approved the plan, a file is not counted, record.md lacks the board's reference, date or role, a signed file sits under another id, or a file came in under the id of a signed file that went before it came in. A signature on that file dated after the last check that saw the file that went clears it, and a file under a new id is never held up. Once none of those holds, the check names the owner's signature first under Needs a person and prints the folder's fingerprint on a Ready to sign line, for internal audit to record what it tests. The signer types the owner role, then the first eight characters of a fingerprint over the memo, rulings, letter, plan, evidence, board approval and the tool's own code, including the engine and the document reader. The signature and the kit's release go into record.md. A later change to a covered file asks for a fresh signature. Entries the closers make in record.md do not, because they come after the signature: internal audit's, the Supervisor's and the issue-management owner's. When internal audit enters at least eight characters on `Internal audit tested fingerprint:`, the page compares them with the folder as it stands and asks for a fresh test if the folder moves on.

## The log

closure/finding-log.jsonl gets one line when `check --repaste` records a corrected paste of the letter, and the first such correction starts the file. After a lost state file, the next check adds a `record restarted` line only when closure/finding-log.jsonl is already there, and before then it writes no line. Every log line names the kind, the issuer and the first check.

## Measures

closure/measures.md holds what the Measures line on the check page counts, and no signature covers it. One line a month for hours and one line for each thing internal audit sends back:

```
Hours | 2026-10 | 38
Hours | 2026-11 | 12.5
Sent back | 2026-11-02 | Line 8 | the figure was the draft's | missed by the check
```

Part hours count, and so does the same line written as a table row. The check adds hours exactly and prints the total as it stands, such as 50.5 hours. A line that starts with Hours or Sent back and cannot be read, such as `Hours | 2026-11 | 1,240` or `Hours: 38`, is named on the page for the engagement team and counts for nothing.

## Fitting it to a bank

Two optional lists sit beside finding.md, or one folder up for the whole engagement. `denylist.txt` holds terms that must never print, one a line, matched in any letter case and with or without accents. `role-words.txt` holds ordinary words or phrases never to treat as a name, and a line there clears a term the check took for a name, even after a refused run. `denylist.txt` wins over it. A run of capitalised words that holds a document word, such as Procedure, Policy, Report, Plan, Minutes, Register or Methodology, is a title, so the check never takes it for a name, and the bank's file names can keep it. Every refusal over a term the check took from the letter offers role-words.txt, the refusal over a file name included, because renaming a bank's file breaks its link to the bank's records. A line can also clear one word of the bank's name, such as First in First Fenmoor Trust Bank, on the pages, and that word then passes in every form. The bank's full name never clears, so its refusal never offers the file. The check page prints only counts, as `Deny list: 3 names.`, and adds `; role-words.txt cleared 1 word of the bank's name.` when a line did. `finding/finding check <folder> --names` prints the names, for the person who asks.

The hours `finding size` assumes sit in a third optional file, `size-assumptions.txt`, in the same two places. It holds one line for each assumption the team has timed, and a line left out keeps the kit's value. A line beside the finding wins over the one in the folder above. The file changes no fingerprint, and `size` says how many lines it read. A folder of findings reads the file in that folder, and a finding's own file still wins for that finding, with its values named on the run's closing line. These are the kit's values:

```
minutes a claim by hand: 10
memo versions: 3
hours a status report: 2
minutes to find a signed file: 30
hours a rework round: 8
minutes a cover: 10
minutes a ruling: 15
minutes to read a claim: 10
rework rounds with the kit: 1
minutes a status report with the kit: 15
minutes to type and compare a page: 15
```

The templates, the plan columns and the record fields are constants at the top of finding.py. A column the bank adds to plan.md is read past wherever it sits, so it needs no change there. Renaming a column or a record field the check reads, or adding a kind of matter, needs a code change and a self-test case. A change to finding.py changes every fingerprint, and `python3 -I finding/release.py` refreshes RELEASE.json. With no version named it steps the kit to a site version, such as 0.7.0+site.1, so a kit changed at a bank never reads as the published release.

## Known limits

Each of these is open in 0.7.0 and can turn up in ordinary material, so a person reads for it.

- A person's name inside a title, such as the Natarajan Report, stays off the deny list, because a run holding a document word is a title. Put such a name in denylist.txt.
- An uncited claim in a lettered list such as a) or i), a middle-dot bullet or a table row borrows the cite on the next line, so it can tie.
- June of 2026 and the typo May. 22, 2026 are not read as dates, so a wrong one can pass.
- A month or a quarter ties any date inside it on its page. So a wrong month the page also shows, as in a monthly table, ties, as a wrong figure the page holds elsewhere does.
- A bracketed id such as (CP-07) reads as a misspelt cite, so the sentence's real cite is lost and its row asks for [CP-07].
- A cite written [EV-21 pp. 1, 2] or [EV-21 pages 1 and 2] gives each page number a row, and a cite after the point, as in (See [EV-21 p2].), or a point in i.e. leaves a claim with no cite.
- In Markdown evidence, an image's text, as in `![...](chart.png)`, and a link's title read as shown, so a figure found only there ties, and a placeholder of two or more words, such as `<Title Firstname Surname>`, leaves out the rest of its page, so that page's figures go on the list.
- A signed file swapped under a new evidence id with a backdated signature shows only as the old file gone, and not at all while the old file stays. When one of two identical documents is taken out, the other is named as filed under another id, and sign refuses it until it is signed again.
- In closure/record.md a reference such as IA-2026-TBC counts, while a two-letter role such as IA and a reference with no digit, such as BRC minutes (July), count for nothing.
- A person's name typed in a record role line prints as written unless it is on the deny list.

## Reference

A check exits 0 when nothing needs a person, 1 otherwise, and 2 on a usage error. An unsigned folder still needs its owner, so it exits 1. `--today YYYY-MM-DD` checks as of another date, and works on sign only as the Sign section says. `--names` and `--repaste` are the two options above. `python3 -I finding/selftest.py` tests the tool, including that the kit's own files import only modules on a fixed list and start no process.
