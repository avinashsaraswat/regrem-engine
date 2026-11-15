# Trap rulings, agent run 02, with reasons

The key opened on 2026-11-14 at 20:55 EST. A reviewer agent in a fresh context, holding no seat, then read key/KEY.md, key/traps.json and build/generate.py. It proposed a ruling for each trap from the seat of a remediation reviewer reading a closure memo before it goes to the supervisor. Real means a competent reviewer must catch it. Trivial means the case holds the error but repeating it changes no milestone's status, no conclusion and nothing the supervisor would act on. Wrong means the key is mistaken. The owner adopted all twelve proposals, and trap-rulings.tsv holds them. The assistant session had proposed T01, T02 and T04 as real, since in each the memo would cite a page that does not hold its figure or date.

| Trap | Ruling | The reviewer agent's reason |
|---|---|---|
| T01 | trivial | The approval email's 348 is a slip for the 384 the workbook and the sample test both show, and repeating it changes no pass rate, no milestone status and nothing the supervisor would act on. |
| T02 | trivial | The deck's 2026-03-02 falls before the pilot and before the deck's own date, and either date puts the main session ahead of the review window that opened 2026-04-07, so the trained-before-review conclusion is unchanged. |
| T03 | real | The clean-up report misquotes the standard as 90 days when section 6.2 says 120, so a memo repeating it misstates the institution's own rule and turns a 91-day clean-up into a false breach or a false claim of compliance. |
| T04 | trivial | The email says 64 cloud privileged accounts and the status report says 54, but M5 is in progress either way and the email itself says the inventory is still unconfirmed. |
| T05 | real | The board committed M3 for 2026-05-31, and the status report's swapped 2026-06-30 would make a clean-up report signed on 2026-06-05 look on time when it was signed after the committed date. |
| T06 | trivial | The test report gives the approval as 2026-05-06 and the email is dated 2026-05-08, but both fall after M2's committed date of 2026-04-30 and nothing in the case turns on those two days. |
| T07 | real | The review report says it followed method version 2.4 of 2026-04-01, and the only approved version in the folder is 2.3, so a memo cannot say the review followed an approved method. |
| T08 | real | The signed clean-up report says every team was briefed before assigning any owner, yet the only briefing on record is 2026-04-14 and the extract shows at least 20 of 83 assignments before it. |
| T09 | real | The status report tells the committee that 100% of leavers were removed in one business day when the workbook shows 23 late out of 1,135, and M2 promised every leaver. |
| T10 | real | The run log is headed UAT, a test environment, and its first-run count of 48 does not match the live backlog of 136, so it cannot show the live feed ran each day. |
| T11 | real | The break-glass exception was approved 2026-01-05 for 90 days and so ended 2026-04-05, two days before the review opened, which leaves the nine most powerful accounts unreviewed with no valid exception while the sign-off claims compliance with section 5. |
| T12 | real | The 98.0% figure times only the disabling of the directory account, while accounts on platforms outside the directory are removed by untimed tasks, so it does not show that leavers' access was removed in one business day. |

The decoys, which the reviewer agent found sound:

- D01: the 240 is recorded as an estimate that the end-of-February baseline would confirm, and the baseline then found 214.
- D02: approved 2026-03-31 for 90 days, the exception ran to 2026-06-29 and covered the whole review window, 2026-04-07 to 2026-04-17.
- D03: 621 is March plus April, 237 and 384, and 1,372 is the total to 2026-06-30, so the two figures agree.

The reviewer agent's notes on the key:

- T08 is the weakest of the traps ruled real. The false statement sits on EV-08 p2, while the key's page is EV-11 p3, where 2026-04-14 is a true date, and the listed true value 2026-03-09 is the first assignment. A catch that cites EV-08 p2 would be fair.
- D02: the cloud platform stays out of review from 2026-03-31 to about 2026-09-17 under two back-to-back 90-day exceptions, the second recorded only in an unsigned email from the requester. A finding on that stacking is fair, and it would name EV-12 p2 and EXC-2026-011 and score as a false alarm.
- T09: the report says "100% of leavers", and with contractors counted the true share is 1,289 of 1,312, about 98.2%. A finding that gives 98.2% or only the 23 late leavers is a real catch.
- T10: KEY.md says the change record gives the live backlog of 136. As built, the change record gives no figure, and 136 is on EV-05 p2 and EV-16 p1.
- T06: the key's reason, that M2's date follows from the email, does not make it material, since both dates miss 2026-04-30.
