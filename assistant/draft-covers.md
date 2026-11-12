# Draft the covers

Goal: give each evidence file its header, so the check can count it and read it.

Reads: each file in evidence/, whose name starts with its evidence id and keeps the bank's name after it, as in `EV-07 TM Alert Backlog MI - Mar 2026 v2 FINAL.xlsx`. The id is one plan.md lists, E-PLAN-1 for the board's minutes, or an EV id. Run `finding covers <folder>` first. It reads each PDF, Word file, Excel workbook, CSV, plain text file and email saved as .eml, writes a draft cover beside each one, and says which pages have no text. A file type it has no reader for, such as an Outlook .msg, gets a cover that says its pages are typed by a person. So does a file it refuses, such as a Word file that still holds tracked changes, and the cover's Source line gives the reason. A file whose name starts with any other id, such as the bank's reference number, gets no draft cover, and nor do two files under one id. The screen names each one.

Writes: the What and For lines of each cover, in a file beside the document named with `.md` added:

```text
What: EV-12 Quality review of reclassified complaints
For: M3 EV-12
Signed by:
Status: DRAFT
Source: read from the document by the check
```

## Rules

- What says what the document is, in the document's own words. Keep the evidence id first.
- For holds the milestone and ends in the evidence id. The id is the last word on the line, and memo cites use it.
- [finding/README.md](../finding/README.md#the-folder) says in one place when a cover takes Signed by, Produced by, Approved by or Never signed. The rules below say how a person fills each.
- Leave Signed by empty and Status at DRAFT. A person who has seen the signature types `Signed by: Head of Complaints, 2026-03-14` and sets `Status: FINAL`. An assistant never does.
- System output, such as a monthly MI workbook, a system aging report or a data extract, comes from a system as at a date. A person who has confirmed its as-at date replaces the Signed by line with `Produced by: case manager aging report, 2026-04-30`, naming the system or report that produced it, and sets `Status: FINAL`. The file then counts on that date, and the page says it was produced by that system with no signature. Never use the line for a document someone should sign, such as an attestation, minutes, a policy or a report a person issues, and an assistant never types it.
- A bank approves some documents by a separate record, such as a QA method approved by email, a lookback method approved on a signed sheet or an MI pack accepted in a resolved minute. Such a document's cover takes `Approved by: EV-29` in place of the Signed by line, naming the approving record's evidence id. Never type the approver's role and date onto the document's own cover, because the document's pages do not show them. Give the approving record its own cover, signed by the role that approved on the date it approved. An approval email, for one, is signed by its sender on the date sent. The document then counts on that record's date, the page names the record beside it, and a record that is missing, unsigned or changed leaves the document unsigned. A person types the line, and an assistant never does.
- Banks never sign material such as a training deck, a quick reference card, a board MI pack, a file copy of a letter or an email that approves nothing. Such a file's cover takes `Never signed: training deck` in place of the Signed by line, with a few words of what it is, and `Status: FINAL`. Its ties count, and it never counts toward a milestone, so the milestone still needs the file that shows it done, such as a signed completion report. Never use the line for a document someone should sign, and never to clear a draft row on a file that is waiting for its signature. A person types the line, and an assistant never does.
- When the covers screen names two files that hold the same bytes, such as a scan saved under a second name, keep one in evidence/ and move the other out of the finding folder before the first check. Say which file went and why in a note below the table in plan.md. Once a check has seen both, keep both and give the reason in the same place, because every later check names a file a check recorded that is gone.
- A later revision goes in as `Revised: 2026-04-02`, and the check then treats the file as unsigned until it is signed again, whether or not a milestone lists it.
- A page with no text is a scan, even when the scan carries a machine text layer, which the check leaves out. A page read only in part, such as a stamped scan, is typed the same way. Ask a person to type that page, or each cited page of a file the check has no reader for, under a heading such as `## Page 7`, and to add `Checked by: role, date` when a second person has compared it. That line goes with the other header lines at the top of the cover, above the blank line and the comment, because a Checked by line below them is not read. The page will say that the tie rests on typed text. Typing a page leaves the cover's signature as it is, because the Checked by line answers for the typed pages. So type only the pages the memo cites, once it cites them. A page typed or changed after a check has seen the cover is a change. The second person compares it and dates the Checked by line on or after the day of the check that first sees the change, and until then the ties on that page wait.

## Passing

`finding check` lists no file under "Not counted". It also names each page the memo cites that has no text and nothing typed, such as `EV-12 page 2 has no text and nothing typed.`, on the signed page too, so a person can see what the check could not read. Both `finding covers` and `finding check` name two files with the same bytes, such as a scan saved under a second name. The engagement team deals with them as the rule above says.
