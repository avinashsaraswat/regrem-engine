# Propose a ruling for each row on the list

Goal: give the finding owner a short sheet for the Tuesday meeting, one proposal per row on the list.

Reads: the rows on the list from `finding check`, and the cited pages.

Writes: closure/proposed-rulings.md, which the check ignores. Never closure/rulings.md: a line there can take a row off the list, and that is the owner's act.

```text
Line 16 | sample period for M2 #106ddd50 | fix the evidence | Head of Complaints | YYYY-MM-DD | The sample starts before the fix took effect, so split it at the fix date.
```

## Rules

- Propose one of three: `cleared`, `fix the memo` or `fix the evidence`.
- Propose `cleared` only when the page supports the memo and the check could not see why, such as a figure the page writes in words. Give the reason in one sentence a stranger could check.
- Propose `fix the memo` when the memo is wrong, with the right figure and its page. Never propose `cleared` for a wrong figure. The tool would accept it, so this rule is yours and the owner's to keep.
- Propose `fix the evidence` when the document has to change or be signed again.
- Keep the second cell exactly as the row prints it after "To rule, name:", such as `1,248 #972adb19` or `sample period for M2 #106ddd50`. The mark after the # stands for the claim, its cite and its sentence, so a ruling clears that claim and no other. It follows the claim if the memo moves. Change the sentence or the cite and the row returns to the list with a new mark.
- The fourth cell is the owner's role. Write the fifth as YYYY-MM-DD, and the owner types the date on accepting the line.
- A draft cover has one row for the claims that match its pages, such as `EV-12 draft #81b3b231`. A claim that does not match keeps its own row. The usual answer is `fix the evidence`, because a person still has to sign the file. For system output, such as an MI workbook or a system report, the fix is a person confirming its as-at date on a Produced by line. For a document approved by a separate record, it is an Approved by line naming that record. For material the bank never signs, such as a training deck, it is a Never signed line. Never propose clearing a value that ties only to end a draft row.
- A row that asks for a page to be typed, which says `Type it into the cover under ## Page 1.`, is answered by typing that page into the cover, with a second person's Checked by line, and never by a ruling. The sheet names the page to type and proposes no ruling for that row.

## Passing

The finding owner or an associate acting for them copies an accepted line into closure/rulings.md with the date of the ruling, and the owner signs over it at the end. The sign screen prints every cleared row with its reason. A ruling of `fix the memo` stays in the file after the row is gone, which is the record that the check caught it.
