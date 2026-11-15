# Plan MRA-PAM-05

One row per milestone. Start each Milestone cell with its id, such as M1. Committed dates are
YYYY-MM-DD, and the Evidence cell lists evidence ids separated by commas, such as EV-03, EV-04.
Put (done) after the file whose date is the milestone's, the one that completes it, as in EV-04 (done).

| Milestone | Owner role | Committed date | What is true when done | Evidence | Internal audit will test |
|---|---|---|---|---|---|
| M1 Revise and approve the access management standard | Chief Information Security Officer | 2026-03-31 | Version 4.0 of the access management standard is approved by the Board Risk Committee and issued, requiring leaver access removal within one business day, quarterly privileged access reviews, and rules for orphaned accounts | EV-01 (done), EV-02 | The approved standard matches the version published and in effect across the bank |
| M2 Automate leaver notices; remove every leaver's access | Head of Identity Services | 2026-04-30 | Automated leaver notices from the HR system to the identity tool run each business day, and access for every employee and contractor leaver is removed within one business day of leaving | EV-04, EV-05, EV-06 (done), EV-07, EV-14, EV-18 | A sample of leavers after the effective date had their access removed within one business day |
| M3 Remove or assign an owner to every orphaned account | Head of Infrastructure | 2026-05-31 | Every orphaned privileged account identified in the baseline is removed or assigned to a named owner, with the outcomes recorded in a signed clean-up report | EV-08, EV-09 (done) | The outcome figures are recomputed from the baseline extract and a sample of removed and assigned accounts is verified |
| M4 Train reviewers; complete the first quarterly review | Head of Identity Services | 2026-06-30 | All privileged access reviewers are trained before the review window, and the first quarterly review of privileged access across in-scope platforms is completed with revocations actioned | EV-03, EV-10, EV-11, EV-12 (done), EV-13, EV-19 | A sample of privileged accounts in the review is checked for reviewer completion, training prior to review, and timely revocation |
| M5 Extend the quarterly review to the cloud hosting platform | Head of Cloud Engineering | 2026-09-30 | The quarterly privileged access review is extended to include the cloud hosting platform, with reviewer decisions recorded and any revocations completed | EV-15, EV-21 (done) | A sample of cloud hosting platform privileged accounts included in the quarterly review is checked for review decisions and timely revocations |

## Source of owners and committed dates

- M1 owner role (Chief Information Security Officer) and committed date (2026-03-31): board minutes E-PLAN-1, page 2 (Item 4).
- M2 owner role (Head of Identity Services) and committed date (2026-04-30): board minutes E-PLAN-1, page 2 (Item 4).
- M3 owner role (Head of Infrastructure) and committed date (2026-05-31): board minutes E-PLAN-1, page 2 (Item 4).
- M4 owner role (Head of Identity Services) and committed date (2026-06-30): board minutes E-PLAN-1, page 2 (Item 4).
- M5 owner role (Head of Cloud Engineering) and committed date (2026-09-30): board minutes E-PLAN-1, page 4 (Item 9 amendment).

## Coverage of Cause sentences

- "The access management standard set no deadline for removing a leaver's access.": answered by M1 (revised access management standard sets a deadline of one business day).
- "The HR system did not tell the identity team when an employee left, and contractor leavers were reported by email when someone remembered.": answered by M2 (automated HR leaver feed and contractor notification procedure).
- "No one reviewed privileged access on a schedule, and the people who would review it were never trained.": answered by M1 (standard requires quarterly privileged access reviews), M4 (reviewer training and first quarterly privileged access review), and M5 (quarterly review extended to the cloud hosting platform).

## Coverage of Corrective action sentences

- Corrective action sentence: "The bank must revise its access management standard to set a deadline for removing a leaver's access and to require a quarterly review of privileged access; automate leaver notices from the HR system and remove the access of every leaver, employee or contractor, within one business day; remove, or assign a named owner to, every privileged account that has none; train every reviewer before they review and complete a first quarterly review of privileged access; and extend the quarterly review to the cloud hosting platform.": answered across milestones M1, M2, M3, M4, and M5 as follows:
  - "The bank must revise its access management standard to set a deadline for removing a leaver's access and to require a quarterly review of privileged access": answered by M1.
  - "automate leaver notices from the HR system and remove the access of every leaver, employee or contractor, within one business day": answered by M2.
  - "remove, or assign a named owner to, every privileged account that has none": answered by M3.
  - "train every reviewer before they review and complete a first quarterly review of privileged access": answered by M4.
  - "and extend the quarterly review to the cloud hosting platform.": answered by M5.

## Notes and questions for the finding owner

- Duplicate board minutes: `evidence/E-PLAN-1 Board minutes 2026-02-12 (1).pdf` and `evidence/E-PLAN-1 Board minutes 2026-02-12.pdf` hold identical bytes. Move the duplicate copy out of the finding folder before running `finding check`, or keep both and note the reason if already recorded.
- Evidence file naming: `evidence/CHG-2026-04417 HR leaver feed go-live record.pdf` starts with the bank's internal change record ID rather than an evidence ID. It should be renamed to `EV-04 CHG-2026-04417 HR leaver feed go-live record.pdf` so `finding covers` can draft its cover under the EV-04 ID assigned in M2.
- Reserved evidence ID: Evidence ID EV-21 is reserved with `(done)` for M5 to represent the future completion report of the privileged access review extended to the cloud hosting platform.
- Supporting evidence files: `EV-20 Board Risk Committee terms of reference.pdf` is present in evidence/ as supporting governance authority for BRC's approval of standards, and `EV-16` / `EV-17` provide status updates on M5 and exception EXC-2026-014. They are not listed in milestone evidence cells because they do not complete milestones, but remain available in the folder to support memo cites. Should any of these be formally listed in the milestone table?
