# Drafting procedures for an AI assistant

RegRem Engine checks the proof and an AI assistant the bank allows drafts it. These pages are the written procedure for each drafting job, one page a job, written for any assistant and naming none. Give the assistant the page and the finding folder, then run the check on what it wrote. Commands run from the kit root, and `finding` stands for `finding/finding`, or `py -I finding\finding.py` on Windows.

| Job | Page | What it writes | What it has to pass |
|---|---|---|---|
| Turn the letter into a plan | [draft-plan.md](draft-plan.md) | plan.md | `finding check` prints no "Not ready" line |
| Describe each evidence file | [draft-covers.md](draft-covers.md) | the What and For lines of each cover | `finding check` counts every file |
| Draft the closure memo | [draft-memo.md](draft-memo.md) | closure/memo.md | every row on the list gets a person's ruling or a fix |
| Propose a ruling for each row | [propose-rulings.md](propose-rulings.md) | closure/proposed-rulings.md | a person copies the ones they accept |
| Answer internal audit's questions | [answer-audit.md](answer-audit.md) | a draft answer outside the record | each answer cites the folder |

## The rules for every job

1. The assistant drafts, and a person decides. It never types a Signed by, Produced by, Approved by, Never signed or Status line, never writes closure/rulings.md or closure/record.md, and never runs `finding sign`.
2. It works only inside the finding folder, on a machine and a service the bank has approved for that information. If the bank allows no assistant for a supervisory finding, a person does these jobs by hand, and the check works the same.
3. It copies nothing from the finding folder to anywhere outside it.
4. Every figure, date and quotation it writes carries a cite to the page it came from, in digits and full dates so the check can read it. A claim it cannot cite goes in as a question for a person.
5. The check reads what it wrote and gives the same answer every run. Run `finding check` after every job. Until a person signs the covers, each draft cover is one row saying how many claims match its pages, so read the other rows as the test of the draft: a claim that does not match keeps its own row, and the assistant fixes it or asks. Once the covers are signed, the whole list is the test. Run `finding eval` when the memo is ready, because it plants errors in the claims that match a draft's pages too. A wrong figure that sits on the cited page still ties, so a person reads each sentence against its page.

## How these pages improve

A miss a reviewer catches can become two things. One is a change to the procedure page, written in general terms. The other is an invented case in [library/cases](../library/README.md), which every later release has to pass. Neither carries anything from a bank's folder, and [CONTRIBUTING.md](../CONTRIBUTING.md) says how to propose one.
