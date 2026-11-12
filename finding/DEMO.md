# finding: the walk

Run every command from the kit root, the folder that holds finding/. On Windows, type `py -I finding\finding.py` wherever this page says `finding/finding`, and do the copies and edits in File Explorer and a text editor. The walk uses `--today 2026-11-04` so your screen matches this page.

## 1. The line that opens every screen

Every check, and every refusal about a finding, starts with this line:

```
This folder may hold confidential supervisory information. Keep it on a machine the bank has approved, and share nothing from it outside the bank.
```

`finding/finding new ../findings/DEMO-01` run a second time prints only its refusal, `Refused: ../findings/DEMO-01 already exists.`, because it has read no finding, and so does `new` on a path inside the kit. The tool sends nothing anywhere. Keeping the folder on an approved machine is up to the people using it.

## 2. Open a finding

```
finding/finding new ../findings/DEMO-01
```

It prints `Made ../findings/DEMO-01. Fill the header lines in finding.md and paste each part of the letter under its heading, then fill plan.md.` and makes `DEMO-01/` in a findings folder beside the kit, with finding.md, plan.md, an empty evidence/, and closure/ with its memo, record, rulings and measures templates. No template holds a SYNTHETIC line to delete. The last part of the path is the finding's id. A folder inside the kit is refused, so `finding/finding new DEMO-01` from the kit root prints `Refused: DEMO-01 is inside the kit's own folders. Make the finding folder outside the kit, such as ../findings/DEMO-01 from the kit root.` To see what to fill first, check the empty folder:

```
finding/finding check ../findings/DEMO-01
```

It prints the opening line, then `Not ready: finding.md has no Institution yet. Fill that line, then check again.` and exits 1, because the header lines are empty. Remove the folder when you have seen enough:

```
rm -r ../findings/DEMO-01
```

## 2b. From a letter to a first check

A real letter has no such headings, so a person fills the header lines and puts each passage under the heading it answers. Here is a short invented letter in that shape, with one milestone:

```
finding/finding new ../findings/DEMO-02
cat > ../findings/DEMO-02/finding.md <<'END'
# Finding DEMO-02
Identifier: DEMO-02
Institution: Harbour Example Bank
Issuer: the Supervisor
Letter date: 2026-09-14
Kind of matter: supervisory finding
Owner role: Head of Complaints

## Concern
Complaint files are not kept for the full period.

## Cause
No procedure sets the retention period.

## Consequence
Files the Supervisor asked for could not be found.

## Corrective action
Set the period in a procedure and move the files.

## Commitment
Report progress to the Supervisor within 60 days.
END
echo '| M1 Issue the retention procedure | Head of Complaints | 2027-01-31 | The procedure sets the period | EV-01 | A sample of files meets the period |' >> ../findings/DEMO-02/plan.md
finding/finding check ../findings/DEMO-02 --today 2026-11-04
```

It prints the full screen, opening with this and ending with what needs a person:

```
Finding DEMO-02, a supervisory finding from the Supervisor dated 2026-09-14. Owner: Head of Complaints. Checked as of 2026-11-04, kit release 0.7.0.

Milestones
M1 Issue the retention procedure. Head of Complaints, committed 2027-01-31 proposed. Not started.
```

That first full check fixes the letter's text. Change a word and check again:

```
sed 's/for the full period/for the whole period/' ../findings/DEMO-02/finding.md > ../findings/DEMO-02/finding.new
mv ../findings/DEMO-02/finding.new ../findings/DEMO-02/finding.md
finding/finding check ../findings/DEMO-02 --today 2026-11-04
```

```
Refused: the Concern in finding.md is not the text first checked on 2026-11-04. The Supervisor's words do not change; restore them, or run check --repaste if the first paste was wrong.
```

If the first paste was wrong, `finding/finding check ../findings/DEMO-02 --repaste --today 2026-11-04` records the correction and keeps the evidence record, the deny list and any signature. Every later page says the text was corrected and on what date, and the folder's log holds the line.

The first check also puts the financial institution's name and any run of two or three capitalised words from the letter on the deny list, and a page that would print one is refused. A run that holds a role word or a document word, such as Head or Procedure, is a title and stays off the list, so an institution's file named for a procedure the letter cites keeps its name. If a term on the list is an ordinary word or a title, the refusal says to add it to `role-words.txt` beside finding.md, and the next check clears it. That holds when the term sits in the name of one of the institution's files too, because renaming the file breaks its link to the institution's records. A word of the institution's name clears the same way, and the page then counts it. The institution's full name never clears, so its refusal does not offer the file. `finding/finding check ../findings/DEMO-02 --names` prints the list, for the person who asks. Every other page prints only its count. Remove the folder:

```
rm -r ../findings/DEMO-02
```

## 3. Read the invented finding

```
finding/finding check finding/cases/MRA-CMP-07 --today 2026-11-04
```

It prints this screen and exits 1:

```
This folder may hold confidential supervisory information. Keep it on a machine the bank has approved, and share nothing from it outside the bank.

Finding MRA-CMP-07, a supervisory finding from the Supervisor dated 2026-01-15. Owner: Head of Complaints. Checked as of 2026-11-04, kit release 0.7.0.

Milestones
M1 Approve revised complaint taxonomy. Head of Complaints, committed 2026-02-28. Present and signed on 2026-02-20.
M2 Reissue intake procedure. Head of Complaints, committed 2026-03-15. Present, unsigned: EV-08 was revised on 2026-04-02, after its signature of 2026-03-14. SLIPPED by 234 days.
M3 Quality review of reclassified complaints. Complaints QA lead, committed 2026-04-30. Present, unsigned: EV-12 is a draft. SLIPPED by 188 days.
M4 Extend taxonomy to the mobile app chat channel. Head of Digital, committed 2026-06-30. Not started. SLIPPED by 127 days.

Board summary, a draft for the finding owner
Flagged commitments: M2 slipped 234 days, M3 slipped 188 days, M4 slipped 127 days.
Quarterly progress:
  Quarter ending 2026-03-31: 2 milestones due, 1 signed, 1 below signed.
  Quarter ending 2026-06-30: 4 milestones due, 1 signed, 3 below signed.
Plan approval: board minutes E-PLAN-1, signed by the Company Secretary on 2026-02-10.

Commitment table, the bank's response in the Supervisor's five-part form, from plan.md
Concern, Cause and Consequence: as written in finding.md.
Corrective action:
| Milestone | Owner role | Committed date |
| M1 Approve revised complaint taxonomy | Head of Complaints | 2026-02-28 |
| M2 Reissue intake procedure | Head of Complaints | 2026-03-15 |
| M3 Quality review of reclassified complaints | Complaints QA lead | 2026-04-30 |
| M4 Extend taxonomy to the mobile app chat channel | Head of Digital | 2026-06-30 |
Commitment: full remediation by 2026-06-30.

Closure memo: present, not tested by internal audit yet.
Internal audit: none recorded.
Supervisor closure: none recorded.
Board approval: none recorded.
Memo check: 13 claims, 7 tie, 3 on the list, 1 cleared.
  Line 8: 1,248 is cited to EV-07 p2, and the page does not hold it; the nearest figures on the page are 1,284 and 2. To rule, name: 1,248 #972adb19
  Line 10: EV-12, which is a draft, holds 4 claims, on lines 10, 15 and 16, that match its pages and wait on a person's signature. To rule, name: EV-12 draft #81b3b231
  Line 16: the sample period for M2 starts 2026-01-05, before the fix took effect on 2026-03-17, so the sample mixes items from before and after the fix. To rule, name: sample period for M2 #106ddd50
  Cleared: line 8, March 2026, by the Head of Complaints on 2026-11-04: The page says January to March, and the plan year is 2026.
  7 ties rest on text a person typed: 7 in plain-text evidence, none on a page typed into a cover.
  Not checked: 1 figure written in words, line 6 (three).
Signature: none yet.
Deny list: 3 names.

Needs a person:
  Head of Complaints: M2, the list (3 rows).
  Complaints QA lead: M3.
  Head of Digital: M4.
  Internal audit: its reference in closure/record.md.
  The Supervisor: its closure notice.
  The board: its approval of closure.
```

Under Milestones, M1 is present and signed. M2 lists two files in plan.md, EV-07 the intake procedure and EV-08 the register of staff trained on it. EV-07 is signed, but EV-08 was revised after its signature, so M2 is unsigned. M3 is unsigned because its quality review is still a draft, and M4 has no evidence at all. All three are SLIPPED. The board summary counts each quarter's due and signed milestones and names the board minutes that approved the plan. The commitment table is the institution's response in the Supervisor's five-part form. The closure lines show a draft memo that internal audit has not tested, no closure record and no board approval yet. The memo check and its list come in step 7. The deny list line counts the names the check keeps off every page, and the last block names what needs a person, grouped by who.

## 4. Change a signed file

Steps 4 and 5 work on a copy, so the shipped case stays as it is. Copy the case, keep a copy of EV-03, the signed taxonomy, change one word of its body, and check again:

```
cp -R finding/cases/MRA-CMP-07 walk-07
cp walk-07/evidence/EV-03-complaint-taxonomy.md walk-07/EV-03.keep
sed 's/with three subcategories/with four subcategories/' walk-07/EV-03.keep > walk-07/evidence/EV-03-complaint-taxonomy.md
finding/finding check walk-07 --today 2026-11-04
```

M1 moves back and joins the flagged commitments:

```
M1 Approve revised complaint taxonomy. Head of Complaints, committed 2026-02-28. Present, unsigned: EV-03 changed since it was signed. SLIPPED by 249 days.
```

```
Flagged commitments: M1 slipped 249 days, M2 slipped 234 days, M3 slipped 188 days, M4 slipped 127 days.
```

The quarterly counts drop to 0 signed, and M1 joins what the Head of Complaints has to do. Put the signed text back and check again:

```
mv walk-07/EV-03.keep walk-07/evidence/EV-03-complaint-taxonomy.md
finding/finding check walk-07 --today 2026-11-04
```

The screen matches step 3 again, and M1 reads `Present and signed on 2026-02-20`. The state file, `.finding-state.json`, kept the hash EV-03 had when it was signed, because the check never records a changed file over a signed one with the same signature date. Plain `ls` hides that file, and `cp -R folder/* copy` leaves it behind, so copy a whole folder with `cp -R folder copy` as this step does. With the state file gone, the page names what was signed before the new first check, because a change before then cannot be seen.

## 5. Call the finding closed

A line that says the finding itself is closed goes on the list until the closer's entry is in the record, and no ruling clears it. Any other use of the word closed, such as accounts closed in error, goes on the list for the owner to rule on. A use with the two words before it and the two after as finding.md has them, as when a plan copies the letter's own wording, is no row.

```
echo "The finding is closed." >> walk-07/plan.md
finding/finding check walk-07 --today 2026-11-04
```

The page prints in full, and the list grows to 4 rows with this one:

```
  Line 10: closed in plan.md claims the finding is closed, and only the Supervisor closes a supervisory finding. Reword the line, as no ruling clears this row.
```

Remove the copy:

```
rm -r walk-07
```

## 6. A finding that waits only on people

```
finding/finding check finding/cases/IA-CMP-02 --today 2026-11-04
echo $?
```

This internal audit finding has both milestones signed, board minutes that approve the plan, and the board's approval of closure. Internal audit has entered nothing yet, because the owner signs first. The screen says `Supervisor closure: not applicable to an internal audit finding.` and ends with these lines:

```
Memo check: 13 claims, 13 tie, 0 on the list.
  13 ties rest on text a person typed: 13 in plain-text evidence, none on a page typed into a cover.
  Not checked: 2 figures written in words, line 6 (five) and line 8 (five).
Signature: none yet.
Deny list: 3 names.

Needs a person:
  Head of Complaints: the signature, which comes first.
  Internal audit: its reference in closure/record.md.
Ready to sign: the folder's fingerprint is a381fa0f. Internal audit records this as what it tests.
```

The exit code is 1, because the owner has not signed. The invented evidence is plain text, so every tie counts as resting on typed text, and none sits on a page typed into a cover, so none needs a second person's Checked by line. The two figures written in words are left for a reader. The fingerprint changes with any release that changes the tool's code, and the Finding line names the release, so your screen matches this page only on release 0.7.0.

## 7. The list

Step 3 ended with the memo check for MRA-CMP-07. The check read every figure and date written in digits and every quotation in closure/memo.md and looked for each one on the evidence page its cite names:

```
Memo check: 13 claims, 7 tie, 3 on the list, 1 cleared.
  Line 8: 1,248 is cited to EV-07 p2, and the page does not hold it; the nearest figures on the page are 1,284 and 2. To rule, name: 1,248 #972adb19
  Line 10: EV-12, which is a draft, holds 4 claims, on lines 10, 15 and 16, that match its pages and wait on a person's signature. To rule, name: EV-12 draft #81b3b231
  Line 16: the sample period for M2 starts 2026-01-05, before the fix took effect on 2026-03-17, so the sample mixes items from before and after the fix. To rule, name: sample period for M2 #106ddd50
  Cleared: line 8, March 2026, by the Head of Complaints on 2026-11-04: The page says January to March, and the plan year is 2026.
  7 ties rest on text a person typed: 7 in plain-text evidence, none on a page typed into a cover.
  Not checked: 1 figure written in words, line 6 (three).
```

The memo says 1,248 where the procedure says 1,284. The figure 31 and the three dates on the Fix effective and Sample period lines come from a quality review that is still a draft, so EV-12 gets one row for the 4 claims that match its pages until a person signs it. The sample for the tested control also starts before its fix. That sample row is not a claim, so the 13 claims are the 7 that tie, the 1,248, the 4 on the EV-12 row and the 1 cleared. Each row ends with what a ruling names to clear it. The finding owner has already cleared one row in closure/rulings.md, and the page prints it with its reason. Move that file aside on a copy to see it come back:

```
cp -R finding/cases/MRA-CMP-07 walk-07
mv walk-07/closure/rulings.md walk-07/rulings.keep
finding/finding check walk-07 --today 2026-11-04
```

With the rulings moved aside, the row for March 2026 comes back, because EV-07 page 2 holds no date:

```
Memo check: 13 claims, 7 tie, 4 on the list.
  Line 8: March 2026 is cited to EV-07 p2, and the page holds no date. To rule, name: March 2026 #f2ba27f8
  Line 8: 1,248 is cited to EV-07 p2, and the page does not hold it; the nearest figures on the page are 1,284 and 2. To rule, name: 1,248 #972adb19
  Line 10: EV-12, which is a draft, holds 4 claims, on lines 10, 15 and 16, that match its pages and wait on a person's signature. To rule, name: EV-12 draft #81b3b231
  Line 16: the sample period for M2 starts 2026-01-05, before the fix took effect on 2026-03-17, so the sample mixes items from before and after the fix. To rule, name: sample period for M2 #106ddd50
  7 ties rest on text a person typed: 7 in plain-text evidence, none on a page typed into a cover.
  Not checked: 1 figure written in words, line 6 (three).
```

Put the rulings back before the next step:

```
mv walk-07/rulings.keep walk-07/closure/rulings.md
```

## 8. Rule on a row

Suppose the finding owner drew the sample across the fix on purpose, to compare error rates before and after it. One line in closure/rulings.md says so, with the memo line, what the row names after "To rule, name:", the ruling, the owner role, a date and a reason:

```
echo 'Line 16 | sample period for M2 #106ddd50 | cleared | Head of Complaints | 2026-11-04 | The sample spans the fix on purpose, to compare error rates before and after it.' >> walk-07/closure/rulings.md
finding/finding check walk-07 --today 2026-11-04
```

The row leaves the list and the count of cleared rows goes up:

```
Memo check: 13 claims, 7 tie, 2 on the list, 2 cleared.
  Line 8: 1,248 is cited to EV-07 p2, and the page does not hold it; the nearest figures on the page are 1,284 and 2. To rule, name: 1,248 #972adb19
  Line 10: EV-12, which is a draft, holds 4 claims, on lines 10, 15 and 16, that match its pages and wait on a person's signature. To rule, name: EV-12 draft #81b3b231
  Cleared: line 8, March 2026, by the Head of Complaints on 2026-11-04: The page says January to March, and the plan year is 2026.
  Cleared: line 16, sample period for M2, by the Head of Complaints on 2026-11-04: The sample spans the fix on purpose, to compare error rates before and after it.
  7 ties rest on text a person typed: 7 in plain-text evidence, none on a page typed into a cover.
  Not checked: 1 figure written in words, line 6 (three).
```

A ruling from another role, or one with no date or reason, leaves its row where it is. So does `fix the memo` or `fix the evidence`, because only the fix itself clears those rows. If a later edit moves the memo, a cleared ruling follows its claim to the new line while the memo holds that claim, cite and sentence once. Change the sentence or the cite and the row returns to the list. Remove the copy:

```
rm -r walk-07
```

## 9. Sign

Signing needs a terminal, so piped input is refused:

```
echo "Head of Complaints" | finding/finding sign finding/cases/IA-CMP-02 --today 2026-11-04
```

```
This folder may hold confidential supervisory information. Keep it on a machine the bank has approved, and share nothing from it outside the bank.

Refused: sign needs a terminal.
```

The terminal test stops a script by accident and proves nobody's identity, and the institution's access controls supply that. The walk's `--today` works on sign only because this folder opens with a shipped case's SYNTHETIC line. `finding new` writes none, so a real finding is signed on the machine's date.

Sign a copy of IA-CMP-02 by typing at the terminal:

```
cp -R finding/cases/IA-CMP-02 walk-02
finding/finding sign walk-02 --today 2026-11-04
```

It prints the check screen from step 6 and asks for the owner role:

```
Type the finding owner's role to sign: Head of Complaints
```

It then prints `Fingerprint` and a 64-character hash of the memo, rulings, board approval, letter, plan, evidence and the tool's own code, including the engine and the document reader. Type back its first eight characters when it asks `Type its first eight characters to confirm:`. Sign then writes the role, the date, the full fingerprint and the kit's release into closure/record.md and prints the signed line with the same eight characters. A run on 2026-11-10 printed `Signed by the Head of Complaints on 2026-11-04, a date typed with --today on a machine dated 2026-11-10, fingerprint a381fa0f. Written to closure/record.md.` When the typed date is not the machine's, the line and record.md give both. Each later check prints that line in place of `Signature: none yet.`

The tool's own code is part of the hash, so a new version of the tool gives a new fingerprint.

On MRA-CMP-07 sign stops before it asks anything, with `Refused: 3 rows are on the list; rule on them first.` That case ships unfinished on purpose. Before it can be signed, the memo needs 1,284 in place of 1,248. That changes the sentence on line 8, so the ruling on March 2026 names no row, and the owner rules on it again under its new mark. The quality review needs a signature and Status FINAL. Then the 31 and the three dates on the Fix effective and Sample period lines tie, because each already has a cite to a page that holds it. M2 to M4 each need a signed evidence file. The line 16 sample row needs a ruling, as in step 8, or a sample that starts on or after the fix date. closure/record.md also needs the board's approval of closure.

## 10. Change a signed memo

```
echo "Internal audit has the memo." >> walk-02/closure/memo.md
finding/finding check walk-02 --today 2026-11-04
```

The signed line stays, and the check names the file that changed after it, `Changed since signing: closure/memo.md.` The screen ends with `Needs a person:`, internal audit's line and `  Head of Complaints: a fresh signature.`, and the exit code is 1. An entry by internal audit or the Supervisor in the record asks for no fresh signature, because those come after it. Run sign again to sign the memo as it now reads. Remove the copy when you are done:

```
rm -r walk-02
```

## 11. A document instead of a text file

Most evidence arrives as PDFs, Word files and spreadsheets. The check reads them itself, so a cover needs only its header lines. Copy the invented sample PDF into a fresh copy of the case and let the tool draft its cover:

```
cp -R finding/cases/MRA-CMP-07 walk-07
cp finding/samples/EV-30-sample-listing.pdf walk-07/evidence/
finding/finding covers walk-07
```

```
This folder may hold confidential supervisory information. Keep it on a machine the bank has approved, and share nothing from it outside the bank.

evidence/EV-30-sample-listing.pdf: 3 pages, 2 with text; no text on page 3. Draft cover written for evidence id EV-30.

A person checks the evidence id, fills Signed by and sets Status to FINAL on each cover. Type a page only where it has no text, was read only in part or is in a file the check has no reader for.
A PDF page is its printed page. A Word, CSV, email or text file is always page 1, so a cite does not say where in the file a figure sits. A workbook page is a visible sheet, in workbook order, and an Excel percent or date reads as its stored fraction or serial number.
```

The exit code is 1 because page 3 has no text. Open `walk-07/evidence/EV-30-sample-listing.pdf.md` to see the draft. Until a person signs it, the claims that match its pages share one row, `EV-30, which is a draft, holds 1 claim that matches its pages and waits on a person's signature.`, and a claim that does not match gets its own row. Once it says `Signed by: Complaints QA lead, 2026-03-20` and `Status: FINAL`, a memo line such as `The sample held 1,284 complaints [EV-30 p2].` ties on the PDF's own page 2. A cite to page 3 goes on the list and says to type that page into the cover under `## Page 3`, and each check then names it as `EV-30 page 3 has no text and nothing typed.` until someone types it. A page the memo does not cite is never named. Typing the page leaves the signature of 2026-03-20 as it is. The screen counts the page 3 tie as one on a page typed into a cover with no Checked by line, and sign refuses. A second person then compares the page and adds `Checked by:`, dated on or after the check that first saw it typed.

## 12. Test the check

An eval plants errors in the memo in memory, one at a time, in the claims that tie today or match a draft's pages, and names any claim it could not plant in. It lists every plant the check did not catch, and it changes nothing in the folder:

```
finding/finding eval finding/cases/IA-CMP-02
```

```
This folder may hold confidential supervisory information. Keep it on a machine the bank has approved, and share nothing from it outside the bank.

Eval of the memo check on IA-CMP-02. Nothing in the folder changed.
Planted 38 errors, one at a time, in the 13 claims that tie today.
  A figure with one digit changed: 6 planted, 6 caught.
  A figure with two digits swapped: 6 planted, 6 caught.
  A figure swapped for another on the same page: 6 planted, 0 caught.
  A date moved: 7 planted, 7 caught.
  A cite moved to another page: 13 planted, 11 caught.
Caught 30 of 38.
What the check did not catch, for a person to look for:
  Line 6: 2026-05-04 with its cite moved to EV-21 p2 still ties.
  Line 6: 120 changed to 118 still ties.
  Line 6: 118 changed to 120 still ties.
  Line 6: 98.3 percent changed to 120 still ties.
  Line 8: 402 changed to 410 still ties.
  Line 8: 410 changed to 402 still ties.
  Line 8: 98.0 percent changed to 410 still ties.
  Line 11: 2026-05-04 with its cite moved to EV-21 p2 still ties.
```

A wrong figure that sits on the cited page ties, so a person reads each sentence against its page. `finding/finding eval --library` runs the [library](../library/README.md) of invented cases and prints `Library cases: 21, 21 as expected, 6 of them a known limit.`

## 13. Size the work

```
finding/finding size finding/cases
```

```
This folder may hold confidential supervisory information. Keep it on a machine the bank has approved, and share nothing from it outside the bank.

IA-CMP-02: 2 milestones, 3 evidence files (0 with a separate cover), 13 claims on the memo check, 0 rows before rulings, 3 months.
  By hand, assumed: 22.0 hours. Checking claims 6.5, status reports 6.0, finding signed files 1.5, one rework round 8.0.
  With the kit, assumed: 11.5 hours. Reading each claim against its page 2.2, cover lines 0.5, rulings 0.0, status reports 0.8, rework 8.0.
MRA-CMP-07: 4 milestones, 6 evidence files (0 with a separate cover), 13 claims on the memo check, 4 rows before rulings, 6 months.
  By hand, assumed: 29.5 hours. Checking claims 6.5, status reports 12.0, finding signed files 3.0, one rework round 8.0.
  With the kit, assumed: 13.7 hours. Reading each claim against its page 2.2, cover lines 1.0, rulings 1.0, status reports 1.5, rework 8.0.

2 findings: 51.5 hours by hand, 25.2 with the kit, assumed.

These hours are assumptions: 10 minutes a claim by hand over 3 memo versions, 2 hours a monthly status report, 30 minutes to find a signed file, 8 hours a rework round, 10 minutes a cover, 15 minutes a ruling, and with the kit 10 minutes to read a claim once against its page, 15 minutes to type and compare a page, 15 minutes to review a status report the kit drafts and 1 rework round. Replace them with timed figures in a size-assumptions.txt beside a finding or in this folder of findings, which changes no fingerprint.
```

Rows before rulings counts every row a person has to rule on, including any already cleared, so it can be higher than the check's list. Both sides carry a person's work: with the kit, a person still reads each claim once against its page, reviews each status report the kit drafts and types any page the reader cannot read, and one rework round is assumed until it is timed. Each part is rounded as printed, and the total is their sum. A finding with its own size-assumptions.txt gets a line saying how many values it set, and the closing line names them, so each part can be worked out from the screen. The hours are assumptions until someone times the work. Remove the copy:

```
rm -r walk-07
```

## 14. Which release is this

```
finding/finding --version
```

It prints `RegRem Engine 0.7.0` and `Every file matches this release.`, or names the files that changed since. A full check names the release at the end of its Finding line, and sign writes it into the record. A Not ready or Refused screen does not print the release, and like every other screen it names any kit file that changed since.
