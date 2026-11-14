# Cross-read the closure memo

Goal: give the finding owner a list of the problems in closure/memo.md, found by a reader who wrote no part of it. The owner reads each one against its pages and rules.

Who: an agent that wrote no part of the memo and has seen nothing of how it was drafted. `docs/weekly-run.md` in the kit asks that of the reviewer. The finding owner stays the named reviewer, and this pass is called a cross-read.

Reads: finding.md, plan.md, each cover and each document in evidence/, each to its last page, then closure/memo.md. It is handed no check page and no eval output, and it reads neither closure/rulings.md nor closure/proposed-rulings.md, so its list stands on its own. It reads nothing outside the finding folder apart from the kit's pages and this page.

Writes: findings.tsv in its output folder, which sits outside the finding folder. The file is plain UTF-8 text. Its first line is the header below, and each later line holds one finding in four fields, separated by one tab character:

```text
memo line	cite	value seen	problem
<line number>	<the cite as the memo writes it>	<the memo's figure, date or words>	<one sentence on what the folder shows>
```

- The memo line is the number of the line in closure/memo.md, counting from 1 with blank lines included.
- The cite is the cite of the sentence the finding is about, exactly as the memo writes it with its square brackets. It is `none` when the sentence has no cite.
- The value seen is the figure, date or words in the memo that the finding is about, copied character for character. It is `none` when the problem is something the memo leaves out.
- The problem is one sentence a stranger could check against the folder.

A field holds no tab and no line break. When the reader finds no problem, the file holds the header line and nothing else.

This file sits outside the finding folder, and rule 3 of `assistant/README.md` forbids that on a real finding, where the file stays inside the folder. The run that carries this page uses an invented case that is published whole, and its protocol names this as its one departure from the assistant/ rules.

## Steps

1. Read finding.md and plan.md, so you know what each milestone has to show and by when.
2. Read every document in evidence/ with its cover, each to its last page, before you read the memo, because a later page may amend an earlier one.
3. Read every sentence of the memo against its cited page. Open the page the cite names and check each figure, date and quotation on it, and check that the page shows what the sentence says it shows. A figure, date or quotation with no cite is a finding.
4. Read the evidence as a whole, then read the memo against it. The check reads each claim against its own cite only, so it cannot see what two pages show only when read together. Read for the five things listed in step 7 of `docs/internal-audit.md` in the kit. Read also for any place where the memo says more than the folder shows, or differs from it.
5. Write findings.tsv.

## Rules

- Write one line for each problem, on the memo line where the problem sits. A problem that runs across several memo lines gets a line for each of them.
- Copy the value seen from the memo character for character, with its commas, spaces and quotation marks.
- In the problem, name every page the problem rests on as a cite in the memo's form, with its evidence id and page number in square brackets. Give the figure, date or words that page holds.
- Write a finding wherever the folder contradicts a sentence or fails to support it. Say only what the folder shows. Propose no ruling, no rewording and no fix.
- Change nothing in the finding folder. The memo, the plan and the covers stay as they are, and the drafter makes any fix later.
- Never sign and never rule. Never type a Signed by, Produced by, Approved by, Never signed, Checked by or Status line, never write inside closure/rulings.md or closure/record.md, and never run `finding sign`.
- Copy nothing from the finding folder anywhere except findings.tsv.

## Passing

The run reads findings.tsv and names any line it cannot read, and such a line counts as no finding. The finding owner reads each finding against its page and decides what it means. Nothing in the file clears a row on the list or adds one, because only the owner's rulings and the memo's fixes change the list.
