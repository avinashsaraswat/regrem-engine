# Draft the plan

Goal: turn the Supervisor's letter into plan.md, one row per milestone, for the finding owner to correct.

Reads: finding.md, the letter as pasted, with its five parts: Concern, Cause, Consequence, Corrective action, Commitment. Also the board minutes E-PLAN-1 or the financial institution's written answer if the folder holds them, read to the last page, because a later page may amend an owner or a date.

Writes: rows in the table in plan.md, under its header row. Leave the header row as it is. Each row has six cells:

```text
| M1 Short name of the milestone | Owner role | 2026-02-28 | What is true when done | EV-03, EV-04 (done) | What internal audit will test |
```

## Rules

- Start each milestone with its id, M1, M2 and so on. Keep each to one thing a person can show evidence for.
- Use a date from the letter or the institution's written answer. If the letter gives no date for a step, write the date as a question below the table for the finding owner, and leave the row out until there is one.
- The check does not compare plan.md with the minutes or the institution's answer, so a wrong owner or date passes it. Take each owner and date from the latest page that sets it, and name that page in a line under the table.
- Use a role in the owner cell. A person's name in a cell can trip the deny list and must never leave the institution.
- Number the evidence ids and keep them stable. Later covers and memo cites use the same ids.
- List every file that shows the milestone done in its Evidence cell, the file that completes it included, such as a lookback's final report. A file that does not exist yet gets an evidence id now, kept for it, such as EV-61. The check keeps the milestone unsigned while that file is missing. A row that lists only the methodology and its approval reads as signed once those two are, however much of the work is left.
- Mark the file that completes the milestone with `(done)` after its id, as in `EV-60, EV-61 (done)`, and reserve that id with its mark before the file exists. Mark one file a row. The milestone's date and its lateness then come from that file, such as a training roster's last completion date. Every other file the row lists still has to be signed. Without the mark, a report signed three days after the work ended makes the milestone read three days later than all the institution's papers say. Keep every file that shows the milestone done in its Evidence cell, and let the mark set the date.
- Answer every sentence of the Cause and Corrective action. Under the table, write one line per sentence naming its milestone or the reason it needs none, so the owner can see nothing was dropped.
- Write what internal audit will test as something a person can test: a sample, a recomputation, a comparison.
- Never say the finding is closed. Until the record holds the issuer's entry, such a line is a row on the list that stops the signature, and no ruling clears it, so it has to be reworded. Any other use of the word closed goes on the list for the owner to rule on.

## Passing

`finding check` prints no "Not ready" line. The screen shows the plan's dates marked proposed until the board's minutes, E-PLAN-1, are signed. The finding owner corrects the rows, and the board approves.
