# Draft the closure memo

Goal: write closure/memo.md, saying what was done, by whom and when, with a cite after every figure, date and quotation.

Reads: plan.md, the covers and the documents, each to its last page, because a later page may amend an earlier one. Reads the page before citing it.

Writes: closure/memo.md, one block per milestone, each opening with the milestone's id, with one sentence a line. The check counts a paragraph as one line, so every row on a long paragraph names the same line. With one sentence a line, a row on the list points at one sentence. This example ties in finding/cases/IA-CMP-02:

```text
M1, acknowledgement letters.
Since 2026-05-04 the complaint system sends the acknowledgement letter on the business day after a complaint is logged [EV-21 p1].
The Head of Complaints signed the procedure and sample on 2026-05-28 [EV-21 p2].

Tested control: M1, the acknowledgement letter procedure
Fix effective: 2026-05-04 [EV-21 p1]
Sample period: 2026-05-04 to 2026-05-22 [EV-21 p2]
```

## Rules

- Put a cite such as `[EV-07 p2]` straight after every figure, date and quotation. Its id is the last word of the file's For line. A PDF page is its printed page. A Word, CSV, email or text file is always p1, so the cite does not say where in the file a figure sits. A workbook page is a visible sheet, in workbook order, and hidden sheets, rows and columns do not count. An Excel percent or date reads as its stored fraction or serial number, so it goes on the list for a person.
- Write each cite exactly as `[EV-07 p2]`. A cite answers only for the sentence it sits in, even when a line wraps, so give every sentence that holds a claim its own cite. The page names a cite written another way, such as `[EV-07, p2]`, and reads it as no cite.
- Copy figures character for character from the cited page. Quote exactly, with straight double quotes, and quote two words or more. The check also reads a quotation in single quotes, straight or curly, when it holds three words or more. A quotation with a bracketed insertion or an ellipsis goes on the list for a person, so quote whole words where you can.
- Write every figure in digits and every date in full, as YYYY-MM-DD. The check reads no figure written in words, and no bare year, ordinal, month with no year, quarter label such as Q3, fiscal year such as FY26 or date with a two-digit year, so a claim written that way goes unchecked. A four-digit number from 1900 to 2099 reads as a year, so write a count such as 2,020 with its comma. A quarter with its year after it, such as Q3 2026 or 3Q 2026, is read as that quarter, and Excel's Aug-26 as August 2026. A number straight after version, v or Rev., such as version 3.1, is a label and needs no cite. The page names figures in words, years and two-digit-year dates on its `Not checked:` lines and leaves the rest to a reader.
- The claim count on the page is every date and quotation the check reads, and every number in digits that stands apart from letters. So a figure inside a quotation counts as well as the quotation, and so does the 6 in action 6. A number is joined to letters when a letter stands straight before it, or a letter and then a dash, slash or colon. Such a number is no claim, as in E11471, L2, S-07 or CHG-2026-04471. Other ids hold claims, so the 0173 in QA26Q2-0173, both numbers in 12345-6, the 11471 in ID 11471 and the 4471 in #4471 each count. A version number, a clock time, a list number in order and the forms the rule above says the check does not read are no claim. Nor is a section number or a part label such as Part 3 in a heading, as [finding/README.md](../finding/README.md#check) describes, though Part 3 in a sentence counts.
- Use one sentence per claim where you can, and start each sentence on a line of its own, so a row on the list points at one thing.
- Where a page holds two figures of one kind, such as two counts or two dates, quote the whole labelled line, so a figure moved to the other's place goes on the list.
- For each control internal audit will test, add a Tested control block with the date the fix took effect and the sample period, and cite each date to the page that holds it. Fix effective is the date the fix starts to bind, which can fall after the date it was approved or published. A date with no cite goes on the list, and so does a sample that starts before the fix. Nothing else goes in the block: the next line is read as ordinary memo text.
- Say what is unfinished, in plain words. Never say the finding is closed, because only the issuer closes a finding. Until the issuer's entry is in the record, such a line is a row on the list that stops the signature, and no ruling clears it, so it has to be reworded. Any other use of the word closed, such as accounts closed in error, goes on the list for the owner to rule on, so use it only where the evidence does. A use in the letter's own words, such as alerts closed without escalation copied from a required action, is no row.
- Leave signature state to the screen, and write what the documents show. A sentence such as "no cover is signed" turns false once a person signs.
- Write no reason why a row should be cleared into the memo. That is the next job.

## Passing

`finding check` prints the list. Until the covers are signed, a clean draft leaves one row for each draft cover, which waits on a person's signature, and rows a person has to decide. A claim that does not match its page keeps its own row, so fix it before handing over. Then run `finding eval <folder>`, which plants errors in memory and shows what the check would catch and what a person still has to read for. A figure in the right sentence that is wrong but sits on the cited page ties, so a reviewer reads each sentence against its page.
