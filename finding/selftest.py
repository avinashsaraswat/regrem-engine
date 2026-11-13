"""Self-test for the finding tool, run on invented cases.

Purpose: build the two invented cases from the spec in a temporary folder (MRA-CMP-07, a
  supervisory finding, and IA-CMP-02, an internal audit finding, each the shipped files byte for
  byte), then check `new`, the usage exits, the MRA-CMP-07 screen byte for byte, the flags on
  other dates, the proposed plan, the refusals, the evidence states, the state file, the
  memo check and its rulings, `sign` (at no terminal, at a pseudo-terminal on posix, and with a
  stand-in terminal for its refusals), and the signature fingerprint and "changed since signing".
  When the shipped cases under cases/ are present, temporary copies of them are checked too: the
  same screens, and each shipped state file against a fresh recompute. Last, a whole copy of the kit
  with a changed tool file, marked a site version, runs this self-test again and must pass.
Reads: finding.py, tieout/ through it, cases/ when it is present, and the documentation pages
  when they are present. A copy brought in without the pages skips each check that reads one and says how many.
Writes: temporary folders only, removed at the end.
Network: none.
Exit codes: 0 when every expectation holds, 1 when an expectation fails.
"""
import ast
import contextlib
import datetime
import io
import json
import os
import re
import select
import shutil
import subprocess
import sys
import tempfile
import time
import tracemalloc
import zipfile
import zlib
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import finding  # noqa: E402

CASES = HERE / "cases"
SYN = "SYNTHETIC. Everything in this folder is invented."
NETWORK_FREE = ("finding/documents.py", "finding/finding.py", "finding/release.py", "tieout/claims.py",
                "tieout/docx_reader.py", "tieout/record.py", "tieout/verify.py", "tieout/words.py")
# The only modules the kit's own files may import: the standard library modules they use today and the kit's own.
# One fixed list, so the same check runs on every Python. A new import is a deliberate one-line change here.
ALLOWED_IMPORTS = {
    "argparse", "ast", "base64", "bisect", "csv", "datetime", "decimal", "email", "hashlib", "html", "io", "json",
    "math", "os", "pathlib", "re", "shutil", "sys", "tempfile", "unicodedata", "xml", "zipfile", "zlib",
    "claims", "docx_reader", "documents", "finding", "record", "verify", "words",
}
# Calls that import by name or start a process, which no import list can see.
BANNED_CALLS = {"__import__", "eval", "exec"}
BANNED_OS = re.compile(r"^(?:system|popen|fork|forkpty|posix_spawnp?|exec\w*|spawn\w*)$")
NOW = "2026-11-04"

EXPECTED_MRA = """\
This folder may hold confidential supervisory information. Keep it on a machine the institution has approved, and share nothing from it outside the institution.

Finding MRA-CMP-07, a supervisory finding from the Supervisor dated 2026-01-15. Owner: Head of Complaints. Checked as of 2026-11-04, kit release KITRELEASE.

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

Commitment table, the institution's response in the Supervisor's five-part form, from plan.md
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
"""

MRA_ROWS_WITHOUT_RULINGS = """\
Memo check: 13 claims, 7 tie, 4 on the list.
  Line 8: March 2026 is cited to EV-07 p2, and the page holds no date. To rule, name: March 2026 #f2ba27f8
  Line 8: 1,248 is cited to EV-07 p2, and the page does not hold it; the nearest figures on the page are 1,284 and 2. To rule, name: 1,248 #972adb19
  Line 10: EV-12, which is a draft, holds 4 claims, on lines 10, 15 and 16, that match its pages and wait on a person's signature. To rule, name: EV-12 draft #81b3b231
  Line 16: the sample period for M2 starts 2026-01-05, before the fix took effect on 2026-03-17, so the sample mixes items from before and after the fix. To rule, name: sample period for M2 #106ddd50
  7 ties rest on text a person typed: 7 in plain-text evidence, none on a page typed into a cover.
  Not checked: 1 figure written in words, line 6 (three).
Signature: none yet.
"""

EXPECTED_IA_TAIL = """\
Supervisor closure: not applicable to an internal audit finding.
Board approval: BM-2026-07 dated 2026-07-08, recorded by the Company Secretary.
Memo check: 13 claims, 13 tie, 0 on the list.
  13 ties rest on text a person typed: 13 in plain-text evidence, none on a page typed into a cover.
  Not checked: 2 figures written in words, line 6 (five) and line 8 (five).
Signature: none yet.
Deny list: 3 names.

Needs a person:
  Head of Complaints: the signature, which comes first.
"""

MRA_FILES = {
    "finding.md": SYN + """
# Finding MRA-CMP-07
Identifier: MRA-CMP-07
Institution: Wrenfield Example Bank
Issuer: the Supervisor
Letter date: 2026-01-15
Kind of matter: supervisory finding
Owner role: Head of Complaints

## Concern

The bank does not classify customer complaints consistently. In the second half of 2025, complaints that asked for a fee reversal were often logged as service issues. Those complaints missed the fee-review queue and were left out of the fee lines in complaint trend reports to the board.

## Cause

The complaint taxonomy had no category for fee disputes. The intake procedure gave staff no rule for a complaint that mentions a fee, so each handler chose a category. No one reviewed the quality of complaint classification after intake.

## Consequence

The board and senior management received complaint trend reports that understated fee complaints. Customers with valid fee disputes waited longer for an answer, and some may not have received a refund they were owed.

## Corrective action

The bank must revise the complaint taxonomy to cover fee disputes, reissue the intake procedure with a rule for fee complaints and train intake staff on it, test classification quality on the complaints it reclassifies, and extend the taxonomy to every channel through which customers complain.

## Commitment

The bank must send the Supervisor a written remediation plan approved by its board within 30 days of this letter, with an owner role and a committed date for each action. The Supervisor will consider the matter for closure only after internal audit has tested the remediation.
""",
    "plan.md": SYN + """
# Plan MRA-CMP-07

| Milestone | Owner role | Committed date | What is true when done | Evidence | Internal audit will test |
|---|---|---|---|---|---|
| M1 Approve revised complaint taxonomy | Head of Complaints | 2026-02-28 | The taxonomy has a fee dispute category and the committee has approved it | EV-03, EV-04 | The approved taxonomy matches the version in use in the complaint system |
| M2 Reissue intake procedure | Head of Complaints | 2026-03-15 | Version 3 of the intake procedure routes fee complaints to the fee-review queue and every intake handler is trained on it | EV-07, EV-08 | A sample of complaints logged after the effective date follows the fee rule |
| M3 Quality review of reclassified complaints | Complaints QA lead | 2026-04-30 | A signed quality review of a random sample of reclassified complaints, with the error rate and its causes | EV-12 | The sample was random and the error rate is recomputed from the sample |
| M4 Extend taxonomy to the mobile app chat channel | Head of Digital | 2026-06-30 | Complaints received through the mobile app chat channel are logged and classified against the taxonomy | EV-15 | A sample of chat complaints is logged within one business day and classified correctly |
""",
    "evidence/E-PLAN-1-board-minutes.md": SYN + """
What: E-PLAN-1 Board minutes approving the remediation plan
For: PLAN E-PLAN-1
Signed by: Company Secretary, 2026-02-10
Status: FINAL

The board approved the remediation plan for MRA-CMP-07 with the dates in plan.md.
""",
    "evidence/EV-03-complaint-taxonomy.md": SYN + """
What: EV-03 Complaint taxonomy, revision 4
For: M1 EV-03
Signed by: Head of Complaints, 2026-02-20
Status: FINAL

# EV-03 Complaint taxonomy, revision 4

## Page 1

Purpose: every complaint is classified into one category and one subcategory at intake.

Change from revision 3: a new category, fee dispute, with three subcategories.

- Fee reversal request: the customer asks for a fee to be refunded.
- Fee disclosure: the customer says a fee was not explained before it was charged.
- Fee charged in error: the customer says a fee was applied to the wrong account or twice.

A complaint that mentions a fee and a service failure is classified as a fee dispute first. The service failure is recorded as a secondary tag.

## Page 2

Scope: phone, branch and web complaints. The mobile app chat channel is out of scope for this revision.

Approval: approved by the Operational Risk Committee on 2026-02-20 (see EV-04). Signature: the Head of Complaints, on 2026-02-20.
""",
    "evidence/EV-04-committee-minutes.md": SYN + """
What: EV-04 Operational Risk Committee minutes, meeting of 2026-02-20
For: M1 EV-04
Signed by: Operational Risk Committee chair, 2026-02-20
Status: FINAL

# EV-04 Operational Risk Committee minutes

## Page 1

Meeting of 2026-02-20. Present, by role: the committee chair, the Chief Risk Officer, the Head of Complaints, the Head of Digital and the Company Secretary.

Item 3, complaint taxonomy. The Head of Complaints presented revision 4 of the complaint taxonomy (EV-03), which adds a fee dispute category. The committee approved revision 4 with effect from 2026-02-20 and asked the Head of Digital to bring a plan for the mobile app chat channel to a later meeting.
""",
    "evidence/EV-07-intake-procedure.md": SYN + """
What: EV-07 Complaint intake procedure, version 3
For: M2 EV-07
Signed by: Head of Complaints, 2026-03-14
Status: FINAL

# EV-07 Complaint intake procedure, version 3

## Page 1

Owner: Head of Complaints. Signed 2026-03-14.

Scope: every customer complaint received by phone, branch or web is logged in the complaint system within one business day and classified against the complaint taxonomy approved by the Operational Risk Committee.

## Page 2

Change from version 2: complaints that mention a fee reversal are now routed to the fee-review queue before classification. Between January and March the team reclassified 1,284 complaints that version 2 had logged as service issues.

Open item: the taxonomy does not yet cover complaints received through the mobile app chat channel.
""",
    "evidence/EV-08-training-register.md": SYN + """
What: EV-08 Intake procedure training register, version 3
For: M2 EV-08
Signed by: Head of Complaints, 2026-03-14
Status: FINAL
Revised: 2026-04-02

# EV-08 Intake procedure training register, version 3

## Page 1

Intake handlers in scope: 48. Trained on version 3 of the intake procedure by 2026-03-13: 46. Not yet trained: 2, both on leave.

Training covered the fee dispute category, the fee rule and the fee-review queue. Each handler passed a ten-question check.

Signature: the Head of Complaints, on 2026-03-14.

## Page 2

Revision of 2026-04-02: the 2 remaining handlers completed training on 2026-03-30 and 2026-04-01. The register now shows 48 of 48 trained. This revision has not been signed.
""",
    "evidence/EV-12-quality-review.md": SYN + """
What: EV-12 Quality review results, first quarter
For: M3 EV-12
Signed by: none
Status: DRAFT

# EV-12 Quality review results, first quarter

## Page 1

Prepared by the Complaints QA lead. Draft, not signed.

Method: 240 complaints drawn at random from the complaints reclassified between 2026-01-05 and 2026-03-31. A second reviewer classified each one against revision 4 of the taxonomy without seeing the first classification.

## Page 2

Sample: 240 complaints. Misclassified: 31, a rate of 12.9 percent. Most misclassifications were fee complaints logged as service issues before the version 3 procedure took effect on 2026-03-17.
""",
    "closure/memo.md": SYN + """
# Closure memo MRA-CMP-07

This memo is a draft for the Head of Complaints. It records the evidence held for each milestone so far. M2, M3 and M4 still lack signed evidence, so the memo is not ready for internal audit.

M1, the complaint taxonomy. The revised taxonomy adds a fee dispute category with three subcategories [EV-03 p1]. A complaint that mentions a fee and a service failure is "classified as a fee dispute first" [EV-03 p1]. The Operational Risk Committee approved the revision on 2026-02-20 [EV-04 p1], and the Head of Complaints signed it on 2026-02-20 [EV-03 p2].

M2, the intake procedure. The reissued procedure routes complaints that mention a fee reversal to the fee-review queue before classification [EV-07 p2]. In March 2026 the team reclassified 1,248 complaints that the earlier procedure had logged as service issues [EV-07 p2]. The Head of Complaints signed the procedure on 2026-03-14 [EV-07 p1]. The training register showed 46 of 48 intake handlers trained when it was signed [EV-08 p1], and it was revised on 2026-04-02 to show every handler trained [EV-08 p2]. That revision needs a fresh signature before M2 counts.

M3, the quality review. The review is still a draft and carries no signature. It found 31 misclassified complaints in its sample [EV-12 p2], most of them fee complaints logged as service issues before the reissued procedure took effect.

M4, the mobile app chat channel. No evidence is held yet. The intake procedure itself lists this channel as an open item [EV-07 p2].

Tested control: M2, the reissued intake procedure
Fix effective: 2026-03-17 [EV-12 p2]
Sample period: 2026-01-05 to 2026-03-31 [EV-12 p1]

Before this memo goes to internal audit, the Head of Complaints needs a re-signed training register, a signed quality review and evidence for M4. Internal audit will then test each milestone against its column in plan.md, and the Supervisor decides the finding.
""",
    "closure/record.md": SYN + """
Internal audit reference:
Internal audit date:
Internal audit recorded by (role):
Supervisor closure notice:
Supervisor closure date:
Supervisor closure recorded by (role):
Board approval reference:
Board approval date:
Board approval recorded by (role):
Signed by (role):
Signed on:
Fingerprint:
""",
    "closure/rulings.md": SYN + """
# Rulings MRA-CMP-07

Line 8 | March 2026 #f2ba27f8 | cleared | Head of Complaints | 2026-11-04 | The page says January to March, and the plan year is 2026.
""",
}

IA_FILES = {
    "finding.md": SYN + """
# Finding IA-CMP-02
Identifier: IA-CMP-02
Institution: Wrenfield Example Bank
Issuer: the Head of Internal Audit
Letter date: 2026-04-10
Kind of matter: internal audit finding
Owner role: Head of Complaints

## Concern

Customers who complain are not told promptly that their complaint has been received. In a sample of complaints from the first quarter of 2026, a quarter of the acknowledgement letters went out more than five business days after the complaint arrived.

## Cause

Acknowledgement letters are prepared by hand from a daily list, and no one owns the list when the usual handler is away. The complaints team does not measure how long acknowledgement takes, so delays are not seen.

## Consequence

Customers who hear nothing tend to complain again or escalate, which adds work and raises the risk of an unfair outcome. The complaints policy promises acknowledgement within five business days, and the bank cannot show that it keeps that promise.

## Corrective action

Management should send every acknowledgement letter within five business days of receipt, with a named owner role and cover for absence, and should report acknowledgement timeliness every month to the Head of Complaints.

## Commitment

Management should agree an action plan with owner roles and committed dates, approved by the board, within 15 business days of this report. Internal audit will validate the actions before it treats the finding as resolved.
""",
    "plan.md": SYN + """
# Plan IA-CMP-02

| Milestone | Owner role | Committed date | What is true when done | Evidence | Internal audit will test |
|---|---|---|---|---|---|
| M1 Send acknowledgement letters within five days | Head of Complaints | 2026-05-31 | The complaint system sends an acknowledgement letter within five business days of receipt, with an owner role and cover for absence | EV-21 | A sample of complaints received after the change was acknowledged within five business days |
| M2 Issue a monthly timeliness report | Complaints QA lead | 2026-06-30 | A monthly report of acknowledgement timeliness goes to the Head of Complaints | EV-22 | The report figures are recomputed from the complaint system for one month |
""",
    "evidence/E-PLAN-1-board-minutes.md": SYN + """
What: E-PLAN-1 Board minutes approving the remediation plan
For: PLAN E-PLAN-1
Signed by: Company Secretary, 2026-04-24
Status: FINAL

The board approved the remediation plan for IA-CMP-02 with the dates in plan.md.
""",
    "evidence/EV-21-acknowledgement-procedure.md": SYN + """
What: EV-21 Acknowledgement letter procedure and May sample
For: M1 EV-21
Signed by: Head of Complaints, 2026-05-28
Status: FINAL

# EV-21 Acknowledgement letter procedure and May sample

## Page 1

From 2026-05-04 the complaint system sends an acknowledgement letter automatically on the business day after a complaint is logged. The complaints operations manager owns the daily exception list of letters that failed to send, and the deputy covers when the manager is away.

## Page 2

Sample: 120 complaints received between 2026-05-04 and 2026-05-22. Acknowledged within five business days: 118, or 98.3 percent. The other 2 were acknowledged on the sixth business day after an address error, and both were fixed from the exception list.

Signature: the Head of Complaints, on 2026-05-28.
""",
    "evidence/EV-22-timeliness-report.md": SYN + """
What: EV-22 Monthly acknowledgement timeliness report, first issue for May 2026
For: M2 EV-22
Signed by: Complaints QA lead, 2026-06-29
Status: FINAL

# EV-22 Monthly acknowledgement timeliness report, first issue

## Page 1

Period: complaints received in May 2026. Complaints received: 410. Acknowledged within five business days: 402, or 98.0 percent. Median time to acknowledgement: 1 business day.

## Page 2

Distribution: the Head of Complaints each month, and the Operational Risk Committee each quarter. The Complaints QA lead prepares the report from the complaint system by the tenth business day of the following month.

Signature: the Complaints QA lead, on 2026-06-29.
""",
    "closure/memo.md": SYN + """
# Closure memo IA-CMP-02

This memo is for internal audit. It sets out the evidence that both milestones in plan.md are done.

M1, acknowledgement letters. Since 2026-05-04 the complaint system sends the acknowledgement letter on the business day after a complaint is logged [EV-21 p1]. An owner role holds the daily exception list, and a deputy covers absence [EV-21 p1]. In a sample of 120 complaints, 118 were acknowledged within five business days, or 98.3 percent [EV-21 p2]. The Head of Complaints signed the procedure and sample on 2026-05-28 [EV-21 p2].

M2, the monthly timeliness report. The first report covers May 2026 [EV-22 p1]. It shows 402 of 410 complaints acknowledged within five business days, or 98.0 percent [EV-22 p1]. It goes to the Head of Complaints each month and to the Operational Risk Committee each quarter [EV-22 p2]. The Complaints QA lead signed it on 2026-06-29 [EV-22 p2].

Tested control: M1, the acknowledgement letter procedure
Fix effective: 2026-05-04 [EV-21 p1]
Sample period: 2026-05-04 to 2026-05-22 [EV-21 p2]

Internal audit can test both milestones against the column in plan.md. Only internal audit decides whether this finding is resolved.
""",
    "closure/record.md": SYN + """
Internal audit reference:
Internal audit date:
Internal audit recorded by (role):
Supervisor closure notice:
Supervisor closure date:
Supervisor closure recorded by (role):
Board approval reference: BM-2026-07
Board approval date: 2026-07-08
Board approval recorded by (role): Company Secretary
Signed by (role):
Signed on:
Fingerprint:
""",
    "closure/rulings.md": SYN + """
# Rulings IA-CMP-02

<!-- One line per row on the list, in this form, with the line number and the words after "To rule, name:" as the screen prints them:
Line 8 | March 2026 #1a2b3c4d | cleared | Head of Complaints | 2026-11-04 | The page says January to March, and the plan year is 2026.
The ruling is cleared, fix the memo or fix the evidence. Only a cleared ruling by the finding owner's role, dated and with a reason, takes a row off the list. -->
""",
}

COUNT = 0
FAILURES = []
SKIPPED = []  # the page checks this run skipped, because their pages are not in this copy of the kit
SITE_RUN = "FINDING_SELFTEST_SITE_COPY"  # set for the run test_site_copy_passes starts, so that run starts no other


def pages(*rels):
    """The text of each documentation page named, from the kit root, or None when one is not in this copy. An institution
    may bring the kit in without its pages, so the check that reads them is skipped, and the run says how many."""
    paths = [HERE.parent / rel for rel in rels]
    if not all(path.is_file() for path in paths):
        SKIPPED.append(", ".join(rels))
        return None
    texts = [path.read_text(encoding="utf-8") for path in paths]
    return texts[0] if len(texts) == 1 else texts


EXPECTED_MRA = EXPECTED_MRA.replace("KITRELEASE", finding.kit_release()[0])


def page_section(text, start):
    """The part of a page from a heading to the next heading of the same level."""
    level = start.split(" ", 1)[0] + " "
    rest = text.split(start, 1)[1] if start in text else ""
    return rest.split("\n" + level, 1)[0]


def test_pages_match_the_tool(root):
    """The pages say what the tool does: what the walk promises, and how the README's commands run."""
    # A file type with no reader gets an honest cover.
    folder = ia(root, "pages-msg")
    (folder / "evidence" / "EV-31-signoff.msg").write_bytes(b"x")
    run(["covers", str(folder)])
    cover = (folder / "evidence" / "EV-31-signoff.msg.md").read_text(encoding="utf-8")
    expect("Source: typed by a person, because the check has no reader for this file type" in cover
           and "read from the document by the check" not in cover and "The check cannot read this file." in cover,
           "a cover for a file type with no reader says its pages are typed", cover)
    found = pages("README.md", "finding/DEMO.md", "assistant/README.md")
    if found is None:
        return
    readme, demo, assistant = found
    # Step 9 of the walk names everything sign asks of the shipped supervisory case.
    copy = root / "pages-mra"
    shutil.copytree(str(CASES / "MRA-CMP-07"), str(copy))
    out = check(copy)[1]
    left = re.search(r"(\d+) on the list", out)
    step9 = page_section(demo, "## 9. Sign")
    expect(left is not None and "Refused: {} rows are on the list; rule on them first.".format(left.group(1)) in step9
           and "approval of closure" in step9 and "March 2026" in step9 and "a cite" in step9,
           "the walk's step 9 names every refusal sign gives on MRA-CMP-07", step9[-600:])
    # Step 14 and step 1 say where the release and the opening line appear.
    lines = out.splitlines()
    expect(lines[2].startswith("Finding ") and "kit release" in lines[2] and "on its first line" not in demo
           and "at the end of its Finding line" in page_section(demo, "## 14. Which release is this"),
           "the walk says the release ends the Finding line", lines[2])
    expect("prints only its refusal" in page_section(demo, "## 1. The line that opens every screen"),
           "the walk says new on a name in use prints only its refusal")
    # The README writes commands as they run from the repository root and explains its fixed date.
    bare = re.findall(r"`finding (?:new|check|sign|covers|eval|size)\b[^`]*`", readme)
    expect(not bare, "the README writes every command as it runs from the repository root", ", ".join(bare))
    expect("--today 2026-11-04" in readme and "The `--today` option fixes the date" in readme,
           "the README says why its dates are fixed")
    expect("`finding` stands for `finding/finding`" in assistant, "assistant/README.md says what the bare finding command stands for")
    # The README names the formats the reader takes and the ones it has no reader for.
    reads = page_section(readme, "## What it reads")
    expect("email saved as .eml" in reads and ".msg" in reads and "no reader for" in reads,
           "the README names the formats the reader takes and the ones it does not", reads[:300])


def expect(condition, label, detail=""):
    global COUNT
    COUNT += 1
    if not condition:
        FAILURES.append(label + (": " + detail if detail else ""))


class StandInTerminal(io.StringIO):
    """Typed answers for sign, read one line at a time, from a stdin that says it is a terminal."""

    def __init__(self, text="", on_line=None):
        io.StringIO.__init__(self, text)
        self.on_line = on_line
        self.lines_read = 0

    def isatty(self):
        return True

    def readline(self, *args):
        self.lines_read += 1
        if self.on_line is not None:
            self.on_line(self.lines_read)
        return io.StringIO.readline(self, *args)


def run(args, cwd=None, stdin=None):
    """Run the tool in this process. Returns (exit code, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    old = os.getcwd()
    old_stdin = sys.stdin
    try:
        if cwd is not None:
            os.chdir(str(cwd))
        if stdin is not None:
            sys.stdin = stdin
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = finding.main(args)
    finally:
        sys.stdin = old_stdin
        os.chdir(old)
    return code, out.getvalue(), err.getvalue()


def check(folder, today=NOW):
    return run(["check", str(folder), "--today", today])


def build(root, name, files, first_check):
    folder = root / name
    for rel, text in files.items():
        path = folder / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        finding.write_text(path, text)
    if first_check:
        check(folder, first_check)
    return folder


def edit(path, old, new):
    text = path.read_text(encoding="utf-8")
    if old not in text:
        raise AssertionError("selftest setup: {!r} not in {}".format(old, path))
    finding.write_text(path, text.replace(old, new, 1))


def state_of(folder):
    return json.loads((folder / finding.STATE_NAME).read_text(encoding="utf-8"))


def refusal(text):
    return finding.CONFIDENTIAL + "\n\n" + text + "\n"


def line_of(screen, prefix):
    for line in screen.splitlines():
        if line.startswith(prefix):
            return line
    return ""


def fresh(root, name, files=None, first_check="2026-02-10"):
    return build(root, name, MRA_FILES if files is None else files, first_check)


def test_new_and_usage(root):
    work = root / "new"
    work.mkdir()
    code, out, _ = run(["new", "MRA-TEST-01"], cwd=work)
    expect(code == 0, "new exits 0", str(code))
    expect(out == "Made MRA-TEST-01. Fill the header lines in finding.md and paste each part of the letter under its "
                  "heading, then fill plan.md.\n",
           "new prints the made line", out)
    made = work / "MRA-TEST-01"
    for rel in ("finding.md", "plan.md", "closure/memo.md", "closure/record.md", "closure/rulings.md", "closure/measures.md"):
        path = made / rel
        expect(path.is_file() and "SYNTHETIC" not in path.read_text(encoding="utf-8"),
               "new writes " + rel + " with no SYNTHETIC line, so a real finding starts with no edit to it")
    values = {"id": "MRA-TEST-01"}
    for rel, template in (("closure/memo.md", finding.TEMPLATE_MEMO),
                          ("closure/record.md", finding.TEMPLATE_RECORD),
                          ("closure/rulings.md", finding.TEMPLATE_RULINGS)):
        path = made / rel
        expect(path.is_file() and path.read_text(encoding="utf-8") == template.format(**values),
               "new writes the " + rel + " template exactly")
    memo = (made / "closure" / "memo.md").read_text(encoding="utf-8")
    expect("[EV-12 p2]" in memo and "Fix effective: 2026-05-04 [EV-21 p1]" in memo
           and "Sample period: 2026-05-04 to 2026-05-22 [EV-21 p2]" in memo and memo.count("Tested control:") == 1,
           "the memo template shows the cite form and the tested-control lines once")
    record = (made / "closure" / "record.md").read_text(encoding="utf-8")
    expect(all(key + ":" in record for key in finding.RECORD_FIELDS),
           "the record template holds every field the check reads")
    expect((made / "evidence").is_dir() and not any((made / "evidence").iterdir()),
           "new makes an empty evidence folder")
    code, out, _ = run(["new", "MRA-TEST-01"], cwd=work)
    expect(code == 1 and out == "Refused: MRA-TEST-01 already exists here.\n", "new refuses a repeat", out)
    code, out, _ = run(["check", str(made), "--today", NOW])
    expect(code == 1 and "Not ready: finding.md has no Institution yet." in out,
           "check on a fresh template says not ready", out)
    expect(not (made / finding.STATE_NAME).exists(), "a not-ready check writes no state file")
    for args, label in (
        (["new", "bad id!"], "new with a bad id"),
        (["new", "-x"], "new with a flag for an id"),
        (["new"], "new with no id"),
        ([], "no command"),
        (["frob"], "an unknown command"),
        (["check", str(made), "--today", "2026-13-01"], "check with a bad date"),
        (["check", str(made), "--today"], "check with --today and no date"),
        (["check", str(made), str(made)], "check with two folders"),
        (["check", str(work)], "check on a folder with no finding.md"),
    ):
        code, _, err = run(args, cwd=work)
        expect(code == 2 and finding.USAGE in err, label + " exits 2 with usage", str(code))


def test_screens(root):
    mra = fresh(root, "screen-mra")
    code, out, _ = check(mra)
    expect(out == EXPECTED_MRA, "MRA-CMP-07 screen equals section 10", diff_hint(out, EXPECTED_MRA))
    expect(code == 1, "MRA-CMP-07 exits 1", str(code))
    code, out2, _ = run(["check", "--today", NOW], cwd=mra)
    expect(out2 == EXPECTED_MRA and code == 1, "check defaults to the current folder")
    ia = build(root, "screen-ia", IA_FILES, "2026-04-17")
    code, out, _ = check(ia)
    expect(code == 1, "IA-CMP-02 exits 1 until the owner signs", str(code) + "\n" + out)
    expect("Supervisor closure: not applicable to an internal audit finding.\n" in out,
           "IA-CMP-02 shows the not-applicable line")
    expect(out.endswith("Needs a person:\n  Head of Complaints: the signature, which comes first.\n"
                        "  Internal audit: its reference in closure/record.md.\n" + ready_line(ia)),
           "the shipped IA-CMP-02 names the owner's signature first, then internal audit", out[-400:])
    expect("Flagged commitments: none." in out, "IA-CMP-02 has no flags")

    code, out, _ = check(mra, "2026-06-20")
    m4 = line_of(out, "M4 ")
    expect(m4.endswith("Not started. AT RISK, due in 10 days."), "M4 at risk on 2026-06-20", m4)
    expect("M4 at risk, due in 10 days" in line_of(out, "Flagged commitments:"),
           "the board summary flags M4 at risk")
    code, out, _ = check(mra, "2026-02-01")
    expect("SLIPPED" not in out and "AT RISK" not in out, "no flag on 2026-02-01", out)
    expect("Flagged commitments: none." in out, "no flagged commitments on 2026-02-01")
    expect("EV-03 carries a signature dated 2026-02-20, after the check date" in out,
           "a signature after the check date does not count")


def test_proposed(root):
    mra = fresh(root, "proposed")
    (mra / "evidence" / "E-PLAN-1-board-minutes.md").unlink()
    code, out, _ = check(mra)
    expect("Plan approval: proposed, no signed board minutes E-PLAN-1 yet." in out,
           "no E-PLAN-1 gives a proposed plan", out)
    expect("committed 2026-02-28 proposed." in line_of(out, "M1 "), "milestone dates say proposed")
    expect("| M1 Approve revised complaint taxonomy | Head of Complaints | 2026-02-28 proposed |" in out,
           "table dates say proposed")
    expect("Commitment: full remediation by 2026-06-30 proposed." in out, "the commitment says proposed")
    expect("  The board: its approval of the plan, its approval of closure.\n" in out,
           "a proposed plan needs the board", out[-400:])


def test_refusal_parts(root):
    mra = fresh(root, "refusal-1")
    before = (mra / finding.STATE_NAME).read_bytes()
    edit(mra / "finding.md", "The intake procedure gave staff no rule",
         "The intake procedure gave staff no guidance")
    code, out, _ = check(mra)
    expect(code == 1 and out == refusal(
        "Refused: the Cause in finding.md is not the text first checked on 2026-02-10. The "
        "Supervisor's words do not change; restore them, or run check --repaste if the "
        "first paste was wrong."), "an edited Cause gives refusal 1", out)
    expect((mra / finding.STATE_NAME).read_bytes() == before, "refusal 1 leaves the state file alone")

    mra3 = fresh(root, "refusal-1-wrap")
    text = (mra3 / "finding.md").read_text(encoding="utf-8")
    wrapped = text.replace("The intake procedure gave staff no rule", "The intake procedure\ngave  staff no rule")
    expect(wrapped != text, "the re-wrap test found its line")
    finding.write_text(mra3 / "finding.md", wrapped)
    code, out, _ = check(mra3)
    expect("Refused" not in out, "re-wrapped lines in a part are not a change", out)


def test_closed_claim_row(root):
    """A line saying the finding itself is closed is a row on the list until the closer's entry is in the record. The
    rest of the page prints, no ruling clears the row, and sign refuses while it stands."""
    mra = fresh(root, "claim-row")
    append_to(mra / "plan.md", "\nThe finding is Closed.\n")
    lineno = len((mra / "plan.md").read_text(encoding="utf-8").splitlines())
    row = ("  Line {}: closed in plan.md claims the finding is closed, and only the Supervisor closes a supervisory finding. "
           "Reword the line, as no ruling clears this row.\n".format(lineno))
    code, out, _ = check(mra)
    expect(code == 1 and "Refused" not in out and "Milestones\n" in out and row in out
           and "Memo check: 13 claims, 7 tie, 4 on the list, 1 cleared." in out and "the list (4 rows)" in out,
           "a claim that the finding is closed is a row, and the page prints", out[-1200:])
    append_to(mra / "closure" / "rulings.md", "Line {} | closed in plan.md | cleared | Head of Complaints | 2026-11-04 | "
              "It is.\n".format(lineno))
    code, out, _ = check(mra)
    expect(row in out and "  Ruling at rulings.md line 5 names no row: no ruling clears the row on that line.\n" in out,
           "no ruling clears the row, and the page says so", out[-1200:])
    edit(mra / "closure" / "record.md", "Supervisor closure notice:", "Supervisor closure notice: EXN-2026-118")
    expect(row in check(mra)[1], "a Supervisor notice with no date or role leaves the row", check(mra)[1][-900:])
    edit(mra / "closure" / "record.md", "Supervisor closure date:", "Supervisor closure date: 2026-11-03")
    edit(mra / "closure" / "record.md", "Supervisor closure recorded by (role):",
         "Supervisor closure recorded by (role): Company Secretary")
    code, out, _ = check(mra)
    expect("closed in plan.md" not in out and "Supervisor closure: notice EXN-2026-118 dated 2026-11-03, recorded by the Company "
           "Secretary." in out, "the Supervisor's recorded entry takes the row away", out[-900:])

    folder = build(root, "claim-row-ia", IA_FILES, "2026-04-17")
    append_to(folder / "closure" / "memo.md", "\nThe remediation is closed.\n")
    code, out, _ = check(folder)
    expect(code == 1 and "Refused" not in out and "Memo check: 13 claims, 13 tie, 1 on the list.\n  Line 16: closed in "
           "closure/memo.md claims the finding is closed, and only internal audit closes an internal audit finding. Reword the "
           "line, as no ruling clears this row.\n" in out and "Ready to sign" not in out,
           "a closed claim in the memo of an internal audit finding is a row, and the page prints", out[-1200:])
    code, out, _ = run(["sign", str(folder), "--today", NOW], stdin=answers("Head of Complaints", "x"))
    expect(code == 1 and out == refusal("Refused: closure/memo.md line 16 claims the finding is closed, and only internal audit "
                                        "closes an internal audit finding. Reword the line, as no ruling clears this row."),
           "sign refuses while the row stands, and says to reword the line", out)
    for field, value in (("Internal audit reference", "IAV-2026-031"), ("Internal audit date", "2026-07-15"),
                         ("Internal audit recorded by (role)", "Head of Internal Audit")):
        edit(folder / "closure" / "record.md", field + ":\n", "{}: {}\n".format(field, value))
    out = check(folder)[1]
    expect("closed in closure/memo.md" not in out and "Memo check: 13 claims, 13 tie, 0 on the list." in out,
           "internal audit's recorded entry takes the row away", out[-900:])


def test_refusal_names(root):
    files = dict(MRA_FILES)
    files["finding.md"] = files["finding.md"].replace(
        "in complaint trend reports to the board.",
        "in complaint trend reports to the board, as the notes of Placeholder Person show.")
    files["evidence/E-PLAN-1-board-minutes.md"] = files["evidence/E-PLAN-1-board-minutes.md"].replace(
        "Signed by: Company Secretary, 2026-02-10", "Signed by: Placeholder Person, 2026-02-10")
    mra = build(root, "refusal-3", files, None)
    code, out, _ = check(mra)
    expect(code == 1 and out == refusal(
        'Refused: "Placeholder Person" is on this finding\'s deny list and would be printed. Use roles only. '
        "If it is an ordinary word or a title, add it to role-words.txt."),
        "a name in the Concern and a Signed by line gives refusal 3", out)
    state = state_of(mra)
    expect(state["deny"] == {"identifier": "MRA-CMP-07",
                             "names": ["Wrenfield Example Bank", "Wrenfield", "Example", "Placeholder Person"]},
           "the state file holds the seeded deny list", json.dumps(state.get("deny")))

    files = dict(MRA_FILES)
    files["finding.md"] = files["finding.md"].replace(
        "in complaint trend reports to the board.",
        "in complaint trend reports to the board, as the notes of Placeholder\nPerson show.")
    wrapped = build(root, "refusal-3-wrapped", files, "2026-02-10")
    expect("Placeholder Person" in state_of(wrapped)["deny"]["names"],
           "a name wrapped over two lines is put on the deny list",
           json.dumps(state_of(wrapped)["deny"]))
    edit(wrapped / "plan.md", "| Head of Digital |", "| Placeholder Person |")
    code, out, _ = check(wrapped)
    expect(code == 1 and out == refusal(
        'Refused: "Placeholder Person" is on this finding\'s deny list and would be printed. Use roles only. '
        "If it is an ordinary word or a title, add it to role-words.txt."),
        "a wrapped name on the screen gives refusal 3", out)

    mra2 = fresh(root, "refusal-3-institution")
    edit(mra2 / "plan.md", "| Head of Digital |", "| Wrenfield digital lead |")
    code, out, _ = check(mra2)
    expect(out == refusal(
        'Refused: "Wrenfield" is on this finding\'s deny list and would be printed. Use roles only. '
        "If it is an ordinary word or a title, add it to role-words.txt."),
        "an institution word on the screen gives refusal 3, which offers role-words.txt", out)

    mra3 = fresh(root, "deny-extend")
    names_before = state_of(mra3)["deny"]["names"]
    expect(names_before == ["Wrenfield Example Bank", "Wrenfield", "Example"],
           "the deny list holds the institution and its words", json.dumps(names_before))


def test_evidence_states(root):
    mra = fresh(root, "signed-edit")
    ev03 = mra / "evidence" / "EV-03-complaint-taxonomy.md"
    edit(ev03, "three subcategories", "four subcategories")
    code, out, _ = check(mra)
    expect("Present, unsigned: EV-03 changed since it was signed. SLIPPED by 249 days." in line_of(out, "M1 "),
           "an edited signed body changed since it was signed", line_of(out, "M1 "))
    expect("  Head of Complaints: M1, M2," in out, "M1 needs a person again", out[-400:])
    edit(ev03, "four subcategories", "three subcategories")
    code, out, _ = check(mra)
    expect(out == EXPECTED_MRA, "restoring the body restores the screen")
    edit(ev03, "three subcategories", "four subcategories")
    edit(ev03, "Signed by: Head of Complaints, 2026-02-20", "Signed by: Head of Complaints, 2026-03-01")
    code, out, _ = check(mra)
    expect(line_of(out, "M1 ").endswith("Present and signed on 2026-03-01."),
           "a later Signed by date re-records the file", line_of(out, "M1 "))
    expect(state_of(mra)["evidence"]["evidence/EV-03-complaint-taxonomy.md"]["signed"] == "2026-03-01",
           "the state file holds the new signature date")

    mra = fresh(root, "reasons")
    edit(mra / "plan.md", "| EV-03, EV-04 |", "| EV-03, EV-05, EV-04 |")
    edit(mra / "evidence" / "EV-07-intake-procedure.md",
         "Signed by: Head of Complaints, 2026-03-14", "Signed by: none")
    code, out, _ = check(mra)
    expect("Present, unsigned: EV-05 is missing. SLIPPED by 249 days." in line_of(out, "M1 "),
           "a missing id gives its reason", line_of(out, "M1 "))
    expect("Present, unsigned: EV-07 names no role. SLIPPED by 234 days." in line_of(out, "M2 "),
           "no role gives its reason", line_of(out, "M2 "))
    expect("Present, unsigned: EV-12 is a draft." in line_of(out, "M3 "), "a DRAFT gives its reason")
    edit(mra / "evidence" / "EV-07-intake-procedure.md",
         "Signed by: none", "Signed by: Head of Complaints, 2026-03-14")
    code, out, _ = check(mra)
    expect("EV-08 was revised on 2026-04-02, after its signature of 2026-03-14" in line_of(out, "M2 "),
           "a Revised date after the signature gives its reason", line_of(out, "M2 "))


def test_state_and_uncounted(root):
    mra = fresh(root, "state")
    shipped = state_of(mra)
    expect(shipped["first_check"] == "2026-02-10", "the first check date is recorded")
    expect(shipped["evidence"]["evidence/EV-12-quality-review.md"]["signed"] is None,
           "an unsigned file is recorded with signed null")
    expect(len(shipped["evidence"]) == 6, "every evidence file is recorded", str(len(shipped["evidence"])))
    expect(recompute_matches(mra), "the state file matches a recompute")

    pdf = mra / "evidence" / "EV-30-sample.pdf"
    pdf.write_bytes(b"%PDF-1.4\n% synthetic test bytes\n")
    code, out, _ = check(mra)
    expect("evidence/EV-30-sample.pdf, which has no cover file EV-30-sample.pdf.md." in out,
           "an uncounted PDF is named", out)
    expect("  The engagement team: the uncounted file evidence/EV-30-sample.pdf" in out,
           "an uncounted file needs a person", out[-400:])
    finding.write_text(mra / "evidence" / "EV-30-sample.pdf.md", SYN + """
What: EV-30 Reclassification sample listing
For: M3 EV-30
Signed by: Complaints QA lead, 2026-04-20
Status: FINAL
Covers: EV-30-sample.pdf

The listing has 240 rows, dated 2026-04-20.
""")
    code, out, _ = check(mra)
    expect("Not counted" not in out, "a cover counts the PDF", out)
    ev = state_of(mra)["evidence"]
    expect("evidence/EV-30-sample.pdf" in ev and "evidence/EV-30-sample.pdf.md" in ev,
           "the tool hashes both the PDF and its cover")
    pdf.write_bytes(b"%PDF-1.4\n% synthetic test bytes, edited\n")
    edit(mra / "plan.md", "| EV-12 |", "| EV-30 |")
    code, out, _ = check(mra)
    expect("EV-30 changed since it was signed" in line_of(out, "M3 "),
           "an edited PDF under a signed cover changed since it was signed", line_of(out, "M3 "))


def test_plan_and_covers(root):
    mra = fresh(root, "repeat-id")
    edit(mra / "plan.md", "| M2 Reissue intake procedure |", "| M1 Reissue intake procedure |")
    code, out, _ = check(mra)
    expect(code == 1 and out == refusal(
        "Not ready: plan.md line 7 repeats milestone M1 from line 6; give each milestone its own id."),
        "a repeated milestone id stops the check", out)

    mra = fresh(root, "orphan-cover")
    finding.write_text(mra / "evidence" / "EV-15-chat-volumes.xlsx.md", SYN + """
What: EV-15 Chat complaint volumes
For: M4 EV-15
Signed by: Head of Digital, 2026-06-20
Status: FINAL
Covers: EV-15-chat-volumes.xlsx

The workbook lists 412 chat complaints received from 2026-05-01 to 2026-06-15.
""")
    code, out, _ = check(mra)
    expect("evidence/EV-15-chat-volumes.xlsx.md, whose covered file EV-15-chat-volumes.xlsx is missing."
           in out, "a cover without its file is named as not counted", out)
    expect(line_of(out, "M4 ").endswith("Not started. SLIPPED by 127 days."),
           "a cover without its file does not count as evidence", line_of(out, "M4 "))
    (mra / "evidence" / "EV-15-chat-volumes.xlsx").write_bytes(b"PK synthetic test bytes\n")
    code, out, _ = check(mra)
    expect("Not counted" not in out and "Present and signed on 2026-06-20." in line_of(out, "M4 "),
           "the cover counts once its file is present", out)


def block_from(screen, prefix):
    """The screen from the line starting prefix up to and including the Signature or Signed line."""
    lines = screen.splitlines()
    for i, line in enumerate(lines):
        if line.startswith(prefix):
            for j in range(i, len(lines)):
                if lines[j].startswith(("Signature:", "Signed by ")):
                    return "\n".join(lines[i:j + 1]) + "\n"
    return ""


def ia(root, name):
    """IA-CMP-02 with internal audit's entry in the record, as it reads once internal audit has tested the signed memo.
    The shipped case holds no entry, because the owner signs first. These lines are ones a signature does not cover."""
    folder = build(root, name, IA_FILES, "2026-04-17")
    for field, value in (("Internal audit reference", "IAV-2026-031"), ("Internal audit date", "2026-07-15"),
                         ("Internal audit recorded by (role)", "Head of Internal Audit")):
        edit(folder / "closure" / "record.md", field + ":\n", "{}: {}\n".format(field, value))
    return folder


def ready_line(folder):
    return "Ready to sign: the folder's fingerprint is {}. Internal audit records this as what it tests.\n".format(
        finding.fingerprint(folder)[:8])


def only_the_signature(code, screen):
    """True when the page's one remaining need is the owner's signature."""
    return code == 1 and screen.split("Needs a person:\n")[-1].startswith(
        "  Head of Complaints: the signature, which comes first.\nReady to sign: the folder's fingerprint is ")


def row_named(screen, claimed):
    """("Line 8", "1,248 #972adb19") for the row on this page whose ruling names this claim."""
    m = re.search(r"^  Line (\d+): .* To rule, name: (" + re.escape(claimed) + r" #[0-9a-f]{8})$", screen, re.M)
    if m is None:
        raise AssertionError("selftest setup: no row names {!r} on\n{}".format(claimed, screen))
    return "Line " + m.group(1), m.group(2)


def ruling_for(folder, claimed, rest="cleared | Head of Complaints | 2026-11-04 | Checked by hand.", today=NOW):
    """The rulings.md line for the row this folder's page prints for this claim, in the form the page names."""
    line, name = row_named(check(folder, today)[1], claimed)
    return "{} | {} | {}\n".format(line, name, rest)


def add_ruling(folder, claimed, rest="cleared | Head of Complaints | 2026-11-04 | Checked by hand.", today=NOW):
    append_to(folder / "closure" / "rulings.md", ruling_for(folder, claimed, rest, today))


def test_memo_list(root):
    mra = fresh(root, "memo-list")
    memo_before = (mra / "closure" / "memo.md").read_bytes()
    code, out, _ = check(mra)
    expect(block_from(out, "Board approval:") == EXPECTED_MRA[EXPECTED_MRA.index("Board approval:"):
                                                                EXPECTED_MRA.index("Deny list:")]
           and code == 1, "MRA-CMP-07 shows the memo list with one row cleared", out)
    expect((mra / "closure" / "memo.md").read_bytes() == memo_before, "the check never changes the memo")

    rulings = mra / "closure" / "rulings.md"
    rulings_text = rulings.read_text(encoding="utf-8")
    rulings.unlink()
    code, out, _ = check(mra)
    expect(block_from(out, "Memo check:") == MRA_ROWS_WITHOUT_RULINGS,
           "without rulings.md the March 2026 row stays on the list", block_from(out, "Memo check:"))
    expect(line_of(out, "Needs a person:") == line_of(EXPECTED_MRA, "Needs a person:"),
           "the memo list adds nothing to the Needs a person line")

    good = "Line 8 | March 2026 #f2ba27f8 | cleared | Head of Complaints | 2026-11-04 | The page says January to March, and the plan year is 2026."
    for bad, label in (
        (good.replace("| Head of Complaints |", "| Complaints QA lead |"), "a ruling by another role"),
        (good.replace("| The page says January to March, and the plan year is 2026.", "| "), "a ruling with no reason"),
        (good.replace("| 2026-11-04 |", "| 4 November |"), "a ruling with a bad date"),
        (good.replace("| cleared |", "| fix the memo |"), "a fix the memo ruling"),
    ):
        finding.write_text(rulings, rulings_text.replace(good, bad))
        code, out, _ = check(mra)
        expect("Memo check: 13 claims, 7 tie, 4 on the list." in out
               and "  Line 8: March 2026 is cited to EV-07 p2, and the page holds no date." in out,
               label + " keeps the row", line_of(out, "Memo check:"))
    finding.write_text(rulings, rulings_text + "Line 9 | 9,999 | cleared | Head of Complaints | 2026-11-04 | A slip.\n")
    code, out, _ = check(mra)
    expect("  Line 16: the sample period for M2 starts" in out
           and "  Ruling at rulings.md line 5 names no row." in out.split("  Line 16: the sample period for M2 starts")[1],
           "a ruling matching no row prints its line after the rows", block_from(out, "Memo check:"))
    finding.write_text(rulings, rulings_text + "Line 16 | sample period for M2 #106ddd50 | cleared | Head of Complaints | "
                       "2026-11-04 | The sample is split at the fix date in the workpapers.\n")
    code, out, _ = check(mra)
    expect("Memo check: 13 claims, 7 tie, 2 on the list, 2 cleared." in out and "the sample period for M2 starts" not in out,
           "a cleared ruling takes the sample row off the list", line_of(out, "Memo check:"))

    finding.write_text(rulings, rulings_text)
    memo = mra / "closure" / "memo.md"
    edit(memo, "Sample period: 2026-01-05 to 2026-03-31", "Sample period: 2026-03-17 to 2026-03-31")
    code, out, _ = check(mra)
    expect("Memo check: 13 claims, 7 tie, 3 on the list, 1 cleared." in out and "sample period for M2" not in out,
           "the sample row goes when the sample starts on the fix date", line_of(out, "Memo check:"))
    edit(memo, "Fix effective: 2026-03-17 [EV-12 p2]\n", "")
    code, out, _ = check(mra)
    expect("  Line 14: the tested control M2 has no Fix effective line." in out,
           "a missing Fix effective line is a row", block_from(out, "Memo check:"))
    edit(memo, "Sample period: 2026-03-17 to 2026-03-31", "Sample period: 17 March to 2026-03-31")
    code, out, _ = check(mra)
    expect(line_of(out, "Memo check:") == "Memo check: 12 claims, 7 tie, 5 on the list, 1 cleared.",
           "control rows count on the list and not as claims", line_of(out, "Memo check:"))
    expect('  Line 15: the Sample period date "17 March to 2026-03-31" is not YYYY-MM-DD.' in out,
           "a sample date not written YYYY-MM-DD is a row", block_from(out, "Memo check:"))

    planted = mra / "closure" / "memo.md"
    finding.write_text(planted, SYN + """
# Closure memo MRA-CMP-07

The register lists 46 handlers [EV-99 p1]. The procedure runs to 3 sections [EV-07 p3]. The register showed 46 of 48 [EV-08]. The Head of Complaints signed the procedure on 2026-03-15 [EV-07 p1].

A complaint that mentions a fee is "classified as a service issue first" [EV-03 p1]. The team has 48 handlers.
""")
    code, out, _ = check(mra)
    for row, label in (
        ("  Line 4: 46 is cited to EV-99 p1, and there is no evidence file EV-99.", "a missing evidence id"),
        ("  Line 4: 3 is cited to EV-07 p3, and EV-07 has 2 pages.", "a page beyond the file"),
        ("  Line 4: 46 is cited to EV-08, and EV-08 has 2 pages, so the cite needs a page.", "a cite with no page"),
        ("  Line 4: 2026-03-15 is cited to EV-07 p1, and the page does not hold it; the date on the page is "
         "2026-03-14.", "a wrong date"),
        ('  Line 6: "classified as a service issue first" is cited to EV-03 p1, and the page does not hold '
         '"classified as a service issue first"; the page reads "', "a misquote"),
        ("  Line 6: 48 has no cite.", "a figure with no cite"),
    ):
        expect(any(line.startswith(row) for line in out.splitlines()), label + " gives its sentence",
               block_from(out, "Memo check:"))
    expect("Line 8:" not in out and "  Line 16:" not in out, "the planted memo has no tested control", out)

    mra2 = fresh(root, "memo-ids")
    finding.write_text(mra2 / "evidence" / "EV-1-2-extra.md", SYN + """
What: EV-1-2 An extra listing
For: M3 EV-1-2
Signed by: none
Status: DRAFT

A listing.
""")
    code, out, _ = check(mra2)
    expect(out == refusal("Not ready: evidence ids EV-1-2 and EV-12 cannot be told apart by the memo check; "
                          "rename one."), "two ids the memo check cannot tell apart stop the check", out)

    iaf = ia(root, "memo-ia")
    code, out, _ = check(iaf)
    expect(code == 1 and out.endswith(EXPECTED_IA_TAIL + ready_line(iaf)),
           "IA-CMP-02 ties all 13 claims and needs only its signature", out)


def test_needs_and_order(root):
    wrong = ia(root, "needs-wrong")
    edit(wrong / "closure" / "memo.md", "402", "403")
    code, out, _ = check(wrong)
    expect(code == 1 and "Needs a person:\n  Head of Complaints: the list (1 row).\n" in out,
           "a row on the list reaches Needs a person, even with internal audit's reference in", out[-300:])
    code, out, _ = run(["sign", str(wrong), "--today", NOW], stdin=answers())
    expect(code == 1 and "1 row is on the list" in out, "and sign refuses it", out)

    noboard = ia(root, "needs-board")
    edit(noboard / "closure" / "record.md", "Board approval reference: BM-2026-07", "Board approval reference:")
    code, out, _ = check(noboard)
    expect(code == 1 and "  The board: its approval of closure (no reference).\n" in out, "no board approval needs the board", out[-300:])

    moved = fresh(root, "ruling-moved")
    memo = moved / "closure" / "memo.md"
    text = memo.read_text(encoding="utf-8")
    finding.write_text(memo, text.replace("M1, the complaint taxonomy.", "A new opening paragraph.\n\nM1, the complaint taxonomy.", 1))
    code, out, _ = check(moved)
    expect("  Cleared: line 10 (ruled at memo line 8), March 2026, by the Head of Complaints on 2026-11-04:" in out
           and "names no row" not in out, "a cleared ruling follows its claim when the memo moves", block_from(out, "Memo check:"))

    kept = fresh(root, "ruling-kept")
    rulings = kept / "closure" / "rulings.md"
    finding.write_text(rulings, rulings.read_text(encoding="utf-8")
                       + "Line 99 | 7,777 | fix the memo | Head of Complaints | 2026-10-01 | Fixed in the next version.\n")
    code, out, _ = check(kept)
    expect("names no row" not in out, "a fix the memo ruling whose row is gone stays in the record without a warning", out[-500:])

    any_order = fresh(root, "header-order")
    path = any_order / "evidence" / "EV-08-training-register.md"
    lines = path.read_text(encoding="utf-8").splitlines()
    head = [line for line in lines if line.startswith(finding.HEADER_KEYS)]
    body = [line for line in lines[1:] if line not in head]
    shuffled = ["Source: typed from the register", "Checked by: Associate 2, 2026-04-03"] + list(reversed(head))
    finding.write_text(path, "\n".join([lines[0]] + shuffled + body) + "\n")
    code, out, _ = check(any_order)
    expect("EV-08 was revised on 2026-04-02" in line_of(out, "M2 "),
           "the cover's lines may sit in any order, with Source and Checked by among them", line_of(out, "M2 "))

    fit = fresh(root, "fit-lists")
    check(fit)
    finding.write_text(fit / "denylist.txt", "# the engagement's own terms\nQuality\n")
    code, out, _ = check(fit)
    expect(code == 1 and "is on this finding's deny list" in out, "a term in denylist.txt beside the finding is denied", out)
    (fit / "denylist.txt").unlink()
    state = state_of(fit)
    state["deny"]["names"] = [n for n in state["deny"]["names"] if n != "Quality"]
    finding.write_text(fit / finding.STATE_NAME, json.dumps(state))
    code, out, _ = check(fit)
    expect("deny list" not in out, "the term leaves with the file once the state is cleaned", out[:200])

    measured = fresh(root, "measures")
    finding.write_text(measured / "closure" / "measures.md", SYN + "\nHours | 2026-10 | 38\nHours | 2026-11 | 12\n"
                       "Sent back | 2026-11-02 | Line 8 | wrong figure | missed by the check\n"
                       "Sent back | 2026-11-03 | Line 9 | stale date | found by a person\n")
    code, out, _ = check(measured)
    expect("Measures: 50 hours booked, 267 days since the first check, 2 sent back by internal audit, 1 missed by the check.\n" in out,
           "measures print one line", line_of(out, "Measures:"))
    code, out, _ = check(fresh(root, "no-measures"))
    expect("Measures:" not in out, "with no measures the page prints no line")


def test_signing_order(root):
    fp_folder = ia(root, "order")
    code, out, _ = run(["sign", str(fp_folder), "--today", NOW], stdin=answers("Head of Complaints", finding.fingerprint(fp_folder)[:8]))
    expect(code == 0, "the owner signs", out[-200:])
    record = fp_folder / "closure" / "record.md"
    edit(record, "Internal audit reference: IAV-2026-031", "Internal audit reference: IAV-2026-099")
    code, out, _ = check(fp_folder)
    expect(code == 0 and "Changed since signing" not in out, "internal audit's later entry asks for no fresh signature", out[-300:])
    fp = finding.fingerprint(fp_folder)
    edit(record, "Internal audit recorded by (role): Head of Internal Audit",
         "Internal audit recorded by (role): Head of Internal Audit\nInternal audit tested fingerprint: {}".format(fp[:8]))
    code, out, _ = check(fp_folder)
    expect(code == 0 and "tested fingerprint" not in out, "a tested fingerprint that matches is quiet", out[-300:])
    finding.write_text(fp_folder / "closure" / "memo.md",
                       (fp_folder / "closure" / "memo.md").read_text(encoding="utf-8") + "\nOne more sentence.\n")
    code, out, _ = check(fp_folder)
    expect(code == 1 and "Changed since signing: closure/memo.md." in out and "  Head of Complaints: a fresh signature.\n" in out,
           "a memo change still asks for a fresh signature", out[-400:])

    proposed = ia(root, "sign-proposed")
    edit(proposed / "evidence" / "E-PLAN-1-board-minutes.md", "Status: FINAL", "Status: DRAFT")
    code, out, _ = run(["sign", str(proposed), "--today", NOW], stdin=answers())
    expect(code == 1 and "the plan approval is still proposed" in out, "sign refuses a proposed plan", out)

    uncounted = ia(root, "sign-uncounted")
    (uncounted / "evidence" / "EV-30-sample.pdf").write_bytes(b"%PDF-1.4 not a real file")
    code, out, _ = run(["sign", str(uncounted), "--today", NOW], stdin=answers())
    expect(code == 1 and "EV-30-sample.pdf is not counted" in out, "sign refuses an uncounted file", out)


def test_release_and_network(root):
    version, changed = finding.kit_release()
    expect(version != "unknown" and not changed, "RELEASE.json is current; run python3 -I finding/release.py",
           ", ".join(changed))
    code, out, _ = run(["--version"])
    expect(code == 0 and out == "RegRem Engine {}\nEvery file matches this release.\n".format(version),
           "--version prints the release and confirms the files", out)
    expect(sorted(json.loads((HERE.parent / "RELEASE.json").read_text(encoding="utf-8"))["files"]) == sorted(finding.KIT_FILES),
           "RELEASE.json lists the kit's files")
    kit = HERE.parent
    for rel in NETWORK_FREE:
        names, calls = imports_and_calls((kit / rel).read_text(encoding="utf-8"))
        expect(names <= ALLOWED_IMPORTS, rel + " imports only the modules on the fixed list",
               ", ".join(sorted(names - ALLOWED_IMPORTS)))
        expect(not calls, rel + " starts no process and imports nothing by name", ", ".join(sorted(calls)))
    py = sorted(rel for rel in finding.KIT_FILES if rel.endswith(".py"))
    expect(set(py) <= set(NETWORK_FREE), "the import check covers every Python file in RELEASE.json",
           ", ".join(sorted(set(py) - set(NETWORK_FREE))))
    for label, source in (("import socket", "import socket\n"), ("a lazy import", "def f():\n    import requests\n"),
                          ("concurrent.futures", "from concurrent import futures\n"),
                          ("__import__", "__import__('socket')\n"), ("os.system", "import os\nos.system('true')\n"),
                          ("from os import popen", "from os import popen\n"), ("importlib", "import importlib\n")):
        names, calls = imports_and_calls(source)
        expect(not names <= ALLOWED_IMPORTS or calls, "the import check catches " + label)


def imports_and_calls(source):
    """(top-level module names imported anywhere in the source, calls that start a process or import by name)."""
    names, calls = set(), set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.add((node.module or "").split(".")[0] or "a relative import")
            if node.module == "os":
                calls.update("os." + a.name for a in node.names if BANNED_OS.match(a.name))
        elif isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id in BANNED_CALLS:
                calls.add(func.id)
            elif (isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) and func.value.id == "os"
                  and BANNED_OS.match(func.attr)):
                calls.add("os." + func.attr)
    return names, calls


def pdf_bytes(objects, trailer_extra="", root=1, unlisted=b""):
    """A PDF from {number: body bytes}, with a real cross-reference table. `unlisted` is bytes the table does
    not point at, placed after the objects."""
    out = bytearray(b"%PDF-1.5\n")
    offsets = {}
    for num in sorted(objects):
        offsets[num] = len(out)
        out += str(num).encode() + b" 0 obj\n" + objects[num] + b"\nendobj\n"
    out += unlisted
    start = len(out)
    size = max(objects) + 1
    out += "xref\n0 {}\n0000000000 65535 f \n".format(size).encode()
    for num in range(1, size):
        out += "{:010d} 00000 n \n".format(offsets.get(num, 0)).encode()
    out += "trailer\n<< /Size {} /Root {} 0 R {} >>\nstartxref\n{}\n%%EOF\n".format(size, root, trailer_extra, start).encode()
    return bytes(out)


def stream_obj(data, head=b"", deflate=False):
    if deflate:
        data = zlib.compress(data)
        head += b" /Filter /FlateDecode"
    return b"<< /Length " + str(len(data)).encode() + head + b" >>\nstream\n" + data + b"\nendstream"


def simple_pdf(pages, deflate=False, trailer_extra=""):
    """A PDF with one page per text. An empty text is a page with no text layer, as a scan has."""
    objects = {1: b"<< /Type /Catalog /Pages 2 0 R >>",
               3: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"}
    kids = []
    num = 4
    for text in pages:
        lines = []
        y = 720
        for line in text.split("\n"):
            safe = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            lines.append("BT /F1 12 Tf 72 {} Td ({}) Tj ET".format(y, safe))
            y -= 16
        content = "\n".join(lines).encode("latin-1") if text else b"q 100 0 0 100 0 0 cm Q"
        objects[num + 1] = stream_obj(content, deflate=deflate)
        objects[num] = ("<< /Type /Page /Parent 2 0 R /Contents {} 0 R "
                        "/Resources << /Font << /F1 3 0 R >> >> >>").format(num + 1).encode()
        kids.append("{} 0 R".format(num))
        num += 2
    objects[2] = "<< /Type /Pages /Count {} /Kids [{}] >>".format(len(pages), " ".join(kids)).encode()
    return pdf_bytes(objects, trailer_extra)


def cid_pdf(text):
    """A page whose text is two-byte codes, readable only through its ToUnicode map."""
    codes = sorted(set(text))
    code_of = {ch: i + 1 for i, ch in enumerate(codes)}
    pairs = "".join("<{:04X}> <{:04X}>\n".format(code_of[ch], ord(ch)) for ch in codes)
    cmap = ("/CIDInit /ProcSet findresource begin begincmap 1 begincodespacerange <0000> <FFFF> endcodespacerange "
            "{} beginbfchar\n{}endbfchar endcmap").format(len(codes), pairs).encode()
    hexed = "".join("{:04X}".format(code_of[ch]) for ch in text)
    content = "BT /F1 12 Tf 72 720 Td [<{}>] TJ ET".format(hexed).encode()
    objects = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        2: b"<< /Type /Pages /Count 1 /Kids [4 0 R] >>",
        3: b"<< /Type /Font /Subtype /Type0 /BaseFont /Example /Encoding /Identity-H /DescendantFonts [6 0 R] /ToUnicode 7 0 R >>",
        4: b"<< /Type /Page /Parent 2 0 R /Contents 5 0 R /Resources << /Font << /F1 3 0 R >> >> >>",
        5: stream_obj(content, deflate=True),
        6: b"<< /Type /Font /Subtype /CIDFontType2 /BaseFont /Example /DW 500 >>",
        7: stream_obj(cmap),
    }
    return pdf_bytes(objects)


def objstm_pdf(text):
    """The catalog, page tree and page inside a compressed object stream, as modern writers do."""
    inside = {1: b"<< /Type /Catalog /Pages 2 0 R >>",
              2: b"<< /Type /Pages /Count 1 /Kids [4 0 R] >>",
              3: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
              4: b"<< /Type /Page /Parent 2 0 R /Contents 5 0 R /Resources << /Font << /F1 3 0 R >> >> >>"}
    body = b""
    table = []
    for num in sorted(inside):
        table.append("{} {}".format(num, len(body)))
        body += inside[num] + b" "
    head = (" ".join(table) + " ").encode()
    stm = head + body
    objects = {5: stream_obj("BT /F1 12 Tf 72 720 Td ({}) Tj ET".format(text).encode(), deflate=True),
               6: stream_obj(stm, " /Type /ObjStm /N 4 /First {}".format(len(head)).encode(), deflate=True)}
    return pdf_bytes(objects)


def test_documents(root):
    docs = finding.documents_module()
    folder = root / "documents"
    folder.mkdir()

    def write(name, data):
        path = folder / name
        path.write_bytes(data)
        return path

    got = docs.read(write("plain.pdf", simple_pdf(["Reclassified 1,284 complaints.", "Signed on 2026-03-14."])))
    expect(got["problem"] is None and got["pages"] == ["Reclassified 1,284 complaints.", "Signed on 2026-03-14."],
           "a PDF's text reads page by page", str(got))
    got = docs.read(write("flate.pdf", simple_pdf(["Rate (98.3 percent) held.\nSecond line."], deflate=True)))
    expect(got["pages"] == ["Rate (98.3 percent) held.\nSecond line."], "a compressed PDF reads, with its lines", str(got))
    got = docs.read(write("cid.pdf", cid_pdf("Total 1,284 items")))
    expect(got["pages"] == ["Total 1,284 items"], "a two-byte font reads through its ToUnicode map", str(got))
    got = docs.read(write("objstm.pdf", objstm_pdf("Held in an object stream 402")))
    expect(got["pages"] == ["Held in an object stream 402"], "a PDF with an object stream reads", str(got))
    got = docs.read(write("scan.pdf", simple_pdf(["Typed page.", ""])))
    expect(got["pages"] == ["Typed page.", ""], "a page with no text layer comes back empty", str(got))
    got = docs.read(write("locked.pdf", simple_pdf(["Secret."], trailer_extra="/Encrypt 9 0 R")))
    expect(got["problem"] == "the PDF is encrypted", "an encrypted PDF is refused in words", str(got))
    got = docs.read(write("fake.pdf", b"not a pdf at all"))
    expect(got["problem"] == "the file does not start like a PDF", "a file that is no PDF says so", str(got))
    got = docs.read(write("note.rtf", b"{}"))
    expect(got["problem"] and got["pages"] == [], "a file type with no reader says so", str(got))
    whole = simple_pdf(["Reclassified 1,284 complaints."], deflate=True)
    crashed = []
    for cut in range(0, len(whole), max(1, len(whole) // 40)):
        path = write("cut.pdf", whole[:cut])
        try:
            docs.read(path)
        except Exception as exc:  # every failure must come back as a reason, never a crash
            crashed.append("{}: {}".format(cut, exc))
    expect(not crashed, "a truncated PDF never crashes the reader", "; ".join(crashed[:3]))

    word = folder / "memo.docx"
    with zipfile.ZipFile(str(word), "w") as zf:
        zf.writestr("[Content_Types].xml", "<Types/>")
        zf.writestr("word/document.xml", '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                    "<w:body><w:p><w:r><w:t>The team reclassified 1,284 complaints.</w:t></w:r></w:p></w:body></w:document>")
    got = docs.read(word)
    expect(got["problem"] is None and "1,284" in got["pages"][0], "a Word file reads", str(got))

    book = folder / "sample.xlsx"
    with zipfile.ZipFile(str(book), "w") as zf:
        ns = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
        zf.writestr("xl/workbook.xml", '<workbook {} xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                    '<sheets><sheet name="Sample" r:id="rId1"/><sheet name="Other" r:id="rId2"/></sheets></workbook>'.format(ns))
        zf.writestr("xl/_rels/workbook.xml.rels", '<Relationships><Relationship Id="rId1" Target="worksheets/sheet1.xml"/>'
                    '<Relationship Id="rId2" Target="worksheets/sheet2.xml"/></Relationships>')
        zf.writestr("xl/sharedStrings.xml", "<sst {}><si><t>Complaints</t></si></sst>".format(ns))
        zf.writestr("xl/worksheets/sheet1.xml", '<worksheet {}><sheetData><row><c t="s"><v>0</v></c><c><v>1284</v></c></row>'
                    "</sheetData></worksheet>".format(ns))
        zf.writestr("xl/worksheets/sheet2.xml", '<worksheet {}><sheetData><row><c t="inlineStr"><is><t>Second</t></is></c></row>'
                    "</sheetData></worksheet>".format(ns))
    got = docs.read(book)
    expect(got["pages"] == ["Sample\nComplaints\t1284", "Other\nSecond"], "an Excel workbook reads, one page per sheet", str(got))
    got = docs.read(write("rows.csv", b"Complaints,1284\n"))
    expect(got["pages"] == ["Complaints\t1284"], "a CSV reads", str(got))
    got = docs.read(write("mail.eml", b"From: a\r\nSubject: Sign-off\r\nContent-Type: text/plain\r\n\r\nApproved 2026-03-14.\r\n"))
    expect("Approved 2026-03-14." in got["pages"][0] and "Subject: Sign-off" in got["pages"][0], "an email reads", str(got))


# ---------------------------------------------------------------- the reader


SHOWN = "BT /F1 14 Tf 72 660 Td (The sample held 9,999 items.) Tj ET"
BAR = "60 650 320 30 re f"
SCAN = "q 612 0 0 792 0 0 cm /Im0 Do Q"
IMAGE_OBJ = stream_obj(b"\xff", b" /Type /XObject /Subtype /Image /Width 1 /Height 1 /BitsPerComponent 8 /ColorSpace /DeviceGray")
IMAGE = "/XObject << /Im0 6 0 R >>"
# F1 with its widths given, every glyph 500 units. The F1 of one_page_pdf names Helvetica with none, as a standard font may.
WIDTHS = {3: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding /FirstChar 32 /LastChar 126 "
             b"/Widths [" + b"500 " * 95 + b"] >>"}
# At 10 points from x 64 this ends at 634 on a guess of 500 units a glyph, past the page's 612, and at 543 in Helvetica's own widths.
LONG_LINE = "The review matched the training roster to the contractor list in the case file, and found that the file held 9,999"


def one_page_pdf(content, resources="", page="", objects=None, catalog="", fonts="", root=1, unlisted=b"", trailer=""):
    """One page holding `content`, with Helvetica as F1. Objects 6 and up come from `objects`."""
    all_objects = {
        1: "<< /Type /Catalog /Pages 2 0 R {} >>".format(catalog).encode(),
        2: b"<< /Type /Pages /Count 1 /Kids [4 0 R] >>",
        3: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        4: ("<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 5 0 R /Resources << /Font << /F1 3 0 R {} >> {} >> "
            "{} >>").format(fonts, resources, page).encode(),
        5: stream_obj(content if isinstance(content, bytes) else content.encode("latin-1")),
    }
    all_objects.update(objects or {})
    return pdf_bytes(all_objects, trailer, root, unlisted)


def pdf_update(base, objects, root=1):
    """A proper incremental update of `base`: new objects, a new table, /Prev pointing at the old one."""
    prev = int(re.findall(rb"startxref\s+(\d+)", base)[-1])
    out = bytearray(base)
    offsets = {}
    for num in sorted(objects):
        offsets[num] = len(out)
        out += str(num).encode() + b" 0 obj\n" + objects[num] + b"\nendobj\n"
    start = len(out)
    out += b"xref\n"
    for num in sorted(offsets):
        out += "{} 1\n{:010d} 00000 n \n".format(num, offsets[num]).encode()
    size = max(offsets) + 1
    out += "trailer\n<< /Size {} /Root {} 0 R /Prev {} >>\nstartxref\n{}\n%%EOF\n".format(size, root, prev, start).encode()
    return bytes(out)


def xref_stream_pdf(text):
    """The catalog, page tree and page in an object stream, found through a cross-reference stream."""
    inside = {1: b"<< /Type /Catalog /Pages 2 0 R >>",
              2: b"<< /Type /Pages /Count 1 /Kids [4 0 R] >>",
              3: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
              4: b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 5 0 R /Resources << /Font << /F1 3 0 R >> >> >>"}
    body, table = b"", []
    for num in sorted(inside):
        table.append("{} {}".format(num, len(body)))
        body += inside[num] + b" "
    head = (" ".join(table) + " ").encode()
    out = bytearray(b"%PDF-1.5\n")
    offset_5 = len(out)
    out += b"5 0 obj\n" + stream_obj("BT /F1 12 Tf 72 720 Td ({}) Tj ET".format(text).encode(), deflate=True) + b"\nendobj\n"
    offset_6 = len(out)
    out += b"6 0 obj\n" + stream_obj(head + body, " /Type /ObjStm /N 4 /First {}".format(len(head)).encode(), deflate=True) + b"\nendobj\n"
    offset_7 = len(out)
    rows = [(0, 0, 65535), (2, 6, 0), (2, 6, 1), (2, 6, 2), (2, 6, 3), (1, offset_5, 0), (1, offset_6, 0), (1, offset_7, 0)]
    table_bytes = b"".join(kind.to_bytes(1, "big") + a.to_bytes(4, "big") + b.to_bytes(2, "big") for kind, a, b in rows)
    out += b"7 0 obj\n" + stream_obj(table_bytes, b" /Type /XRef /Size 8 /W [1 4 2] /Root 1 0 R", deflate=True) + b"\nendobj\n"
    out += "startxref\n{}\n%%EOF\n".format(offset_7).encode()
    return bytes(out)


def reader_in(root, name):
    """(documents module, read(file name, data)). The read catches what the promise says cannot happen."""
    docs = finding.documents_module()
    folder = root / name
    folder.mkdir()

    def read(filename, data):
        path = folder / filename
        path.write_bytes(data)
        try:
            return docs.read(path)
        except Exception as exc:
            return {"pages": [], "problem": "RAISED {}".format(type(exc).__name__), "partly": [], "hidden": {}, "notes": []}

    return docs, read


def page_of(got):
    return "\n".join(got["pages"])


def with_document(root, name, filename, data, memo_line, cover_lines=""):
    """A copy of IA-CMP-02 with one covered document and one more memo line citing it."""
    folder = ia(root, name)
    (folder / "evidence" / filename).write_bytes(data)
    finding.write_text(folder / "evidence" / (filename + ".md"), "What: EV-30 Listing\nFor: EV-30\n"
                       "Signed by: Head of Complaints, 2026-07-01\nStatus: FINAL\n" + cover_lines)
    memo = folder / "closure" / "memo.md"
    finding.write_text(memo, memo.read_text(encoding="utf-8") + "\n" + memo_line + "\n")
    return folder


def zip_patched(data, flags=None, method=None):
    """A zip with its flag bits or compression method overwritten in every header."""
    out = bytearray(data)
    for signature, flag_at, method_at in ((b"PK\x03\x04", 6, 8), (b"PK\x01\x02", 8, 10)):
        pos = out.find(signature)
        while pos >= 0:
            if flags is not None:
                out[pos + flag_at:pos + flag_at + 2] = flags.to_bytes(2, "little")
            if method is not None:
                out[pos + method_at:pos + method_at + 2] = method.to_bytes(2, "little")
            pos = out.find(signature, pos + 4)
    return bytes(out)


WORD_NS = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'


def word_bytes(root, body, styles=None, encoding=None):
    """A Word file whose body is `body`, as bytes."""
    path = root / "word-built.docx"
    document = "<w:document {}><w:body>{}</w:body></w:document>".format(WORD_NS, body)
    with zipfile.ZipFile(str(path), "w") as zf:
        zf.writestr("word/document.xml", document.encode(encoding) if encoding else document)
        if styles:
            zf.writestr("word/styles.xml", "<w:styles {}>{}</w:styles>".format(WORD_NS, styles))
    data = path.read_bytes()
    path.unlink()
    return data


def word_run(text, props=""):
    return "<w:p><w:r><w:rPr>{}</w:rPr><w:t>{}</w:t></w:r></w:p>".format(props, text)


def book_bytes(root, sheets, shared=None):
    """A workbook from [(name, state, worksheet body)], as bytes."""
    ns = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
    path = root / "book-built.xlsx"
    tags = "".join('<sheet name="{}" r:id="rId{}"{}/>'.format(name, i, ' state="{}"'.format(state) if state else "")
                   for i, (name, state, _) in enumerate(sheets, 1))
    rels = "".join('<Relationship Id="rId{0}" Target="worksheets/sheet{0}.xml"/>'.format(i) for i in range(1, len(sheets) + 1))
    with zipfile.ZipFile(str(path), "w") as zf:
        zf.writestr("xl/workbook.xml", '<workbook {} xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                    "<sheets>{}</sheets></workbook>".format(ns, tags))
        zf.writestr("xl/_rels/workbook.xml.rels", "<Relationships>{}</Relationships>".format(rels))
        for i, (_, _, body) in enumerate(sheets, 1):
            zf.writestr("xl/worksheets/sheet{}.xml".format(i), "<worksheet {}>{}</worksheet>".format(ns, body))
        if shared is not None:
            zf.writestr("xl/sharedStrings.xml", "<sst {}>{}</sst>".format(ns, "".join("<si><t>{}</t></si>".format(t) for t in shared)))
    data = path.read_bytes()
    path.unlink()
    return data


def email_bytes(*parts, head=""):
    """A multipart/alternative email from (type, body) pairs, or a one-part email from one pair."""
    top = "From: a@b.c\nSubject: Sign-off\n" + head
    if len(parts) == 1:
        kind, body = parts[0]
        return (top + "Content-Type: {}; charset=utf-8\n\n{}\n".format(kind, body)).encode("utf-8")
    text = top + 'Content-Type: multipart/alternative; boundary="b"\n\n'
    for kind, body in parts:
        text += "--b\nContent-Type: {}; charset=utf-8\n\n{}\n".format(kind, body)
    return (text + "--b--\n").encode("utf-8")


def test_reader_never_raises(root):
    """One ordinary CSV, email or damaged zip must not stop every verb with a traceback."""
    docs, read = reader_in(root, "reader-raises")
    cases = {
        "a CSV with old Mac line endings": ("mac.csv", b"Complaints,1284\rTotal,1284\r", "1284"),
        "a CSV with a bare return in a field": ("bare.csv", b"id,note\n1,first line\rsecond line\n2,1284\n", "1284"),
        "a CSV field over the default limit": ("long.csv", b"note,1284\n" + b"x" * 140000 + b",2\n", "1284"),
        "a CSV with an unclosed quote": ("quote.csv", b'a,b\n"open,1284\n' + b"row,2\n" * 40000, "1284"),
        "a UTF-16 CSV": ("wide.csv", "Complaints,1284\r\n".encode("utf-16"), "1284"),
        "a UTF-16 CSV with plain line feeds": ("wide-lf.csv", "Complaints,1284\n".encode("utf-16"), "1284"),
    }
    for label, (name, data, figure) in cases.items():
        got = read(name, data)
        expect(got["problem"] is None and figure in page_of(got), label + " reads", str(got)[:200])
    got = read("nul.csv", b"Complaints,12\x0084\n")
    expect(got["problem"] == "the CSV holds NUL characters, so its encoding is not known",
           "a CSV holding NUL is refused on every Python, so no digits join silently", str(got)[:200])
    got = read("unknown.eml", b'From: a@b.c\nContent-Type: text/plain; charset="unknown-8bit"\n\nThe sample held 1,284 items.\n')
    expect(got["problem"] is None and "1,284" in page_of(got), "an email naming an unknown character set reads when it is plain ASCII", str(got)[:200])
    # a private x- name no Python will ever know; windows-874 served until Python 3.14 learned it as cp874
    got = read("thai.eml", b'From: a@b.c\nContent-Type: text/plain; charset="x-unregistered"\nContent-Transfer-Encoding: 8bit\n\nHeld \xe1 1,284\n')
    expect(got["problem"] == "the email names a character set this reader does not know",
           "an email naming an unknown character set is refused in words when it is not ASCII: nothing guesses", str(got)[:200])
    word = word_bytes(root, word_run("Held 1,284 items."))
    book = book_bytes(root, [("Sample", None, '<sheetData><row><c><v>1284</v></c></row></sheetData>')])
    for label, name, data in (("an encrypted-flag Word file", "flag.docx", zip_patched(word, flags=1)),
                              ("an unknown-method Word file", "method.docx", zip_patched(word, method=99)),
                              ("an encrypted-flag workbook", "flag.xlsx", zip_patched(book, flags=1)),
                              ("an unknown-method workbook", "method.xlsx", zip_patched(book, method=99))):
        got = read(name, data)
        expect(bool(got["problem"]) and not got["problem"].startswith("RAISED") and got["pages"] == [],
               label + " comes back as a reason", str(got)[:200])
    folder = ia(root, "reader-raises-case")
    (folder / "evidence" / "EV-60-mac.csv").write_bytes(b"Complaints,1284\rTotal,1284\r")
    (folder / "evidence" / "EV-61-mail.eml").write_bytes(b'From: a@b.c\nContent-Type: text/plain; charset="unknown-8bit"\n\nHeld 7 items.\n')
    try:
        code, out, _ = run(["covers", str(folder)])
    except Exception as exc:
        code, out = 99, "RAISED {}".format(type(exc).__name__)
    expect(code in (0, 1) and "evidence/EV-60-mac.csv: 1 page, 1 with text. Draft cover written for evidence id EV-60." in out
           and "evidence/EV-61-mail.eml: 1 page, 1 with text. Draft cover written for evidence id EV-61." in out,
           "covers gets through a folder holding such files", out)
    bad = with_document(root, "reader-raises-typed", "EV-30-bad.docx", zip_patched(word, flags=1), "The listing held 1,284 items [EV-30 p1].")
    try:
        code, out, _ = check(bad)
    except Exception as exc:
        code, out = 99, "RAISED {}".format(type(exc).__name__)
    expect(code == 1 and docs.DAMAGED + ". Type it into the cover under ## Page 1." in out,
           "a document that cannot be read puts a plain reason on the row", out)


def test_reader_word(root):
    """The Word path's reasons, its DOCTYPE search and hidden text."""
    docs, read = reader_in(root, "reader-word")
    ole = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\0" * 600
    got = read("locked.docx", ole)
    expect(got["problem"] == "the Word file is password protected, or is an old .doc file",
           "a password-protected Word file says so in words", str(got)[:200])
    got = read("junk.docx", b"not a zip at all")
    expect(got["problem"] == "the Word file could not be read: not a readable .docx (File is not a zip file)",
           "a reason about a Word file names no file and no folder, so a file name cannot refuse the page", str(got)[:200])
    screens = []
    for parent in ("Neutral", "Wrenfield"):
        (root / parent).mkdir()
        folder = with_document(root, parent + "/case", "EV-30-listing.docx", ole, "The listing held 9,999 items [EV-30 p1].")
        code, out, _ = check(folder)
        screens.append(out)
        expect("Refused" not in out and "the Word file is password protected, or is an old .doc file. Type it into the cover" in out,
               "a folder named after the institution does not turn an unreadable Word file into a deny-list refusal", out)
    expect(screens[0] == screens[1], "the screen is the same whatever the folder is called", diff_hint(screens[0], screens[1]))
    got = read("locked.xlsx", ole)
    expect(got["problem"] == "the workbook is password protected, or is an old .xls file",
           "a password-protected workbook says so in words", str(got)[:200])
    saved = docs.MAX_WORD_TAGS
    try:
        docs.MAX_WORD_TAGS = 10
        got = read("tags.docx", word_bytes(root, word_run("Held 1,284.") * 3))
    finally:
        docs.MAX_WORD_TAGS = saved
    expect(got["problem"] == "the Word file is too large to read",
           "a Word part with more tags than its tree can hold is refused before it is parsed", str(got)[:200])
    source = (HERE / "documents.py").read_text(encoding="utf-8")
    expect(source.count("== OLE_HEADER") == 1 and source.count("if _holds_doctype(data)") == 1,
           "the Word file and the workbook share one refusal of an OLE file and one set of guards on a part",
           "{} OLE checks, {} DOCTYPE searches".format(source.count("== OLE_HEADER"), source.count("if _holds_doctype(data)")))

    # The DOCTYPE search. Small files, because the point is that nothing parses them.
    doctype = '<!DOCTYPE l [<!ENTITY a "9,999">]>'
    for label, encoding in (("UTF-8", "utf-8"), ("UTF-16", "utf-16")):
        path = root / "doctype.docx"
        with zipfile.ZipFile(str(path), "w") as zf:
            body = '<?xml version="1.0" encoding="{}"?>{}<w:document {}><w:body><w:p><w:r><w:t>&a;</w:t></w:r></w:p></w:body></w:document>'.format(
                label, doctype, WORD_NS)
            zf.writestr("word/document.xml", body.encode(encoding))
        got = read("doctype-{}.docx".format(label), path.read_bytes())
        path.unlink()
        expect(got["problem"] == "the Word file holds a DOCTYPE, which the reader refuses",
               "a {} Word part holding a DOCTYPE is refused before it is parsed".format(label), str(got)[:200])
        path = root / "doctype.xlsx"
        ns = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
        with zipfile.ZipFile(str(path), "w") as zf:
            zf.writestr("xl/workbook.xml", '<workbook {} xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                        '<sheets><sheet name="S" r:id="rId1"/></sheets></workbook>'.format(ns))
            zf.writestr("xl/_rels/workbook.xml.rels", '<Relationships><Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>')
            sheet = '<?xml version="1.0" encoding="{}"?>{}<worksheet {}><sheetData><row><c t="inlineStr"><is><t>&a;</t></is></c></row></sheetData></worksheet>'.format(
                label, doctype, ns)
            zf.writestr("xl/worksheets/sheet1.xml", sheet.encode(encoding))
        got = read("doctype-{}.xlsx".format(label), path.read_bytes())
        path.unlink()
        expect(got["problem"] == "the workbook holds a DOCTYPE, which the reader refuses",
               "a {} workbook part holding a DOCTYPE is refused before it is parsed".format(label), str(got)[:200])

    # Hidden text in Word.
    hidden_styles = ('<w:style w:type="character" w:styleId="Secret"><w:rPr><w:vanish/></w:rPr></w:style>'
                     '<w:style w:type="paragraph" w:styleId="Base"><w:rPr><w:vanish/></w:rPr></w:style>'
                     '<w:style w:type="paragraph" w:styleId="Child"><w:basedOn w:val="Base"/></w:style>')
    refused = {
        "a run marked hidden": word_bytes(root, word_run("Held 1,284.") + word_run("Held 9,999.", "<w:vanish/>")),
        "white text with nothing behind it": word_bytes(root, word_run("Held 1,284.") + word_run("Held 9,999.", '<w:color w:val="FFFFFF"/>')),
        "a run in a hidden character style": word_bytes(root, word_run("Held 9,999.", '<w:rStyle w:val="Secret"/>'), hidden_styles),
        "a paragraph whose style inherits hidden": word_bytes(
            root, '<w:p><w:pPr><w:pStyle w:val="Child"/></w:pPr><w:r><w:t>Held 9,999.</w:t></w:r></w:p>', hidden_styles),
    }
    for label, data in refused.items():
        got = read("hidden.docx", data)
        expect(got["problem"] == "the Word file holds hidden or white text; show or delete it in Word",
               "a Word file with {} is refused in words".format(label), str(got)[:200])
    kept = {
        "a hidden mark switched off": word_bytes(root, word_run("Held 9,999.", '<w:vanish w:val="0"/>')),
        "a hidden paragraph mark": word_bytes(root, '<w:p><w:pPr><w:rPr><w:vanish/></w:rPr></w:pPr><w:r><w:t>Held 9,999.</w:t></w:r></w:p>'),
        "white text on a shaded run": word_bytes(root, word_run("Held 9,999.", '<w:color w:val="FFFFFF"/><w:shd w:val="clear" w:fill="1F3864"/>')),
        "white text in a shaded cell": word_bytes(root, '<w:tbl><w:tr><w:tc><w:tcPr><w:shd w:val="clear" w:fill="1F3864"/></w:tcPr>'
                                                  + word_run("Held 9,999.", '<w:color w:val="FFFFFF"/>') + "</w:tc></w:tr></w:tbl>"),
    }
    for label, data in kept.items():
        got = read("shown.docx", data)
        expect(got["problem"] is None and "9,999" in page_of(got), "a Word file with {} reads".format(label), str(got)[:200])
    folder = with_document(root, "reader-word-hidden", "EV-30-listing.docx", refused["a run marked hidden"], "The listing held 9,999 items [EV-30 p1].")
    code, out, _ = check(folder)
    expect(code == 1 and "the Word file holds hidden or white text; show or delete it in Word. Type it into the cover" in out,
           "a figure in hidden Word text does not tie", out)


def test_reader_caps(root):
    """Small files must not take unbounded memory or never finish. Counted caps give the same refusal every
    run. Caps are lowered here where the real one would take a gigabyte to reach."""
    docs, read = reader_in(root, "reader-caps")
    too_much = docs.TOO_MUCH
    got = read("predictor.pdf", one_page_pdf("", objects={5: stream_obj(zlib.compress(b"\0" * 64), b" /Filter /FlateDecode /DecodeParms << /Predictor 12 /Columns 2000000000 >>")}))
    expect(got["problem"] == "a stream in the PDF is too large to read", "a predictor row of two gigabytes is refused before it is built", str(got)[:200])
    got = read("predictor-huge.pdf", one_page_pdf("", objects={5: stream_obj(zlib.compress(b"\0" * 64), b" /Filter /FlateDecode /DecodeParms << /Predictor 12 /Columns 90000000000000000000 >>")}))
    expect(got["problem"] == "a stream in the PDF is too large to read", "a predictor row past all memory is refused in words", str(got)[:200])
    got = read("runlength.pdf", one_page_pdf("", objects={5: stream_obj(zlib.compress(b"\x81A" * 1000000), b" /Filter [/FlateDecode /RunLengthDecode]")}))
    expect(got["problem"] == "a stream in the PDF is too large to read", "run-length decoding is capped", str(got)[:200])
    stream = stream_obj(SHOWN.encode() + b" " * 1000000)
    objects = {1: b"<< /Type /Catalog /Pages 2 0 R >>", 2: b"<< /Type /Pages /Count 1 /Kids [4 0 R] >>",
               3: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
               4: "<< /Type /Page /Parent 2 0 R /Contents [{}] /Resources << /Font << /F1 3 0 R >> >> >>".format("5 0 R " * 100).encode(), 5: stream}
    got = read("contents.pdf", pdf_bytes(objects))
    expect(got["problem"] == "a page in the PDF is too large to read", "a page listing one stream many times is capped", str(got)[:200])
    calls = " ".join("/Fm0 Do" for _ in range(40))
    fan = {6: stream_obj(calls.encode(), b" /Type /XObject /Subtype /Form /BBox [0 0 612 792] /Resources << /XObject << /Fm0 6 0 R >> >>")}
    first = read("fan.pdf", one_page_pdf(SHOWN + " /Fm0 Do", "/XObject << /Fm0 6 0 R >>", objects=fan))
    second = read("fan.pdf", one_page_pdf(SHOWN + " /Fm0 Do", "/XObject << /Fm0 6 0 R >>", objects=fan))
    expect(first["pages"] == ["The sample held 9,999 items."] and first["partly"] == [1] and first == second,
           "a form that calls itself ends, says the page was read in part and reads the same each run", str(first)[:200])
    for label, cmap in (("a map repeating a begin marker", b"begincodespacerange " * 20000),
                        ("a map with an unclosed array", b"beginbfrange " + b"<0><0>[ " * 40000 + b"endbfrange")):
        got = read("cmap.pdf", one_page_pdf(SHOWN, objects={3: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /ToUnicode 6 0 R >>", 6: stream_obj(cmap)}))
        expect(got["problem"] is None and "9,999" in page_of(got), label + " reads in one pass", str(got)[:200])
    wide = b"beginbfrange " + b"".join("<{:06X}><{:06X}><0041> ".format(k * 70000, k * 70000 + 65535).encode() for k in range(60)) + b"endbfrange"
    got = read("cmap-wide.pdf", one_page_pdf(SHOWN, objects={3: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /ToUnicode 6 0 R >>", 6: stream_obj(wide)}))
    expect(got["problem"] == too_much, "a font map too large to hold is refused in words", str(got)[:200])
    book = book_bytes(root, [("Sample", None, "<sheetData/>")])
    with zipfile.ZipFile(str(root / "twice.xlsx"), "w") as out:
        with zipfile.ZipFile(io.BytesIO(book)) as source:
            for name in source.namelist():
                if name != "xl/workbook.xml":
                    out.writestr(name, source.read(name))
        ns = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
        out.writestr("xl/workbook.xml", '<workbook {} xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>{}</sheets></workbook>'.format(
            ns, '<sheet name="S" r:id="rId1"/>' * 2000))
    got = read("twice.xlsx", (root / "twice.xlsx").read_bytes())
    expect(got["problem"] == "the workbook has too many sheets to read", "a workbook listing a sheet thousands of times is refused", str(got)[:200])
    with zipfile.ZipFile(str(root / "two.xlsx"), "w") as out:
        with zipfile.ZipFile(io.BytesIO(book)) as source:
            for name in source.namelist():
                if name != "xl/workbook.xml":
                    out.writestr(name, source.read(name))
        out.writestr("xl/workbook.xml", '<workbook {} xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>{}</sheets></workbook>'.format(
            ns, '<sheet name="S" r:id="rId1"/>' * 2))
    got = read("two.xlsx", (root / "two.xlsx").read_bytes())
    expect(got["problem"] == "the workbook lists the same sheet twice, so its page numbers cannot be trusted",
           "a sheet listed twice is refused", str(got)[:200])
    got = read("long-head.eml", b"From: a@b.c\nTo: " + b"x@y.z, " * 400000 + b"\nContent-Type: text/plain\n\nHeld 1,284.\n")
    expect(got["problem"] == "the email's header lines are too long to read", "a very long email header is refused before it is parsed", str(got)[:200])
    got = read("bad-html.eml", email_bytes(("text/html", "<a " * 300000)))
    expect(not got["problem"] or "RAISED" not in got["problem"], "a broken HTML body ends in one pass", str(got)[:200])
    saved = docs.MAX_DECODED, docs.MAX_STEPS, docs.MAX_PAGE_GLYPHS
    try:
        docs.MAX_DECODED = 8 * 1024 * 1024
        heads = b"".join("{} 0 obj\n<< /Length 0 >>\nstream\n".format(n).encode() for n in range(6, 300))
        got = read("overlap.pdf", b"%PDF-1.5\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n" + heads + b"x" * 500000 + b"\nendstream\nendobj\n")
        expect(got["problem"] == "no pages were found in the PDF", "stream headers that all run to one end cost one pass", str(got)[:200])
        repeat = {1: b"<< /Type /Catalog /Pages 2 0 R >>", 3: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
                  2: "<< /Type /Pages /Count 20 /Kids [{}] >>".format(" ".join("{} 0 R".format(n) for n in range(10, 30))).encode(),
                  5: stream_obj(b" " * 1000000, deflate=True)}
        for n in range(10, 30):
            repeat[n] = b"<< /Type /Page /Parent 2 0 R /Contents 5 0 R >>"
        got = read("repeat.pdf", pdf_bytes(repeat))
        expect(got["problem"] == too_much, "pages that decode one stream again and again are capped by what they decode", str(got)[:200])
        many = {n: stream_obj(zlib.compress(b"1 0 " * 300000), b" /Type /ObjStm /N 0 /First 0 /Filter /FlateDecode") for n in range(6, 20)}
        got = read("object-streams.pdf", b"%PDF-1.5\n" + b"".join(str(n).encode() + b" 0 obj\n" + body + b"\nendobj\n" for n, body in many.items()))
        expect(got["problem"] == too_much, "object streams that decode past the cap are refused", str(got)[:200])
        docs.MAX_DECODED = saved[0]
        docs.MAX_STEPS = 20000
        got = read("steps.pdf", one_page_pdf("0 0 m " * 20000))
        expect(got["problem"] == too_much, "operators past the cap are refused", str(got)[:200])
        docs.MAX_STEPS = saved[1]
        docs.MAX_PAGE_GLYPHS = 100
        got = read("glyphs.pdf", one_page_pdf("BT /F1 12 Tf 72 700 Td ({}) Tj ET".format("x" * 200)))
        expect(got["problem"] == too_much, "glyphs past the page cap are refused", str(got)[:200])
    finally:
        docs.MAX_DECODED, docs.MAX_STEPS, docs.MAX_PAGE_GLYPHS = saved
    saved = docs.MAX_TEXT, docs.MAX_FIGURES
    try:
        docs.MAX_FIGURES = 3
        got = read("figures.csv", b"1,2\n3,4\n5,6\n")
        expect(got["problem"] == docs.TOO_MUCH_TEXT and got["pages"] == [], "a file with more figures than the check can hold is refused in words", str(got)[:200])
        docs.MAX_FIGURES = saved[1]
        docs.MAX_TEXT = 10
        got = read("text.txt", b"x" * 20)
        expect(got["problem"] == docs.TOO_MUCH_TEXT, "a file with more text than the check can hold is refused in words", str(got)[:200])
    finally:
        docs.MAX_TEXT, docs.MAX_FIGURES = saved
    source = (HERE / "documents.py").read_text(encoding="utf-8")
    expect("import time" not in source and "time." not in source, "the reader's caps are counted, with no clock")


def test_reader_hidden_pdf(root):
    """Text a reader cannot see does not tie, and a scan's invisible layer stays out of the document's text."""
    docs, read = reader_in(root, "reader-hidden")
    off_layer = {"catalog": "/OCProperties << /OCGs [7 0 R] /D << /OFF [7 0 R] >> >>"}
    group = b"<< /Type /OCG /Name (Draft) >>"
    hidden = {
        "a black bar": dict(content=SHOWN + " 0 0 0 rg " + BAR),
        "a white patch": dict(content=SHOWN + " 1 1 1 rg " + BAR),
        "a bar drawn with lines": dict(content=SHOWN + " 0 0 0 rg 60 650 m 380 650 l 380 680 l 60 680 l h f"),
        "a wide stroked line": dict(content=SHOWN + " 0 0 0 RG 30 w 60 665 m 380 665 l S"),
        "an image": dict(content=SHOWN + " q 320 0 0 30 60 650 cm /Im0 Do Q", resources=IMAGE, objects={6: IMAGE_OBJ}),
        "white ink": dict(content="1 1 1 rg " + SHOWN),
        "ink the colour of the fill under it": dict(content="0 0 0 rg " + BAR + " " + SHOWN),
        "render mode 3": dict(content="BT /F1 14 Tf 3 Tr 72 660 Td (The sample held 9,999 items.) Tj ET"),
        "render mode 7": dict(content="BT /F1 14 Tf 7 Tr 72 660 Td (The sample held 9,999 items.) Tj ET"),
        "a place off the page": dict(content="BT /F1 14 Tf 72 9000 Td (The sample held 9,999 items.) Tj ET"),
        "a run that starts right of the page": dict(content="BT /F1 14 Tf 700 660 Td (The sample held 9,999 items.) Tj ET"),
        "a run that starts far left of the page": dict(content="BT /F1 14 Tf -2000 660 Td (The sample held 9,999 items.) Tj ET"),
        "character spacing that carries it off the page": dict(content="BT /F1 14 Tf 40 Tc 72 660 Td (The sample held 9,999 items.) Tj ET"),
        "word spacing that carries it off the page": dict(content="BT /F1 14 Tf 300 Tw 72 660 Td (The sample held 9,999 items.) Tj ET"),
        "a TJ offset that carries it off the page": dict(content="BT /F1 14 Tf 72 660 Td [(The sample held) -40000 (9,999 items.)] TJ ET"),
        "horizontal scaling of its spacing": dict(content="BT /F1 14 Tf 4 Tc 1000 Tz 72 660 Td (The sample held 9,999 items.) Tj ET"),
        "a rise off the page": dict(content="BT /F1 14 Tf 9000 Ts 72 660 Td (The sample held 9,999 items.) Tj ET"),
        "a transform off the page": dict(content="q 1 0 0 1 900 0 cm " + SHOWN + " Q"),
        "horizontal scaling, in a font with widths": dict(content="BT /F1 14 Tf 1000 Tz 72 660 Td (The sample held 9,999 items.) Tj ET",
                                                          objects=WIDTHS),
        "a stretching transform, in a font with widths": dict(content="q 30 0 0 1 0 0 cm BT /F1 14 Tf 2 660 Td (The sample held 9,999 items.) Tj ET Q",
                                                              objects=WIDTHS),
        "a long line whose widths run it off the page": dict(content="BT /F1 10 Tf 64 500 Td ({}) Tj ET".format(LONG_LINE), objects=WIDTHS),
        "horizontal scaling alone, in a font with no widths": dict(content="BT /F1 14 Tf 3000 Tz 72 660 Td (The sample held 9,999 items.) Tj ET"),
        "a stretching transform, in a font with no widths": dict(content="q 30 0 0 1 0 0 cm BT /F1 14 Tf 2 660 Td (The sample held 9,999 items.) Tj ET Q"),
        "a stretching text matrix, in a font with no widths": dict(content="BT /F1 14 Tf 30 0 0 1 60 660 Tm (The sample held 9,999 items.) Tj ET"),
        "a line too long at any width, in a font with no widths": dict(content="BT /F1 14 Tf 72 660 Td ({} 9,999) Tj ET".format("x" * 300)),
        "a place outside the crop box": dict(content=SHOWN, page="/CropBox [0 0 612 600]"),
        "a clip": dict(content="q 0 0 100 100 re W n " + SHOWN + " Q"),
        "alpha zero": dict(content="/G0 gs " + SHOWN, resources="/ExtGState << /G0 << /ca 0 >> >>"),
        "font size zero": dict(content="BT /F1 0 Tf 72 660 Td (The sample held 9,999 items.) Tj ET"),
        "font size 0.05": dict(content="BT /F1 0.05 Tf 72 660 Td (The sample held 9,999 items.) Tj ET"),
        "a layer switched off": dict(content="/OC /MC0 BDC " + SHOWN + " EMC", resources="/Properties << /MC0 7 0 R >>",
                                     objects={7: group}, **off_layer),
        "a form on a layer switched off": dict(content="/Fm0 Do", resources="/XObject << /Fm0 8 0 R >>", objects={
            7: group, 8: stream_obj(SHOWN.encode(), b" /Type /XObject /Subtype /Form /BBox [0 0 612 792] /OC 7 0 R /Resources << /Font << /F1 3 0 R >> >>")}, **off_layer),
        "a form whose box clips it": dict(content="/Fm0 Do", resources="/XObject << /Fm0 8 0 R >>", objects={
            8: stream_obj(SHOWN.encode(), b" /Type /XObject /Subtype /Form /BBox [0 0 10 10] /Resources << /Font << /F1 3 0 R >> >>")}),
        "a filled square comment": dict(content=SHOWN, page="/Annots [8 0 R]", objects={
            8: b"<< /Type /Annot /Subtype /Square /Rect [60 650 380 680] /IC [0 0 0] >>"}),
        "a square comment with an appearance": dict(content=SHOWN, page="/Annots [8 0 R]", objects={
            8: b"<< /Type /Annot /Subtype /Square /Rect [60 650 380 680] /AP << /N 9 0 R >> >>",
            9: stream_obj(b"0 0 0 rg 0 0 320 30 re f", b" /Type /XObject /Subtype /Form /BBox [0 0 320 30]")}),
    }
    for label, parts in hidden.items():
        got = read("hidden.pdf", one_page_pdf(**parts))
        expect(got["problem"] is None and "9,999" not in page_of(got) and got["hidden"].get(1),
               "text under {} is left out and counted".format(label), str(got)[:300])
    shown = {
        "plain on the page": dict(content=SHOWN),
        "white on a dark fill": dict(content="0 0 0.4 rg " + BAR + " 1 1 1 rg " + SHOWN),
        "on a light shade": dict(content="0.9 0.9 0.9 rg " + BAR + " 0 g " + SHOWN),
        "under a thin strike-through": dict(content=SHOWN + " 0 0 0 rg 60 664 320 1 re f"),
        "under a see-through highlight": dict(content=SHOWN + " /G0 gs 1 1 0 rg " + BAR, resources="/ExtGState << /G0 << /ca 0.4 >> >>"),
        "under a multiply highlight": dict(content=SHOWN + " /G0 gs 1 1 0 rg " + BAR, resources="/ExtGState << /G0 << /BM /Multiply >> >>"),
        "under a highlight comment": dict(content=SHOWN, page="/Annots [8 0 R]", objects={
            8: b"<< /Type /Annot /Subtype /Highlight /Rect [60 650 380 680] /AP << /N 9 0 R >> >>",
            9: stream_obj(b"1 1 0 rg 0 0 320 30 re f", b" /Type /XObject /Subtype /Form /BBox [0 0 320 30]")}),
        "white on a rounded dark shape": dict(content="0 0 0 rg 60 650 m 380 650 l 380 680 390 680 390 690 c 60 690 l h f 1 1 1 rg " + SHOWN),
        "white on an image": dict(content="q 320 0 0 30 60 650 cm /Im0 Do Q 1 1 1 rg " + SHOWN, resources=IMAGE, objects={6: IMAGE_OBJ}),
        "in a frame of two rectangles": dict(content=SHOWN + " 0 0 0 rg 40 640 400 60 re 50 645 380 50 re f*"),
        "in a form that draws inside its box": dict(content="/Fm0 Do", resources="/XObject << /Fm0 8 0 R >>", objects={
            8: stream_obj(SHOWN.encode(), b" /Type /XObject /Subtype /Form /BBox [0 0 612 792] /Resources << /Font << /F1 3 0 R >> >>")}),
        "on a layer switched on": dict(content="/OC /MC0 BDC " + SHOWN + " EMC", resources="/Properties << /MC0 7 0 R >>",
                                       objects={7: group}, catalog="/OCProperties << /OCGs [7 0 R] /D << /OFF [] >> >>"),
        "in a long line inside a clip, in a font with no widths": dict(content="q 0 0 580 792 re W n BT /F1 10 Tf 64 500 Td ({}) Tj ET Q".format(LONG_LINE)),
        # ZapfDingbats draws x as a bar 138 units wide, the narrowest glyph of the standard fonts, so this ends at 600.
        "after a line of thin bars, in a font with no widths": dict(content="BT /F1 10 Tf 64 500 Td ({} 9,999) Tj ET".format("x" * 360),
                                                                    objects={3: b"<< /Type /Font /Subtype /Type1 /BaseFont /ZapfDingbats >>"}),
        "after a run of codes with no glyph, in a font with no widths": dict(content="BT /F1 10 Tf 64 500 Td ({} 9,999) Tj ET".format("\x01" * 400)),
        "drawn as shapes with an invisible copy": dict(content="0 g 72 660 m 300 660 l 300 680 310 680 310 690 c 72 690 l h f BT /F1 14 Tf 3 Tr 72 660 Td (The sample held 9,999 items.) Tj ET"),
    }
    for label, parts in shown.items():
        got = read("shown.pdf", one_page_pdf(**parts))
        expect(got["problem"] is None and "9,999" in page_of(got) and not got["hidden"],
               "text {} stays".format(label), str(got)[:300])
    got = read("long.pdf", one_page_pdf("BT /F1 10 Tf 64 500 Td ({}) Tj ET".format(LONG_LINE)))
    expect(page_of(got) == LONG_LINE and not got["hidden"],
           "a line that runs off the page only on a guessed width reads in full, with no word left out", str(got)[:300])
    got = read("patch.pdf", one_page_pdf(SHOWN + " 1 1 1 rg " + BAR + " 0 g BT /F1 14 Tf 72 660 Td (The sample held 1,284 items.) Tj ET"))
    expect("9,999" not in page_of(got) and "1,284" in page_of(got), "a figure typed over a white patch stays and the one under it goes", str(got)[:300])

    # The two ways a scan carries a machine layer, and the case with no image at all.
    misread = "BT /F1 14 Tf 3 Tr 72 700 Td (Reclassified complaints: 1,324 in total.) Tj ET"
    scan = one_page_pdf(SCAN + " " + misread, IMAGE, objects={6: IMAGE_OBJ})
    got = read("ocr.pdf", scan)
    expect(got["pages"] == [""], "a page that is an image with an invisible layer has no text", str(got)[:300])
    got = read("ocr-under.pdf", one_page_pdf("BT /F1 14 Tf 72 700 Td (Reclassified complaints: 1,324 in total.) Tj ET " + SCAN, IMAGE, objects={6: IMAGE_OBJ}))
    expect(got["pages"] == [""], "a layer painted in a visible mode under the image has no text either", str(got)[:300])
    got = read("ocr-stamped.pdf", one_page_pdf(SCAN + " " + misread + " BT /F1 9 Tf 0 Tr 72 40 Td (BANK-000123) Tj ET", IMAGE, objects={6: IMAGE_OBJ}))
    expect("1,324" not in page_of(got) and "BANK-000123" in page_of(got) and got["partly"] == [1],
           "a stamped scan keeps its stamp, loses the layer and counts as read in part", str(got)[:300])

    folder = with_document(root, "reader-hidden-misread", "EV-30-scan.pdf", scan, "The team reclassified 1,324 complaints [EV-30 p1].")
    code, out, _ = check(folder)
    expect(code == 1 and "1,324 is cited to EV-30 p1, and the check cannot read that page: the document has no text a reader can see on that page. "
           "Type it into the cover under ## Page 1." in out, "a misread in a scan's layer does not tie", block_from(out, "Memo check:"))
    run(["covers", str(folder)])
    typed = with_document(root, "reader-hidden-typed", "EV-30-scan.pdf", scan, "The team reclassified 1,824 complaints [EV-30 p1].",
                          "Checked by: Associate 2, 2026-07-02\n\n## Page 1\nReclassified complaints: 1,824 in total.\n")
    code, out, _ = check(typed)
    expect("14 tie, 0 on the list" in out and "14 ties rest on text a person typed" in out,
           "the true figure ties once a person types the scan's page", block_from(out, "Memo check:"))
    code, out, _ = run(["covers", str(folder)])
    expect(("evidence/EV-30-scan.pdf: 1 page, 0 with text; no text on page 1; 5 words a reader cannot see left out on page 1: "
            '"Reclassified", "complaints", "1,324", "in" and "total". It has a cover already.') in out,
           "covers says a scan's page has no text and that its layer was left out", out)

    bar = one_page_pdf(SHOWN + " 0 0 0 rg " + BAR + " 0 g BT /F1 14 Tf 72 620 Td (The sample held 1,284 items.) Tj ET")
    folder = with_document(root, "reader-hidden-bar", "EV-30-bar.pdf", bar, "The listing held 9,999 items [EV-30 p1].")
    code, out, _ = check(folder)
    expect(code == 1 and "9,999 is cited to EV-30 p1, and the page does not hold it; the nearest figure on the page is 1,284. "
           "The page also holds 5 words a reader cannot see, which the check leaves out." in out,
           "a figure under a redaction bar goes on the list and the row says hidden text was left out", block_from(out, "Memo check:"))
    code, out, _ = run(["sign", str(folder), "--today", NOW], stdin=StandInTerminal())
    expect(code == 1 and "Refused: 1 row is on the list" in out, "sign refuses a figure under a redaction bar", out)


def test_reader_excel(root):
    """Hidden sheets, rows and columns, and how a workbook's pages number."""
    docs, read = reader_in(root, "reader-excel")
    seen = "<sheetData><row><c><v>1284</v></c></row></sheetData>"
    prior = "<sheetData><row><c><v>9999</v></c></row></sheetData>"
    for state in ("hidden", "veryHidden"):
        got = read("hidden-sheet.xlsx", book_bytes(root, [("Prior", state, prior), ("Sample", None, seen)]))
        expect(got["pages"] == ["Sample\n1284"] and got["notes"] == ["1 hidden sheet left out"],
               "a {} sheet is left out and pages number by visible sheets".format(state), str(got))
    got = read("hidden-row.xlsx", book_bytes(root, [("Sample", None, '<sheetData><row r="1"><c><v>1284</v></c></row><row r="2" hidden="1"><c><v>9999</v></c></row></sheetData>')]))
    expect(got["pages"] == ["Sample\n1284"] and got["notes"] == ["1 hidden row left out"], "a hidden row is left out", str(got))
    got = read("hidden-col.xlsx", book_bytes(root, [("Sample", None, '<cols><col min="2" max="2" width="0" hidden="1"/></cols>'
                                                     '<sheetData><row r="1"><c r="A1"><v>1284</v></c><c r="B1"><v>9999</v></c></row></sheetData>')]))
    expect(got["pages"] == ["Sample\n1284"] and got["notes"] == ["1 hidden column left out"], "a hidden column is left out", str(got))
    got = read("no-ref.xlsx", book_bytes(root, [("Sample", None, '<cols><col min="2" max="2" hidden="1"/></cols>'
                                                  "<sheetData><row><c><v>1284</v></c><c><v>9999</v></c><c><v>77</v></c></row></sheetData>")]))
    expect(got["pages"] == ["Sample\n1284\t77"], "a cell with no reference finds its column by position", str(got))
    got = read("plain.xlsx", book_bytes(root, [("Sample", None, seen), ("Other", None, prior)]))
    expect(got["pages"] == ["Sample\n1284", "Other\n9999"] and got["notes"] == [], "a workbook with nothing hidden reads as before", str(got))
    book = book_bytes(root, [("Prior", "hidden", prior), ("Sample", None, seen)])
    folder = with_document(root, "reader-excel-case", "EV-30-book.xlsx", book, "The listing held 9,999 items [EV-30 p1].\n\nThe listing held 1,284 items [EV-30 p1].")
    code, out, _ = check(folder)
    expect("9,999 is cited to EV-30 p1, and the page does not hold it; the nearest figure on the page is 1284" in out
           and "1,284 is cited" not in out, "a figure on a hidden sheet goes on the list, and p1 is the first sheet a person can see", block_from(out, "Memo check:"))
    (folder / "evidence" / "EV-31-other.xlsx").write_bytes(book)
    code, out, _ = run(["covers", str(folder)])
    expect("evidence/EV-31-other.xlsx: 1 page, 1 with text; 1 hidden sheet left out. Draft cover written for evidence id EV-31." in out,
           "covers says hidden content was left out", out)
    expect("A PDF page is its printed page. A Word, CSV, email or text file is always page 1" in out
           and "A workbook page is a visible sheet, in workbook order" in out, "covers states what a page is, by file type", out)
    page = pages("assistant/draft-memo.md")
    if page is not None:
        expect("A Word, CSV, email or text file is always p1" in page and "A workbook page is a visible sheet" in page,
               "the memo procedure states what a page is, by file type")


def test_reader_xref(root):
    """The reader follows the cross-reference table, so another object cannot replace a page."""
    docs, read = reader_in(root, "reader-xref")
    true_page = "BT /F1 14 Tf 72 660 Td (Reclassified complaints: 1,284 in total.) Tj ET"
    false_page = stream_obj(b"BT /F1 14 Tf 72 660 Td (Attached draft: the sample held 9,999 items.) Tj ET")
    planted = b"5 0 obj\n" + false_page + b"\nendobj\n"
    routes = {
        "an object quoted inside a stream, as an attached PDF is": one_page_pdf(true_page, objects={9: stream_obj(planted)}),
        "an object after the end of the file": one_page_pdf(true_page) + planted,
        "a later object the table does not point at": one_page_pdf(true_page, unlisted=planted),
        "an orphan catalog with a higher number": one_page_pdf(true_page, objects={
            20: b"<< /Type /Catalog /Pages 21 0 R >>", 21: b"<< /Type /Pages /Count 1 /Kids [22 0 R] >>",
            22: b"<< /Type /Page /Parent 21 0 R /MediaBox [0 0 612 792] /Contents 23 0 R /Resources << /Font << /F1 3 0 R >> >> >>",
            23: false_page}),
    }
    for label, data in routes.items():
        got = read("route.pdf", data)
        expect(got["problem"] is None and "1,284" in page_of(got) and "9,999" not in page_of(got) and not got["notes"],
               "{} cannot replace the page".format(label), str(got)[:300])
    old = one_page_pdf("BT /F1 14 Tf 72 660 Td (Old revision: The sample held 9,999 items.) Tj ET", root=7, objects={7: b"<< /Type /Catalog /Pages 2 0 R >>"})
    new = pdf_update(old, {1: b"<< /Type /Catalog /Pages 12 0 R >>", 12: b"<< /Type /Pages /Count 1 /Kids [13 0 R] >>",
                           13: b"<< /Type /Page /Parent 12 0 R /MediaBox [0 0 612 792] /Contents 14 0 R /Resources << /Font << /F1 3 0 R >> >> >>",
                           14: stream_obj(b"BT /F1 14 Tf 72 660 Td (New revision: The sample held 1,284 items.) Tj ET")})
    got = read("revision.pdf", new)
    expect("New revision" in page_of(got) and "9,999" not in page_of(got), "an incremental update whose catalog has a lower number reads the new revision", str(got)[:300])
    same = pdf_update(one_page_pdf("BT /F1 14 Tf 72 660 Td (Old 9,999.) Tj ET"), {5: stream_obj(b"BT /F1 14 Tf 72 660 Td (New 1,284.) Tj ET")})
    got = read("same-number.pdf", same)
    expect(got["pages"] == ["New 1,284."], "an update of the same object number reads the new object", str(got)[:300])
    got = read("xref-stream.pdf", xref_stream_pdf("Held in an object stream 402"))
    expect(got["pages"] == ["Held in an object stream 402"] and not got["notes"], "a cross-reference stream and its object stream are followed", str(got)[:300])
    broken = re.sub(rb"startxref\s+\d+", b"startxref\n7", one_page_pdf(true_page, objects={9: stream_obj(planted)}))
    got = read("broken.pdf", broken)
    expect("1,284" in page_of(got) and "9,999" not in page_of(got) and any("scanning" in note for note in got["notes"]),
           "a broken table falls back to a scan that skips stream bodies, and the file says so", str(got)[:300])
    data = one_page_pdf(true_page + " %/Encrypt") + b"%/Encrypt\n"
    got = read("comment.pdf", data)
    expect(got["problem"] is None and "1,284" in page_of(got), "a comment holding the word Encrypt does not make a file encrypted", str(got)[:300])
    got = read("orphan-deep.pdf", one_page_pdf(true_page, objects={9: b"[" * 41 + b"]" * 41}))
    expect(got["problem"] is None and "1,284" in page_of(got), "one unused object nested too deep does not fail the file", str(got)[:300])
    got = read("attached.pdf", simple_pdf(["Reclassified 1,284 complaints."], trailer_extra="/Encrypt 9 0 R"))
    expect(got["problem"] == "the PDF is encrypted", "an encrypted trailer is still refused", str(got)[:300])


def test_reader_typed_pages(root):
    """Where a typed page stands, and where the screen says it did not."""
    docs, read = reader_in(root, "reader-typed")
    cover = "\n## Page 1\nThe sample held 1,824 items.\n"
    memo = "The listing held 1,824 items [EV-30 p1]."
    typed_line = "14 ties rest on text a person typed"  # the 13 on IA-CMP-02's text files and this one
    stamped = one_page_pdf(SCAN + " BT /F1 9 Tf 72 40 Td (CONFIDENTIAL BANK-000123) Tj ET", IMAGE, objects={6: IMAGE_OBJ})
    no_map = {6: b"<< /Type /Font /Subtype /Type0 /BaseFont /Example /Encoding /Identity-H /DescendantFonts [7 0 R] >>",
              7: b"<< /Type /Font /Subtype /CIDFontType2 /BaseFont /Example >>"}
    mixed = one_page_pdf("BT /F1 12 Tf 72 700 Td (Heading) Tj ET BT /F2 12 Tf 72 680 Td <00140018001A001B> Tj ET", fonts="/F2 6 0 R", objects=no_map)
    form = one_page_pdf("BT /F1 12 Tf 72 700 Td (Sample size:) Tj ET", page="/Annots [8 0 R]", objects={
        8: b"<< /Type /Annot /Subtype /Widget /Rect [200 690 300 710] /AP << /N 9 0 R >> >>",
        9: stream_obj(b"BT /F1 12 Tf 0 0 Td (1,824) Tj ET", b" /Type /XObject /Subtype /Form /BBox [0 0 100 20] /Resources << /Font << /F1 3 0 R >> >>")})
    subset = one_page_pdf("BT /F4 12 Tf 72 700 Td <0102030405> Tj ET", fonts="/F4 6 0 R",
                          objects={6: b"<< /Type /Font /Subtype /TrueType /BaseFont /ABCDEF+Example >>"})
    nest = {}
    for level in range(6, 15):
        inner = "/Fm{} Do".format(level + 1) if level < 14 else "BT /F1 12 Tf 72 680 Td (The sample held 1,824 items.) Tj ET"
        nest[level] = stream_obj(inner.encode(), "/Type /XObject /Subtype /Form /BBox [0 0 612 792] /Resources << /Font << /F1 3 0 R >> /XObject << /Fm{} {} 0 R >> >>".format(level + 1, level + 1).encode())
    deep = one_page_pdf("BT /F1 12 Tf 72 700 Td (Heading) Tj ET /Fm6 Do", "/XObject << /Fm6 6 0 R >>", objects=nest)
    for label, data in (("a stamped scan", stamped), ("a heading over a font with no map", mixed), ("a filled form", form),
                        ("a font that reads as control characters", subset), ("a form nested too deep", deep)):
        folder = with_document(root, "typed-" + re.sub(r"\W", "-", label), "EV-30-listing.pdf", data, memo, cover)
        code, out, _ = check(folder)
        expect("14 tie, 0 on the list" in out and typed_line in out, "a typed page stands on " + label + " and counts as typed", block_from(out, "Memo check:"))
    got = read("subset.pdf", subset)
    expect(got["pages"] == [""], "a simple font with no map reads as no text, as the reader's page says", str(got)[:200])
    got = read("mixed.pdf", mixed)
    expect(got["partly"] == [1], "a page with a font it cannot map counts as read in part", str(got)[:200])
    folder = with_document(root, "typed-stamped-hint", "EV-30-listing.pdf", stamped, memo)
    code, out, _ = check(folder)
    expect("The check read this page only in part; if the page shows it, type it into the cover under ## Page 1." in out,
           "the row says how to answer a page read in part", block_from(out, "Memo check:"))
    code, out, _ = run(["covers", str(folder)])
    expect("evidence/EV-30-listing.pdf: 1 page, 1 with text; read only in part: page 1." in out, "covers says which pages were read in part", out)
    (folder / "evidence" / "EV-30-listing.pdf.md").unlink()
    plain = one_page_pdf("BT /F1 12 Tf 72 700 Td (The sample held 1,284 items.) Tj ET")
    folder = with_document(root, "typed-unused", "EV-30-listing.pdf", plain, memo, cover)
    code, out, _ = check(folder)
    expect(code == 1 and "1,824 is cited to EV-30 p1, and the page does not hold it; the nearest figure on the page is 1,284. "
           "The typed page 1 in the cover was not used, because the check read the document's own text there." in out,
           "a typed page never overrides a page the reader read, and the row says it was not used", block_from(out, "Memo check:"))

    # A typed page past the end of the document, and a cover note that is no page.
    listing = simple_pdf(["Page one.", "Page two.", "Page three."])
    folder = with_document(root, "typed-past-end", "EV-30-listing.pdf", listing, "The sample held 9,999 complaints [EV-30 p9].",
                           "\n## Page 9\nThe sample held 9,999 complaints.\n")
    code, out, _ = check(folder)
    expect(code == 1 and "9,999 is cited to EV-30 p9, and EV-30 has 3 pages." in out, "a typed page past the end of a PDF does not tie", block_from(out, "Memo check:"))
    code, out, _ = run(["sign", str(folder), "--today", NOW], stdin=StandInTerminal())
    expect(code == 1 and "Refused: 1 row is on the list" in out, "sign refuses a typed page past the end", out)
    folder = with_document(root, "typed-past-end-csv", "EV-30-rows.csv", b"Complaints,1284\n", "The rows held 8,888 items [EV-30 p2].",
                           "\n## Page 2\nThe rows held 8,888 items.\n")
    code, out, _ = check(folder)
    expect("8,888 is cited to EV-30 p2, and EV-30 has 1 page." in out, "a typed page 2 on a one-page CSV does not tie", block_from(out, "Memo check:"))
    word = word_bytes(root, word_run("Held 1,284."))
    folder = with_document(root, "typed-past-end-word", "EV-30-note.docx", word, "The note held 8,888 items [EV-30 p2].",
                           "\n## Page 2\nThe note held 8,888 items.\n")
    code, out, _ = check(folder)
    expect("8,888 is cited to EV-30 p2, and EV-30 has 1 page." in out, "a typed page 2 on a Word file does not tie", block_from(out, "Memo check:"))
    blank = simple_pdf([""])
    folder = with_document(root, "typed-note", "EV-30-scan.pdf", blank, "The sample held 9,999 items [EV-30 p1].", "\nPreparer note: the sample held 9,999 items.\n")
    code, out, _ = check(folder)
    expect(code == 1 and "Type it into the cover under ## Page 1." in out, "a note in a scan's cover with no page heading is no page", block_from(out, "Memo check:"))

    # A refused document's typed page may tie, and the refusal is printed beside it.
    tracked = word_bytes(root, '<w:p><w:ins w:id="1" w:author="a" w:date="2026-01-01T00:00:00Z"><w:r><w:t>Held 7.</w:t></w:r></w:ins></w:p>')
    folder = with_document(root, "typed-tracked", "EV-30-note.docx", tracked, memo, "Checked by: Associate 2, 2026-07-02\n" + cover)
    code, out, _ = check(folder)
    expect(typed_line in out and "  EV-30 was not read: the Word file still holds tracked changes." in out,
           "a refused document's reason is printed even when its typed page ties", block_from(out, "Memo check:"))

    # A second person has to compare a typed page before anyone signs.
    folder = with_document(root, "typed-unchecked", "EV-30-scan.pdf", blank, memo, cover)
    code, out, _ = check(folder)
    expect(code == 1 and "14 ties rest on text a person typed: 13 in plain-text evidence, 1 on a page typed into a cover, 1 with no Checked by line." in out and "The engagement team: a second person's Checked by line on 1 tie typed into a cover." in out
           and "Ready to sign" not in out, "the screen says a typed tie needs a second person, so it never says ready to sign", out)
    code, out, _ = run(["sign", str(folder), "--today", NOW], stdin=StandInTerminal())
    expect(code == 1 and out.endswith(refusal("Refused: 1 tie rests on text typed into a cover with no Checked by line.")),
           "sign refuses a typed tie nobody compared", out)
    edit(folder / "evidence" / "EV-30-scan.pdf.md", "Status: FINAL", "Status: FINAL\nChecked by: Associate 2, 2026-07-02")
    edit(folder / "evidence" / "EV-30-scan.pdf.md", "Head of Complaints, 2026-07-01", "Head of Complaints, 2026-07-02")
    code, out, _ = check(folder)
    expect("Ready to sign" in out and "14 ties rest on text a person typed: 13 in plain-text evidence, 1 on a page typed into a cover, "
           "with a Checked by line." in out and "The engagement team" not in out and "with no Checked by line" not in out,
           "a Checked by line answers it, and the plain-text evidence is never said to lack one", out)


def test_reader_email(root):
    """An email reads as the HTML a person sees."""
    docs, read = reader_in(root, "reader-email")
    visible = "<p>The sample held 1,284 items.</p>"
    hidden = {
        "a display:none block": visible + '<div style="display:none">The sample held 9,999 items.</div>',
        "a display: none block with a space": visible + '<div style="DISPLAY: none">9,999</div>',
        "a hidden attribute": visible + "<div hidden>9,999</div>",
        "a CSS comment": "<head><style>/* 9,999 */ .x{margin:0}</style></head>" + visible,
        "a script": visible + '<script>var a="9,999";</script>',
        "a head title": "<head><title>9,999</title></head>" + visible,
        "an HTML comment": visible + "<!-- 9,999 -->",
        "a class a style sheet hides": '<style>.gone, .x { display: none; }</style>' + visible + '<div class="y gone">9,999</div>',
        "white ink on nothing": visible + '<span style="color:#ffffff">9,999</span>',
        "an unclosed comment": visible + "<!-- 9,999",
    }
    for label, body in hidden.items():
        got = read("hidden.eml", email_bytes(("text/html", body)))
        expect(got["problem"] is None and "9,999" not in page_of(got) and "1,284" in page_of(got),
               "a figure in {} is left out of an email".format(label), str(got)[:300])
    got = read("void.eml", email_bytes(("text/html", '<img hidden src="x"><p>The sample held 9,999 items.</p>')))
    expect("9,999" in page_of(got), "a hidden image does not swallow the rest of the mail", str(got)[:300])
    got = read("white.eml", email_bytes(("text/html", '<table bgcolor="#123456"><tr><td style="color:#fff">9,999</td></tr></table>')))
    expect("9,999" in page_of(got), "white ink on a painted background stays", str(got)[:300])
    got = read("entities.eml", email_bytes(("text/html", "<p>The sample held 9&#44;999&nbsp;items &amp; more.</p>")))
    expect("The sample held 9,999 items & more." in page_of(got), "an email's entities are decoded", str(got)[:300])
    got = read("inline.eml", email_bytes(("text/html", "<p>Held <b>9</b>,<i>999</i>.</p><table><tr><td>12</td><td>34</td></tr></table>")))
    expect("Held 9,999." in page_of(got) and "12 34" in page_of(got), "inline tags join and cells keep apart", str(got)[:300])
    got = read("differs.eml", email_bytes(("text/plain", "The sample held 9,999 items."), ("text/html", visible)))
    expect(got["problem"] == "the email's plain part and its HTML part hold different figures", "parts that disagree are refused in words", str(got)[:300])
    got = read("agrees.eml", email_bytes(("text/plain", "The sample held 1,284 items. http://x.y/99"), ("text/html", visible)))
    expect(got["problem"] is None and "1,284" in page_of(got), "parts that agree read as the HTML", str(got)[:300])
    attached = (b'From: a@b.c\nSubject: See attached\nContent-Type: multipart/mixed; boundary="b"\n\n--b\n'
                b'Content-Type: application/pdf\nContent-Disposition: attachment; filename="x.pdf"\n\nAAAA\n--b--\n')
    got = read("attached.eml", attached)
    expect(got["problem"] == "the email has no body text of its own, so its content is in an attachment",
           "an email with only an attachment says so", str(got)[:300])
    folder = with_document(root, "reader-email-case", "EV-30-mail.eml", email_bytes(("text/html", "<p>The sample held 9&#44;999 items.</p>")), "The listing held 9,999 items [EV-30 p1].")
    code, out, _ = check(folder)
    expect("14 tie, 0 on the list" in out, "a figure written with an entity ties", block_from(out, "Memo check:"))
    folder = with_document(root, "reader-email-hidden", "EV-30-mail.eml", email_bytes(("text/html", visible + '<div style="display:none">9,999</div>')), "The listing held 9,999 items [EV-30 p1].")
    code, out, _ = check(folder)
    expect(code == 1 and "9,999 is cited to EV-30 p1, and the page does not hold it" in out, "a figure in hidden HTML does not tie", block_from(out, "Memo check:"))


def test_reader_page_text(root):
    """Rotated text keeps its words, and q and Q restore the font."""
    docs, read = reader_in(root, "reader-text")
    words = "[(The)-278(sample)-278(held)-278(9,999)-278(items.)]"
    flat = read("flat.pdf", one_page_pdf("BT /F1 12 Tf 1 0 0 1 72 700 Tm {} TJ ET".format(words)))
    for label, matrix in (("90", "0 1 -1 0 300 200"), ("270", "0 -1 1 0 300 700")):
        got = read("rot.pdf", one_page_pdf("BT /F1 12 Tf {} Tm {} TJ ET".format(matrix, words)))
        expect(got["pages"] == flat["pages"] == ["The sample held 9,999 items."], "text rotated {} degrees reads as level text does".format(label), str(got))
    got = read("rot-cm.pdf", one_page_pdf("q 0 1 -1 0 300 200 cm BT /F1 12 Tf {} TJ ET Q".format(words)))
    expect(got["pages"] == ["The sample held 9,999 items."], "text rotated by the page matrix reads too", str(got))
    got = read("rot-wide.pdf", one_page_pdf("BT /F1 12 Tf 0 1 -1 0 300 200 Tm [(The)-400(sample)-400(held)] TJ ET"))
    expect(got["pages"] == ["The sample held"], "wide rotated gaps do not break a line per word", str(got))
    got = read("rot-kern.pdf", one_page_pdf("BT /F1 12 Tf 0 1 -1 0 300 200 Tm [(W)80(A)80(V)80(E)] TJ ET"))
    expect(got["pages"] == ["WAVE"], "a kerned rotated word stays one word", str(got))
    got = read("rot-lines.pdf", one_page_pdf("BT /F1 12 Tf 0 1 -1 0 300 200 Tm (First) Tj 1 0 0 1 0 0 Tm ET BT /F1 12 Tf 0 1 -1 0 320 200 Tm (Second) Tj ET"))
    expect(got["pages"] == ["First\nSecond"], "rotated lines keep their break", str(got))
    q_font = "BT /F1 12 Tf 72 700 Td (Start) Tj ET q BT /F2 12 Tf 72 680 Td <0041> Tj ET Q BT 72 660 Td (1,284) Tj ET"
    no_map = {6: b"<< /Type /Font /Subtype /Type0 /BaseFont /Example /Encoding /Identity-H /DescendantFonts [7 0 R] >>",
              7: b"<< /Type /Font /Subtype /CIDFontType2 /BaseFont /Example >>"}
    got = read("q-font.pdf", one_page_pdf(q_font, fonts="/F2 6 0 R", objects=no_map))
    expect("1,284" in page_of(got) and page_of(got).startswith("Start"), "text after Q uses the font from before q", str(got))
    got = read("q-leading.pdf", one_page_pdf("BT /F1 12 Tf 14 TL 72 700 Td (a) Tj ET q 0 TL Q BT /F1 12 Tf 14 TL 72 660 Td (b) Tj T* (c) Tj ET"))
    expect(got["pages"] == ["a\nb\nc"], "the leading comes back with Q too", str(got))
    got = read("extra-q.pdf", one_page_pdf("Q Q BT /F1 12 Tf 72 700 Td (Held 1,284.) Tj ET"))
    expect(got["pages"] == ["Held 1,284."], "an extra Q costs nothing", str(got))
    # A slot named wrong would raise inside the page loop, which costs the operator in silence, so each is checked here.
    table = getattr(docs, "STATE_NUMBERS", {})
    expect(sorted(table) == ["TL", "Tc", "Ts", "Tw", "w"] and all(slot in docs.State.__slots__ for slot in table.values()),
           "the operators that each set one number in the graphics state are one table, each naming a slot of the state", str(table))

    class Plain:  # all a font dictionary with no references asks of its PDF
        resolve = staticmethod(lambda value: value)

    kinds = [(f.type3, f.two_byte) for f in (docs.Font(Plain, {"Subtype": s}) for s in ("Type1", "Type3", "Type0"))]
    init = (HERE / "documents.py").read_text(encoding="utf-8").split("class Font:")[1].split("def _simple_widths")[0]
    expect(kinds == [(False, False), (True, False), (False, True)] and init.count("self.type3 =") == 1
           and init.count("self.two_byte = False") == 1, "a font's kind is set once, from its subtype", str(kinds))


def test_reader_text_file(root):
    """A plain text export can have a cover, and its bytes stay as they came."""
    docs, read = reader_in(root, "reader-txt")
    got = read("export.txt", b"Complaints 1,284\n")
    expect(got["pages"] == ["Complaints 1,284\n"] and got["problem"] is None, "a text file reads as one page", str(got))
    got = read("wide.txt", "Complaints 1,284\n".encode("utf-16"))
    expect(got["pages"] == ["Complaints 1,284\n"], "a UTF-16 text file reads by its mark", str(got))
    folder = ia(root, "reader-txt-case")
    export = folder / "evidence" / "EV-53-export.txt"
    export.write_bytes(b"Complaints 1,284\nTotal 1,284\n")
    before = export.read_bytes()
    code, out, _ = check(folder)
    expect("evidence/EV-53-export.txt, which has no cover file EV-53-export.txt.md." in out, "a text file with no cover says what it needs", out)
    code, out, _ = run(["covers", str(folder)])
    cover = folder / "evidence" / "EV-53-export.txt.md"
    expect("evidence/EV-53-export.txt: 1 page, 1 with text. Draft cover written for evidence id EV-53." in out and cover.is_file(), "covers drafts a cover for a text file", out)
    edit(cover, "Signed by:", "Signed by: Head of Complaints, 2026-07-01")
    edit(cover, "Status: DRAFT", "Status: FINAL")
    memo = folder / "closure" / "memo.md"
    original = memo.read_text(encoding="utf-8")
    finding.write_text(memo, original + "\nThe export held 1,284 items [EV-53 p1].\n")
    code, out, _ = check(folder)
    expect("14 tie, 0 on the list" in out and "13 ties rest on text a person typed: 13 in plain-text evidence, none on a page typed into a cover." in out
           and "Not counted" not in out, "a figure ties against the text file's own bytes, and a .txt with a cover of its "
           "own is the document's own text", block_from(out, "Memo check:"))
    expect(export.read_bytes() == before, "the export's bytes stay untouched")
    finding.write_text(memo, original + "\nThe export held 1,999 items [EV-53 p1].\n")
    code, out, _ = check(folder)
    expect("1,999 is cited to EV-53 p1, and the page does not hold it; the nearest figure on the page is 1,284" in out,
           "a wrong figure against a text file goes on the list", block_from(out, "Memo check:"))
    files = finding.fingerprint_files(folder)[0]
    expect("evidence/EV-53-export.txt" in files, "the fingerprint covers the text file", ", ".join(files))
    legacy = ia(root, "reader-txt-legacy")
    finding.write_text(legacy / "evidence" / "EV-54-note.txt", "What: EV-54 Note\nFor: EV-54\nSigned by: Head of Complaints, 2026-07-01\nStatus: FINAL\n\nHeld 77.\n")
    code, out, _ = check(legacy)
    expect("Not counted" not in out, "a text file that carries its own header still counts as it did", out)
    code, out, _ = run(["covers", str(legacy)])
    expect("EV-54" not in out, "covers leaves a text file with its own header alone", out)


def test_reader_page_tree(root):
    """A page listed twice would shift every later page number by one, so it is refused."""
    docs, read = reader_in(root, "reader-tree")

    def tree(kids, extra=None):
        objects = {1: b"<< /Type /Catalog /Pages 2 0 R >>",
                   2: "<< /Type /Pages /Count 3 /Kids [{}] >>".format(kids).encode(),
                   3: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
                   4: b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 5 0 R /Resources << /Font << /F1 3 0 R >> >> >>",
                   5: stream_obj(b"BT /F1 12 Tf 72 700 Td (Page one 1,284.) Tj ET"),
                   6: b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 7 0 R /Resources << /Font << /F1 3 0 R >> >> >>",
                   7: stream_obj(b"BT /F1 12 Tf 72 700 Td (Page three 9,999.) Tj ET")}
        objects.update(extra or {})
        return pdf_bytes(objects)

    twice = "the PDF lists the same page twice, so its page numbers cannot be trusted"
    got = read("twice.pdf", tree("4 0 R 4 0 R 6 0 R"))
    expect(got["problem"] == twice, "a page listed twice is refused in words", str(got)[:200])
    got = read("twice-node.pdf", tree("8 0 R 8 0 R", {8: b"<< /Type /Pages /Count 1 /Kids [4 0 R] >>"}))
    expect(got["problem"] == twice, "a page-tree node listed twice is refused", str(got)[:200])
    got = read("loop.pdf", tree("4 0 R 2 0 R 6 0 R"))
    expect(got["pages"] == ["Page one 1,284.", "Page three 9,999."], "a loop in the tree still ends and reads", str(got)[:200])
    got = read("plain-tree.pdf", tree("4 0 R 6 0 R"))
    expect(got["pages"] == ["Page one 1,284.", "Page three 9,999."], "a plain tree reads", str(got)[:200])
    levels = {}
    for k in range(8, 46):
        levels[k] = "<< /Type /Pages /Kids [{0} 0 R {0} 0 R] >>".format(k + 1).encode()
    levels[46] = b"<< /Type /Pages /Kids [4 0 R] >>"
    got = read("doubling.pdf", tree("8 0 R", levels))
    expect(got["problem"] == twice, "a small tree that doubles at each level is refused at once", str(got)[:200])


def lzw_bytes(data, early):
    """LZW as a PDF writer makes it, with the code width changing `early` codes ahead."""
    table = {bytes([i]): i for i in range(256)}
    codes = [256]
    widths = [9]
    bits = 9
    following = 258
    word = b""
    for value in data:
        grown = word + bytes([value])
        if grown in table:
            word = grown
            continue
        codes.append(table[word])
        widths.append(bits)
        table[grown] = following
        following += 1
        if following - 1 + early >= (1 << bits) and bits < 12:
            bits += 1
        word = bytes([value])
    codes += [table[word], 257]
    widths += [bits, bits]
    buffer = count = 0
    out = bytearray()
    for code, width in zip(codes, widths):
        buffer = (buffer << width) | code
        count += width
        while count >= 8:
            count -= 8
            out.append((buffer >> count) & 255)
    if count:
        out.append((buffer << (8 - count)) & 255)
    return bytes(out)


def test_reader_decode_gaps(root):
    """Small gaps in decoding, and reasons in plain words."""
    docs, read = reader_in(root, "reader-gaps")
    got = read("null.pdf", one_page_pdf("", objects={5: stream_obj(SHOWN.encode(), b" /Filter null")}))
    expect("9,999" in page_of(got), "a null filter is no filter", str(got)[:200])
    long_text = "\n".join("BT /F1 8 Tf 72 {} Td (Row {} held {} items of the sample.) Tj ET".format(780 - k * 9, k, 1000 + k * 7) for k in range(80))
    for early in (1, 0):
        head = b" /Filter /LZWDecode" + (b" /DecodeParms << /EarlyChange 0 >>" if early == 0 else b"")
        got = read("lzw.pdf", one_page_pdf("", objects={5: stream_obj(lzw_bytes(long_text.encode(), early), head)}))
        expect("Row 79 held 1553 items" in page_of(got), "LZW with EarlyChange {} reads to the end".format(early), page_of(got)[-200:])
    got = read("self-length.pdf", one_page_pdf("", objects={5: b"<< /Length 5 0 R >>\nstream\n" + SHOWN.encode() + b"\nendstream"}))
    expect(got["problem"] is None and "9,999" in page_of(got), "a stream whose length points at itself still reads", str(got)[:200])
    folder = root / "reader-gaps"
    (folder / "broken.xlsx").write_bytes(book_bytes(root, [("S", None, '<sheetData><row><c t="s"><v>notanumber</v></c></row></sheetData>')]))
    got = docs.read(folder / "broken.xlsx")
    expect(got["problem"] == docs.DAMAGED, "a failure reason holds plain words and no Python name", str(got)[:200])
    nest = {}
    for level in range(6, 15):
        inner = "/Fm{} Do".format(level + 1) if level < 14 else "BT /F1 12 Tf 72 680 Td (The sample held 9,999 items.) Tj ET"
        nest[level] = stream_obj(inner.encode(), "/Type /XObject /Subtype /Form /BBox [0 0 612 792] /Resources << /Font << /F1 3 0 R >> /XObject << /Fm{} {} 0 R >> >>".format(level + 1, level + 1).encode())
    got = read("deep.pdf", one_page_pdf("BT /F1 12 Tf 72 700 Td (Heading) Tj ET /Fm6 Do", "/XObject << /Fm6 6 0 R >>", objects=nest))
    expect(got["pages"] == ["Heading"] and got["partly"] == [1], "a form nested too deep says the page was read in part", str(got)[:200])


def test_covers(root):
    folder = ia(root, "covers")
    (folder / "evidence" / "EV-30-sample-listing.pdf").write_bytes(simple_pdf(["Listing page one.", "The sample held 1,284 items.", ""]))
    (folder / "evidence" / "stray-name.pdf").write_bytes(simple_pdf(["Nothing."]))
    code, out, _ = run(["covers", str(folder)])
    cover = folder / "evidence" / "EV-30-sample-listing.pdf.md"
    expect(code == 1 and "evidence/EV-30-sample-listing.pdf: 3 pages, 2 with text; no text on page 3. Draft cover written for evidence id EV-30." in out
           and "evidence/stray-name.pdf: 1 page, 1 with text. Rename it to start with an evidence id plan.md lists" in out,
           "covers reads each document and writes a draft cover", out)
    expect(cover.is_file() and "Status: DRAFT" in cover.read_text(encoding="utf-8") and "For: EV-30" in cover.read_text(encoding="utf-8"),
           "the draft cover holds the evidence id and stays a draft", cover.read_text(encoding="utf-8") if cover.is_file() else "")
    (folder / "evidence" / "stray-name.pdf").unlink()
    code, out, _ = run(["covers", str(folder)])
    expect("It has a cover already." in out and cover.read_text(encoding="utf-8").startswith("What: EV-30 Sample listing"),
           "covers never overwrites a cover", out)

    memo = folder / "closure" / "memo.md"
    original = memo.read_text(encoding="utf-8")
    finding.write_text(memo, original + "\nThe listing held 1,284 items [EV-30 p2].\n")
    code, out, _ = check(folder)
    expect("EV-30, which is a draft, holds 1 claim that matches its pages and waits on a person's signature." in out
           and "Memo check: 14 claims, 13 tie, 1 on the list." in out,
           "a draft cover's matching figure is no tie and sits on the cover's one row", block_from(out, "Memo check:"))
    edit(cover, "Signed by:", "Signed by: Head of Complaints, 2026-07-01")
    edit(cover, "Status: DRAFT", "Status: FINAL")
    code, out, _ = check(folder)
    expect("Memo check: 14 claims, 14 tie, 0 on the list." in out and "13 ties rest on text a person typed" in out,
           "a four-line cover is enough: the figure ties on the PDF's own page", block_from(out, "Memo check:"))
    finding.write_text(memo, original + "\nThe listing held 1,248 items [EV-30 p2].\n")
    code, out, _ = check(folder)
    expect("1,248 is cited to EV-30 p2, and the page does not hold it; the nearest figure on the page is 1,284" in out,
           "a wrong figure against the PDF goes on the list", block_from(out, "Memo check:"))
    finding.write_text(memo, original + "\nThe third page held 77 items [EV-30 p3].\n")
    code, out, _ = check(folder)
    expect("the check cannot read that page: the document has no text on that page. Type it into the cover under ## Page 3." in out,
           "a page with no text says how to fix it", block_from(out, "Memo check:"))
    finding.write_text(cover, cover.read_text(encoding="utf-8") + "\n## Page 3\nThe third page held 77 items.\n")
    code, out, _ = check(folder)
    expect("Memo check: 14 claims, 14 tie, 0 on the list." in out
           and "14 ties rest on text a person typed: 13 in plain-text evidence, 1 on a page typed into a cover, 1 with no Checked by line." in out,
           "a typed page counts with the cover's signature as it was, and the page says it was typed", block_from(out, "Memo check:"))
    edit(cover, "Status: FINAL", "Status: FINAL\nChecked by: Associate 2, 2026-11-04")
    code, out, _ = check(folder)
    expect("14 ties rest on text a person typed: 13 in plain-text evidence, 1 on a page typed into a cover, with a Checked by line." in out,
           "a second person's Checked by line answers the page", block_from(out, "Memo check:"))
    changing = ia(root, "covers-change")
    pdf = changing / "evidence" / "EV-30-sample-listing.pdf"
    pdf.write_bytes(simple_pdf(["The sample held 1,284 items."]))
    run(["covers", str(changing)])
    cover2 = changing / "evidence" / "EV-30-sample-listing.pdf.md"
    edit(cover2, "Signed by:", "Signed by: Head of Complaints, 2026-05-01")
    edit(cover2, "Status: DRAFT", "Status: FINAL")
    edit(changing / "plan.md", "EV-21 |", "EV-21, EV-30 |")
    code, out, _ = check(changing)
    expect("Present and signed" in line_of(out, "M1 "), "a covered document can back a milestone", line_of(out, "M1 "))
    pdf.write_bytes(simple_pdf(["The sample held 9,999 items."]))
    code, out, _ = check(changing)
    expect("EV-30 changed since it was signed" in line_of(out, "M1 "), "a document changed after its signature is noticed", line_of(out, "M1 "))
    files = finding.fingerprint_files(folder)[0]
    expect("evidence/EV-30-sample-listing.pdf" in files and "finding/documents.py" in files,
           "the fingerprint covers the document and its reader", ", ".join(files))

    typed = fresh(root, "covers-unread")
    (typed / "evidence" / "EV-31-scan.png").write_bytes(b"\x89PNG not read")
    finding.write_text(typed / "evidence" / "EV-31-scan.png.md", SYN + "\nWhat: EV-31 Scan\nFor: EV-31\n"
                       "Signed by: Head of Complaints, 2026-03-01\nStatus: FINAL\n\nThe scan shows 555 items.\n")
    edit(typed / "closure" / "memo.md", "M4, the mobile app chat channel.",
         "M4, the mobile app chat channel. The scan shows 555 items [EV-31 p1].")
    code, out, _ = check(typed)
    expect("8 ties rest on text a person typed" in out and "555" not in block_from(out, "Memo check:").split("typed")[0],
           "a file type with no reader falls back to the typed cover", block_from(out, "Memo check:"))


def test_eval_and_size(root):
    folder = ia(root, "eval")
    before = {p: p.read_bytes() for p in folder.rglob("*") if p.is_file()}
    code, out, _ = run(["eval", str(folder)])
    expect(code == 0 and "Eval of the memo check on IA-CMP-02. Nothing in the folder changed." in out
           and "A figure with one digit changed: 6 planted, 6 caught." in out
           and "A figure swapped for another on the same page: 6 planted, 0 caught." in out
           and "What the check did not catch, for a person to look for:" in out, "eval plants errors and counts the catches", out)
    expect({p: p.read_bytes() for p in folder.rglob("*") if p.is_file()} == before, "eval changes nothing in the folder")
    code, out, _ = run(["eval", "--library"])
    expect(code == 0 and out.startswith("Library cases: ") and "as expected" in out, "the library's cases all behave as written", out)
    count = len(list((HERE.parent / "library" / "cases").glob("*.json")))
    expect("Library cases: {}, {} as expected".format(count, count) in out, "every library case ran", out)
    code, out, _ = run(["size", str(fresh(root, "size-mra"))])
    expect(code == 0 and "MRA-CMP-07: 4 milestones, 6 evidence files (0 with a separate cover), 13 claims on the memo check, 4 rows before rulings, 6 months." in out
           and "By hand, assumed: 29.5 hours." in out
           and "With the kit, assumed: 13.7 hours. Reading each claim against its page 2.2, cover lines 1.0, rulings 1.0, "
               "status reports 1.5, rework 8.0." in out
           and "These hours are assumptions" in out, "size prints the counts and the assumed hours", out)
    code, out, _ = run(["size", str(HERE / "cases")])
    expect(code == 0 and "2 findings: 51.5 hours by hand, 25.2 with the kit, assumed." in out, "size sums a folder of findings", out)
    code, _, err = run(["size", str(root / "no-such-folder")])
    expect(code == 2, "size on a missing folder is a usage error")


def test_row_wording(root):
    class Fail(object):
        def __init__(self, code, reason, hint=None):
            self.code, self.reason, self.hint = code, reason, hint
    expect(finding.row_text(Fail("figure_not_found", "x", "nearest values on the page: 3"), "EV-07", 2, True)
           == "and the page does not hold it; the nearest figure on the page is 3.", "one nearest figure reads singular")
    expect(finding.row_text(Fail("date_not_found", "x", "dates on the page: 2026-03-14; 2026-04-01"), "EV-07", 2, True)
           == "and the page does not hold it; the dates on the page are 2026-03-14 and 2026-04-01.",
           "two dates read plural")
    expect([finding.row_text(Fail(code, "x", hint), "EV-07", 2, True) for code, hint in (
        ("figure_not_found", "nearest values on the page: 3; 30"), ("figure_not_found", "no figure on the page"),
        ("date_not_found", "dates on the page: 2026-03-14"), ("date_not_found", "no date on the page"))]
           == ["and the page does not hold it; the nearest figures on the page are 3 and 30.", "and the page holds no figure.",
               "and the page does not hold it; the date on the page is 2026-03-14.", "and the page holds no date."],
           "a figure or a date not found reads as before, one or several, or none on the page")
    expect(finding.row_text(Fail("check_error", "the check could not run: TypeError: bad"), "EV-07", 2, True)
           == "and the check could not run: TypeError: bad.", "a crash reason is not prefixed twice")


def answers(*lines):
    return StandInTerminal("".join(line + "\n" for line in lines))


def signed_on(date=NOW):
    """The signature date as sign writes it: a date typed with --today says so, with the machine's own date."""
    machine = datetime.date.today().isoformat()
    return date if date == machine else "{}, a date typed with --today on a machine dated {}".format(date, machine)


def test_sign(root):
    iaf = ia(root, "sign-devnull")
    proc = subprocess.run([sys.executable, "-I", str(HERE / "finding.py"), "sign", str(iaf), "--today", NOW],
                          input=b"", stdout=subprocess.PIPE, stderr=subprocess.PIPE)  # a pipe is no terminal anywhere; NUL on Windows claims to be one
    expect(proc.returncode == 1 and proc.stdout.decode("utf-8").replace("\r\n", "\n") == refusal(
        "Refused: sign needs a terminal."), "sign with no terminal refuses",
        proc.stdout.decode("utf-8", "replace") + proc.stderr.decode("utf-8", "replace"))
    code, _, err = run(["sign", "--today", NOW], stdin=answers())
    expect(code == 2 and finding.USAGE in err, "sign with no folder exits 2 with usage")

    mra = fresh(root, "sign-rows")
    code, out, _ = run(["sign", str(mra), "--today", NOW], stdin=answers())
    expect(code == 1 and out == refusal("Refused: 3 rows are on the list; rule on them first."),
           "sign refuses while rows are on the list", out)
    for claimed in ("1,248", "EV-12 draft"):
        add_ruling(mra, claimed)
    code, out, _ = run(["sign", str(mra), "--today", NOW], stdin=answers())
    expect(out == refusal("Refused: 1 row is on the list; rule on it first."), "one row left is named, in the singular", out)

    below = ia(root, "sign-below")
    plan = below / "plan.md"
    finding.write_text(plan, plan.read_text(encoding="utf-8")
                       + "| M3 Publish the letter standard | Head of Complaints | 2026-12-31 | Done | EV-23 | Read |\n")
    code, out, _ = run(["sign", str(below), "--today", NOW], stdin=answers())
    expect(code == 1 and out == refusal("Refused: M3 is below signed."), "sign refuses a milestone below signed", out)

    noboard = ia(root, "sign-board")
    edit(noboard / "closure" / "record.md", "Board approval reference: BM-2026-07", "Board approval reference:")
    code, out, _ = run(["sign", str(noboard), "--today", NOW], stdin=answers())
    expect(code == 1 and out == refusal("Refused: closure/record.md holds no board approval (no reference)."),
           "sign refuses with no board approval", out)

    wrong = ia(root, "sign-wrong")
    code, out, _ = run(["sign", str(wrong), "--today", NOW], stdin=answers("Head of Internal Audit"))
    expect(code == 1 and out.endswith(refusal("Refused: that is not the finding owner's role."))
           and "Type the finding owner's role to sign: " in out, "a wrong role refuses", out[-300:])
    code, out, _ = run(["sign", str(wrong), "--today", NOW], stdin=answers("head of complaints"))
    expect(code == 1 and "that is not the finding owner's role" in out, "the role is matched with its case")
    code, out, _ = run(["sign", str(wrong), "--today", NOW], stdin=answers("Head of  Complaints", "zzzzzzzz"))
    expect(code == 1 and out.endswith(refusal("Refused: the characters typed do not match the fingerprint.")),
           "wrong characters refuse", out[-300:])
    expect(state_of(wrong)["signature"] is None and "Signed on:\n" in
           (wrong / "closure" / "record.md").read_text(encoding="utf-8"), "a refused sign writes no signature")

    def touch_memo(n):
        if n == 2:
            memo = wrong / "closure" / "memo.md"
            finding.write_text(memo, memo.read_text(encoding="utf-8") + "\nA late line.\n")
    fp = finding.fingerprint(wrong)
    code, out, _ = run(["sign", str(wrong), "--today", NOW],
                       stdin=StandInTerminal("Head of Complaints\n" + fp[:8] + "\n", touch_memo))
    expect(code == 1 and out.endswith(refusal("Refused: a file changed while sign was running; run it again.")),
           "a file changed while sign ran refuses", out[-300:])

    signed = ia(root, "sign-pty")
    fp = None
    if os.name == "posix":
        code, out = sign_at_pty(signed)
        fp = finding.fingerprint(signed)
        expect(code == 0, "sign at a pseudo-terminal exits 0", out[-500:])
        m = re.search(r"Fingerprint ([0-9a-f]{64})", out)
        expect(m is not None and m.group(1) == fp, "the printed fingerprint is fingerprint(folder)", out[-500:])
        expect("Signed by the Head of Complaints on {}, fingerprint {}. Written to closure/record.md."
               .format(signed_on(), fp[:8]) in out, "sign prints the signed line", out[-300:])
    else:
        print("selftest: note: no pseudo-terminal on this system, so sign was driven by a stand-in terminal")
        fp = finding.fingerprint(signed)
        code, out, _ = run(["sign", str(signed), "--today", NOW], stdin=answers("Head of Complaints", fp[:8]))
        expect(code == 0, "sign with a stand-in terminal exits 0", out[-500:])
    record = (signed / "closure" / "record.md").read_text(encoding="utf-8")
    expect(record.endswith("Signed by (role): Head of Complaints\nSigned on: {}\nFingerprint: {}\nKit release: {}\n".format(signed_on(), fp, finding.kit_release()[0])),
           "sign writes its four lines into closure/record.md", record)
    sig = state_of(signed)["signature"]
    expect(isinstance(sig, dict) and sig.get("role") == "Head of Complaints" and sig.get("date") == NOW
           and sig.get("fingerprint") == fp and sig.get("files") == finding.fingerprint_files(signed)[0],
           "sign writes the signature into the state file", json.dumps(sig)[:300])
    expect(list(state_of(signed))[-1] == "signature", "the signature is the state file's last key")
    files = finding.fingerprint_files(signed)[0]
    expect(sorted(files) == sorted(["closure/memo.md", "closure/record.md", "closure/rulings.md", "finding.md",
                                    "finding.py", "finding/documents.py", "plan.md", "tieout/claims.py", "tieout/docx_reader.py", "tieout/record.py",
                                    "tieout/verify.py", "tieout/words.py",
                                    "evidence/E-PLAN-1-board-minutes.md",
                                    "evidence/EV-21-acknowledgement-procedure.md",
                                    "evidence/EV-22-timeliness-report.md"]),
           "the fingerprint covers the memo, plan, finding, evidence, rulings, record and the tool",
           ", ".join(sorted(files)))
    code, out, _ = check(signed)
    expect(code == 0 and out.endswith("Signed by the Head of Complaints on {}, fingerprint {}.\n"
                                      "Deny list: 3 names.\n\n"
                                      "Nothing needs a person.\n".format(signed_on(), fp[:8])),
           "a check after signing prints the signed line", out[-300:])
    code, out, _ = run(["sign", str(signed), "--today", NOW], stdin=answers())
    expect(code == 1 and out == refusal("Refused: this finding is signed already and nothing has changed since."),
           "signing twice refuses", out)

    memo = signed / "closure" / "memo.md"
    finding.write_text(memo, memo.read_text(encoding="utf-8") + "\nThe Head of Complaints holds the sample.\n")
    code, out, _ = check(signed)
    expect(code == 1 and out.endswith("Signed by the Head of Complaints on {}, fingerprint {}.\n"
                                      "Changed since signing: closure/memo.md.\n"
                                      "Deny list: 3 names.\n\n"
                                      "Needs a person:\n  Head of Complaints: a fresh signature.\n".format(signed_on(), fp[:8])),
           "a memo edit after signing needs a fresh signature", out[-300:])
    edit(signed / "closure" / "record.md", "Signed on: 2026-11-04", "Signed on: 2026-11-05")
    code, out, _ = check(signed)
    expect("Changed since signing: closure/memo.md, closure/record.md." in out,
           "an edited signature line in record.md is a change", line_of(out, "Changed since"))
    edit(signed / "closure" / "record.md", "Signed on: 2026-11-05", "Signed on: 2026-11-04")
    fp2 = finding.fingerprint(signed)
    code, out, _ = run(["sign", str(signed), "--today", "2026-11-06"], stdin=answers("Head of Complaints", fp2[:8]))
    expect(code == 0 and fp2 != fp and "Signed by the Head of Complaints on {}, fingerprint {}."
           .format(signed_on("2026-11-06"), fp2[:8]) in out, "a changed finding may be signed again", out[-300:])
    code, out, _ = check(signed)
    expect(code == 0 and "Changed since signing" not in out, "the fresh signature clears the change")

    crlf = ia(root, "sign-crlf")
    rec = crlf / "closure" / "record.md"
    rec.write_bytes(rec.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
    fp3 = finding.fingerprint(crlf)
    finding.write_signature(crlf, "Head of Complaints", "2026-11-04", fp3)
    data = rec.read_bytes()
    expect(b"Fingerprint: " + fp3.encode() + b"\r\n" in data and data.count(b"\n") == data.count(b"\r\n"),
           "sign keeps a record.md with Windows line endings in those endings")


def sign_at_pty(folder):
    """Sign at a pseudo-terminal, typing the owner's role and the fingerprint's first characters."""
    import pty
    master, slave = pty.openpty()
    proc = subprocess.Popen([sys.executable, "-I", str(HERE / "finding.py"), "sign", str(folder), "--today", NOW],
                            stdin=slave, stdout=slave, stderr=slave, close_fds=True,
                            env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
    os.close(slave)
    buf = b""
    replies = [b"Type the finding owner's role to sign: ", b"Type its first eight characters to confirm: "]
    deadline = time.time() + 30
    while time.time() < deadline:
        ready, _, _ = select.select([master], [], [], 1)
        if ready:
            try:
                data = os.read(master, 4096)
            except OSError:
                data = b""
            if not data:
                break
            buf += data
            if replies and buf.endswith(replies[0]):
                if len(replies) == 2:
                    os.write(master, b"Head of Complaints\n")
                else:
                    m = re.search(rb"Fingerprint ([0-9a-f]{64})", buf)
                    os.write(master, (m.group(1)[:8] if m else b"none") + b"\n")
                replies.pop(0)
        elif proc.poll() is not None:
            break
    if proc.poll() is None:
        proc.kill()
    proc.wait()
    os.close(master)
    return proc.returncode, buf.decode("utf-8", "replace").replace("\r\n", "\n")


def recompute_matches(folder):
    """True when a fresh first check gives the same parts, evidence and deny list."""
    with tempfile.TemporaryDirectory() as tmp:
        copy = Path(tmp) / folder.name
        shutil.copytree(str(folder), str(copy))
        stored = state_of(copy)
        (copy / finding.STATE_NAME).unlink()
        check(copy)
        again = state_of(copy)
    keys = ("version", "parts", "evidence", "deny", "signature")
    return all(stored.get(k) == again.get(k) for k in keys)


def with_memo(root, name, body):
    """IA-CMP-02, internal audit's entry in, with this memo in place of its own. The body starts at line 4."""
    folder = ia(root, name)
    finding.write_text(folder / "closure" / "memo.md", SYN + "\n# Closure memo\n\n" + body)
    return folder


def memo_block(out):
    return out[out.index("Memo check:"):out.index("Deny list:")]


def test_memo_reads_every_line(root):
    """Text under a heading, a figure in a heading and text in a control block all reach the list."""
    folder = with_memo(root, "read-under-heading", '## M1, acknowledgement letters\nThe team reclassified 9,999 complaints on '
                       '2031-01-01, and the policy says "nothing like this at all" [EV-21 p1].\n')
    code, out, _ = check(folder)
    expect(code == 1 and "Memo check: 3 claims, 0 tie, 3 on the list." in out and "  Line 5: 9,999 is cited to EV-21 p1" in out
           and "Ready to sign" not in out, "text straight under a heading is read, on its true line", memo_block(out))
    folder = with_memo(root, "read-heading", "## 9,999 complaints were acknowledged in 2031\n\nA plain line.\n")
    out = check(folder)[1]
    expect("  Line 4: 9,999 has no cite." in out, "a figure in a heading is a claim", memo_block(out))
    folder = with_memo(root, "read-heading-number", "## 120 complaints were sampled\n\nA plain line.\n")
    out = check(folder)[1]
    expect("  Line 4: 120 has no cite." in out, "a figure opening a heading is a claim", memo_block(out))
    folder = with_memo(root, "read-section-numbers", "## 2. Letters\n\n## 2.1. Letters\n\n## 3) Letters\n\n## (4) Letters\n\n"
                       "## 5: Letters\n\n## 6 - Letters\n\nThe sample held 120 complaints [EV-21 p2].\n")
    out = check(folder)[1]
    expect("Memo check: 1 claim, 1 tie, 0 on the list." in out, "a section number in a heading is no figure", memo_block(out))
    expect("Memo check: 13 claims, 13 tie, 0 on the list." in check(ia(root, "read-title"))[1], "a memo's title with its id is no claim")

    text_after = ia(root, "read-in-control")
    edit(text_after / "closure" / "memo.md", "Sample period: 2026-05-04 to 2026-05-22 [EV-21 p2]\n",
         'Sample period: 2026-05-04 to 2026-05-22 [EV-21 p2]\nThe sample of 9,999 complaints had 8,888 failures, or "not a word of this" [EV-21 p2].\n')
    out = check(text_after)[1]
    expect("Memo check: 16 claims, 13 tie, 3 on the list." in out and "  Line 13: 9,999 is cited to EV-21 p2" in out
           and "  Line 13: 8,888 is cited to EV-21 p2" in out and '  Line 13: "not a word of this" is cited to EV-21 p2' in out,
           "a sentence straight after a control block is read as memo text", memo_block(out))
    on_the_line = ia(root, "read-control-line")
    edit(on_the_line / "closure" / "memo.md", "Tested control: M1, the acknowledgement letter procedure",
         "Tested control: M1, the procedure across 9,999 letters")
    out = check(on_the_line)[1]
    expect("  Line 10: 9,999 has no cite." in out, "a figure on a control's own line is read too", memo_block(out))


def test_control_dates_tie(root):
    """Fix effective and Sample period are dates like any other, so a wrong one cannot pass by losing its cite."""
    folder = ia(root, "control-uncited")
    memo = folder / "closure" / "memo.md"
    edit(memo, "Fix effective: 2026-05-04 [EV-21 p1]", "Fix effective: 2025-01-01")
    edit(memo, "Sample period: 2026-05-04 to 2026-05-22 [EV-21 p2]", "Sample period: 2025-02-01 to 2025-03-01")
    code, out, _ = check(folder)
    expect(code == 1 and "  Line 11: 2025-01-01 has no cite." in out and "  Line 12: 2025-02-01 has no cite." in out
           and "  Line 12: 2025-03-01 has no cite." in out and "Ready to sign" not in out,
           "an uncited Fix effective or Sample period date is a row", memo_block(out))
    folder = ia(root, "control-one-cite")
    edit(folder / "closure" / "memo.md", "Fix effective: 2026-05-04 [EV-21 p1]", "Fix effective: 2026-05-04")
    out = check(folder)[1]
    expect("  Line 11: 2026-05-04 has no cite." in out, "the Sample period line's cite does not answer for the Fix effective line", memo_block(out))
    folder = ia(root, "control-wrong")
    edit(folder / "closure" / "memo.md", "Fix effective: 2026-05-04 [EV-21 p1]", "Fix effective: 2025-01-01 [EV-21 p1]")
    out = check(folder)[1]
    expect("  Line 11: 2025-01-01 is cited to EV-21 p1, and the page does not hold it; the date on the page is 2026-05-04." in out,
           "a wrong cited Fix effective date is a row", memo_block(out))
    page = pages("assistant/draft-memo.md")
    if page is None:
        return
    example = page.split("```text\n", 1)[1].split("```", 1)[0]
    expect("Fix effective: 2026-05-04 [EV-21 p1]" in example and "Sample period: 2026-05-04 to 2026-05-22 [EV-21 p2]" in example,
           "the memo procedure's example cites both control dates")
    pasted = with_memo(root, "control-example", example)
    expect("Memo check: 5 claims, 5 tie, 0 on the list." in check(pasted)[1],
           "the memo procedure's example ties in IA-CMP-02, the case it is drawn from", memo_block(check(pasted)[1]))


def test_figures_in_words(root):
    """The page says how many figures written in words it found and did not check."""
    folder = fresh(root, "words-mra")
    edit(folder / "closure" / "memo.md", "with three subcategories", "with nine subcategories")
    out = check(folder)[1]
    expect("  Not checked: 1 figure written in words, line 6 (nine).\n" in out and "Memo check: 13 claims, 7 tie, 3 on the list, 1 cleared." in out,
           "a figure in words is named and stays off the list", memo_block(out))
    expect(check(folder)[1] == out, "the words line is the same every run")
    code, out, _ = check(ia(root, "words-ia"))
    expect("  Not checked: 2 figures written in words, line 6 (five) and line 8 (five).\n" in out and only_the_signature(code, out),
           "a figure in words does not stop the signature", memo_block(out))
    folder = with_memo(root, "words-overlap", 'The sample ended on the fourteenth of March 2026 [EV-21 p2]. It says "within five business days of logging" [EV-21 p2].\n')
    expect("Not checked" not in check(folder)[1], "a phrase holding a digit claim, or inside a quotation, is not counted", memo_block(check(folder)[1]))
    folder = with_memo(root, "words-many", "".join("Teams held {} letters.\n\n".format(w) for w in (
        "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen")))
    out = check(folder)[1]
    expect("  Not checked: 14 figures written in words, line 4 (two), " in out and "line 26 (thirteen) and 2 more.\n"[:8] in out
           and " and 2 more.\n" in out, "a long list of them is cut short", memo_block(out))


def test_quotation_and_date_readings(root):
    """A bracket or a sentence end inside a quotation does not hide it, and a date that reads two ways must tie both ways."""
    def case(name, memo, body='Signed on 2026-04-03. It says the Bank "shall promptly acknowledge every complaint in writing" here. Slash 04/03/2026.'):
        folder = with_memo(root, name, memo)
        typed_evidence(folder, "EV-40-note.md", "EV-40", body)
        return check(folder)[1]
    out = case("quote-bracket", 'It says "shall [not] be sent to anyone at all" [EV-40 p1].\n')
    expect("Memo check: 1 claim, 0 tie, 1 on the list." in out and "is cited to EV-40 p1, and the page does not hold" in out,
           "a bracket inside a quotation is no cite, so the quotation is read", memo_block(out))
    out = case("quote-bracket-no-cite", 'It says "an invented [word] quotation here".\n')
    expect("Memo check: 1 claim, 0 tie, 1 on the list." in out and "has no cite" in out, "an uncited quotation with a bracket has no cite", memo_block(out))
    out = case("quote-two-sentences", 'It says "first thing here. Second thing here too" [EV-40 p1].\n')
    expect("Memo check: 1 claim, 0 tie, 1 on the list." in out and '"first thing here. Second thing here too" is cited to EV-40 p1' in out,
           "a quotation of two sentences stays one claim", memo_block(out))
    out = case("quote-then-sentence", 'He wrote "shall promptly acknowledge every complaint." Then 9,999 went out [EV-40 p1].\n')
    expect('"shall promptly acknowledge every complaint." has no cite' in out, "a sentence end at the closing mark still ends the sentence", memo_block(out))

    out = case("date-two-ways", "It was signed on 03/04/2026 [EV-40 p1].\n", "Signed on 2026-04-03.")
    expect("Memo check: 1 claim, 0 tie, 1 on the list." in out and "This date reads two ways, so write it as YYYY-MM-DD." in out,
           "a date that reads two ways with one reading on the page is a row", memo_block(out))
    out = case("date-other-way", "It was signed on 04/03/2026 [EV-40 p1].\n", "Signed on 2026-04-03.")
    expect("Memo check: 1 claim, 0 tie, 1 on the list." in out, "either reading alone is a row", memo_block(out))
    out = case("date-same-form", "It went out on 04/03/2026 [EV-40 p1].\n", "Sent 04/03/2026.")
    expect("Memo check: 1 claim, 1 tie, 0 on the list." in out, "the same two-way date on the page ties", memo_block(out))
    out = case("date-one-way", "It went out on 03/31/2026 [EV-40 p1].\n", "Sent 2026-03-31.")
    expect("Memo check: 1 claim, 1 tie, 0 on the list." in out, "a slash date with one reading ties its ISO form", memo_block(out))


def test_cited_files_outside_the_plan(root):
    """A cited file no milestone lists is held to the same signature as one the plan lists."""
    def extra(name, head):
        folder = ia(root, name)
        finding.write_text(folder / "evidence" / "EV-40-extra.md", "What: EV-40 Extra\nFor: EV-40\n{}\n\nThe extra page holds 777 items.\n".format(head))
        append_to(folder / "closure" / "memo.md", "\nThe extra page holds 777 items [EV-40 p1].\n")
        return folder
    for name, head, words in (
            ("revised", "Signed by: Head of Complaints, 2026-05-01\nStatus: FINAL\nRevised: 2026-06-01", "EV-40 was revised on 2026-06-01, after its signature of 2026-05-01"),
            ("no-role", "Signed by:\nStatus: FINAL", "EV-40 names no role"),
            ("future", "Signed by: Head of Complaints, 2099-05-01\nStatus: FINAL", "EV-40 carries a signature dated 2099-05-01, after the check date")):
        folder = extra("outside-" + name, head)
        code, out, _ = check(folder)
        expect(code == 1 and "  Line 16: 777 is cited to EV-40 p1, which is not signed: {}.".format(words) in out and "Ready to sign" not in out,
               "a cited file outside the plan that is not signed goes on the list: " + name, memo_block(out))
        code, out, _ = run(["sign", str(folder), "--today", NOW], stdin=StandInTerminal())
        expect(code == 1 and "1 row is on the list" in out, "and sign refuses it: " + name, out[-200:])
    folder = extra("outside-changed", "Signed by: Head of Complaints, 2026-05-01\nStatus: FINAL")
    expect(only_the_signature(*check(folder)[:2]), "a signed file outside the plan ties as usual")
    append_to(folder / "evidence" / "EV-40-extra.md", "One more line.\n")
    out = check(folder)[1]
    expect("which is not signed: EV-40 changed since it was signed." in out, "a cited file changed after its signature goes on the list", memo_block(out))
    expect("evidence/EV-40-extra.md" in state_of(folder)["evidence"], "the state records a cited file outside the plan",
           json.dumps(state_of(folder)["evidence"]))
    listed = fresh(root, "outside-listed")
    out = check(listed)[1]
    expect(out.count("EV-08 was revised") == 1, "a file a plan row lists is named once, on its milestone", memo_block(out))


def test_rulings_bind(root):
    """A ruling names its line, its claim and the sentence around it, and clears nothing else."""
    def ruled(name):
        folder = ia(root, name)
        append_to(folder / "closure" / "memo.md", "\nThe reviewer noted 399 late letters [EV-21 p1].\n")
        add_ruling(folder, "399", "cleared | Head of Complaints | 2026-11-04 | The page gives 399 in words.")
        return folder
    folder = ruled("bind-base")
    code, out, _ = check(folder)
    expect("Memo check: 14 claims, 13 tie, 0 on the list, 1 cleared." in out and "  Cleared: line 16, 399, by the Head of Complaints on 2026-11-04:" in out,
           "a ruling in the form the row names clears it", memo_block(out))
    plain = ia(root, "bind-no-mark")
    append_to(plain / "closure" / "memo.md", "\nThe reviewer noted 399 late letters [EV-21 p1].\n")
    append_to(plain / "closure" / "rulings.md", "Line 16 | 399 | cleared | Head of Complaints | 2026-11-04 | No mark.\n")
    out = check(plain)[1]
    expect("0 on the list" not in out and "names no row" in out, "a ruling with no mark clears nothing and says so", memo_block(out))

    folder = ruled("bind-other-sentence")
    edit(folder / "closure" / "memo.md", "The reviewer noted 399 late letters [EV-21 p1].", "All 399 customers were refunded [EV-22 p2].")
    out = check(folder)[1]
    expect("Memo check: 14 claims, 13 tie, 1 on the list." in out and "  Line 16: 399 is cited to EV-22 p2" in out and "names no row" in out,
           "a new sentence with the same figure takes no old ruling, and the old ruling is named", memo_block(out))
    folder = ruled("bind-other-cite")
    edit(folder / "closure" / "memo.md", "late letters [EV-21 p1].", "late letters [EV-21 p2].")
    out = check(folder)[1]
    expect("1 on the list" in out and "names no row" in out, "the same sentence with another cite takes no old ruling", memo_block(out))
    folder = ruled("bind-moved")
    edit(folder / "closure" / "memo.md", "This memo is for internal audit.", "A new opening line.\n\nThis memo is for internal audit.")
    out = check(folder)[1]
    expect("0 on the list, 1 cleared." in out and "  Cleared: line 18 (ruled at memo line 16), 399," in out and "names no row" not in out,
           "a ruling follows its own claim when the memo moves", memo_block(out))

    def two_lines(name, ruling):
        folder = with_memo(root, name, "In a sample of 120 complaints the procedure held [EV-21 p2].\n\n"
                           "A further 120 complaints were reviewed in the second batch [EV-22 p1].\n")
        line, key = row_named(check(folder)[1], "120")
        expect(line == "Line 6", "setup: the second 120 is the row", line)
        append_to(folder / "closure" / "rulings.md", ruling.replace("KEY", key.split(" #")[1]))
        return folder, key
    folder, _ = two_lines("bind-tied-line", "Line 4 | 120 | cleared | Head of Complaints | 2026-11-01 | Another size.\n")
    expect("  Line 6: 120 is cited to EV-22 p1" in check(folder)[1], "a ruling for a line that still ties clears no other copy")
    folder, _ = two_lines("bind-cell", "Line of sight | 120 #KEY | cleared | Head of Complaints | 2026-11-01 | Odd.\n")
    expect("  Line 6: 120 is cited to EV-22 p1" in check(folder)[1], "the line cell must be Line and a number", memo_block(check(folder)[1]))
    folder, _ = two_lines("bind-fix-wins", "Line 2 | 120 #KEY | cleared | Head of Complaints | 2026-11-01 | Old.\n"
                          "Line 6 | 120 #KEY | fix the memo | Head of Complaints | 2026-11-02 | Wrong figure.\n")
    expect("  Line 6: 120 is cited to EV-22 p1" in check(folder)[1], "a later fix the memo ruling on the row beats an old cleared one from another line",
           memo_block(check(folder)[1]))
    folder, _ = two_lines("bind-future", "Line 6 | 120 #KEY | cleared | Head of Complaints | 2031-01-01 | Dated ahead.\n")
    expect("  Line 6: 120 is cited to EV-22 p1" in check(folder)[1], "a ruling dated after the check date does not count", memo_block(check(folder)[1]))
    folder, _ = two_lines("bind-today", "Line 6 | 120 #KEY | cleared | Head of Complaints | {} | Dated today.\n".format(NOW))
    expect("0 on the list, 1 cleared." in check(folder)[1], "a ruling dated on the check date counts", memo_block(check(folder)[1]))
    twice = with_memo(root, "bind-repeated", "A batch of 120 complaints was reviewed [EV-22 p1].\n\nA batch of 120 complaints was reviewed [EV-22 p1].\n")
    out = check(twice)[1]
    key = row_named(out, "120")[1]
    append_to(twice / "closure" / "rulings.md", "Line 4 | {} | cleared | Head of Complaints | 2026-11-01 | One only.\n".format(key))
    out = check(twice)[1]
    expect("1 on the list, 1 cleared." in out and "  Line 6: 120 is cited" in out, "one ruling clears one of two copies of a sentence", memo_block(out))
    both = with_memo(root, "bind-one-sentence", "Of 120 complaints, 120 were reviewed [EV-22 p1].\n")
    rows = re.findall(r"To rule, name: (120 #[0-9a-f]{8})$", check(both)[1], re.M)
    expect(len(rows) == 2 and rows[0] != rows[1], "two rows in one sentence carry two marks", str(rows))


def test_board_fields(root):
    """A board reference with no date or role is not an approval, and the page and sign agree."""
    for name, blanks, words in (
            ("both", ("Board approval date", "Board approval recorded by (role)"), "no date and role"),
            ("date", ("Board approval date",), "no date"),
            ("role", ("Board approval recorded by (role)",), "no role")):
        folder = ia(root, "board-" + name)
        record = folder / "closure" / "record.md"
        for key in blanks:
            finding.write_text(record, re.sub(r"(?m)^" + re.escape(key) + r":.*$", key + ":", record.read_text(encoding="utf-8")))
        code, out, _ = check(folder)
        expect(code == 1 and "  The board: its approval of closure ({}).\n".format(words) in out and "Ready to sign" not in out,
               "the page names what a board approval lacks: " + name, out[-300:])
        code, out, _ = run(["sign", str(folder), "--today", NOW], stdin=StandInTerminal())
        expect(code == 1 and out == refusal("Refused: closure/record.md holds no board approval ({}).".format(words)),
               "sign names the same thing: " + name, out)


def test_signature_on_the_page(root):
    """Once sign's own conditions pass, the page names the owner's signature first and prints the folder's fingerprint."""
    files = dict(IA_FILES)
    files["finding.md"] = files["finding.md"].replace("Kind of matter: internal audit finding", "Kind of matter: supervisory finding")
    files["finding.md"] = re.sub(r"(?m)^Issuer:.*$", "Issuer: the Supervisor", files["finding.md"])
    folder = build(root, "order-supervisory", files, "2026-04-17")
    code, out, _ = check(folder)
    expect(code == 1 and out.endswith("Needs a person:\n  Head of Complaints: the signature, which comes first.\n"
                                      "  Internal audit: its reference in closure/record.md.\n"
                                      "  The Supervisor: its closure notice.\n" + ready_line(folder)),
           "a supervisory finding says Ready to sign and names the owner first", out[-400:])
    expect(check(folder)[1] == out, "the fingerprint line is the same every run")
    fp = finding.fingerprint(folder)
    code, signed, _ = run(["sign", str(folder), "--today", NOW], stdin=answers("Head of Complaints", fp[:8]))
    expect(code == 0, "sign works from that page", signed[-200:])
    code, out, _ = check(folder)
    expect(code == 1 and out.endswith("Needs a person:\n  Internal audit: its reference in closure/record.md.\n  The Supervisor: its closure notice.\n"),
           "after signing the owner's line and the Ready line are gone", out[-300:])
    not_yet = ia(root, "order-not-ready")
    edit(not_yet / "closure" / "memo.md", "402", "403")
    out = check(not_yet)[1]
    expect("the signature" not in out and "Ready to sign" not in out, "a folder sign would refuse names no signature", out[-300:])
    done = ia(root, "order-signed")
    expect(sign_folder(done)[0] == 0, "the folder signs")
    code, out, _ = check(done)
    expect(code == 0 and out.endswith("Nothing needs a person.\n"), "signed and tested exits 0, so exit 0 means signed", out[-200:])
    page = (HERE / "cases" / "IA-CMP-02" / "closure" / "record.md").read_text(encoding="utf-8")
    expect("Internal audit reference:\n" in page, "the shipped case holds no internal audit entry before its signature")


def test_tested_fingerprint(root):
    """Internal audit's tested fingerprint is compared with the folder as it stands."""
    def tested(name, value=None):
        folder = ia(root, name)
        expect(sign_folder(folder)[0] == 0, "the folder signs")
        signed = finding.fingerprint(folder)
        append_to(folder / "closure" / "record.md", "Internal audit tested fingerprint: {}\n".format(value or signed[:8]))
        return folder, signed
    folder, signed = tested("tested-moved")
    append_to(folder / "closure" / "memo.md", "\nThe Head of Complaints holds the sample.\n")
    now = finding.fingerprint(folder)
    code, out, _ = check(folder)
    expect(code == 1 and "Internal audit tested fingerprint {}; the folder is now {}.".format(signed[:8], now[:8]) in out
           and "  Head of Complaints: a fresh signature.\n" in out and "  Internal audit: a fresh test.\n" in out,
           "a memo change after a test asks internal audit for a fresh test at once", out[-400:])
    folder, signed = tested("tested-current")
    append_to(folder / "closure" / "memo.md", "\nThe Head of Complaints holds the sample.\n")
    edit(folder / "closure" / "record.md", "Internal audit tested fingerprint: " + signed[:8],
         "Internal audit tested fingerprint: " + finding.fingerprint(folder)[:8])
    out = check(folder)[1]
    expect("tested fingerprint" not in out and "a fresh test" not in out, "a test of the folder as it stands is quiet", out[-300:])
    folder, signed = tested("tested-short", "PREFIX")
    edit(folder / "closure" / "record.md", "fingerprint: PREFIX", "fingerprint: " + finding.fingerprint(folder)[:1])
    code, out, _ = check(folder)
    expect(code == 1 and "  Internal audit: a fresh test.\n" in out, "a value under eight characters asks for a fresh test", out[-300:])


def test_board_flags_late(root):
    """A milestone signed after its committed date is flagged on the board summary."""
    folder = fresh(root, "late-signed")
    edit(folder / "evidence" / "EV-08-training-register.md", "Signed by: Head of Complaints, 2026-03-14", "Signed by: Head of Complaints, 2026-04-03")
    out = check(folder)[1]
    expect("Flagged commitments: M2 signed 19 days after its commitment, M3 slipped 188 days, M4 slipped 127 days." in out,
           "a late signature stays on the flagged list with its days", line_of(out, "Flagged commitments:"))
    expect("Present and signed on 2026-04-03." in line_of(out, "M2 "), "the milestone's own row is unchanged", line_of(out, "M2 "))
    files = dict(MRA_FILES)
    files["plan.md"] = files["plan.md"].replace("| 2026-02-28 |", "| 2026-02-19 |", 1)
    one = fresh(root, "late-one-day", files)
    expect("M1 signed 1 day after its commitment" in line_of(check(one, "2026-02-21")[1], "Flagged commitments:"), "one day reads as one",
           line_of(check(one, "2026-02-21")[1], "Flagged commitments:"))
    expect("Flagged commitments: none." in check(ia(root, "late-on-time"))[1], "a milestone signed on time is not flagged")


def test_draft_rows(root):
    """One row per draft cover, while a claim that does not match keeps its own."""
    body = "## Page 1\nThe review held 111 items, 222 items and 333 items.\n\n## Page 2\nIt found 444 errors.\n"
    def draft(name, memo):
        folder = with_memo(root, name, memo)
        finding.write_text(folder / "evidence" / "EV-13-review.md", "What: EV-13 Review\nFor: EV-13\nSigned by:\nStatus: DRAFT\n\n" + body)
        return folder
    memo = "It held 111 items [EV-13 p1]. It held 222 items [EV-13 p1]. It held 333 items [EV-13 p1].\n\nIt found 444 errors [EV-13 p2].\n"
    folder = draft("draft-matches", memo)
    code, out, _ = check(folder)
    expect("Memo check: 4 claims, 0 tie, 1 on the list." in out
           and "  Line 4: EV-13, which is a draft, holds 4 claims, on lines 4 and 6, that match its pages and wait on a person's signature. To rule, name: EV-13 draft #" in out,
           "the claims matching a draft's pages sit on one row and count as no ties", memo_block(out))
    expect(code == 1 and "Head of Complaints: the list (1 row)" in out and "Ready to sign" not in out, "the draft's row stops the signature", out[-300:])
    code, out, _ = run(["eval", str(folder)])
    expect(code == 0 and "Planted 11 errors, one at a time, in the 4 claims that tie today or match a draft's pages." in out
           and "A figure with one digit changed: 4 planted, 4 caught." in out, "eval runs while the evidence is a draft", out)
    single = draft("draft-single", "It found 444 errors [EV-13 p2].\n")
    expect("A figure with one digit changed: 1 planted, 1 caught." in run(["eval", str(single)])[1],
           "a plant on a draft's only claim is caught, though the count of rows stays", run(["eval", str(single)])[1])
    folder = draft("draft-mismatch", memo.replace("444", "445"))
    out = check(folder)[1]
    expect("Memo check: 4 claims, 0 tie, 2 on the list." in out and "holds 3 claims that match its pages" in out
           and "  Line 6: 445 is cited to EV-13 p2, which is a draft, and the page does not hold it; the nearest figure on the page is 444." in out,
           "a claim that does not match a draft's page keeps its own row", memo_block(out))
    folder = draft("draft-ruling", memo)
    add_ruling(folder, "EV-13 draft", "cleared | Head of Complaints | 2026-11-04 | Signed copy is on its way.")
    out = check(folder)[1]
    expect("0 on the list, 1 cleared." in out and "0 tie" in out, "the owner can rule on the cover's row", memo_block(out))
    append_to(folder / "closure" / "memo.md", "\nThe review held 111 items again [EV-13 p1].\n")
    out = check(folder)[1]
    expect("holds 5 claims" in out and "names no row" in out, "a new claim on the draft brings its row back", memo_block(out))
    two = draft("draft-two-covers", memo + "\nThe note holds 555 items [EV-14 p1].\n")
    finding.write_text(two / "evidence" / "EV-14-note.md", "What: EV-14 Note\nFor: EV-14\nSigned by:\nStatus: DRAFT\n\nThe note holds 555 items.\n")
    out = check(two)[1]
    expect("EV-13, which is a draft, holds 4 claims" in out and "EV-14, which is a draft, holds 1 claim that matches its pages and waits on a person's signature." in out
           and "Memo check: 5 claims, 0 tie, 2 on the list." in out, "each draft cover has its own row", memo_block(out))


def test_blank_pages_named(root):
    """A cited page with no text and nothing typed is named on the page, signed or not, and a page nobody cites is not."""
    data = simple_pdf(["The listing held 1,284 items.", "", "More text."])
    folder = with_document(root, "blank-named", "EV-30-listing.pdf", data, "The listing held 1,284 items [EV-30 p1].")
    code, out, _ = check(folder)
    expect("no text and nothing typed" not in out and only_the_signature(code, out), "a blank page nobody cites is not named", memo_block(out))
    append_to(folder / "closure" / "memo.md", "The second page held 5 items [EV-30 p2].")
    add_ruling(folder, "5")
    code, out, _ = check(folder)
    expect("  EV-30 page 2 has no text and nothing typed.\n" in out and only_the_signature(code, out), "a cited blank page is named, and a ruling on its row leaves nothing for a person", memo_block(out))
    expect(sign_folder(folder)[0] == 0, "the folder signs")
    expect("  EV-30 page 2 has no text and nothing typed.\n" in check(folder)[1], "the signed screen names it too", check(folder)[1][-400:])
    unlisted = with_document(root, "blank-uncited", "EV-30-listing.pdf", simple_pdf(["", ""]), "The sample held 120 complaints [EV-21 p2].")
    expect("no text and nothing typed" not in check(unlisted)[1], "a counted document nobody cites is not named", memo_block(check(unlisted)[1]))
    typed = with_document(root, "blank-typed", "EV-30-listing.pdf", data, "The listing held 1,284 items [EV-30 p1].",
                          "\n## Page 2\nThe second page held 5 items.\n")
    expect("no text and nothing typed" not in check(typed)[1], "a typed page is no longer named", memo_block(check(typed)[1]))


def test_eval_honest(root):
    """eval plants a curly-quoted or wrapped quotation by position, and names a claim it could not plant in."""
    def quoted(name, memo):
        folder = with_memo(root, name, memo)
        run_out = run(["eval", str(folder)])[1]
        return run_out
    words = "the complaint system sends an acknowledgement letter automatically"
    for name, memo in (("straight", '"{}" [EV-21 p1].\n'.format(words)),
                       ("curly", '“{}” [EV-21 p1].\n'.format(words)),
                       ("low", '„{}” [EV-21 p1].\n'.format(words)),
                       ("wrapped", '"the complaint system sends\nan acknowledgement letter automatically" [EV-21 p1].\n')):
        out = quoted("eval-" + name, memo)
        expect("A quotation with one word dropped: 1 planted, 1 caught." in out, "eval plants a quotation written " + name, out)
    folder = with_memo(root, "eval-two-copies", '“{0}” [EV-21 p1].\n\n"{0}" [EV-21 p1].\n'.format(words))
    entries = finding.scan_evidence(folder)[0]
    base = finding.memo_check(folder, entries, "Head of Complaints")
    record_mod, _ = finding.engine()
    text = finding.memo_text(folder)
    plants = finding.eval_plants(text, base["tied"], record_mod, base["by_label"], base["index"])[0]
    landed = [(p[1], [i + 1 for i, (a, b) in enumerate(zip(text.split("\n"), p[3].split("\n"))) if a != b])
              for p in plants if p[0] == "quote_changed"]
    expect(landed == [(4, [4]), (6, [6])], "each quotation's plant lands on its own line", str(landed))

    folder = with_memo(root, "eval-bare", 'The dispute was a "fee dispute" [EV-41 p1], logged 03/14/2026 [EV-41 p1].\n')
    typed_evidence(folder, "EV-41-note.md", "EV-41", 'A "fee dispute" logged 03/14/2026.')
    out = run(["eval", str(folder)])[1]
    expect('2 claims had no error of their own kind planted, so read these by hand: line 4 "fee dispute"; line 4 03/14/2026.' in out
           and "Planted 0 errors, one at a time, in the 2 claims that tie today." in out, "eval names the claims it could not plant in", out)
    single = with_memo(root, "eval-one", "The sample held 120 complaints [EV-21 p2].\n")
    out = run(["eval", str(single)])[1]
    expect("in the 1 claim that ties today." in out and "had no error" not in out, "eval reads right in the singular", out)
    one_bare = with_memo(root, "eval-one-bare", 'It says "two words" [EV-41 p1].\n')
    typed_evidence(one_bare, "EV-41-note.md", "EV-41", 'It says "two words".')
    expect('1 claim had no error of its own kind planted, so read it by hand: line 4 "two words".' in run(["eval", str(one_bare)])[1], "and for one bare claim",
           run(["eval", str(one_bare)])[1])


def test_small_page_errors(root):
    """The small slips: owner, days, covers, size, cite, eval's speed, a four-line note."""
    blank = fresh(root, "small-owner")
    edit(blank / "plan.md", "| M1 Approve revised complaint taxonomy | Head of Complaints |", "| M1 Approve revised complaint taxonomy | |")
    expect(check(blank)[1] == refusal("Not ready: plan.md line 6 has no owner role."), "a plan row with no owner is refused", check(blank)[1][:200])

    days = fresh(root, "small-days", first_check=None)
    finding.write_text(days / "closure" / "measures.md", "Hours | 2026-10 | 5\n")
    check(days)
    out = check(days, "2026-10-01")[1]
    expect("0 days since the first check" in out, "days since the first check never go below nothing", line_of(out, "Measures:"))

    typed = with_document(root, "small-covers", "EV-30-scan.pdf", simple_pdf(["Text.", "", "More."]), "The sample held 120 complaints [EV-21 p2].")
    code, out, _ = run(["covers", str(typed)])
    expect(code == 1 and "no text on page 2" in out, "covers says a page has no text and exits 1", out)
    append_to(typed / "evidence" / "EV-30-scan.pdf.md", "\n## Page 2\nThe second page.\n")
    code, out, _ = run(["covers", str(typed)])
    expect(code == 0 and "no text on page 2" in out, "covers exits 0 once the page is typed, and still says what the document holds", out)
    noted = with_document(root, "small-covers-note", "EV-30-scan.pdf", simple_pdf(["", "More."]), "The sample held 120 complaints [EV-21 p2].", "\nA note, not a page.\n")
    expect(run(["covers", str(noted)])[0] == 1, "a note in a cover types no page")

    parent = root / "small-size"
    parent.mkdir()
    shutil.copytree(str(fresh(root, "small-size-a")), str(parent / "first"))
    shutil.copytree(str(fresh(root, "small-size-b")), str(parent / "second"))
    edit(parent / "second" / "finding.md", "Owner role: Head of Complaints", "Owner role:")
    code, out, _ = run(["size", str(parent)])
    expect(code == 1 and "\nMRA-CMP-07: 4 milestones," in out
           and "\nsecond: Not ready: finding.md has no Owner role yet. Fill that line, then check again.\n" in out
           and "\n1 finding: 29.5 hours by hand, 13.7 with the kit, assumed.\n1 finding not ready and left out of these "
               "hours.\n" in out, "size over several folders sizes the ready ones and names the one left out", out)
    edit(parent / "first" / "finding.md", "Owner role: Head of Complaints", "Owner role:")
    code, out, _ = run(["size", str(parent)])
    expect(code == 1 and out == refusal("first: Not ready: finding.md has no Owner role yet. Fill that line, then check "
                                        "again.\nsecond: Not ready: finding.md has no Owner role yet. Fill that line, then "
                                        "check again."), "size over folders none of which is ready names each", out)

    no_pin = with_document(root, "small-no-pin", "EV-31-scan.pdf", simple_pdf(["", "More 77.", "Last."]), "The scan held 77 items [EV-31].")
    edit(no_pin / "evidence" / "EV-31-scan.pdf.md", "EV-30", "EV-31")
    edit(no_pin / "evidence" / "EV-31-scan.pdf.md", "EV-30", "EV-31")
    out = check(no_pin)[1]
    expect("and EV-31 has 3 pages, so the cite needs a page." in out, "a cite with no page to a blank first page is told it needs a page", memo_block(out))

    many = with_memo(root, "small-many", "".join("Group {} held {} items [EV-42 p1].\n\n".format(i, 1000 + i) for i in range(40)))
    typed_evidence(many, "EV-42-note.md", "EV-42", " ".join("{} items.".format(1000 + i) for i in range(40)))
    calls = []
    real = finding.build_index
    finding.build_index = lambda folder, entries: (calls.append(1), real(folder, entries))[1]
    try:
        code, out, err = run(["eval", str(many)])
    finally:
        finding.build_index = real
    expect(len(calls) == 1, "eval reads the evidence once, whatever it plants", str(len(calls)))
    expect("Eval: 25 of " in err and "Eval: 25 of " not in out, "a long eval says how far it has got, on stderr only", err[:200])
    short_err = run(["eval", str(ia(root, "small-short"))])[2]
    expect(short_err == "", "a short eval prints no progress", short_err[:200])

    page = pages("README.md")
    if page is not None:
        expect("a four-line text note" not in page, "the README does not call a drafted cover four lines")
    page = pages("finding/README.md")
    if page is not None:
        expect("also writes a Source line and a comment" in page, "the finding page says what covers adds")


def test_wrapper(root):
    wrapper = HERE / "finding"
    expect(wrapper.is_file(), "the wrapper exists")
    if os.name != "posix":
        return
    expect(os.access(str(wrapper), os.X_OK), "the wrapper is executable")
    mra = fresh(root, "wrapper")
    proc = subprocess.run([str(wrapper), "check", str(mra), "--today", NOW],
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
    expect(proc.returncode == 1 and proc.stdout.decode("utf-8") == EXPECTED_MRA,
           "the wrapper prints the same screen", proc.stderr.decode("utf-8", "replace"))


def test_shipped(root):
    if not CASES.is_dir():
        print("selftest: note: no cases/ folder, so the shipped cases were not checked")
        return
    for name in ("MRA-CMP-07", "IA-CMP-02"):
        src = CASES / name
        expect((src / "finding.md").is_file(), "shipped case " + name + " exists")
        if not (src / "finding.md").is_file():
            continue
        for path in sorted(src.rglob("*")):
            if path.is_file() and path.name != finding.STATE_NAME and path.suffix.lower() in (".md", ".txt"):
                first = path.read_text(encoding="utf-8").splitlines()[:1]
                expect(first and first[0].startswith("SYNTHETIC"),
                       "shipped file starts with SYNTHETIC: " + path.relative_to(HERE).as_posix())
        copy = root / ("shipped-" + name)
        shutil.copytree(str(src), str(copy))
        code, out, _ = check(copy)
        if name == "MRA-CMP-07":
            expect(out == EXPECTED_MRA and code == 1, "shipped MRA-CMP-07 screen equals section 10",
                   diff_hint(out, EXPECTED_MRA))
        else:
            expect(code == 1 and out.endswith(EXPECTED_IA_TAIL + "  Internal audit: its reference in closure/record.md.\n"
                                              + ready_line(copy)),
                   "shipped IA-CMP-02 waits on the owner's signature, then internal audit", out)
        files = MRA_FILES if name == "MRA-CMP-07" else IA_FILES
        shipped = {path.relative_to(src).as_posix(): path.read_bytes() for path in src.rglob("*")
                   if path.is_file() and path.name != finding.STATE_NAME}
        expect(shipped == {rel: text.encode("utf-8") for rel, text in files.items()},
               "the self-test's " + name + " files are the shipped files byte for byte",
               ", ".join(sorted(set(shipped) ^ set(files))))
        expect(state_of(src).get("signature", "absent") is None,
               "the shipped " + name + " state file carries a null signature")
        expect(dict(state_of(copy), checked=None) == dict(state_of(src), checked=None) and state_of(copy)["checked"] == NOW,
               "a check leaves the shipped " + name + " state unchanged but for the date of the latest check")
        expect(recompute_matches(src), "shipped " + name + " state file matches a recompute")


def kit_copy(root, name):
    """A copy of the kit's code and test assets, for tests that change kit files."""
    kit = HERE.parent
    target = root / name
    target.mkdir()
    shutil.copy2(str(kit / "RELEASE.json"), str(target / "RELEASE.json"))
    for folder in ("finding", "library"):
        shutil.copytree(str(kit / folder), str(target / folder), ignore=shutil.ignore_patterns("__pycache__", "fixture"))
    (target / "tieout").mkdir()
    for path in (kit / "tieout").glob("*.py"):
        shutil.copy2(str(path), str(target / "tieout" / path.name))
    return target


def kit_run(copy, *args):
    """(exit code, what it printed) from the tool in a kit copy."""
    proc = subprocess.run([sys.executable, "-I", str(copy / "finding" / "finding.py")] + [str(a) for a in args],
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, input=b"")
    return proc.returncode, proc.stdout.decode("utf-8", "replace").replace("\r\n", "\n")


def release_run(copy, *args):
    """(exit code, what it printed) from release.py in a kit copy."""
    proc = subprocess.run([sys.executable, "-I", str(copy / "finding" / "release.py")] + list(args),
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, input=b"")
    return proc.returncode, proc.stdout.decode("utf-8", "replace").replace("\r\n", "\n")


def append_to(path, line):
    finding.write_text(path, path.read_text(encoding="utf-8") + line + "\n")


def typed_evidence(folder, filename, eid, body, head=""):
    """A text file in evidence/ with a whole header and the body given."""
    finding.write_text(folder / "evidence" / filename, "What: {0} Note\nFor: {0}\nSigned by: Head of Complaints, 2026-07-01\n"
                       "Status: FINAL\n{1}\n{2}\n".format(eid, head, body))


def sign_folder(folder, today=NOW):
    fp = finding.fingerprint(folder)
    code, out, _ = run(["sign", str(folder), "--today", today], stdin=answers("Head of Complaints", fp[:8]))
    return code, out


def test_evidence_ids(root):
    """An institution's evidence id may hold several number groups and many digits."""
    for eid in ("EV-2026-0042", "EV-10000000", "EV-20260042", "DOC20260042", "BN-00012345", "EV-9999999"):
        folder = ia(root, "id-" + eid)
        typed_evidence(folder, eid + "-note.md", eid, "Total 5,555 items.")
        append_to(folder / "closure" / "memo.md", "\nTotal 5,555 items [{} p1].".format(eid))
        code, out, _ = check(folder)
        expect(only_the_signature(code, out) and "Memo check: 14 claims, 14 tie, 0 on the list." in out, "evidence id {} ties".format(eid), out[-300:])
        append_to(folder / "closure" / "memo.md", "\nTotal 6,666 items [{} p1].".format(eid))
        code, out, _ = check(folder)
        expect("6,666 is cited to {} p1, and the page does not hold it; the nearest figure on the page is 5,555.".format(eid) in out,
               "a wrong figure against evidence id {} goes on the list".format(eid), block_from(out, "Memo check:"))

    pages = ia(root, "id-pages")
    finding.write_text(pages / "evidence" / "EV-2026-0042-note.md", "What: EV-2026-0042 Note\nFor: EV-2026-0042\n"
                       "Signed by: Head of Complaints, 2026-07-01\nStatus: FINAL\n\n## Page 1\nFirst 1,111.\n\n## Page 2\nSecond 2,222.\n")
    append_to(pages / "closure" / "memo.md", "\nSecond 2,222 [EV-2026-0042 p2]. Third 3,333 [EV-2026-0042 p3]. Other 1,111 [EV-2026-0042 p2].")
    code, out, _ = check(pages)
    expect("3,333 is cited to EV-2026-0042 p3, and EV-2026-0042 has 2 pages." in out
           and "1,111 is cited to EV-2026-0042 p2, and the page does not hold it; the nearest figure on the page is 2,222." in out
           and "2,222 is cited" not in out, "a page of a long id ties and is told from its other pages", block_from(out, "Memo check:"))
    apart = ia(root, "id-apart")
    typed_evidence(apart, "EV-2026-0042-note.md", "EV-2026-0042", "A note.")
    typed_evidence(apart, "EV-20260042-note.md", "EV-20260042", "A note.")
    code, out, _ = check(apart)
    expect(out == refusal("Not ready: evidence ids EV-2026-0042 and EV-20260042 cannot be told apart by the memo check; rename one."),
           "two long ids that read the same stop the check", out)

    long_id = "EV-" + "7" * 5000
    folder = ia(root, "id-long")
    typed_evidence(folder, "long-id-note.md", long_id, "Total 5,555 items.")
    append_to(folder / "closure" / "memo.md", "\nTotal 5,555 items [{} p1].".format(long_id))
    code, out, _ = check(folder)
    expect(only_the_signature(code, out) and "Memo check: 14 claims, 14 tie, 0 on the list." in out, "an id of any length ties", out[-300:])

    two = ia(root, "id-two-numbers")
    (two / "evidence" / "EV-2026-0042-procedure.csv").write_bytes(b"Items,1111\n")
    (two / "evidence" / "EV-2026-0043-minutes.csv").write_bytes(b"Items,7777\n")
    code, out, _ = run(["covers", str(two)])
    expect("Draft cover written for evidence id EV-2026-0042." in out and "Draft cover written for evidence id EV-2026-0043." in out,
           "covers takes the whole id and says which id it wrote", out)
    for name in ("EV-2026-0042-procedure.csv.md", "EV-2026-0043-minutes.csv.md"):
        cover = two / "evidence" / name
        expect("For: EV-2026-004" in cover.read_text(encoding="utf-8"), "a cover keeps the whole id", cover.read_text(encoding="utf-8"))
        edit(cover, "Signed by:", "Signed by: Head of Complaints, 2026-07-01")
        edit(cover, "Status: DRAFT", "Status: FINAL")
    append_to(two / "closure" / "memo.md", "\nThe procedure holds 1,111 items [EV-2026-0042 p1]. The minutes hold 7,777 items [EV-2026-0043 p1].")
    code, out, _ = check(two)
    expect("Memo check: 15 claims, 15 tie, 0 on the list." in out, "each of two ids ties to its own document", block_from(out, "Memo check:"))

    same = ia(root, "id-same-twice")
    typed_evidence(same, "EV-40-first.md", "EV-40", "Total 4,242 items.")
    typed_evidence(same, "EV-40-second.md", "EV-40", "Total 5,353 items.")
    code, out, _ = check(same)
    expect(code == 1 and out == refusal("Not ready: two files in evidence/ carry evidence id EV-40, and the memo check reads one "
                                        "document per id; give each its own id."), "two files under one id stop the check", out)

    dated = ia(root, "id-date-after")
    edit(dated / "plan.md", "| EV-21 |", "| EV-21, EV-12 |")
    (dated / "evidence" / "EV-12-2026-03-14-minutes.csv").write_bytes(b"Items,1\n")
    (dated / "evidence" / "EV-77-2026-03-14-minutes.csv").write_bytes(b"Items,2\n")
    (dated / "evidence" / "EV-78-3rd-party.csv").write_bytes(b"Items,3\n")
    code, out, _ = run(["covers", str(dated)])
    expect("Draft cover written for evidence id EV-12." in out and "For: M1 EV-12\n" in
           (dated / "evidence" / "EV-12-2026-03-14-minutes.csv.md").read_text(encoding="utf-8"),
           "a date after an id the plan lists stays out of the id", out)
    expect("Draft cover written for evidence id EV-77-2026-03-14." in out,
           "a date after an id the plan does not list lands in the id, and the screen shows it for a person to catch", out)
    expect("Draft cover written for evidence id EV-78." in out, "a number run into a word is no part of the id", out)


def test_cover_by_name(root):
    """A cover named with a Covers: line counts its document, and covers leaves it alone."""
    folder = ia(root, "cover-by-name")
    extract = folder / "evidence" / "raw-extract.csv"
    extract.write_bytes(b"a,b\n5555,2\n")
    typed_evidence(folder, "EV-70.md", "EV-70", "", "Covers: raw-extract.csv\n")
    append_to(folder / "closure" / "memo.md", "\nCount was 5555 [EV-70 p1].")
    code, out, _ = check(folder)
    expect(only_the_signature(code, out) and "Not counted" not in out and "Memo check: 14 claims, 14 tie, 0 on the list." in out,
           "a cover named with a Covers: line counts the document", out)
    expect("evidence/raw-extract.csv" in state_of(folder)["evidence"], "the state file hashes the covered document")
    code, out, _ = run(["covers", str(folder)])
    expect("evidence/raw-extract.csv: 1 page, 1 with text. It has a cover already." in out
           and not (folder / "evidence" / "raw-extract.csv.md").exists(), "covers writes no second cover", out)
    code, out = sign_folder(folder)
    expect(code == 0 and "Signed by the Head of Complaints" in out, "sign gets past the document a Covers: line counts", out[-300:])

    reverse = ia(root, "cover-names-another")
    (reverse / "evidence" / "other.csv").write_bytes(b"a,1\n")
    (reverse / "evidence" / "other2.csv").write_bytes(b"a,2\n")
    written = "What: EV-71 Other\nFor: EV-71\nSigned by: Head of Complaints, 2026-07-01\nStatus: FINAL\nCovers: other2.csv\n"
    finding.write_text(reverse / "evidence" / "other.csv.md", written)
    code, out, _ = check(reverse)
    expect("evidence/other.csv, which other.csv.md does not cover." in out and "evidence/other2.csv," not in out,
           "a file its namesake cover does not name is listed as not counted", out)
    code, out, _ = run(["covers", str(reverse)])
    expect(code == 1 and "other.csv.md names another file, so this file has no cover." in out
           and (reverse / "evidence" / "other.csv.md").read_text(encoding="utf-8") == written,
           "covers never overwrites a cover that names another file", out)


def test_header_stops(root):
    """The evidence header is the first run of header lines. A body line is body."""
    folder = ia(root, "header-body")
    typed_evidence(folder, "EV-55-note.md", "EV-55", "Status: 412 complaints were open at quarter end.\nSource: the complaints system, "
                   "9,876 rows.\nFor: the Head of Complaints.\nPlain sentence after those with 321 items.")
    append_to(folder / "closure" / "memo.md", "\nOpen complaints were 412 [EV-55 p1]. The system held 9,876 rows [EV-55 p1]. Items were 321 [EV-55 p1].")
    code, out, _ = check(folder)
    expect(only_the_signature(code, out) and "Memo check: 16 claims, 16 tie, 0 on the list." in out, "body lines starting with a header word stay on the page",
           block_from(out, "Memo check:"))

    def milestone_with(name, body, head=""):
        case = ia(root, name)
        edit(case / "plan.md", "| EV-21 |", "| EV-21, EV-55 |")
        typed_evidence(case, "EV-55-note.md", "EV-55", body, head)
        return check(case)[1]

    out = milestone_with("header-revised", "Revised: 2026-08-01\n\nThe note.")
    expect("EV-55 was revised on 2026-08-01, after its signature of 2026-07-01" in line_of(out, "M1 "),
           "a dated Revised line first after the blank still counts, so a revised file never reads as signed", line_of(out, "M1 "))
    out = milestone_with("header-revised-body", "Source: the complaints system.\nRevised: 2026-08-01")
    expect("Present and signed" in line_of(out, "M1 "), "a Revised line deeper in the body is body", line_of(out, "M1 "))
    out = milestone_with("header-revised-words", "Revised: the policy was changed.")
    expect("Present and signed" in line_of(out, "M1 "), "a Revised line with no date is body", line_of(out, "M1 "))

    unsigned = ia(root, "header-signed-in-body")
    finding.write_text(unsigned / "evidence" / "EV-55-note.md", "What: EV-55 Note\nFor: EV-55\nStatus: FINAL\n\n"
                       "Signed by: Head of Complaints, 2026-03-01\nA note.\n")
    code, out, _ = check(unsigned)
    expect("evidence/EV-55-note.md, whose first lines are not the evidence header." in out,
           "a body line cannot stand in for a missing signature", out)

    covers = ia(root, "header-covers-in-body")
    typed_evidence(covers, "EV-55-note.md", "EV-55", "Covers: the first quarter, with 321 items.")
    append_to(covers / "closure" / "memo.md", "\nItems were 321 [EV-55 p1].")
    code, out, _ = check(covers)
    expect(only_the_signature(code, out) and "Not counted" not in out and "14 tie, 0 on the list" in out,
           "a body line starting Covers: names no covered file", out)


def test_line_endings(root):
    """A line-ending change alone leaves a signed folder as it was. A change of bytes in a binary still shows."""
    folder = ia(root, "crlf")
    (folder / "evidence" / "EV-30-rows.csv").write_bytes(b"Items,1284\n")
    typed_evidence(folder, "EV-30-rows.csv.md", "EV-30", "")
    pdf = folder / "evidence" / "EV-31-listing.pdf"
    pdf.write_bytes(simple_pdf(["The listing held 1,824 items."]))
    typed_evidence(folder, "EV-31-listing.pdf.md", "EV-31", "")
    edit(folder / "plan.md", "| EV-21 |", "| EV-21, EV-30, EV-31 |")
    append_to(folder / "closure" / "memo.md", "\nThe rows held 1284 items [EV-30 p1]. The listing held 1,824 items [EV-31 p1].")
    code, out = sign_folder(folder)
    expect(code == 0, "the folder signs", out[-300:])
    code, before, _ = check(folder)
    expect(code == 0 and "Nothing needs a person." in before, "the signed folder needs no one", before[-300:])
    for path in sorted(folder.rglob("*")):
        if path.is_file() and path.suffix.lower() in (".md", ".csv"):
            path.write_bytes(path.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
    code, after, _ = check(folder)
    expect(code == 0 and after == before, "rewriting line endings leaves the page the same", diff_hint(after, before))
    code, out, _ = run(["sign", str(folder), "--today", NOW], stdin=answers())
    expect(out == refusal("Refused: this finding is signed already and nothing has changed since."),
           "a line-ending change asks for no fresh signature", out)
    note = folder / "evidence" / "EV-21-acknowledgement-procedure.md"
    note.write_bytes(note.read_bytes().replace(b"120 complaints", b"121 complaints"))
    code, out, _ = check(folder)
    expect(code == 1 and "EV-21 changed since it was signed" in line_of(out, "M1 "), "a real edit still shows", line_of(out, "M1 "))
    note.write_bytes(note.read_bytes().replace(b"121 complaints", b"120 complaints"))
    expect(check(folder)[0] == 0, "restoring the words clears it")
    data = pdf.read_bytes()
    expect(b"\n" in data and b"\r\n" not in data, "the test PDF holds bare line feeds")
    pdf.write_bytes(data.replace(b"\n", b"\r\n"))
    code, out, _ = check(folder)
    expect("EV-31 changed since it was signed" in line_of(out, "M1 "), "a binary's bytes are hashed as they stand", line_of(out, "M1 "))


def test_record_case(root):
    """Internal audit's later entries ask for no fresh signature, whatever case they are typed in."""
    for typed in ("Internal Audit Reference: IAV-1", "INTERNAL AUDIT REFERENCE: IAV-1", "internal audit reference: IAV-1"):
        folder = ia(root, "record-case-" + re.sub(r"\W", "-", typed))
        expect(sign_folder(folder)[0] == 0, "the folder signs")
        edit(folder / "closure" / "record.md", "Internal audit reference: IAV-2026-031", typed)
        code, out, _ = check(folder)
        expect(code == 0 and "Internal audit: reference IAV-1" in out and "Changed since signing" not in out,
               "'{}' asks for no fresh signature".format(typed), out[-300:])
    folder = ia(root, "record-case-covered")
    expect(sign_folder(folder)[0] == 0, "the folder signs")
    edit(folder / "closure" / "record.md", "Board approval reference: BM-2026-07", "Board Approval Reference: BM-2026-08")
    code, out, _ = check(folder)
    expect(code == 1 and "Changed since signing: closure/record.md." in out and "a fresh signature" in out,
           "a change to a line a signature covers still asks for one", out[-300:])
    typed = ia(root, "record-case-signed")
    edit(typed / "closure" / "record.md", "Fingerprint:", "fingerprint:")
    expect(sign_folder(typed)[0] == 0, "the folder signs")
    record = (typed / "closure" / "record.md").read_text(encoding="utf-8")
    expect(len(re.findall(r"(?im)^fingerprint:", record)) == 1, "sign replaces a signature line typed in another case", record)
    expect(check(typed)[0] == 0, "and the check after it is clean")


def test_typed_count(root):
    """Every tie on text a person typed is counted, and only a tie typed into a cover stops the signature."""
    folder = ia(root, "typed-whole")
    typed_evidence(folder, "EV-40-scan.md", "EV-40", "The scan holds 777 items.")
    append_to(folder / "closure" / "memo.md", "\nThe scan holds 777 items [EV-40 p1].")
    code, out, _ = check(folder)
    plain = "  14 ties rest on text a person typed: 14 in plain-text evidence, none on a page typed into a cover.\n"
    expect(only_the_signature(code, out) and plain in out,
           "a document typed in full counts as typed, and the exit code stays", block_from(out, "Memo check:"))
    expect("Ready to sign" in out and "The engagement team" not in out, "a text file with no document behind it asks for no second person", out[-200:])
    typed_evidence(folder, "EV-40-scan.md", "EV-40", "The scan holds 777 items.", "Checked by: Associate 2, 2026-07-02\n")
    edit(folder / "evidence" / "EV-40-scan.md", "Head of Complaints, 2026-07-01", "Head of Complaints, 2026-07-02")
    code, out, _ = check(folder)
    expect(plain in out and "with no Checked by line" not in out,
           "plain-text evidence needs no Checked by line, so one changes nothing on the line", block_from(out, "Memo check:"))
    one = build(root, "typed-one", {rel: text for rel, text in IA_FILES.items() if rel != "closure/memo.md"}, "2026-04-17")
    typed_evidence(one, "EV-40-scan.md", "EV-40", "The scan holds 777 items.")
    finding.write_text(one / "closure" / "memo.md", "The scan holds 777 items [EV-40 p1].\n")
    code, out, _ = check(one)
    expect("  1 tie rests on text a person typed: 1 in plain-text evidence, none on a page typed into a cover." in out,
           "one tie reads as one", block_from(out, "Memo check:"))


def test_fingerprint_covers_reader(root):
    """A change to the Word reader's imports asks for a fresh signature, and the two lists cannot drift."""
    signed = ia(root, "fingerprint-scope")
    files = finding.fingerprint_files(signed)[0]
    for rel in finding.KIT_FILES:
        if rel not in ("finding/finding", "finding/finding.py"):
            expect(rel in files, "the fingerprint covers " + rel)
    copy = kit_copy(root, "kit-fingerprint")
    old_kit = finding.KIT
    finding.KIT = copy
    try:
        base = finding.fingerprint(signed)
        for rel in ("tieout/claims.py", "tieout/words.py"):
            append_to(copy / rel, "# a comment")
            moved = finding.fingerprint(signed)
            expect(moved != base, "a comment in {} moves the fingerprint".format(rel))
            base = moved
    finally:
        finding.KIT = old_kit


def test_kit_list(root):
    """--version reads no match from an emptied list or from code the kit does not ship."""
    emptied = kit_copy(root, "kit-emptied")
    doc = json.loads((emptied / "RELEASE.json").read_text(encoding="utf-8"))
    doc["files"] = {}
    (emptied / "RELEASE.json").write_text(json.dumps(doc), encoding="utf-8")
    code, out = kit_run(emptied, "--version")
    expect(code == 1 and "Every file matches" not in out and "finding/finding.py (not listed)" in out and out.count("(not listed)") == len(finding.KIT_FILES),
           "an emptied list names every file", out)
    mra = fresh(root, "kit-list-mra")
    code, out = kit_run(emptied, "check", mra, "--today", NOW)
    expect("Kit files changed since release" in out and "(not listed)" in out, "and the check page says so", out[:400])

    planted = kit_copy(root, "kit-planted")
    finding.write_text(planted / "tieout" / "csv.py", "# planted\n")
    code, out = kit_run(planted, "--version")
    expect(code == 1 and "tieout/csv.py (not part of the kit)" in out, "a planted module is named", out)
    code, out = kit_run(planted, "check", mra, "--today", NOW)
    expect("tieout/csv.py (not part of the kit)" in out, "and on the check page", out[:400])
    (planted / "tieout" / "csv.py").unlink()
    (planted / "tieout" / "__pycache__").mkdir()
    finding.write_text(planted / "tieout" / "__pycache__" / "verify.cpython-313.pyc", "x")
    code, out = kit_run(planted, "--version")
    expect(code == 1 and "tieout/__pycache__ (not part of the kit)" in out, "a cache folder that could run in place of the source is named", out)
    shutil.rmtree(str(planted / "tieout" / "__pycache__"))
    code, out = kit_run(planted, "--version")
    expect(code == 0 and "Every file matches this release." in out, "the kit's own code raises no alarm", out)

    for label, body in (("a number", '{"version":"x","files":5}'), ("null", '{"version":"x","files":null}'),
                        ("a list", '{"version":"x","files":["a"]}'), ("no JSON", "not json"), ("a list file", "[1]")):
        (planted / "RELEASE.json").write_text(body, encoding="utf-8")
        code, out = kit_run(planted, "--version")
        expect(code == 1 and "cannot be checked" in out and "Traceback" not in out, "a RELEASE.json holding {} gives the plain line".format(label), out)
        code, out = kit_run(planted, "check", mra, "--today", NOW)
        expect("Traceback" not in out and "kit release unknown" in out, "and the check page runs with {}".format(label), out[-300:])


def test_site_version(root):
    """A hash change refreshed with no version named becomes a site version."""
    copy = kit_copy(root, "kit-site")
    version = json.loads((copy / "RELEASE.json").read_text(encoding="utf-8"))["version"]
    base, _, n = version.partition("+site.")
    step = int(n or 0)

    def version_now():
        return json.loads((copy / "RELEASE.json").read_text(encoding="utf-8"))["version"]

    code, out = release_run(copy)
    expect(code == 0 and version_now() == version, "a refresh with no hash moved keeps the version", out)
    append_to(copy / "finding" / "finding.py", "# a site change")
    code, out = release_run(copy)
    expect(code == 0 and version_now() == "{}+site.{}".format(base, step + 1), "a hash change steps to a site version", out)
    expect("site change log" in out, "and says to record it", out)
    code, out = kit_run(copy, "--version")
    expect(code == 0 and "RegRem Engine {}+site.{}\nEvery file matches this release.".format(base, step + 1) in out,
           "--version prints the site version", out)
    mra = fresh(root, "kit-site-mra")
    code, out = kit_run(copy, "check", mra, "--today", NOW)
    expect("kit release {}+site.{}.".format(base, step + 1) in out, "the check page prints the site version", out[:300])
    code, out = release_run(copy)
    expect(version_now() == "{}+site.{}".format(base, step + 1), "a second refresh with nothing moved stays there", out)
    append_to(copy / "library" / "cases" / "figure-transposed.json", " ")
    code, out = release_run(copy)
    expect(version_now() == "{}+site.{}".format(base, step + 2), "a changed test asset steps it too", out)
    code, out = release_run(copy, "9.8.7")
    expect(code == 0 and version_now() == "9.8.7", "a version named wins", out)
    code, out = kit_run(copy, "--version")
    expect(code == 0 and "RegRem Engine 9.8.7\n" in out, "a numbered release reads plainly", out)
    code, out = release_run(copy, "--help")
    expect(code == 2 and version_now() == "9.8.7", "a flag is no version", out)
    code, out = release_run(copy, "9.8.7", "9.8.8")
    expect(code == 2 and version_now() == "9.8.7", "two versions are a usage error", out)


def test_test_assets(root):
    """--version notices a case or the self-test moved, and a finding's pages stay the same."""
    listed = json.loads((HERE.parent / "RELEASE.json").read_text(encoding="utf-8"))["tests"]
    for rel in ("finding/selftest.py", "library/cases/figure-transposed.json", "finding/cases/MRA-CMP-07/finding.md",
                "finding/cases/MRA-CMP-07/.finding-state.json", "finding/samples/EV-30-sample-listing.pdf"):
        expect(rel in listed, "RELEASE.json lists " + rel)
    expect(not any(rel in listed for rel in finding.KIT_FILES), "a file is listed once")

    copy = kit_copy(root, "kit-tests")
    cases = copy / "library" / "cases"
    (cases / "figure-transposed.json").unlink()
    (cases / "no-cite.json").unlink()
    code, out = kit_run(copy, "--version")
    expect(code == 1 and "Test files changed since this release: library/cases/figure-transposed.json, library/cases/no-cite.json." in out
           and "Every file matches" not in out, "deleted cases are named", out)
    copy = kit_copy(root, "kit-tests-gutted")
    finding.write_text(copy / "library" / "cases" / "figure-transposed.json", '{"evidence": [], "memo": "", "expect": {"list": 0}}\n')
    code, out = kit_run(copy, "--version")
    expect(code == 1 and "library/cases/figure-transposed.json" in out, "a gutted case is named", out)
    copy = kit_copy(root, "kit-tests-stub")
    finding.write_text(copy / "finding" / "selftest.py", 'print("selftest: PASS (1 expectations)")\n')
    code, out = kit_run(copy, "--version")
    expect(code == 1 and "finding/selftest.py" in out, "a replaced self-test is named", out)
    copy = kit_copy(root, "kit-tests-added")
    finding.write_text(copy / "library" / "cases" / "a-new-case.json", '{"evidence": [], "memo": "", "expect": {"list": 0}}\n')
    code, out = kit_run(copy, "--version")
    expect(code == 1 and "library/cases/a-new-case.json" in out, "an added case is named", out)
    copy = kit_copy(root, "kit-tests-carry")
    shutil.rmtree(str(copy / "library"))
    code, out = kit_run(copy, "--version")
    expect(code == 1 and "Test files changed" in out, "a kit without its library says so on --version", out[:300])
    mra = fresh(root, "kit-tests-mra")
    code, out = kit_run(copy, "check", mra, "--today", NOW)
    expect(out == EXPECTED_MRA, "and a finding's page stays the same", diff_hint(out, EXPECTED_MRA))
    copy = kit_copy(root, "kit-tests-bad-case")
    finding.write_text(copy / "library" / "cases" / "figure-transposed.json", "not json\n")
    finding.write_text(copy / "library" / "cases" / "no-cite.json", "{}\n")
    code, out = kit_run(copy, "eval", "--library")
    expect(code == 1 and "figure-transposed: this case cannot be run" in out and "no-cite: this case cannot be run" in out and "Traceback" not in out,
           "a library case that cannot be run says so", out)


def test_kit_note(root):
    """Every page says when the kit differs from its release, and the record keeps it."""
    copy = kit_copy(root, "kit-note")
    append_to(copy / "finding" / "finding.py", "# a site change")
    version = json.loads((copy / "RELEASE.json").read_text(encoding="utf-8"))["version"]
    note = "Kit files changed since release {}: finding/finding.py.".format(version)
    iaf = ia(root, "kit-note-ia")
    for label, args in (("check", ("check", iaf, "--today", NOW)), ("eval", ("eval", iaf)), ("size", ("size", iaf)),
                        ("covers", ("covers", iaf)), ("eval --library", ("eval", "--library"))):
        code, out = kit_run(copy, *args)
        expect(note in out, "the {} page names the changed file".format(label), out[:400])

    signed = ia(root, "kit-note-signed")
    old_kit = finding.KIT
    finding.KIT = copy
    try:
        code, out = sign_folder(signed)
    finally:
        finding.KIT = old_kit
    expect(code == 0 and "Kit release: {}, changed: finding/finding.py\n".format(version)
           in (signed / "closure" / "record.md").read_text(encoding="utf-8"), "the record keeps the changed file beside the release", out[-300:])


def test_malformed(root):
    """A state file, a RELEASE.json or a folder shape a check never writes gives a plain refusal."""
    words = refusal("Refused: {} holds a value no check writes. Restore it, or delete it to start the record again; "
                    "the next check then counts as the first, and the first-check date, the record of signed files and "
                    "the signature are gone.".format(finding.STATE_NAME))

    def state_with(name, change, measures=True):
        folder = ia(root, name)
        doc = state_of(folder)
        change(doc)
        (folder / finding.STATE_NAME).write_text(json.dumps(doc), encoding="utf-8")
        if measures:
            finding.write_text(folder / "closure" / "measures.md", "Hours | 2026-01 | 3\n")
        return folder

    def signature(doc, **fields):
        doc["signature"] = dict({"role": "Head of Complaints", "date": NOW, "fingerprint": "a" * 64, "files": {}}, **fields)

    for label, change in (
            ("a first check that is no date", lambda d: d.update(first_check="garbage")),
            ("a null first check", lambda d: d.update(first_check=None)),
            ("a signature date that is no date", lambda d: signature(d, date="garbage")),
            ("a fingerprint that is a number", lambda d: signature(d, fingerprint=5)),
            ("a deny name that is a number", lambda d: d["deny"].update(names=[5])),
            ("an evidence date that is a number",
             lambda d: d["evidence"]["evidence/EV-21-acknowledgement-procedure.md"].update(signed=5))):
        folder = state_with("state-" + re.sub(r"\W", "-", label), change)
        code, out, _ = check(folder)
        expect(code == 1 and out == words, label + " refuses plainly", out[:300])
        code, out, _ = run(["eval", str(folder)])
        expect(code == 1 and out == words, label + " refuses plainly at eval too", out[:300])
    good = state_with("state-good", lambda d: None)
    expect(only_the_signature(*check(good)[:2]), "a good state file with a measures line passes")

    shape = ia(root, "shape-evidence-file")
    shutil.rmtree(str(shape / "evidence"))
    finding.write_text(shape / "evidence", "not a folder\n")
    code, out, _ = run(["covers", str(shape)])
    expect(code == 1 and out.startswith(finding.CONFIDENTIAL) and "Refused: could not read or write evidence:" in out,
           "covers refuses when evidence is a file", out)
    shape = ia(root, "shape-cover-folder")
    (shape / "evidence" / "EV-30-rows.csv").write_bytes(b"a,1\n")
    (shape / "evidence" / "EV-30-rows.csv.md").mkdir()
    code, out, _ = run(["covers", str(shape)])
    expect(code == 1 and "Refused: could not read or write EV-30-rows.csv.md:" in out, "covers refuses when the cover path is a folder", out)
    shape = ia(root, "shape-closure-file")
    shutil.rmtree(str(shape / "closure"))
    finding.write_text(shape / "closure", "not a folder\n")
    code, out, _ = check(shape)
    expect(code == 1 and out.startswith(finding.CONFIDENTIAL) and "Traceback" not in out and str(shape) not in out,
           "check refuses plainly when closure is a file", out)


def ia_with(root, name, change, first_check="2026-04-17"):
    """IA-CMP-02 with its files changed before the first check."""
    files = dict(IA_FILES)
    change(files)
    return build(root, name, files, first_check)


def append_to(path, text):
    finding.write_text(path, path.read_text(encoding="utf-8") + text)


DENIED = "is on this finding's deny list and would be printed. Use roles only."
CLEARS = " If it is an ordinary word or a title, add it to role-words.txt."
IN_A_FILE_NAME = ("is on this finding's deny list, and the page would print it in the name of a file in this folder." + CLEARS
                  + " Otherwise rename the file using roles only.")
RENAME = "is on this finding's deny list, and the page would print it in the name of a file in this folder. Rename the file using roles only."


def test_role_words(root):
    """A term wrongly taken for a name clears with role-words.txt, after a refused run too."""
    def duty(files):
        files["finding.md"] = files["finding.md"].replace(
            "Customers who complain are", "Customers who complain under the Consumer Duty are")
        files["plan.md"] = files["plan.md"].replace(
            "M2 Issue a monthly timeliness report", "M2 Report against the Consumer Duty monthly")

    phrase = ia_with(root, "role-phrase", duty, None)
    code, out, _ = check(phrase)
    expect(code == 1 and out == refusal('Refused: "Consumer Duty" ' + DENIED + CLEARS),
           "a run from the letter on the page is refused, and the refusal names the file that clears it", out)
    first = state_of(phrase)["first_check"]
    baselines = state_of(phrase)["evidence"]
    finding.write_text(phrase / "role-words.txt", "Consumer Duty\n")
    code, out, _ = check(phrase, "2026-11-05")
    state = state_of(phrase)
    expect("Refused" not in out and "M2 Report against the Consumer Duty monthly" in out,
           "a phrase line in role-words.txt clears a term after a refused run", out[:300])
    expect("Consumer Duty" not in state["deny"]["names"] and state["first_check"] == first
           and state["evidence"] == baselines, "clearing keeps the first-check date and the evidence record", json.dumps(state["deny"]))
    first_run = ia_with(root, "role-phrase-first", duty, None)
    finding.write_text(first_run / "role-words.txt", "Consumer Duty\n")
    expect("Refused" not in check(first_run)[1], "a phrase line works before the first check too")
    word = ia_with(root, "role-word-after", duty, None)
    check(word)
    finding.write_text(word / "role-words.txt", "Consumer\n")
    expect("Refused" not in check(word)[1], "one word of the run clears it after a refused run")
    listed = ia_with(root, "role-listed", duty, None)
    finding.write_text(listed / "role-words.txt", "Consumer Duty\n")
    finding.write_text(listed / "denylist.txt", "Consumer Duty\n")
    code, out, _ = check(listed)
    expect(code == 1 and out == refusal('Refused: "Consumer Duty" ' + DENIED),
           "denylist.txt wins over role-words.txt, and that refusal does not offer the file", out)

    def capital(files):
        files["finding.md"] = files["finding.md"].replace("Institution: Wrenfield Example Bank", "Institution: Quillmere Bank")
        files["plan.md"] = files["plan.md"].replace("| Complaints QA lead |", "| Chief Quillmere Officer |")

    bank = ia_with(root, "role-capital", capital, None)
    code, out, _ = check(bank)
    expect(code == 1 and out == refusal('Refused: "Quillmere" ' + DENIED + CLEARS), "a word of the institution's name is refused, "
           "and the refusal offers role-words.txt", out)
    edit(bank / "plan.md", "| Chief Quillmere Officer |", "| Quillmere Bank QA lead |")
    finding.write_text(bank / "role-words.txt", "Quillmere\nQuillmere Bank\n")
    code, out, _ = check(bank)
    expect(code == 1 and out == refusal('Refused: "Quillmere Bank" ' + DENIED), "the institution's full name stays denied, and "
           "its refusal never offers role-words.txt", out)

    def community(files):  # an institution named with ordinary words, and a milestone that uses one of them
        files["finding.md"] = files["finding.md"].replace("Institution: Wrenfield Example Bank",
                                                          "Institution: First Fenmoor Trust Bank")
        files["plan.md"] = files["plan.md"].replace("| M2 Reissue intake procedure |",
                                                    "| M2 Reissue intake procedure for First line staff |")

    files = dict(MRA_FILES)
    community(files)
    trust = fresh(root, "role-bank-word", files, None)
    for words, refused in (("", True), ("First Fenmoor Trust Bank\n", True), ("First\n", False)):
        finding.write_text(trust / "role-words.txt", words)
        code, out, _ = check(trust)
        expect((out == refusal('Refused: "First" ' + DENIED + CLEARS)) == refused and (refused or (
            "M2 Reissue intake procedure for First line staff." in out and "; role-words.txt cleared 1 word of the institution's "
            "name.\n" in out and "First" not in state_of(trust)["deny"]["names"])),
            "role-words.txt clears a word of the institution's name, never its full name, and the page counts it: " + repr(words),
            out[-700:])


def test_deny_on_every_page(root):
    """check, eval and covers print nothing denylist.txt bars, in any letter case."""
    def quoted(files):
        files["evidence/EV-50-note.md"] = (SYN + '\nWhat: EV-50 Note\nFor: EV-50\nSigned by: Head of Complaints, 2026-07-01\n'
                                           'Status: FINAL\n\n## Page 1\nThe note says "approved by Priya Raman on the day" in full.\n\n'
                                           '## Page 2\nThe note says "approved by Priya Raman on the day" in full.\n')
        files["closure/memo.md"] += '\nThe note says "approved by Priya Raman on the day" [EV-50 p1].\n'

    folder = ia_with(root, "deny-eval", quoted)
    code, out, _ = run(["eval", str(folder)])
    expect("still ties" in out and "Priya Raman" in out, "eval names a miss when nothing bars it", out[-300:])
    finding.write_text(folder / "denylist.txt", "Priya Raman\n")
    code, out, _ = run(["eval", str(folder)])
    expect(code == 1 and out == refusal('Refused: "Priya Raman" ' + DENIED), "eval refuses a miss that holds a barred name", out[-300:])
    held = ia_with(root, "deny-eval-state", quoted)
    (held / "denylist.txt").write_text("Priya Raman\n", encoding="utf-8")
    check(held)
    (held / "denylist.txt").unlink()
    code, out, _ = run(["eval", str(held)])
    expect(code == 1 and "still ties" not in out, "eval reads the names a check saved", out[-300:])

    cover = ia(root, "deny-covers")
    (cover / "evidence" / "EV-60-Drevanholt-extract.csv").write_bytes(b"a,b\n1,2\n")
    finding.write_text(cover / "denylist.txt", "Drevanholt\n")
    code, out, _ = run(["covers", str(cover)])
    expect(code == 1 and out == refusal('Refused: "Drevanholt" ' + RENAME), "covers refuses a barred word in a file name before any check, "
           "and the refusal over a line of denylist.txt says only to rename the file", out)
    expect(not (cover / "evidence" / "EV-60-Drevanholt-extract.csv.md").exists(), "a refused covers run writes no cover")
    (cover / "denylist.txt").unlink()
    up = build(root, "deny-up/case", IA_FILES, "2026-04-17")
    (up / "evidence" / "EV-60-Drevanholt-extract.csv").write_bytes(b"a,b\n1,2\n")
    finding.write_text(up.parent / "denylist.txt", "Drevanholt\n")
    code, out, _ = run(["covers", str(up)])
    expect(code == 1 and "Drevanholt-extract" not in out, "covers reads a denylist.txt one folder up", out)

    upper = ia(root, "deny-case")
    finding.write_text(upper / "denylist.txt", "Drevanholt\n")
    append_to(upper / "closure" / "memo.md", '\nThe note says "DREVANHOLT signed this memo" today.\n')
    code, out, _ = check(upper)
    expect(code == 1 and out == refusal('Refused: "Drevanholt" ' + DENIED), "a listed term stops the page in another letter case", out[-300:])
    accents = ia(root, "deny-accent")
    finding.write_text(accents / "denylist.txt", "Société Quillvane\n")
    append_to(accents / "closure" / "memo.md", '\nThe note says "Societe Quillvane signed this memo" today.\n')
    code, out, _ = check(accents)
    expect(code == 1 and "signed this memo" not in out, "a listed term stops the page with its accents off", out[-300:])
    name = ia(root, "deny-exact")
    append_to(name / "closure" / "memo.md", '\nThe note says "for example the letter" today.\n')
    code, out, _ = check(name)
    expect('"for example the letter" has no cite.' in out and "Refused" not in out,
           "a word of the institution's name matches exactly, so an ordinary word still prints", out[-300:])


def test_names_harvested(root):
    """Real names do not print: the harvest's old gaps, the derived names in the state, and a silent removal."""
    names = finding.harvest_names({"Institution": "QX Bank"}, {
        "Concern": "Priya Natarajan led the review. It passed to June Park of the bank. In March the team met. "
                   "By June it had stopped. The Consumer Duty applies, and March April is a run of months."})
    expect(all(n in names for n in ("QX Bank", "QX", "Priya Natarajan", "June Park", "Consumer Duty")),
           "the harvest keeps short capitals, a name opening a sentence and a name holding a month", str(names))
    expect(not any(n in names for n in ("In March", "By June", "The Consumer Duty", "March April", "Bank")),
           "the harvest drops a sentence opener and a run of months", str(names))
    expect(finding.harvest_names({"Institution": "R&K Bank"}, {})[:2] == ["R&K Bank", "R&K"]
           and finding.harvest_names({"Institution": "QVX Fenwold"}, {}) == ["QVX Fenwold", "QVX", "Fenwold"],
           "a word with an ampersand or all capitals counts alone", str(finding.harvest_names({"Institution": "R&K Bank"}, {})))

    def person(files):
        files["finding.md"] = files["finding.md"].replace(
            "Customers who complain are", "Customers who complain to Priya Natarajan or the Senior Management Team are")
        files["plan.md"] = files["plan.md"].replace("Issue a monthly", "Have the team issue a monthly")

    folder = ia_with(root, "names-state", person)
    state = state_of(folder)
    expect(state["deny"]["names"] == ["Wrenfield Example Bank", "Wrenfield", "Example", "Priya Natarajan", "Senior Management Team"],
           "the state keeps the institution's name, its words and the runs from the letter", json.dumps(state["deny"]))

    removed = ia_with(root, "names-removed", person, None)
    finding.write_text(removed / "role-words.txt", "Natarajan\n")
    code, out, _ = check(removed)
    expect("Deny list: 4 names; role-words.txt left out 1.\n" in out and "Natarajan" not in out,
           "the page counts a run role-words.txt left out and prints no name", out[-300:])
    again = check(removed)[1]
    expect(again == out, "the count line is the same on every run")
    code, out, _ = run(["check", str(removed), "--names"])
    expect(code == 0 and out.startswith(finding.CONFIDENTIAL)
           and "Deny list for IA-CMP-02: 4 names.\n" in out and "  Wrenfield Example Bank\n" in out
           and "Left out by role-words.txt:\n  Priya Natarajan\n" in out,
           "check --names prints the names for the person who asks", out)
    code, out, err = run(["check", str(removed), "--names", "--repaste"])
    expect(code == 2 and finding.USAGE in err, "--names and --repaste together are a usage error")


def test_list_one_folder_up(root):
    """A denylist.txt one folder up, for the whole engagement, counts on every finding's page beneath it."""
    eng = root / "up-eng"
    case = build(root, "up-eng/m", IA_FILES, "2026-04-17")
    finding.write_text(eng / "denylist.txt", "Project Falcon\n")
    code, out, _ = check(case)
    expect("Deny list: 4 names.\n" in out, "a list one folder up counts on the page", out[-300:])
    append_to(case / "closure" / "memo.md", '\nThe note says "Project Falcon signed this memo" today.\n')
    code, out, _ = check(case)
    expect(code == 1 and out == refusal('Refused: "Project Falcon" ' + DENIED), "a term listed one folder up stops the page", out[-300:])


def test_closed_word(root):
    """A use of closed that claims the finding is closed is a row only rewording clears. Any other use is a row a person
    rules on."""
    for rel, text in (("closure/memo.md", "Accounts closed in error are reopened."),
                      ("plan.md", "Closed-loop testing runs monthly."),
                      ("plan.md", "We closed the gap."),
                      ("plan.md", "The finding is not closed."),
                      ("closure/memo.md", "Complaints closed late were reopened."),
                      ("plan.md", "Reporting runs until the finding is closed."),
                      ("closure/memo.md", "Closure achieved, in the words of the note."),
                      ("closure/memo.md", "Finding accounts closed in error took days."),
                      ("plan.md", "Closed accounts matter here."),
                      ("plan.md", "Accounts closed under this remediation stay closed.")):
        folder = fresh(root, "closed-" + re.sub(r"\W", "-", text)[:24])
        append_to(folder / rel, "\n" + text + "\n")
        line = len((folder / rel).read_text(encoding="utf-8").splitlines())
        code, out, _ = check(folder)
        word = "closure achieved" if text.startswith("Closure") else "closed"
        expect(code == 1 and "Refused" not in out and "Milestones\n" in out
               and "  Line {}: {} in {} does not read as a claim that the finding is closed, so the finding owner rules on it. To rule, name: ".format(line, word, rel) in out,
               text + " is a row and the page prints", out[-600:])
        expect("the list (4 rows)" in out, "a row on the closed word counts on the list: " + text, out[-300:])
        expect(line_of(out, "Memo check:").startswith("Memo check: 13 claims, 7 tie, 4 on the list"), "a closed row leaves the tie count alone", line_of(out, "Memo check:"))
    for rel, text in (("plan.md", "The finding is closed."),
                      ("plan.md", "The finding is Closed."),
                      ("plan.md", "The remediation is now closed."),
                      ("closure/memo.md", "This matter has been reviewed and closed."),
                      ("closure/memo.md", "We closed the finding."),
                      ("closure/memo.md", "Closure achieved for this finding."),
                      ("closure/memo.md", "The remediation closure is complete."),
                      ("plan.md", "MRA-CMP-07 is closed."),
                      ("plan.md", "The finding is\nclosed.")):
        folder = fresh(root, "closes-" + re.sub(r"\W", "-", text)[:24])
        append_to(folder / rel, "\n" + text + "\n")
        line = len((folder / rel).read_text(encoding="utf-8").splitlines())
        code, out, _ = check(folder)
        expect(code == 1 and "Refused" not in out and re.search(r"\n  Line {}: [a-z ]+ in {} claims the finding is closed, and only the "
               "Supervisor closes".format(line, re.escape(rel)), out) is not None and "the list (4 rows)" in out,
               text + " is a row no ruling clears", out[-600:])
    comment = fresh(root, "closed-comment")
    append_to(comment / "closure" / "memo.md", "\n<!-- The finding is closed. -->\n")
    expect(check(comment)[1] == EXPECTED_MRA, "the word in a comment is neither a refusal nor a row", check(comment)[1][-300:])

    ruled = ia(root, "closed-ruled")
    edit(ruled / "closure" / "record.md", "Internal audit reference: IAV-2026-031", "Internal audit reference:")
    append_to(ruled / "plan.md", "\nAccounts closed in error are reopened.\n")
    line = len((ruled / "plan.md").read_text(encoding="utf-8").splitlines())
    fp = finding.fingerprint(ruled)
    code, out, _ = run(["sign", str(ruled), "--today", NOW], stdin=answers("Head of Complaints", fp[:8]))
    expect(code == 1 and out == refusal("Refused: 1 row is on the list; rule on it first."), "a closed row stops the signature", out)
    add_ruling(ruled, "closed in plan.md", "cleared | Head of Complaints | 2026-11-04 | These are customer accounts.")
    code, out, _ = check(ruled)
    expect("Cleared: line {}, closed in plan.md, by the Head of Complaints on 2026-11-04: These are customer accounts.".format(line) in out
           and "does not read as a claim" not in out, "the owner's ruling clears a closed row, and the page prints it", out[-500:])
    recorded = ia(root, "closed-recorded")
    append_to(recorded / "plan.md", "\nAccounts closed in error are reopened.\n")
    expect("closed in plan.md" not in check(recorded)[1], "the closer's entry in the record lets the word pass with no row")
    plain = fresh(root, "closed-eval")
    append_to(plain / "closure" / "memo.md", "\nAccounts closed in error are reopened.\n")
    expect("13 claims on the memo check, 5 rows before rulings" in run(["size", str(plain)])[1]
           and "4 on the list, 1 cleared" in check(plain)[1], "size counts a closed row before rulings, as the check lists it")
    no_memo = fresh(root, "closed-no-memo")
    (no_memo / "closure" / "memo.md").unlink()
    append_to(no_memo / "plan.md", "\nAccounts closed in error are reopened.\n")
    code, out, _ = check(no_memo)
    expect("Closure memo: missing." in out and "closed in plan.md does not read as a claim" in out, "a closed row prints with no memo too", out[-500:])


def test_state_lost(root):
    """Losing the state file is visible on the page and in the log, and its honest causes have another way out."""
    relabel = ia(root, "lost-relabel")
    edit(relabel / "finding.md", "are not told promptly", "are not told quickly")
    run(["check", str(relabel), "--repaste", "--today", NOW])
    lines = (relabel / "closure" / finding.LOG_NAME).read_text(encoding="utf-8").splitlines()
    first_entry = json.loads(lines[0])
    expect(first_entry["kind"] == "internal audit finding" and first_entry["issuer"] == "the Head of Internal Audit"
           and first_entry["first_check"] == "2026-04-17", "every log line names the kind, the issuer and the first check", lines[0])
    (relabel / finding.STATE_NAME).unlink()
    check(relabel)
    lines = (relabel / "closure" / finding.LOG_NAME).read_text(encoding="utf-8").splitlines()
    entry = json.loads(lines[-1])
    expect(entry["outcome"] == "record restarted" and entry["first_check"] == NOW, "a check with the state file gone says so in the log", lines[-1])
    check(relabel)
    expect(len((relabel / "closure" / finding.LOG_NAME).read_text(encoding="utf-8").splitlines()) == len(lines), "only the first check after that adds the line")

    pair = fresh(root, "lost-pair")
    (pair / finding.STATE_NAME).unlink()
    edit(pair / "finding.md", "Kind of matter: supervisory finding", "Kind of matter: internal audit finding")
    code, out, _ = check(pair)
    expect(code == 1 and out == refusal('Refused: finding.md gives the Issuer as "the Supervisor" and the Kind of matter as "internal audit '
                                        'finding". What the Supervisor wrote is a supervisory finding. Correct one of the two lines.'),
           "a first check refuses an internal audit kind from the Supervisor", out)
    expect(not (pair / finding.STATE_NAME).exists(), "that refusal writes no state file")
    label = fresh(root, "lost-label")
    edit(label / "finding.md", "Kind of matter: supervisory finding", "Kind of matter: internal audit finding")
    for args in (["check", str(label), "--today", NOW], ["check", str(label), "--repaste", "--today", NOW]):
        code, out, _ = run(args)
        expect(code == 1 and "the finding owner and the institution's lawyers decide" in out and "delete" not in out,
               "a relabel names who decides and prints no way round: " + " ".join(args[0:1] + args[2:3]), out)

    signed = ia(root, "lost-signed")
    fp = finding.fingerprint(signed)
    run(["sign", str(signed), "--today", NOW], stdin=answers("Head of Complaints", fp[:8]))
    (signed / finding.STATE_NAME).unlink()
    code, out, _ = check(signed)
    held = "closure/record.md holds a signature by the Head of Complaints on {}, fingerprint {}, and .finding-state.json holds none. The folder now reads {}.\n".format(signed_on(), fp[:8], fp[:8])
    early = " It is dated before the first check on " + NOW + ", so the check cannot see when it was made.\n"
    expect(code == 0 and "Signature: none yet.\n" + held in out and "Ready to sign" not in out
           and "Internal audit: reference IAV-2026-031 dated 2026-07-15, recorded by the Head of Internal Audit." + early in out
           and "Board approval: BM-2026-07 dated 2026-07-08, recorded by the Company Secretary." + early in out
           and out.endswith("Nothing needs a person.\n"),
           "a signature only the record holds is printed, and entries dated before the restarted first check count and "
           "say so", out[-900:])
    expect(check(signed)[1] == out, "that page is the same on the next run")
    append_to(signed / "closure" / "memo.md", "\nThe Head of Complaints holds the sample.\n")
    code, out, _ = check(signed)
    expect(code == 1 and "Ready to sign" not in out and "  Head of Complaints: a fresh signature.\n" in out and "and .finding-state.json holds none." in out,
           "an edited folder with the state gone asks for a fresh signature", out[-500:])
    fp2 = finding.fingerprint(signed)
    code, out, _ = run(["sign", str(signed), "--today", NOW], stdin=answers("Head of Complaints", fp2[:8]))
    code, out, _ = check(signed)
    expect(code == 0 and "holds none" not in out and "Signed by the Head of Complaints" in out, "signing again clears it", out[-300:])

    changed = fresh(root, "lost-baseline")
    edit(changed / "evidence" / "EV-03-complaint-taxonomy.md", "three subcategories", "four subcategories")
    (changed / finding.STATE_NAME).unlink()
    code, out, _ = check(changed)
    expect("Signed before the first check on 2026-11-04, so a change before then cannot be seen: E-PLAN-1, EV-03, EV-04, EV-07 and EV-08.\n" in out,
           "evidence signed before the first check is named", line_of(out, "Signed before"))
    expect(check(changed)[1] == out, "that line comes from stored data, so the next run prints the same page")
    expect("Signed before the first check" not in check(fresh(root, "lost-baseline-none"))[1], "a folder first checked in time has no such line")

    paste = ia(root, "lost-paste")
    fp = finding.fingerprint(paste)
    run(["sign", str(paste), "--today", NOW], stdin=answers("Head of Complaints", fp[:8]))
    before = state_of(paste)
    edit(paste / "finding.md", "Customers who complain are", "Customers who complained are")
    code, out, _ = check(paste)
    expect(code == 1 and "run check --repaste if the first paste was wrong" in out and "delete" not in out, "a changed letter points to the correction", out)
    code, out, _ = run(["check", str(paste), "--repaste", "--today", NOW])
    after = state_of(paste)
    expect("The letter's text was corrected on 2026-11-04, after the first check on 2026-04-17. The log holds the change.\n" in out
           and "Changed since signing: finding.md." in out, "--repaste says so on the page and asks for a fresh signature", out[:400])
    expect(after["evidence"] == before["evidence"] and after["signature"]["fingerprint"] == fp and after["first_check"] == before["first_check"]
           and after["deny"] == before["deny"] and after["parts"] != before["parts"], "--repaste keeps the evidence record, the deny list and the signature")
    entry = json.loads((paste / "closure" / finding.LOG_NAME).read_text(encoding="utf-8").splitlines()[-1])
    expect(entry["mode"] == "repaste" and entry["changed"] == ["Concern"], "--repaste leaves a line in the log", str(entry))
    expect(check(paste)[1] == out, "the page keeps saying so on every run")
    code, out, _ = run(["check", str(ia(root, "lost-no-paste")), "--repaste", "--today", NOW])
    expect("was corrected" not in out, "--repaste with nothing to correct changes nothing", out[:300])
    empty = fresh(root, "lost-paste-none")
    (empty / finding.STATE_NAME).unlink()
    code, out, _ = run(["check", str(empty), "--repaste", "--today", NOW])
    expect(code == 1 and "no check has recorded this letter yet" in out, "--repaste needs a first check", out)


def test_sign_date(root):
    """A real finding is signed on the machine's date, and the pages say what a signature is."""
    real = ia(root, "date-real")
    path = real / "finding.md"
    finding.write_text(path, path.read_text(encoding="utf-8").split("\n", 1)[1])
    fp = finding.fingerprint(real)
    code, out, _ = run(["sign", str(real), "--today", "2026-07-20"], stdin=answers("Head of Complaints", fp[:8]))
    expect(code == 1 and out == refusal("Refused: a real finding is signed on this machine's date; drop --today."), "a real finding refuses --today", out)
    expect(state_of(real).get("signature") is None, "that refusal signs nothing")
    today = datetime.date.today().isoformat()
    code, out, _ = run(["sign", str(real)], stdin=answers("Head of Complaints", fp[:8]))
    expect(code == 0 and "Signed by the Head of Complaints on {},".format(today) in out, "a real finding signs on the machine's date", out[-300:])
    sig = state_of(real)["signature"]
    expect(re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+00:00$", str(sig.get("signed_at"))) is not None, "the state keeps the machine's time", json.dumps(sig)[:200])
    expect("signed_at" not in check(real, today)[1], "the machine's time stays off the page")
    synthetic = ia(root, "date-synthetic")
    fp = finding.fingerprint(synthetic)
    code, out, _ = run(["sign", str(synthetic), "--today", "2026-07-20"], stdin=answers("Head of Complaints", fp[:8]))
    expect(code == 0 and "on 2026-07-20," in out, "a SYNTHETIC folder keeps --today, so the walk matches", out[-300:])


def test_first_paste(root):
    """The messages take a person from a real letter to a first check."""
    work = root / "paste"
    work.mkdir()
    run(["new", "P-1"], cwd=work)
    made = work / "P-1"
    text = (made / "finding.md").read_text(encoding="utf-8")
    expect("paste each part of the letter under its heading. The first full check fixes this text" in text, "the template says what to fill")
    code, out, _ = check(made)
    expect(out == refusal("Not ready: finding.md has no Institution yet. Fill that line, then check again."), "an empty header line says fill it", out)
    finding.write_text(made / "finding.md", "A plain letter from the Supervisor.\n")
    code, out, _ = check(made)
    expect(code == 1 and "finding.md has no Identifier line, so its template lines were replaced." in out, "a letter pasted over the template says so", out)
    finding.write_text(made / "finding.md", text.replace("Institution:", "Institution: Tarnwick Example Bank").replace("Letter date:", "Letter date: 2026-10-01")
                       .replace("Owner role:", "Owner role: Head of Complaints"))
    code, out, _ = check(made)
    expect(out == refusal("Not ready: finding.md has no text under ## Concern yet. Paste that part of the letter under its heading; if the "
                          "letter has no such heading, put the matching passage there."), "a missing part says where it goes", out)
    filled = (made / "finding.md").read_text(encoding="utf-8")
    for name in finding.PARTS:
        filled = filled.replace("## {}\n".format(name), "## {}\nThe letter's words on this part.\n".format(name))
    finding.write_text(made / "finding.md", filled)
    append_to(made / "plan.md", "| M1 Reissue the procedure | Head of Complaints | 2027-01-31 | Reissued | EV-01 | Tested |\n")
    code, out, _ = check(made)
    expect("Milestones\nM1 Reissue the procedure" in out and check(made)[1] == out, "the filled template reaches a full screen, the same each run", out[:300])


def diff_hint(got, want):
    g, w = got.splitlines(), want.splitlines()
    for i in range(max(len(g), len(w))):
        a = g[i] if i < len(g) else "<none>"
        b = w[i] if i < len(w) else "<none>"
        if a != b:
            return "line {}: got {!r}, want {!r}".format(i + 1, a, b)
    return "trailing difference"


def test_measures_lines(root):
    """Part hours count exactly, and a line the check cannot read is named for a person."""
    part = ia(root, "measures-part")
    finding.write_text(part / "closure" / "measures.md", SYN + "\nHours | 2026-10 | 38\nHours | 2026-11 | 12.5\n"
                       "| Hours | 2026-12 | 2 |\nsent back | 2026-11-02 | Line 8 | wrong figure | missed by the check\n")
    code, out, _ = check(part)
    expect("Measures: 52.5 hours booked, 201 days since the first check, 1 sent back by internal audit, 1 missed by the "
           "check.\n" in out, "part hours, a table row and a lower-case label all count", line_of(out, "Measures:"))
    expect(only_the_signature(code, out), "measures that read add nothing for a person", out[-300:])

    bad = ia(root, "measures-unread")
    finding.write_text(bad / "closure" / "measures.md", SYN + "\nHours | 2026-10 | 38\nHours | 2026-11 | 1,240\n"
                       "Hours | 2026-11 | 7 hours\nHours: 5\nHours | 2026-12 | \u00b2\nsent back\n")
    code, out, _ = check(bad)
    expect(code == 1 and "Measures: 38 hours booked," in out
           and "Measures: closure/measures.md lines 3, 4, 5, 6 and 7 cannot be read and are not counted. Write each line "
               "in a form its comment shows.\n" in out
           and "  The engagement team: closure/measures.md lines 3, 4, 5, 6 and 7.\n" in out,
           "a measures line that cannot be read is named, never dropped", out[-900:])
    expect("37.5 count" in finding.TEMPLATE_MEASURES and "half up" not in finding.TEMPLATE_MEASURES,
           "the measures template says part hours count, and nothing rounds them")


def test_size_fit(root):
    """Both sides of size carry a person's work, the assumptions sit in a file outside the fingerprint, and a bad line
    in that file is refused."""
    eng = root / "size-fit-engagement"
    eng.mkdir()
    one = eng / "MRA-CMP-07"
    shutil.copytree(str(fresh(root, "size-fit")), str(one))
    before = check(one)[1]
    fp = finding.fingerprint(one)
    finding.write_text(one / finding.SIZE_FILE, "# timed in week two\nMinutes a claim by hand: 6\n")
    finding.write_text(eng / finding.SIZE_FILE, "minutes a claim by hand = 20\nminutes to read a claim: 5\n")
    code, out, _ = run(["size", str(one)])
    expect(code == 0 and "By hand, assumed: 26.9 hours. Checking claims 3.9," in out
           and "With the kit, assumed: 12.6 hours. Reading each claim against its page 1.1," in out
           and "These hours are assumptions, 2 of them from size-assumptions.txt: 6 minutes a claim by hand over 3 memo "
               "versions," in out and "5 minutes to read a claim once against its page" in out,
           "size reads its assumptions beside the finding and one folder up, the finding's own line first", out)
    expect(finding.fingerprint(one) == fp and check(one)[1] == before,
           "an assumptions file changes no fingerprint and no page of the check")
    finding.write_text(one / finding.SIZE_FILE, "bogus = 1\n")
    code, out, _ = run(["size", str(one)])
    expect(code == 1 and out.startswith(refusal("Refused: line 1 of the size-assumptions.txt beside the finding cannot be "
                                                "read.")[:-1]), "a line size cannot read is refused", out)
    (one / finding.SIZE_FILE).unlink()
    code, out, _ = run(["size", str(eng)])
    expect(code == 0 and "2 of them from size-assumptions.txt: 20 minutes a claim by hand" in out,
           "a folder of findings reads the engagement's file in that folder", out[-700:])


def test_kinds_and_plan_columns(root):
    """A self-identified issue is a kind of its own, closed by the institution's issue-management owner, and a plan column
    the institution adds is read past, wherever it sits."""
    def self_identified(files):
        files["finding.md"] = files["finding.md"].replace("Issuer: the Head of Internal Audit", "Issuer: the Head of Compliance").replace(
            "Kind of matter: internal audit finding", "Kind of matter: self-identified issue")
    own = ia_with(root, "kind-self", self_identified)
    code, out, _ = check(own)
    expect("Finding IA-CMP-02, a self-identified issue from the Head of Compliance dated 2026-04-10." in out
           and "\nSupervisor closure: not applicable to a self-identified issue.\nIssue closure: none recorded.\n" in out
           and "  The issue-management owner: its closure reference in closure/record.md.\n" in out,
           "a self-identified issue has its own kind and its own closer", out[-900:])
    for field, value in (("Issue closure reference", "ISS-2026-14"), ("Issue closure date", "2026-08-01"),
                         ("Issue closure recorded by (role)", "Head of Operational Risk")):
        edit(own / "closure" / "record.md", "Board approval reference", "{}: {}\nBoard approval reference".format(field, value))
    code, out, _ = check(own)
    expect("Issue closure: reference ISS-2026-14 dated 2026-08-01, recorded by the Head of Operational Risk.\n" in out
           and "issue-management owner" not in out, "the issue closure, once recorded, reads like the others", out[-900:])
    closed = ia_with(root, "kind-self-closed", self_identified)
    append_to(closed / "closure" / "memo.md", "\nThe finding is closed.\n")
    code, out, _ = check(closed)
    expect(code == 1 and "only the institution's issue-management owner closes a self-identified issue." in out,
           "only the issue-management owner closes a self-identified issue", out)
    def as_supervisor(files):
        self_identified(files)
        files["finding.md"] = files["finding.md"].replace("Issuer: the Head of Compliance", "Issuer: the Supervisor")
    code, out, _ = check(ia_with(root, "kind-self-supervisor", as_supervisor, first_check=None))
    expect(code == 1 and "What the Supervisor wrote is a supervisory finding." in out,
           "a self-identified issue the Supervisor wrote is refused", out)
    def unknown(files):
        files["finding.md"] = files["finding.md"].replace("Kind of matter: internal audit finding", "Kind of matter: an observation")
    code, out, _ = check(ia_with(root, "kind-unknown", unknown, first_check=None))
    expect(out == refusal('Not ready: finding.md gives Kind of matter as "an observation"; use supervisory finding, '
                          'internal audit finding or self-identified issue.'), "the kinds are named on a wrong one", out)

    plain = check(fresh(root, "plan-columns-plain"))[1]
    def added(files):
        lines = files["plan.md"].split("\n")
        for i, line in enumerate(lines):
            if line.startswith("| Milestone"):
                lines[i] = line.replace("| Committed date |", "| Risk rating | Committed date |") + " Notes |"
            elif line.startswith("|---"):
                lines[i] = line + "---|---|"
            elif line.startswith("| M"):
                cells = line.split(" | ")
                lines[i] = " | ".join(cells[:2] + ["High"] + cells[2:]) + " none |"
        files["plan.md"] = "\n".join(lines)
    files = dict(MRA_FILES)
    added(files)
    wide = build(root, "plan-columns-added", files, "2026-02-10")
    code, out, _ = check(wide)
    expect(code == 1 and out.split("Commitment: ")[0] == plain.split("Commitment: ")[0],
           "plan columns the institution adds, in the middle and at the end, change nothing on the page", out[:1200])
    saved = finding.PLAN_COLUMNS
    try:
        finding.PLAN_COLUMNS = saved + ("Risk rating",)
        code, out, _ = check(wide)
        expect(code == 1 and out.split("Commitment: ")[0] == plain.split("Commitment: ")[0],
               "a plan column added to the kit's own list is read by name", out[:600])
    finally:
        finding.PLAN_COLUMNS = saved


def test_library_case_errors(root):
    """A case file a person typed wrong is named and counted wrong, and the other cases still run."""
    copy = kit_copy(root, "kit-library-errors")
    finding.write_text(copy / "library" / "cases" / "zz-slash.json",
                       '{"evidence": [{"id": "EV/1", "pages": ["x"]}], "memo": "x", "expect": {"list": 0}}\n')
    (copy / "library" / "cases" / "zz-folder.json").mkdir()
    count = len(list((copy / "library" / "cases").glob("*.json")))
    code, out = kit_run(copy, "eval", "--library")
    expect(code == 1 and "Library cases: {}, {} as expected".format(count, count - 2) in out
           and "  zz-slash: this case cannot be run: could not read or write" in out
           and "  zz-folder: this case cannot be run: could not read or write zz-folder.json" in out,
           "a case file that cannot be written or read is named and the rest still run", out)


def test_cover_names_checked_by(root):
    """The drafted cover says where a Checked by line goes, since one below the header is not read."""
    folder = ia(root, "cover-checked-by")
    (folder / "evidence" / "EV-30-listing.pdf").write_bytes(simple_pdf(["Listing 120."]))
    run(["covers", str(folder)])
    cover = (folder / "evidence" / "EV-30-listing.pdf.md").read_text(encoding="utf-8")
    expect("adds Checked by: role, YYYY-MM-DD with the lines at the top, above the blank line" in cover,
           "the drafted cover says where Checked by goes", cover)


def test_recheck_readers(root):
    """Small files stay small in memory, and what a person sees of an email is what the check reads."""
    docs, read = reader_in(root, "recheck-readers")
    words = " ".join("=?utf-8?q?a?=" for _ in range(1001))
    got = read("encoded.eml", "From: a@b.c\nSubject: {}\nContent-Type: text/plain\n\nThe total was 1,284.\n".format(words).encode())
    expect(got["problem"] == "the email's header lines are too long to read",
           "an email whose headers hold more encoded words than the parser can hold is refused before parsing", str(got)[:200])
    saved = getattr(docs, "MAX_SHEET_TAGS", None)
    try:
        docs.MAX_SHEET_TAGS = 40
        cells = "<sheetData><row>" + "<c><v>1</v></c>" * 20 + "</row></sheetData>"
        got = read("tags.xlsx", book_bytes(root, [("Sample", None, cells)]))
        expect(got["problem"] == "the workbook is too large to read",
               "a workbook part with more tags than its tree can hold is refused before it is parsed", str(got)[:200])
    finally:
        docs.MAX_SHEET_TAGS = saved
    saved = docs.MAX_FIGURES
    try:
        docs.MAX_FIGURES = 10
        code, out, _ = check(ia(root, "recheck-folder-figures"))
        expect(code == 1 and "Not ready: the files in evidence/ hold more text between them than the memo check can hold"
               in out, "the reader's caps hold for all of a finding's files together", out[-300:])
    finally:
        docs.MAX_FIGURES = saved
    head = ('<html><head><style>.preview{display:none}</style></head><body><p>The sample held 1,284 items.</p>'
            '<p class="preview">The sample held 9,999 items.</p></body></html>')
    expect(docs.visible_html(head) == "The sample held 1,284 items.", "a class hidden by a style sheet in head is hidden",
           docs.visible_html(head))
    shown = ('<p>Intro 1,111.</p><p style="font-size:0.9em">The sample held 1,284 items.</p>'
             '<p style="opacity: 0.85">It held 5 boxes.</p><p style="font-size: 0px">Gone 7.</p><p style="opacity:0">Gone 8.</p>'
             '<div style="font-size:0.875rem">Held 9.</div>')
    expect(docs.visible_html(shown) == "Intro 1,111.\nThe sample held 1,284 items.\nIt held 5 boxes.\nHeld 9.",
           "a small font or a faint paragraph shows, and only a size or opacity of nothing hides", docs.visible_html(shown))
    folder = with_document(root, "recheck-small-font", "EV-30-mail.eml", email_bytes(("text/html", '<p style="font-size:0.9em">The sample held 1,284 items.</p>')),
                           "The listing held 1,284 items [EV-30 p1].")
    expect("14 claims, 14 tie" in check(folder)[1], "an email in a small font ties", memo_block(check(folder)[1]))


def test_recheck_names_on_pages(root):
    """A file name, an institution's name in capitals and a role word each get the right refusal, or none."""
    bad = with_document(root, "recheck-word-name", "EV-30-Wrenfield-listing.docx", b"PK\x03\x04garbage not a zip at all" + b"\0" * 200,
                        "The listing held 9,999 items [EV-30 p1].")
    code, out, _ = check(bad)
    expect(code == 1 and "Refused" not in out and "the check cannot read that page: the Word file could not be read: not a readable "
           ".docx (File is not a zip file)" in out, "an unreadable Word file named with a word of the institution's name gets its row", out[-500:])
    code, out, _ = run(["covers", str(bad)])
    expect(code == 1 and out == refusal('Refused: "Wrenfield" ' + IN_A_FILE_NAME), "covers says to rename a file whose name holds the institution's name", out)
    full = with_memo(root, "recheck-full-name", 'The memo notes "Wrenfield Example Bank signed this memo" [EV-21 p1].\n')
    expect(check(full)[1] == refusal('Refused: "Wrenfield Example Bank" ' + DENIED),
           "a quotation of the institution's full name is named as the full name, with no role-words hint", check(full)[1])
    caps = with_memo(root, "recheck-capitals", 'The memo notes "WRENFIELD EXAMPLE BANK signed this memo" [EV-21 p1].\n')
    expect(check(caps)[1] == refusal('Refused: "Wrenfield Example Bank" ' + DENIED),
           "the institution's name in capitals is refused on the check page", check(caps)[1])
    listing = ia(root, "recheck-capitals-covers")
    (listing / "evidence" / "EV-30-WRENFIELD-listing.csv").write_bytes(b"a,b\n1,2\n")
    code, out, _ = run(["covers", str(listing)])
    expect(code == 1 and out == refusal('Refused: "Wrenfield" ' + IN_A_FILE_NAME)
           and not (listing / "evidence" / "EV-30-WRENFIELD-listing.csv.md").exists(), "covers refuses the institution's name in capitals in a file name", out)


def test_recheck_typed_and_signed(root):
    """A .txt with its own cover is the document's own text, as .md evidence is, and a typed date stays with the shipped walk."""
    folder = ia(root, "recheck-txt-cover")
    finding.write_text(folder / "evidence" / "EV-30-plain.txt", "Export run 2026-05-30: complaints logged 1,284.\n")
    finding.write_text(folder / "evidence" / "EV-30-plain.txt.md", "What: EV-30 Plain export\nFor: EV-30\n"
                       "Signed by: Head of Complaints, 2026-07-01\nStatus: FINAL\n")
    append_to(folder / "closure" / "memo.md", "\nThe export logged 1,284 complaints [EV-30 p1].\n")
    code, out, _ = check(folder)
    expect("Memo check: 14 claims, 14 tie, 0 on the list." in out and "  13 ties rest on text a person typed: 13 in plain-text evidence, "
           "none on a page typed into a cover.\n" in out and "The engagement team" not in out and "Ready to sign" in out,
           "a tie on a .txt with a cover of its own is a document tie, not text typed into a cover", memo_block(out))
    fp = finding.fingerprint(folder)
    code, out, _ = run(["sign", str(folder), "--today", NOW], stdin=answers("Head of Complaints", fp[:8]))
    expect(code == 0 and "with no Checked by line" not in out, "a tie on a covered .txt needs no Checked by line before sign", out[-300:])
    made = root / "recheck-new"
    made.mkdir()
    run(["new", "N-1"], cwd=made)
    real = ia(root, "recheck-template-line")
    path = real / "finding.md"
    finding.write_text(path, "SYNTHETIC. Delete this line when the folder holds a real finding.\n" + path.read_text(encoding="utf-8").split("\n", 1)[1])
    fp = finding.fingerprint(real)
    code, out, _ = run(["sign", str(real), "--today", "2026-07-20"], stdin=answers("Head of Complaints", fp[:8]))
    expect(code == 1 and out == refusal("Refused: a real finding is signed on this machine's date; drop --today.")
           and (made / "N-1" / "finding.md").read_text(encoding="utf-8").startswith("# Finding N-1\n"),
           "new writes no SYNTHETIC line, and the line an older new wrote does not let sign take a typed date", out)


def test_page_counts(root):
    """A document's cover needs four header lines, and the pages say four."""
    four = root / "four-lines.pdf.md"
    finding.write_text(four, "What: EV-30 Sample listing\nFor: M3 EV-30\nSigned by: Complaints QA lead, 2026-03-20\n"
                             "Status: FINAL\n")
    three = root / "three-lines.pdf.md"
    finding.write_text(three, "What: EV-30 Sample listing\nFor: M3 EV-30\nSigned by: Complaints QA lead, 2026-03-20\n")
    expect(finding.parse_header(four) is not None and finding.parse_header(three) is None, "a document's cover needs four header lines")
    found = pages("README.md", "finding/README.md")
    if found is not None:
        readme, page = found
        expect("four-line cover" in readme and "five-line" not in readme and "holding the four lines" in page,
               "the front page and the finding page both say a cover needs four lines",
               re.search(r"A document needs[^.]*\.", readme).group(0) if "A document needs" in readme else "")


def test_signing_record(root):
    """What a signature rests on holds still: record fields in a real form, the owner, the approved plan dates,
    each signed file by its id, the latest Revised line, rulings against re-signed pages, and one fingerprint."""
    today = datetime.date.today().isoformat()
    readme = pages("finding/README.md")
    if readme is not None:
        expect("is a shipped case's SYNTHETIC line, word for word" in readme and "still opens with the SYNTHETIC line" not in readme,
               "the finding page states the rule sign applies to --today")
        expect("`For: PLAN E-PLAN-1`" in readme and "the Plan approval line gives the reason" in readme,
               "the README says how to record the board's approval of the plan")

    # A typed sign date on a shipped case's folder shows on the page and in the record.
    typed = "2027-03-01" if today != "2027-03-01" else "2027-03-02"
    note = "{}, a date typed with --today on a machine dated {}".format(typed, today)
    folder = ia(root, "sr-typed-date")
    path = folder / "finding.md"
    shipped = path.read_text(encoding="utf-8")
    finding.write_text(path, "SYNTHETIC.\n" + shipped.split("\n", 1)[1])
    code, out, _ = run(["sign", str(folder), "--today", typed], stdin=answers("Head of Complaints", finding.fingerprint(folder)[:8]))
    expect(code == 1 and out == refusal("Refused: a real finding is signed on this machine's date; drop --today."),
           "a SYNTHETIC line other than a shipped case's does not let sign take a typed date", out)
    finding.write_text(path, shipped)
    fp = finding.fingerprint(folder)
    code, out, _ = run(["sign", str(folder), "--today", typed], stdin=answers("Head of Complaints", fp[:8]))
    expect(code == 0 and "Signed by the Head of Complaints on {}, fingerprint {}.".format(note, fp[:8]) in out,
           "sign says when its date was typed", out[-300:])
    expect("\nSigned on: {}\n".format(note) in (folder / "closure" / "record.md").read_text(encoding="utf-8"),
           "record.md says the date was typed", (folder / "closure" / "record.md").read_text(encoding="utf-8")[-300:])
    code, out, _ = check(folder, typed)
    expect(code == 0 and "Signed by the Head of Complaints on {}, fingerprint {}.\n".format(note, fp[:8]) in out
           and "Changed since signing" not in out, "the page says the date was typed", out[-300:])

    # Each closer and board field needs a real form, and a role holding a person's name is refused.
    folder = ia(root, "sr-placeholders")
    record = folder / "closure" / "record.md"
    for old, new in (("Internal audit reference: IAV-2026-031", "Internal audit reference: to follow"),
                     ("Board approval reference: BM-2026-07", "Board approval reference: to be tabled"),
                     ("Board approval date: 2026-07-08", "Board approval date: TBC"),
                     ("Board approval recorded by (role): Company Secretary", "Board approval recorded by (role): n/a")):
        edit(record, old, new)
    code, out, _ = check(folder)
    expect(code == 1 and "Closure memo: present, not tested by internal audit yet.\n"
           "Internal audit: not counted (the reference is a placeholder).\n" in out
           and "Board approval: not counted (the reference, date and role are placeholders).\n" in out
           and "  Internal audit: its reference in closure/record.md (the reference is a placeholder).\n" in out
           and "  The board: its approval of closure (the reference, date and role are placeholders).\n" in out
           and "Ready to sign" not in out, "a placeholder in the record counts for nothing, and the page says so", out[-900:])
    code, out, _ = run(["sign", str(folder), "--today", NOW], stdin=answers())
    expect(code == 1 and out == refusal("Refused: closure/record.md holds no board approval (the reference, date and role are "
                                        "placeholders)."), "sign refuses a board approval of placeholders", out)
    edit(folder / "closure" / "memo.md", "Only internal audit decides whether this finding is resolved.", "This finding is closed.")
    code, out, _ = check(folder)
    expect(code == 1 and "claims the finding is closed, and only internal audit closes an internal audit finding." in out,
           "a placeholder reference does not let closed pass", out)
    folder = ia(root, "sr-record-dates")
    edit(folder / "closure" / "record.md", "Internal audit date: 2026-07-15", "Internal audit date: 2027-01-01")
    edit(folder / "closure" / "record.md", "Board approval reference: BM-2026-07", "Board approval reference: x")
    code, out, _ = check(folder)
    expect("Internal audit: not counted (the date 2027-01-01 is after the check date).\n" in out
           and "Board approval: not counted (the reference is a placeholder).\n" in out,
           "a date after the check and a reference under three characters do not count", out[-900:])
    # A record role is taken as written, and the deny list still stops a listed name from printing.
    titles = ("Head of Regulatory Relations", "Head of Issue Management", "SVP, Internal Audit", "MLRO",
              "Company Secretary (on behalf of the Board)")
    mra = fresh(root, "sr-record-titles")
    edit(mra / "closure" / "record.md", "Supervisor closure notice:", "Supervisor closure notice: SUP-2026-118")
    edit(mra / "closure" / "record.md", "Supervisor closure date:", "Supervisor closure date: 2026-11-04")
    def self_identified(files):
        files["finding.md"] = files["finding.md"].replace("Kind of matter: internal audit finding", "Kind of matter: "
                                                          "self-identified issue").replace("Issuer: the Head of Internal Audit",
                                                                                           "Issuer: the Head of Complaints Risk")
        files["closure/record.md"] += "Issue closure reference: ISS-2026-114\nIssue closure date: 2026-11-04\n"
    issue = ia_with(root, "sr-record-titles-issue", self_identified)
    for title in titles:
        for folder, label, key in ((mra, "Supervisor closure: notice SUP-2026-118", "Supervisor closure recorded by (role)"),
                                   (issue, "Issue closure: reference ISS-2026-114", "Issue closure recorded by (role)")):
            text = (folder / "closure" / "record.md").read_text(encoding="utf-8")
            finding.write_text(folder / "closure" / "record.md", re.sub(r"(?m)^" + re.escape(key) + r":.*$", key + ": " + title, text)
                               if key + ":" in text else text + key + ": " + title + "\n")
            out = check(folder)[1]
            expect("Refused" not in out and "{} dated 2026-11-04, recorded by the {}.\n".format(label, title) in out,
                   "a record role written as an institution title records: " + title, out[-600:])
    folder = ia(root, "sr-record-name")
    finding.write_text(folder / "denylist.txt", "Tom Reyes\n")
    edit(folder / "closure" / "record.md", "Board approval recorded by (role): Company Secretary",
         "Board approval recorded by (role): Tom Reyes")
    code, out, _ = check(folder)
    expect(code == 1 and out == refusal('Refused: "Tom Reyes" ' + DENIED), "a name on the deny list in a record role stops the page",
           out)

    # The owner role freezes at the first check.
    folder = ia(root, "sr-owner-frozen")
    edit(folder / "finding.md", "Owner role: Head of Complaints", "Owner role: Engagement Manager")
    frozen = refusal("Refused: the Owner role in finding.md is not the role first checked on 2026-04-17. The owner rules on the "
                     "list and signs, so the role does not change after the first check; restore it. If the institution has named a new "
                     "owner, internal audit decides whether to start .finding-state.json again, which drops the record of signed "
                     "files and the signature.")
    code, out, _ = check(folder)
    expect(code == 1 and out == frozen, "a relabelled owner is refused", out)
    code, out, _ = run(["sign", str(folder), "--today", NOW], stdin=answers("Engagement Manager"))
    expect(code == 1 and out == frozen, "sign refuses a relabelled owner before it asks", out)
    code, out, _ = run(["check", str(folder), "--repaste", "--today", NOW])
    expect(code == 1 and out == frozen, "--repaste does not move the owner", out)
    edit(folder / "finding.md", "Owner role: Engagement Manager", "Owner role: Head of  Complaints")
    expect("Refused" not in check(folder)[1], "spacing alone is no change of owner")

    # Committed dates freeze when the board approves the plan, and lateness counts from the approved date.
    def early(files):
        files["plan.md"] = files["plan.md"].replace("| Head of Complaints | 2026-05-31 |", "| Head of Complaints | 2026-05-15 |")
    folder = ia_with(root, "sr-plan-frozen", early)
    out = check(folder)[1]
    expect("Flagged commitments: M1 signed 13 days after its commitment." in out, "the approved date flags a late signature",
           line_of(out, "Flagged"))
    edit(folder / "plan.md", "| Head of Complaints | 2026-05-15 |", "| Head of Complaints | 2026-06-15 |")
    code, out, _ = check(folder)
    expect("M1 Send acknowledgement letters within five days. Head of Complaints, committed 2026-05-15, moved to 2026-06-15 in "
           "plan.md after the board approved the plan. Present and signed on 2026-05-28.\n" in out
           and "Flagged commitments: M1 signed 13 days after its commitment.\n" in out
           and "Plan approval: board minutes E-PLAN-1, signed by the Company Secretary on 2026-04-24. Changed in plan.md since: "
           "M1 moved to 2026-06-15.\n" in out
           and "| M1 Send acknowledgement letters within five days | Head of Complaints | 2026-05-15, moved to 2026-06-15 |\n" in out
           and "  The board: its approval of the changes to the plan since 2026-04-24 (M1).\n" in out,
           "a date moved after the board approved the plan shows as moved, and the flag stays", out)
    plan = folder / "plan.md"
    finding.write_text(plan, "\n".join(line for line in plan.read_text(encoding="utf-8").split("\n") if not line.startswith("| M2 ")))
    expect("Changed in plan.md since: M1 moved to 2026-06-15 and M2 taken out." in check(folder)[1],
           "a milestone taken out after approval is named", line_of(check(folder)[1], "Plan approval"))
    edit(folder / "evidence" / "E-PLAN-1-board-minutes.md", "Company Secretary, 2026-04-24", "Company Secretary, 2026-07-01")
    out = check(folder)[1]
    expect("Flagged commitments: M1 moved from 2026-05-15 by the board's approval on 2026-07-01, after that date had passed.\n" in out
           and "Head of Complaints, committed 2026-06-15, first committed 2026-05-15 when the board approved the plan on "
           "2026-04-24. Present and signed on 2026-05-28.\n" in out
           and "signed by the Company Secretary on 2026-07-01. The board first approved the plan on 2026-04-24.\n" in out
           and "Changed in plan.md" not in out,
           "minutes signed again approve the plan as it then stands, and keep the first approved date and the slip", out[:1500])
    # A move is late only when the approval that first carried the new date came after the old date had passed.
    folder = build(root, "sr-plan-timely", IA_FILES, "2026-04-17")
    check(folder, "2026-05-01")
    edit(folder / "plan.md", "| Complaints QA lead | 2026-06-30 |", "| Complaints QA lead | 2026-07-31 |")
    edit(folder / "evidence" / "E-PLAN-1-board-minutes.md", "Company Secretary, 2026-04-24", "Company Secretary, 2026-06-01")
    expect("Flagged commitments: none.\n" in check(folder, "2026-06-02")[1], "a move the board approved in time is not flagged",
           line_of(check(folder, "2026-06-02")[1], "Flagged"))
    append_to(folder / "plan.md", "| M3 Retest acknowledgement timeliness | Complaints QA lead | 2026-10-31 | A retest shows letters "
              "within five days | EV-26 | The retest is reperformed |\n")
    edit(folder / "evidence" / "E-PLAN-1-board-minutes.md", "Company Secretary, 2026-06-01", "Company Secretary, 2026-09-01")
    out = check(folder, "2026-09-02")[1]
    expect("Flagged commitments: none.\n" in out, "a later approval that moves nothing leaves an earlier, timely move unflagged",
           line_of(out, "Flagged"))

    # A milestone taken out of the approved plan stops the signature until the board approves the changed plan. A moved
    # date or an added milestone asks the board too, and does not stop it.
    folder = ia(root, "sr-taken-out")
    check(folder)
    plan = folder / "plan.md"
    finding.write_text(plan, "\n".join(line for line in plan.read_text(encoding="utf-8").split("\n") if not line.startswith("| M2 ")))
    code, out, _ = check(folder)
    expect(code == 1 and "Changed in plan.md since: M2 taken out.\n" in out and "Ready to sign" not in out
           and "  The board: its approval of the changes to the plan since 2026-04-24 (M2).\n" in out,
           "a milestone taken out asks the board to approve the changed plan, and stops the signature", out[-700:])
    code, out, _ = run(["sign", str(folder), "--today", NOW], stdin=answers())
    expect(code == 1 and out == refusal("Refused: M2 was taken out of plan.md after the board approved the plan on 2026-04-24. "
                                        "Sign the board minutes E-PLAN-1 again once the board approves the changed plan."),
           "sign refuses while a milestone taken out waits on the board", out)
    edit(folder / "evidence" / "E-PLAN-1-board-minutes.md", "Company Secretary, 2026-04-24", "Company Secretary, 2026-11-04")
    code, out, _ = run(["sign", str(folder), "--today", NOW], stdin=answers("Head of Complaints", finding.fingerprint(folder)[:8]))
    expect(code == 0, "once the board approves the changed plan, sign goes ahead", out[-400:])
    moved, added = ia(root, "sr-moved"), ia(root, "sr-added")
    check(moved), check(added)
    edit(moved / "plan.md", "| Head of Complaints | 2026-05-31 |", "| Head of Complaints | 2026-06-15 |")
    append_to(added / "plan.md", "| M3 Retest | Head of Complaints | 2026-12-31 | A retest | EV-21 | The retest |\n")
    for name, folder in (("moved", moved), ("added", added)):
        code, out, _ = check(folder)
        expect("  The board: its approval of the changes to the plan since 2026-04-24 (M" in out and ready_line(folder) in out,
               "a moved date or an added milestone asks the board and does not stop the signature: " + name, out[-700:])
    folder = ia(root, "sr-minutes-changed")
    append_to(folder / "evidence" / "E-PLAN-1-board-minutes.md", "Amended at the May meeting.\n")
    code, out, _ = check(folder)
    expect("Plan approval: proposed, because E-PLAN-1 changed since it was signed.\n" in out,
           "changed minutes give the reason the plan reads as proposed", line_of(out, "Plan approval"))
    code, out, _ = run(["sign", str(folder), "--today", NOW], stdin=answers())
    expect(code == 1 and out == refusal("Refused: the plan approval is still proposed, because E-PLAN-1 changed since it was "
                                        "signed."), "sign gives the same reason", out)

    # A plan cell that names the wrong id gets a hint naming the file that is there.
    folder = ia(root, "sr-plan-id")
    edit(folder / "plan.md", "| EV-21 |", "| EV-021 |")
    expect("Not started. plan.md names EV-021 and evidence/ holds EV-21 in evidence/EV-21-acknowledgement-procedure.md, which "
           "no milestone lists." in line_of(check(folder)[1], "M1 "), "a misnamed plan id names the file that is there",
           line_of(check(folder)[1], "M1 "))

    # The latest Revised line wins, and any DRAFT Status makes a draft.
    def revised(files):
        files["evidence/EV-22-timeliness-report.md"] = files["evidence/EV-22-timeliness-report.md"].replace(
            "Status: FINAL\n", "Status: FINAL\nRevised: 2026-06-01\nRevised: 2026-07-15\n")
    out = check(ia_with(root, "sr-two-revised", revised))[1]
    expect("Present, unsigned: EV-22 was revised on 2026-07-15, after its signature of 2026-06-29." in line_of(out, "M2 "),
           "a later Revised line below an earlier one still counts", line_of(out, "M2 "))
    def draft(files):
        files["evidence/EV-22-timeliness-report.md"] = files["evidence/EV-22-timeliness-report.md"].replace(
            "Status: FINAL\n", "Status: FINAL\nStatus: DRAFT\n")
    out = check(ia_with(root, "sr-two-status", draft))[1]
    expect("Present, unsigned: EV-22 is a draft." in line_of(out, "M2 "), "a second Status of DRAFT makes a draft", line_of(out, "M2 "))

    # Each signed file's hash is kept by its id, so a swap under a new name or another id is named.
    folder = ia(root, "sr-swap")
    ev = folder / "evidence"
    report = (ev / "EV-22-timeliness-report.md").read_text(encoding="utf-8")
    (ev / "EV-22-timeliness-report.md").rename(ev / "EV-99-old.csv")
    finding.write_text(ev / "EV-99-old.csv.md", "What: EV-99 Old copy\nFor: OLD EV-99\nSigned by: none\nStatus: DRAFT\n")
    finding.write_text(ev / "EV-22-report.md", report.replace("402, or 98.0 percent", "410, or 100.0 percent"))
    edit(folder / "closure" / "memo.md", "402 of 410 complaints acknowledged within five business days, or 98.0 percent",
         "410 of 410 complaints acknowledged within five business days, or 100.0 percent")
    code, out, _ = check(folder)
    expect(code == 1 and "Present, unsigned: EV-22 changed since it was signed." in line_of(out, "M2 ")
           and "Filed under another id since signing\nevidence/EV-99-old.csv holds what was signed as EV-22 on 2026-06-29, and "
           "is now filed as EV-99.\n" in out and "  The engagement team: evidence/EV-99-old.csv, signed as EV-22.\n" in out
           and "Ready to sign" not in out, "a signed file swapped under a new name and its old bytes under another id are named", out)
    folder = ia(root, "sr-swap-sign")
    ev = folder / "evidence"
    (ev / "EV-22-timeliness-report.md").rename(ev / "EV-99-old.csv")
    finding.write_text(ev / "EV-99-old.csv.md", "What: EV-99 Old copy\nFor: OLD EV-99\nSigned by: none\nStatus: DRAFT\n")
    finding.write_text(ev / "EV-24-report.md", report.replace("EV-22", "EV-24"))
    for rel in ("plan.md", "closure/memo.md"):
        finding.write_text(folder / rel, (folder / rel).read_text(encoding="utf-8").replace("EV-22", "EV-24"))
    code, out, _ = run(["sign", str(folder), "--today", NOW], stdin=answers())
    expect(code == 1 and out == refusal("Refused: evidence/EV-99-old.csv holds what was signed as EV-22 and is now filed as "
                                        "EV-99. Take it out, or sign it again under that id."), "sign refuses a signed file under another id", out)
    folder = ia(root, "sr-copy")
    shutil.copyfile(str(folder / "evidence" / "EV-22-timeliness-report.md"), str(folder / "evidence" / "EV-99-copy.csv"))
    finding.write_text(folder / "evidence" / "EV-99-copy.csv.md", "What: EV-99 Copy\nFor: OLD EV-99\nSigned by: none\nStatus: DRAFT\n")
    expect("Filed under another id" not in check(folder)[1], "a copy beside the file signed under the first id is no refiling",
           check(folder)[1][-600:])
    folder = ia(root, "sr-rename")
    (folder / "evidence" / "EV-22-timeliness-report.md").rename(folder / "evidence" / "EV-22-report.md")
    out = check(folder)[1]
    expect("Present and signed on 2026-06-29." in line_of(out, "M2 ") and "Filed under" not in out,
           "a signed file renamed and unchanged stays signed", line_of(out, "M2 "))

    # A cleared ruling stops counting once a page it rests on is signed after the ruling, and says why.
    folder = ia(root, "sr-resigned-page")
    edit(folder / "closure" / "memo.md", "The first report covers May 2026 [EV-22 p1].",
         "The first report covers May 2026 and was issued in June 2026 [EV-22 p1].")
    add_ruling(folder, "June 2026", "cleared | Head of Complaints | 2026-11-04 | The report was issued in June.")
    out = check(folder, "2026-11-05")[1]
    expect("Memo check: 14 claims, 13 tie, 0 on the list, 1 cleared." in out, "the ruling clears the row", memo_block(out))
    edit(folder / "evidence" / "EV-22-timeliness-report.md", "Complaints QA lead, 2026-06-29", "Complaints QA lead, 2026-11-05")
    out = check(folder, "2026-11-05")[1]
    expect("1 on the list" in out and re.search(r"  Ruling at rulings\.md line \d+ does not count: EV-22 was signed on 2026-11-05, "
                                                r"after the ruling's date of 2026-11-04, so the page it rests on may have changed\.\n", out),
           "a ruling dated before its page was signed again stops counting and says why", memo_block(out))

    # Loosely typed rulings say why they count for nothing.
    folder = fresh(root, "sr-loose-rulings")
    rulings = folder / "closure" / "rulings.md"
    n = len(rulings.read_text(encoding="utf-8").splitlines())
    append_to(rulings, "1,248 #972adb19 | cleared | Head of Complaints | 2026-11-04 | Rounded.\n"
                       "Line 10 | EV-12 draft #81b3b231 | cleared | head of complaints | 2026-11-04 | In the review.\n"
                       "Line 16 | sample period for M2 | cleared | Head of Complaints | 2026-11-04 | On purpose.\n")
    out = check(folder)[1]
    expect("  Ruling at rulings.md line {} does not count: it does not start with Line and the memo line number, such as Line 8.\n"
           .format(n + 1) in out
           and "  Ruling at rulings.md line {} does not count: its role is written in another letter case from the finding "
           "owner's role, Head of Complaints.\n".format(n + 2) in out
           and "  Ruling at rulings.md line {} names no row: it has no # mark, and the row on that line prints sample period "
           "for M2 #106ddd50.\n".format(n + 3) in out, "a loosely typed ruling says why it does not count", memo_block(out))

    # sign checks and fingerprints the same bytes: a change while it waits for the role is refused.
    folder = ia(root, "sr-one-pass")
    edited = root / "sr-one-pass-edited"
    shutil.copytree(str(folder), str(edited))
    edit(edited / "closure" / "memo.md", "It shows 402 of 410", "It shows 1,999 of 410")
    later = finding.fingerprint(edited)

    def change(n):
        if n == 1:
            shutil.copyfile(str(edited / "closure" / "memo.md"), str(folder / "closure" / "memo.md"))
    code, out, _ = run(["sign", str(folder), "--today", NOW], stdin=StandInTerminal("Head of Complaints\n" + later[:8] + "\n", change))
    expect(code == 1 and out.endswith(refusal("Refused: a file changed while sign was running; run it again."))
           and state_of(folder)["signature"] is None, "a change while sign waits for the role is refused", out[-300:])


def test_recheck_rows(root):
    """size, eval and check list the same rows, a heading's label is no figure, and a ruling that does not count says why."""
    folder = ia(root, "recheck-revised")
    finding.write_text(folder / "evidence" / "EV-40-extra.md", "What: EV-40 Extra\nFor: EV-40\nSigned by: Head of Complaints, "
                       "2026-05-01\nStatus: FINAL\nRevised: 2026-06-01\n\nThe extra page holds 777 items.\n")
    append_to(folder / "closure" / "memo.md", "\nThe extra page holds 777 items [EV-40 p1].\n")
    today = datetime.date.today().isoformat()
    expect("14 claims, 13 tie, 1 on the list" in check(folder, today)[1], "check lists a revised file no milestone lists",
           memo_block(check(folder, today)[1]))
    expect("14 claims on the memo check, 1 row before rulings" in run(["size", str(folder)])[1], "size counts that row too",
           run(["size", str(folder)])[1][:400])
    expect("in the 13 claims that tie today" in run(["eval", str(folder)])[1], "eval plants only in the claims that tie",
           run(["eval", str(folder)])[1][:400])
    heads = with_memo(root, "recheck-headings", "The first report covers May 2026 [EV-22 p1].\n\n## Milestone 2, the report\n\n"
                      "## Part 3: sample\n\n## Appendix 1\n\n## Section 2.1 Scope\n\n## Closure memo, version 2\n\n"
                      "## Section 4: 120 complaints [EV-21 p2]\n")
    expect("Memo check: 2 claims, 2 tie, 0 on the list." in check(heads)[1], "a number that labels a part of the memo is no figure",
           memo_block(check(heads)[1]))
    quarter = with_memo(root, "recheck-quarter", "The Q3 2026 report followed [EV-22 p1].\n")
    expect("1 claim, 0 tie, 1 on the list" in check(quarter)[1], "a quarter with its year is read", memo_block(check(quarter)[1]))
    later = with_memo(root, "recheck-later-ruling", "A further 120 complaints were reviewed in the second batch [EV-22 p1].\n")
    add_ruling(later, "120", "cleared | Head of Complaints | 2031-11-01 | Checked by hand.")
    out = check(later)[1]
    expect("1 on the list" in out and "does not count: it is dated 2031-11-01, after the check date." in out,
           "a ruling dated after the check date says why it does not count", memo_block(out))


def test_recheck_size(root):
    """size counts what each side asks of a person, its parts add up, and a finding's own assumptions count in a folder run."""
    out = run(["size", str(CASES / "MRA-CMP-07")])[1]
    kit = re.search(r"With the kit, assumed: ([\d.]+) hours\. (.*)\.\n", out)
    parts = [float(x) for x in re.findall(r" ([\d.]+)(?:,|$)", kit.group(2))] if kit else []
    expect(kit is not None and abs(sum(parts) - float(kit.group(1))) < 0.001 and "status reports" in kit.group(2),
           "the kit's parts add up to its total and carry the status reports", out[:600])
    eng = root / "recheck-eng"
    eng.mkdir()
    shutil.copytree(str(ia(root, "recheck-eng-ia")), str(eng / "IA"))
    finding.write_text(eng / "IA" / finding.SIZE_FILE, "minutes a claim by hand: 7\n")
    finding.write_text(eng / finding.SIZE_FILE, "minutes a ruling = 20\n")
    alone = run(["size", str(eng / "IA")])[1]
    folder = run(["size", str(eng)])[1]
    by_hand = re.search(r"By hand, assumed: [\d.]+ hours", alone)
    expect(by_hand is not None and by_hand.group(0) in folder and "1 assumption from its own size-assumptions.txt" in folder,
           "a folder run reads a finding's own size-assumptions.txt as a run on that finding does", folder[:600])
    closing = folder.strip().splitlines()[-1]
    expect("Checking claims 4.5" in folder and closing.startswith("These hours are assumptions")
           and " IA-CMP-02 takes 7 minutes a claim by hand from its own size-assumptions.txt. " in closing,
           "a folder run's closing line names the values a finding's own file set, so its hours can be rebuilt", closing)
    demo = pages("finding/DEMO.md")
    if demo is not None:
        expect("status reports 1.5" in demo and "13.7 hours" in demo, "the walk carries the size screen as it prints")


def test_recheck_pages(root):
    """The pages say what the tool does after this round."""
    kit = HERE.parent
    tests = json.loads((kit / "RELEASE.json").read_text(encoding="utf-8"))["tests"]
    expect("finding/release.py" in tests and not any(rel.endswith(("README.md", "DEMO.md")) for rel in tests),
           "RELEASE.json hashes the code the self-test needs in finding/, and no documentation page")
    copy = kit_copy(root, "recheck-no-pages")
    for rel in ("finding/README.md", "finding/DEMO.md"):
        (copy / rel).unlink(missing_ok=True)
    code, out = kit_run(copy, "--version")
    expect(code == 0 and "Every file matches this release." in out, "a kit brought in without its pages matches its release", out)
    found = pages("README.md", "finding/DEMO.md", "finding/README.md")
    if found is None:
        return
    readme, demo, guide = found
    expect("one page per sheet" not in guide and "one page per visible sheet" in guide, "the finding README says a page is a visible sheet")
    expect("five-line cover" not in readme and "four-line cover" in readme and "sample row is not a claim" in demo,
           "the README gives the cover's lines, and the walk says the sample row is not a claim")
    expect("A finding with nothing left to do" not in demo, "the walk's step 6 title says what the case still needs")
    step11 = page_section(demo, "## 11. A document instead of a text file")
    expect("leaves the signature" in step11 and "Signed by line again" not in step11 and "Checked by" in step11,
           "the walk's step 11 says a typed page leaves the signature alone and waits on a Checked by line", step11[-400:])
    expect("The days follow the weekly rhythm." not in readme and "ten months into its plan" not in readme,
           "the README says nothing false about its days")
    saved = finding.KIT
    try:
        finding.KIT = root / "recheck-kit"
        for rel in ("finding/cases/X/closure/" + finding.LOG_NAME, "finding/cases/X/finding.md"):
            (finding.KIT / rel).parent.mkdir(parents=True, exist_ok=True)
            (finding.KIT / rel).write_text("x\n", encoding="utf-8")
        listed = finding.test_asset_files()
    finally:
        finding.KIT = saved
    expect("finding/cases/X/finding.md" in listed and not any(finding.LOG_NAME in rel for rel in listed),
           "a log written in a shipped case is no test asset", ", ".join(listed))
    saved = finding.kit_release
    try:
        finding.kit_release = lambda: ("9.8.7", ["finding/finding.py"])
        bare = ia(root, "recheck-not-ready")
        (bare / "plan.md").unlink()
        out = check(bare)[1]
    finally:
        finding.kit_release = saved
    expect("Kit files changed since release 9.8.7: finding/finding.py." in out and "Not ready" in out,
           "a Not ready screen names a changed kit file, as every page does", out)


def test_reader_bounds_and_styles(root):
    """A shared string counts in every cell, header lines are counted before parsing, a Date reads the same on every
    Python, a style sheet hides only what the reader can apply, and Markdown evidence reads as it shows."""
    docs, read = reader_in(root, "reader-bounds")
    cells = "<sheetData><row>" + '<c t="s"><v>0</v></c>' * 64 + "</row></sheetData>"
    data = book_bytes(root, [("Sample", None, cells)], shared=["a" * (2 * 1024 * 1024)])
    tracemalloc.start()
    try:
        got = read("shared.xlsx", data)
        peak = tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()
    expect(got["problem"] == docs.TOO_MUCH_TEXT and peak < 48 * 1024 * 1024,
           "a shared string that fills every cell counts in each cell before the row is built", "{} at {} MB".format(got["problem"], peak >> 20))
    got = read("long-index.xlsx", book_bytes(root, [("Sample", None, '<sheetData><row><c t="s"><v>{}</v></c></row></sheetData>'.format("9" * 5000))], shared=["x"]))
    expect(got["problem"] == docs.DAMAGED, "a shared-string number too long for any workbook is damage on every Python", str(got)[:200])
    tangled = {"commas": b"From: a@b.c\nTo: " + b"," * 20000, "dots": b"From: a" + b"." * 20000 + b"@b.c",
               "parameters": b"From: a@b.c\nContent-Type: text/plain; " + "; ".join("a{}=b".format(k) for k in range(4000)).encode(),
               "comments": b"From: " + b"(a)" * 6000 + b" a@b.c", "words": b"From: a@b.c\nSubject: " + b"a " * 12000}
    for label, head in tangled.items():
        tail = b"\nContent-Type: text/plain\n\nHeld 1,284.\n" if label != "parameters" else b"\n\nHeld 1,284.\n"
        got = read("tangled.eml", head + tail)
        expect(got["problem"] == docs.TANGLED_HEADERS, "a header with too many {} for the parser to read quickly is refused before parsing".format(label),
               str(got)[:200])
    many = ", ".join("First{0} Last <first.last{0}@example.com>".format(k) for k in range(400))
    got = read("many.eml", ("From: a@b.c\nTo: " + many + "\nContent-Type: text/plain\n\nHeld 1,284.\n").encode())
    expect(got["problem"] is None and "first.last399@example.com" in page_of(got), "an email to 400 people still reads", str(got)[:200])
    for written, shown in (("2026-05-30T10:00:00Z", "2026-05-30T10:00:00Z"), ("30/05/2026 10:00", "30/05/2026 10:00"),
                           ("Saturday 30 May 2026", "Saturday 30 May 2026"), ("30 May 2026 10:00 GMT", "Sat, 30 May 2026 10:00:00 +0000"),
                           ("30 May 26 10:00 +0000", "30 May 26 10:00 +0000"), ("30 Feb 2026 10:00 +0000", "30 Feb 2026 10:00 +0000")):
        got = read("date.eml", "From: a@b.c\nDate: {}\nContent-Type: text/plain\n\nThe total was 1,284.\n".format(written).encode())
        expect(got["problem"] is None and "\nDate: {}\n".format(shown) in page_of(got),
               "a Date of {} reads as {} on every Python".format(written, shown), str(got)[:200])
    folder = with_document(root, "reader-iso-date", "EV-30-mail.eml", b"From: a@b.c\nTo: d@e.f\nDate: 2026-05-30T10:00:00Z\nSubject: s\n"
                           b"Content-Type: text/plain\n\nThe total was 1,284.\n", "The listing held 1,284 items [EV-30 p1].")
    expect("14 claims, 14 tie, 0 on the list" in check(folder)[1], "an email with an ISO date ties on every Python", memo_block(check(folder)[1]))
    preheader = ('<html><head><style>.wrapper .preheader{display:none !important}</style></head><body><div class="wrapper">'
                 '<span class="preheader">Your listing is ready</span><p>The sample held 1,284 items.</p></div></body></html>')
    expect(docs.read_html(preheader) == ("The sample held 1,284 items.", "Your listing is ready"),
           "a descendant selector leaves out only what it may hide, and never its wrapper", repr(docs.read_html(preheader)))
    got = read("preheader.eml", email_bytes(("text/html", preheader)))
    expect(got["problem"] is None and got["partly"] == [1] and "1,284" in page_of(got),
           "an email with a rule the reader cannot apply exactly is read in part, for a person to type", str(got)[:300])
    early = preheader.replace("ready", "ready 2 days early")
    got = read("preheader-alt.eml", email_bytes(("text/plain", "Your listing is ready 2 days early.\nThe sample held 1,284 items."), ("text/html", early)))
    expect(got["problem"] is None and got["partly"] == [1], "the plain part may show what the HTML part leaves in doubt", str(got)[:300])
    got = read("hidden-all.eml", email_bytes(("text/html", "<style>*{display:none}</style><p>The sample held 1,284 items.</p>")))
    expect(got["problem"] is None and got["partly"] == [1], "a style sheet that may hide everything leaves the page to a person and refuses nothing", str(got)[:300])
    for label, html in (("an id", '<head><style>#pv{display:none}</style></head><body><p>A 1,284.</p><p id="pv">B 9,999.</p></body>'),
                        ("an element name", '<style>span{display:none}</style><p>A 1,284.</p><span>B 9,999.</span>'),
                        ("a box of no height", '<p>A 1,284.</p><p style="height:0;overflow:hidden">B 9,999.</p>'),
                        ("a font of no size", '<p>A 1,284.</p><p style="font:0/0 a">B 9,999.</p>')):
        expect(docs.read_html(html) == ("A 1,284.", ""), "text hidden by {} is left out".format(label), repr(docs.read_html(html)))
    for label, html in (("a line height of nothing", '<p style="font: 12px/0 Arial">A 1,284.</p>'),
                        ("a height with nothing clipped", '<p style="height:0">A 1,284.</p>'),
                        ("an animation", '<style>@keyframes f{0%{opacity:0}100%{opacity:1}}</style><p>A 1,284.</p>')):
        expect(docs.read_html(html) == ("A 1,284.", ""), "text under {} shows".format(label), repr(docs.read_html(html)))
    late = '<p>A 1,284.</p><p class="h">B 9,999.</p><style>.h{display:none}</style>'
    expect(docs.read_html(late) == ("A 1,284.", "B 9,999."), "text a later style sheet hides is left in doubt", repr(docs.read_html(late)))
    media = '<style>@media screen{.m{display:none}}</style><p>A 1,284.</p><div class="m">B 9,999.</div>'
    expect(docs.read_html(media) == ("A 1,284.", "B 9,999."), "text a rule inside @media hides is left in doubt", repr(docs.read_html(media)))
    folder = with_document(root, "reader-late-style", "EV-30-mail.eml", email_bytes(("text/html", late)), "The listing held 9,999 items [EV-30 p1].")
    out = check(folder)[1]
    expect("9,999 is cited to EV-30 p1, and the page does not hold it" in out and "The check read this page only in part" in out,
           "a figure under a later style sheet does not tie, and its row says to type the page", memo_block(out))
    typed = docs.markdown_shown('Held 1.<span hidden>410</span> ok<img hidden src="x">\n\n[ref]: http://x.y "410"\nText [a]: 5\n\n'
                                '<div style="display: none">\n9,999\n</div>\nShown 7.')
    expect("410" not in typed and "9,999" not in typed and "Text [a]: 5" in typed and "Shown 7." in typed and typed.count("\n") == 8,
           "Markdown evidence leaves out what a rendered page hides, line for line", repr(typed))
    folder = ia(root, "markdown-hidden")
    edit(folder / "evidence" / "EV-22-timeliness-report.md", "Median time to acknowledgement: 1 business day.",
         "Median time to acknowledgement: 1 business day.<span hidden>410 of 410, 100.0 percent</span>")
    edit(folder / "closure" / "memo.md", "402 of 410 complaints acknowledged within five business days, or 98.0 percent",
         "410 of 410 complaints acknowledged within five business days, or 100.0 percent")
    out = check(folder)[1]
    expect("100.0 percent is cited to EV-22 p1, and the page does not hold it" in out, "a figure hidden in Markdown evidence does not tie", memo_block(out))
    folder = ia(root, "markdown-repeat")
    append_to(folder / "evidence" / "EV-22-timeliness-report.md", "\n## Page 2\n\nCorrection of 2026-06-30: 405 complaints were acknowledged "
              "within five business days.\n")
    edit(folder / "closure" / "memo.md", "The Complaints QA lead signed it on 2026-06-29 [EV-22 p2].",
         "The Complaints QA lead signed it on 2026-06-29 [EV-22 p2]. A correction raised the count to 405 [EV-22 p2].")
    out = check(folder)[1]
    expect("Memo check: 14 claims" in out and "405" not in memo_block(out), "a page heading typed twice keeps the text under both", memo_block(out))


def test_memo_reads_more_forms(root):
    """A cite binds to its own sentence, single quotes and insertions are read, more date forms are read, a year is
    named, a title-case heading's figure is read, and list numbers, ids and honest uses of closed make no noise."""
    folder = ia(root, "more-wrapped")
    append_to(folder / "closure" / "memo.md", "\nTwo deputies cover the list, and 2 deputies were trained.\n"
              "The other 2 complaints were fixed from the exception list [EV-21 p2].\n")
    code, out, _ = check(folder)
    expect("Memo check: 15 claims, 14 tie, 1 on the list." in out and "  Line 16: 2 has no cite." in out and "Ready to sign" not in out,
           "a hard-wrapped line never lends its cite to the sentence before it", memo_block(out))
    folder = with_memo(root, "more-wrapped-date", "The first report covers\nMay\n2026 [EV-22 p1]. In a sample of 120\n"
                       "complaints, 118 were acknowledged [EV-21 p2].\n")
    expect("Memo check: 3 claims, 3 tie, 0 on the list." in check(folder)[1], "a date or a sentence wrapped across lines still reads whole",
           memo_block(check(folder)[1]))

    for name, quoted in (("straight", "'the deputy never covers when the manager is away'"),
                         ("curly", "\u2018the deputy never covers when the manager is away\u2019")):
        folder = ia(root, "more-single-" + name)
        append_to(folder / "closure" / "memo.md", "\nThe procedure says {} [EV-21 p1].\n".format(quoted))
        out = check(folder)[1]
        expect("Memo check: 14 claims, 13 tie, 1 on the list." in out
               and "  Line 16: 'the deputy never covers when the manager is away' is cited to EV-21 p1, and the page does not hold" in out,
               "a misquotation in {} single quotes goes on the list".format(name), memo_block(out))
    folder = with_memo(root, "more-single-ties", "The procedure says \u2018the deputy covers when the manager is away\u2019 [EV-21 p1]. "
                       "The managers' list and the bank's 'own words' stay as written [EV-21 p1]. It reads 'the deputy covers\n"
                       "when the manager is away.' The next figure is 120 [EV-21 p2].\n")
    out = check(folder)[1]
    expect("Memo check: 3 claims, 2 tie, 1 on the list." in out and "  Line 4: 'the deputy covers when the manager is away.' has no cite." in out,
           "a quotation in single marks ties, apostrophes and two words are left alone, and a cite binds to its own sentence", memo_block(out))
    folder = with_memo(root, "more-insertion", 'It says "the deputy [never] covers when the manager is away" [EV-21 p1]. '
                       "It says 'the deputy covers ... away' [EV-21 p1].\n")
    out = check(folder)[1]
    expect("Memo check: 2 claims, 0 tie, 2 on the list." in out
           and '"the deputy [never] covers when the manager is away" is cited to EV-21 p1, and holds an insertion the check cannot compare.' in out
           and "'the deputy covers ... away' is cited to EV-21 p1, and holds an ellipsis the check cannot compare." in out,
           "a quotation with an insertion or an ellipsis goes on the list for a person", memo_block(out))

    folder = with_memo(root, "more-near-cite", "The sample held 120 complaints [EV-21, p2].\n\nThe sample held 120 complaints "
                       "(EV-21 p. 2).\n\nThe sample held 120 complaints [EV-21 page 2], and 118 were on time [EV-21 p2].\n")
    out = check(folder)[1]
    expect("Memo check: 4 claims, 1 tie, 3 on the list." in out
           and "  Line 4: 120 has no cite. Write [EV-21, p2] as [EV-21 p2], the form the check reads." in out
           and "  Line 6: 120 has no cite. Write (EV-21 p. 2) as [EV-21 p2], the form the check reads." in out
           and "Write [EV-21 page 2] as [EV-21 p2]" in out and "2 has no cite" not in out,
           "a cite written another way gets a hint, and its page number is no claim", memo_block(out))

    folder = with_memo(root, "more-dates", "It was issued on 1 July, 2026 [EV-22 p1], reissued on 01-Aug-2026 [EV-22 p1] and "
                       "covers 2026-01 [EV-22 p1]. It was signed on the 1st of June 2026 [EV-22 p2]. On 2026-05-15 [EV-22 p1] and "
                       "1-Jul-26 it ran.\n")
    out = check(folder)[1]
    expect("Memo check: 5 claims, 0 tie, 5 on the list." in out
           and "1 July, 2026 is cited to EV-22 p1, and the page does not hold it; the date on the page is May 2026." in out
           and "01-Aug-2026 is cited to EV-22 p1" in out and "2026-01 is cited to EV-22 p1" in out
           and "1st of June 2026 is cited to EV-22 p2, and the page does not hold it; the date on the page is 2026-06-29." in out
           and "2026-05-15 is cited to EV-22 p1, and the page gives only the month, May 2026, so it cannot show the day." in out
           and "  Not checked: 1 date with a two-digit year, line 4 (1-Jul-26).\n" in out and " 1 has no cite" not in out,
           "common date forms are read as dates, and a day the page gives only to the month goes on the list", memo_block(out))
    folder = with_memo(root, "more-page-dates", "It was issued on 2026-08-01 [EV-40 p1], reissued on 2026-07-01 [EV-40 p1] and "
                       "covers January 2026 [EV-40 p1]. It took 1 day [EV-40 p1].\n")
    typed_evidence(folder, "EV-40-note.md", "EV-40", "Issued 01-Aug-2026. Reissued 1 July, 2026. Period 2026-01. Ref BM-2026-01.")
    out = check(folder)[1]
    expect("Memo check: 4 claims, 3 tie, 1 on the list." in out and "  Line 4: 1 is cited to EV-40 p1, and the page holds no figure." in out,
           "the same date forms on an evidence page are dates, and their numbers are no figures", memo_block(out))

    folder = ia(root, "more-years")
    edit(folder / "closure" / "memo.md", "In a sample of 120 complaints", "In a sample of 2020 complaints")
    edit(folder / "closure" / "memo.md", "signed it on 2026-06-29", "first signed a report in 2025")
    out = check(folder)[1]
    expect("Memo check: 11 claims, 11 tie, 0 on the list." in out
           and "  Not checked: 2 numbers read as years, line 6 (2020) and line 8 (2025).\n" in out,
           "a bare year and a four-digit number read as a year are named on the Not checked line", memo_block(out))

    folder = with_memo(root, "more-title-case", "The first report covers May 2026 [EV-22 p1].\n\n## 125 Complaints Sampled\n\n"
                       "## 99.1 Percent Acknowledged On Time\n\n## Section 98.3 percent on time\n\n## 4 Letters\n")
    out = check(folder)[1]
    expect("Memo check: 5 claims, 1 tie, 4 on the list." in out and "  Line 6: 125 has no cite." in out and "  Line 8: 99.1 has no cite." in out
           and "  Line 10: 98.3 percent has no cite." in out and "  Line 12: 4 has no cite." in out,
           "a figure that opens a title-case heading, or follows a label as a percentage, is read", memo_block(out))
    folder = ia(root, "more-list-numbers")
    edit(folder / "closure" / "memo.md", "Internal audit can test both milestones", "The board approved closure at BM-2026-07. "
         "What internal audit will find:\n\n1. The procedure gives the exception list an owner role [EV-21 p1].\n2. The report "
         "goes to the Operational Risk Committee each quarter [EV-22 p2].\n(3) Both are signed [EV-22 p2].\n\n## (1) Testing\n\n"
         "## 1 - Letters\n\n## 1: Letters\n\nInternal audit can test both milestones")
    out = check(folder)[1]
    expect("Memo check: 13 claims, 13 tie, 0 on the list." in out, "list numbers, numbered headings and a reference id are no figures",
           memo_block(out))

    folder = fresh(root, "more-backwards")
    edit(folder / "closure" / "memo.md", "Sample period: 2026-01-05 to 2026-03-31", "Sample period: 2026-03-31 to 2026-01-05")
    expect("the sample period for M2 starts 2026-01-05, before the fix took effect on 2026-03-17" in check(folder)[1],
           "a sample period written backwards is read from its earlier date", memo_block(check(folder)[1]))
    for rel, old, new in (("closure/memo.md", "Internal audit can test", "The remediation closed the gap between logging and "
                           "acknowledgement. Internal audit can test"),
                          ("plan.md", "| A sample of complaints received after the change", "| A remediation closed-loop sample of "
                           "complaints received after the change"),
                          ("closure/memo.md", "Internal audit can test", "The remediation team achieved closure of the exception "
                           "list each day. Internal audit can test")):
        folder = build(root, "more-closed-" + re.sub(r"\W", "-", new)[:20], IA_FILES, "2026-04-17")
        edit(folder / rel, old, new)
        out = check(folder)[1]
        expect("Refused" not in out and "does not read as a claim that the finding is closed" in out,
               "an honest use of closed is a row to rule on: " + new[:40], out[-400:])

    folder = with_memo(root, "more-quarters", "The Q3 2026 report followed [EV-22 p1].\n\nThe 3Q 2026 report followed [EV-22 p1].\n\n"
                       "The Q2 2026 report followed [EV-22 p1].\n")
    out = check(folder)[1]
    expect("Memo check: 3 claims, 1 tie, 2 on the list." in out and "  Line 4: Q3 2026 is cited to EV-22 p1, and the page does not hold it" in out
           and "  Line 6: 3Q 2026 is cited to EV-22 p1" in out, "a quarter with its year is read as that quarter", memo_block(out))
    drafting = pages("assistant/draft-memo.md")
    if drafting is not None:
        expect("3Q 2026" in drafting and "it reads the year" not in drafting and "single quotes" in drafting,
               "the drafting procedure describes how quarters, years and quotations are read")

    folder = fresh(root, "more-template-memo")
    finding.write_text(folder / "closure" / "memo.md", finding.TEMPLATE_MEMO.format(id="MRA-CMP-07"))
    expect("Closure memo: nothing written yet.\n" in check(folder)[1], "a memo holding only the template says nothing is written yet")


def test_month_points(root):
    """A month written short with a point, as in Feb. 2, 2026, Jun. 2026 or 2 Jan. 2026, ends no sentence, so the date
    reads whole and a wrong one goes on the list."""
    folder = ia(root, "month-point")
    append_to(folder / "closure" / "memo.md", "\nThe Head of Complaints signed the procedure on Feb. 2, 2026 [EV-21 p2].\n")
    out = check(folder)[1]
    expect("Memo check: 14 claims, 13 tie, 1 on the list." in out
           and "  Line 16: Feb. 2, 2026 is cited to EV-21 p2, and the page does not hold it" in out and "Ready to sign" not in out,
           "a wrong date written Feb. 2, 2026 goes on the list and stops the signature", memo_block(out))
    folder = with_memo(root, "month-point-forms", "The first report covers Jun. 2026 [EV-22 p1].\n\nThe procedure was signed on "
                       "Sept. 30, 2026 [EV-21 p2].\n\nThe procedure was signed on 2 Jan. 2026 [EV-21 p2].\n\nIn a sample of 120 "
                       "complaints received by Jan. 22, 2026, 118 were acknowledged in time [EV-21 p2].\n\nIn a sample of 120 "
                       "complaints received by Aug. 22, 2026, 118 were acknowledged in time [EV-21 p2].\n")
    out = check(folder)[1]
    expect("  Line 4: Jun. 2026 is cited to EV-22 p1, and the page does not hold it; the date on the page is May 2026." in out
           and "  Line 6: Sept. 30, 2026 is cited to EV-21 p2, and the page does not hold it" in out
           and "  Line 8: 2 Jan. 2026 is cited to EV-21 p2, and the page does not hold it" in out
           and "  Line 10: Jan. 22, 2026 is cited to EV-21 p2" in out and "  Line 12: Aug. 22, 2026 is cited to EV-21 p2" in out
           and "has no cite" not in out, "a month written short with a point reads as part of its date", memo_block(out))
    # May is a full word, so its point ends a sentence, and a figure before it borrows no cite from the next one.
    out = check(with_memo(root, "month-point-may", "120 complaints received in May. 2 were late [EV-21 p2].\n"))[1]
    expect("  Line 4: 120 has no cite." in out, "a sentence ending in May. lends no cite to the figure before it", memo_block(out))


def test_long_page_list(root):
    """A cite listing many pages reads in one pass, and an ordinary list of pages still gets its hint."""
    pages = "".join(", p%d" % k for k in range(2, 42))
    folder = ia(root, "page-list")
    append_to(folder / "closure" / "memo.md", "\nThe procedure and the May sample are set out across the pack (EV-21 p1"
              + pages + " and the annex).\n")
    start = time.time()
    out = check(folder)[1]
    expect(time.time() - start < 1 and "Memo check: 13 claims, 13 tie, 0 on the list." in out,
           "a cite of 40 pages that does not close after them reads in under a second", str(time.time() - start))
    folder = with_memo(root, "page-list-near", "The sample held 120 complaints [EV-21 p1, p2, p3].\n\nThe sample held 120 "
                       "complaints [EV-21 p1, EV-22, p1 and EV-21 p2].\n")
    out = check(folder)[1]
    expect("Memo check: 2 claims, 0 tie, 2 on the list." in out and "Write [EV-21 p1, p2, p3] as one cite for each page" in out
           and "Write [EV-21 p1, EV-22, p1 and EV-21 p2] as one cite for each page" in out and " 3 has no cite" not in out,
           "a list of pages gets its hint, and its numbers are no claim", memo_block(out))


def test_dark_mode_and_at_rules(root):
    """A rule for dark mode only hides nothing on the light page a person reads by default, and an at-rule statement
    such as @import or @charset ends at its semicolon, so the hiding rule after it applies."""
    docs, read = reader_in(root, "dark-and-at-rules")
    body = '<table><tr><td><p>The sample held 1,284 items.</p><p class="light">Received 410.</p></td></tr></table>'
    for label, style in (("a dark-mode block", "<style>@media (prefers-color-scheme: dark) { .bg { background:#1e1e1e !important; }"
                                               " h1, p, td { color:#ffffff !important; } .light { display:none } }</style>"),
                         ("a dark-mode block for screens", "<style>@media only screen and (prefers-color-scheme:dark){p{color:#fff}}</style>"),
                         ("Outlook's dark-mode marks", "<style>[data-ogsc] h1, [data-ogsc] p { color:#ffffff !important; } "
                                                       "[data-ogsb] .light { display:none }</style>"),
                         ("a dark-mode style sheet", '<style media="(prefers-color-scheme: dark)">p { color:#ffffff }</style>')):
        got = docs.read_html(style + body)
        expect(got == ("The sample held 1,284 items.\nReceived 410.", ""), "text under " + label + " reads in full", repr(got))
    for label, sheet in (("a block for light mode", "@media (prefers-color-scheme: light) { .w { color:#ffffff } }"),
                         ("a block for dark mode or print", "@media (prefers-color-scheme: dark), print { .w { color:#ffffff } }"),
                         ("a block for all but dark mode", "@media not all and (prefers-color-scheme: dark) { .w { color:#ffffff } }"),
                         ("a rule after a dark-mode block", "@media (prefers-color-scheme: dark) { p { color:#fff } } .w { color:#ffffff }")):
        got = docs.read_html("<style>" + sheet + '</style><p>A 1,284.</p><p class="w">B 9,999.</p>')
        expect(got == ("A 1,284.", "B 9,999."), "white ink from " + label + " leaves the page read in part", repr(got))
    got = docs.read_html('<style>@media (prefers-color-scheme: dark) { p { color:#fff } } .preheader { display:none }</style>'
                         '<p>A 1,284.</p><div class="preheader">B 9,999.</div>')
    expect(got == ("A 1,284.", ""), "a display:none rule after a dark-mode block still hides", repr(got))
    got = docs.read_html('<style>[data-ogsc] .x { display:none }</style><p>A 1,284.</p><div data-ogsc="#000"><p class="x">B 9,999.</p></div>')
    expect(got == ("A 1,284.", "B 9,999."), "an Outlook dark-mode rule still counts where the email's own tags carry the mark", repr(got))
    dark = ('<html><head><meta name="color-scheme" content="light dark"><style>:root{color-scheme:light dark;} @media '
            '(prefers-color-scheme: dark) { .darkmode-bg { background-color:#1e1e1e !important; } h1, p, td { color:#ffffff '
            '!important; } }</style></head><body><table role="presentation" width="100%" class="darkmode-bg"><tr><td '
            'style="padding:20px"><p>The listing for May 2026 held 1,284 items.</p></td></tr></table></body></html>')
    for name, data in (("dark-html", email_bytes(("text/html", dark))),
                       ("dark-alt", email_bytes(("text/plain", "The listing for May 2026 held 1,284 items."), ("text/html", dark)))):
        out = check(with_document(root, name, "EV-30-listing.eml", data, "The listing held 1,284 items [EV-30 p1]."))[1]
        expect("Memo check: 14 claims, 14 tie, 0 on the list." in out and "only in part" not in out,
               "an email from a dark-mode template reads in full and ties: " + name, memo_block(out))

    pre = '<div class="preheader">Preview 9,999 items</div><p>The sample held 1,284 items.</p>'
    for label, sheet in (("@import", "@import url('https://fonts.example.net/css?family=Roboto:400,700');\n.preheader { display:none !important; }"),
                         ("@import with semicolons in its quoted address",
                          "@import url('https://fonts.example.net/css2?family=Inter:wght@400;700&display=swap'); .preheader{display:none}"),
                         ("@import with semicolons in its bare address",
                          "@import url(https://fonts.example.net/css2?family=Inter:wght@400;700); .preheader{display:none}"),
                         ("@charset", '@charset "UTF-8";\n.preheader{display:none}'),
                         ("@namespace", "@namespace svg url(http://www.w3.org/2000/svg); .preheader{display:none}"),
                         ("@import in an HTML comment", "<!--@import url(x.css);.preheader{display:none}-->"),
                         ("@font-face", "@font-face{font-family:x;src:url(x.woff)} .preheader{display:none}")):
        got = docs.read_html("<style>" + sheet + "</style>" + pre)
        expect(got == ("The sample held 1,284 items.", ""), "a hiding rule after " + label + " applies", repr(got))
    html = ("<html><head><style>@import url('https://fonts.example.net/css?family=Roboto:400,700');\n.preheader { display:none "
            "!important; mso-hide:all; }\nbody { margin:0; }</style></head><body><div class=\"preheader\">Your May listing held 1,300 "
            "items.</div><p>The listing for May 2026 held 1,284 items.</p></body></html>")
    out = check(with_document(root, "at-import", "EV-30-listing.eml", email_bytes(("text/html", html)), "The listing held 1,300 items [EV-30 p1]."))[1]
    expect("1,300 is cited to EV-30 p1, and the page does not hold it" in out and "only in part" not in out and "Ready to sign" not in out,
           "a figure in a preheader hidden after @import does not tie", memo_block(out))


def test_review_round_five(root):
    """Markdown and email hide no more text from the check, a template placeholder blanks nothing, a list item keeps
    its own cite, a figure opening a line counts, sections and months read right, record lines take real references
    only, and signed evidence and the plan keep their history."""
    docs, read = reader_in(root, "round-five-reader")
    forms = {"a title": '<span title="410 of 410">.</span>', "an alt text": '<img alt="410 of 410" src="x.png">',
             "white ink": '<span style="color:white">410 of 410</span>', "a comment": '<span style="display:/**/none">410 of 410</span>',
             "an off-screen box": '<span style="position:absolute;left:-9999px">410 of 410</span>'}
    for label, form in forms.items():
        shown = docs.markdown_shown("Median 1 day." + form + "\nNext 7.")
        expect("410" not in shown and "Median 1 day." in shown and "Next 7." in shown and shown.count("\n") == 1,
               "Markdown evidence leaves out a figure in " + label, repr(shown))
    shown, doubt = docs.markdown_read("Each letter opens Dear <Title> <Surname>. Sample: 120\n\nIt sends <Template ACK-1> on day 2.")
    expect("Sample: 120" in shown and "on day 2." in shown and not doubt, "a placeholder in angle brackets blanks only itself", repr(shown))
    start = time.time()
    docs.markdown_read("x\n\n<span hidden>" + "<span " * 200000)
    expect(time.time() - start < 10, "a hidden tag before many unclosed tags reads in one pass", str(time.time() - start))
    gmail = ('<html><head><style>*[class="gmail-fix"] { display: none !important; }</style></head><body><table><tr><td>'
             '<p>The sample held 1,284 items.</p></td></tr></table><div class="gmail-fix">&nbsp;</div></body></html>')
    expect(docs.read_html(gmail) == ("The sample held 1,284 items.", ""), "an attribute selector reaches only what carries its class",
           repr(docs.read_html(gmail)))
    for rule in ('[class~="x_ie-hide"]', "table[class=hide]"):
        html = ("<style>{}{{display:none}}</style><table><tr><td>A 1,284.</td></tr></table>"
                '<table class="hide x_ie-hide"><tr><td>B 9,999.</td></tr></table>').format(rule)
        expect(docs.read_html(html)[0] == "A 1,284.", "a rule " + rule + " leaves the rest of the email read", repr(docs.read_html(html)))
    for style in ("color:transparent", "color:rgba(0,0,0,0)", "position:absolute;left:-9999px", "clip:rect(0,0,0,0)",
                  "transform:scale(0)", "text-indent:-9999px", "display:/**/none"):
        got = docs.read_html('<p>A 1,284.</p><p style="{}">B 9,999.</p>'.format(style))
        expect(got[0] == "A 1,284.", "email text styled " + style + " is not read as shown", repr(got))
    got = docs.read_html("<style>.w{color:#ffffff}</style><p>A 1,284.</p><p class=w>B 9,999.</p>")
    expect(got == ("A 1,284.", "B 9,999."), "white ink from a style sheet's class leaves the page read in part", repr(got))
    to = ",\n ".join('"Person{0}, Name" <first{0}.last@complaints.bank.example.com>'.format(k) for k in range(700))
    got = read("listing.eml", ("From: Head of Complaints <hoc@bank.example.com>\nTo: " + to + "\nSubject: Monthly listing\n"
                               "Content-Type: text/plain\n\nThe total was 1,284.\n").encode("utf-8"))
    expect(got["problem"] is None and "The total was 1,284." in got["pages"][0], "an email to 700 named people reads", str(got["problem"]))

    folder = ia(root, "round-five-markdown")
    edit(folder / "evidence" / "EV-22-timeliness-report.md", "Signed by: Complaints QA lead, 2026-06-29", "Signed by: Complaints QA lead, 2026-06-30")
    edit(folder / "evidence" / "EV-22-timeliness-report.md", "Median time to acknowledgement: 1 business day.",
         'Median time to acknowledgement: 1 business day.<span style="color:white">410 of 410, 100.0 percent</span>')
    edit(folder / "closure" / "memo.md", "402 of 410 complaints acknowledged within five business days, or 98.0 percent",
         "410 of 410 complaints acknowledged within five business days, or 100.0 percent")
    out = check(folder)[1]
    expect("Memo check: 13 claims, 12 tie, 1 on the list." in out and "The page also holds marked-up text a rendered page may not "
           "show, which the check leaves out; write it as plain text if it shows." in out and "Ready to sign" not in out,
           "white text in Markdown evidence does not tie, and the row says why", memo_block(out))
    folder = ia(root, "round-five-placeholder")
    edit(folder / "evidence" / "EV-21-acknowledgement-procedure.md", "Signed by: Head of Complaints, 2026-05-28",
         "Signed by: Head of Complaints, 2026-05-29")
    edit(folder / "evidence" / "EV-21-acknowledgement-procedure.md", "\nSample: 120", "\nEach letter opens Dear <Title> <Surname>. Sample: 120")
    expect("Memo check: 13 claims, 13 tie, 0 on the list." in check(folder)[1], "a letter placeholder leaves its page read",
           memo_block(check(folder)[1]))

    for name, text in (("bullets", "- Two deputies cover the list, and 2 deputies were trained.\n- The Head of Complaints signed the "
                                   "procedure on 2026-05-28 [EV-21 p2].\n"),
                       ("stars", "* Two deputies cover the list, and 2 deputies were trained\n* The Head of Complaints signed the "
                                 "procedure on 2026-05-28 [EV-21 p2].\n"),
                       ("digit", "Two deputies cover the list, and 2 deputies were trained.\n2 complaints were fixed from the "
                                 "exception list [EV-21 p2].\n"),
                       ("numbered", "1. 2 deputies were trained.\n2. 2 complaints were fixed from the exception list [EV-21 p2].\n")):
        folder = ia(root, "round-five-" + name)
        append_to(folder / "closure" / "memo.md", "\n" + text)
        out = check(folder)[1]
        expect("  Line 16: 2 has no cite." in out and "Ready to sign" not in out,
               "a claim with no cite borrows none from the next line: " + name, memo_block(out))
    folder = with_memo(root, "round-five-lists", "The net movement in open complaints was:\n(12) over the quarter [EV-22 p2].\n\n"
                       "119. That was the count of complaints sampled [EV-22 p2].\n\nThe steps were:\n1. The team sampled the list "
                       "[EV-21 p2].\n2. The lead signed it [EV-21 p2].\n")
    out = check(folder)[1]
    expect("Line 5: (12) is cited to EV-22 p2, and the page holds no figure." in out and "Line 7: 119 has no cite." in out
           and "Memo check: 2 claims, 0 tie, 2 on the list." in out,
           "a figure opening a line counts unless it is the next list number", memo_block(out))
    folder = with_memo(root, "round-five-sections", "## 1 Background\n\nThe deputy covers absence [EV-21 p1].\n\n## 2 Method\n\n"
                       "## 2.1 Scope\n\n## 3 Findings\n\n## 4.2 Sample Design\n\n## 125 Complaints Sampled\n")
    out = check(folder)[1]
    expect("Memo check: 1 claim, 0 tie, 1 on the list." in out and "125 has no cite." in out,
           "numbered sections read no figure, and a count in a heading still does", memo_block(out))
    folder = with_memo(root, "round-five-month", "The first report covers June, 2026 [EV-22 p1].\n")
    out = check(folder)[1]
    expect("June, 2026 is cited to EV-22 p1, and the page does not hold it; the date on the page is May 2026." in out
           and "read as a year" not in out, "a month written Month, YYYY reads as a month", memo_block(out))
    folder = with_memo(root, "round-five-near", "The sample held 120 complaints [EV-21 pp. 1-2].\n\nThe sample held 120 complaints "
                       "[EV-21 p2, EV-22 p1].\n\nThe sample held 120 complaints [ EV-21 p2 ].\n")
    out = check(folder)[1]
    expect("Memo check: 3 claims, 0 tie, 3 on the list." in out and "Write [EV-21 pp. 1-2] as one cite for each page, such as "
           "[EV-21 p1], the form the check reads." in out and "Write [ EV-21 p2 ] as [EV-21 p2]" in out
           and " 1 has no cite" not in out and " 2 has no cite" not in out,
           "a page range or a list of cites gets a hint, and its numbers are no claim", memo_block(out))

    folder = ia(root, "round-five-references")
    record = folder / "closure" / "record.md"
    for old, new in (("Internal audit reference: IAV-2026-031", "Internal audit reference: XXX"),
                     ("Board approval reference: BM-2026-07", "Board approval reference: ----")):
        edit(record, old, new)
    out = check(folder)[1]
    expect("Internal audit: not counted (the reference is a placeholder).\n" in out
           and "Board approval: not counted (the reference is a placeholder).\n" in out,
           "a reference with no digit or of XXX counts for nothing", out[-900:])
    for value in ("in progress", "see email", "IA ref later"):
        edit(record, record.read_text(encoding="utf-8").split("Internal audit reference: ")[1].split("\n")[0], value)
        expect("Internal audit: not counted (the reference is a placeholder).\n" in check(folder)[1],
               "a reference written as words holds a place: " + value)
    edit(record, "Internal audit reference: IA ref later", "Internal audit reference: IAV-2026-031")
    for value in ("NA-2026-07", "None-2026", "Later minutes 2026-07"):
        edit(record, record.read_text(encoding="utf-8").split("Board approval reference: ")[1].split("\n")[0], value)
        expect("Board approval: {} dated 2026-07-08".format(value) in check(folder)[1], "a reference that starts with a placeholder "
               "word counts: " + value, line_of(check(folder)[1], "Board approval"))
    # A file that takes the id of a signed file gone before it came in, signed on or before the last check that saw
    # the file that went, is a backdated swap: named, and refused by sign until it is signed again.
    folder = ia(root, "round-five-swap")
    check(folder)
    ev = folder / "evidence"
    report = (ev / "EV-22-timeliness-report.md").read_text(encoding="utf-8")
    (ev / "EV-22-timeliness-report.md").unlink()
    finding.write_text(ev / "EV-22-timeliness-report-v2.md", report.replace("402, or 98.0 percent", "410, or 100.0 percent")
                       .replace("Complaints QA lead, 2026-06-29", "Complaints QA lead, 2026-07-01"))
    edit(folder / "closure" / "memo.md", "402 of 410 complaints acknowledged within five business days, or 98.0 percent",
         "410 of 410 complaints acknowledged within five business days, or 100.0 percent")
    late = ("evidence/EV-22-timeliness-report-v2.md came in under EV-22 after the signed file under that id went, with a signature "
            "dated 2026-07-01, on or before {}, the last check that saw the file that went. Sign it again.".format(NOW))
    code, out, _ = check(folder, "2026-11-05")
    expect(code == 1 and "Came in after a signed file went\n" + late + "\n" in out
           and "  The engagement team: evidence/EV-22-timeliness-report-v2.md, signed again.\n" in out and "Ready to sign" not in out,
           "a backdated file under the id of a signed file that went is named, and stops the signature", out[-1200:])
    code, out, _ = run(["sign", str(folder), "--today", "2026-11-05"], stdin=answers())
    expect(code == 1 and out == refusal("Refused: " + late), "sign refuses it", out)
    edit(ev / "EV-22-timeliness-report-v2.md", "Complaints QA lead, 2026-07-01", "Complaints QA lead, 2026-11-05")
    expect("Came in after" not in check(folder, "2026-11-05")[1], "signing it again clears it", check(folder, "2026-11-05")[1][-600:])

    # A report reissued under its id and signed after the last check that saw the old one, then a new file signed before
    # the check that first sees it, is how evidence arrives: nothing is flagged, and sign goes ahead.
    folder = build(root, "round-five-reissue", IA_FILES, "2026-04-17")
    ev = folder / "evidence"
    report = (ev / "EV-22-timeliness-report.md").read_text(encoding="utf-8")
    (ev / "EV-22-timeliness-report.md").unlink()
    finding.write_text(ev / "EV-22-timeliness-report-v2.md", report.replace("Complaints QA lead, 2026-06-29",
                                                                            "Complaints QA lead, 2026-07-03") + "Reissued.\n")
    check(folder, "2026-07-06")
    retro = build(root, "round-five-retro", IA_FILES, "2026-04-17")
    for where in (folder, retro):
        finding.write_text(where / "evidence" / "EV-26-sample-retest.md", "What: EV-26 Sample retest\nFor: EV-26\nSigned by: "
                           "Complaints QA lead, 2026-09-01\nStatus: FINAL\n\n# Page 1\n\nA retest found all 40 acknowledged.\n")
    code, out, _ = check(folder, "2026-09-03")
    expect("Came in after" not in out and ready_line(folder) in out, "a reissue, then a new file signed before it came in, is "
           "not flagged", out[-900:])
    code, out, _ = run(["sign", str(folder), "--today", "2026-09-03"], stdin=answers("Head of Complaints", finding.fingerprint(folder)[:8]))
    expect(code == 0 and "Signed by the Head of Complaints on 2026-09-03" in out, "and sign goes ahead", out[-300:])
    finding.write_text(retro / "evidence" / "EV-27-note.md", "What: EV-27 Note\nFor: EV-27\nSigned by: Complaints QA lead, "
                       "2026-08-20\nStatus: FINAL\n\n# Page 1\n\nA note.\n")
    check(retro, "2026-09-03")
    (retro / "evidence" / "EV-27-note.md").unlink()
    out = check(retro, "2026-10-01")[1]
    expect("Gone since an earlier check\nevidence/EV-27-note.md.\n" in out and "Came in after" not in out,
           "a withdrawal flags no file that came in before it", out[-900:])

    folder = ia(root, "round-five-twins")
    for eid in ("EV-23", "EV-24"):
        finding.write_text(folder / "evidence" / "{}-exceptions.txt".format(eid), "Exception list review, June 2026.\nLetters that failed to send: 4.\n")
        finding.write_text(folder / "evidence" / "{}-exceptions.txt.md".format(eid), "What: {0} Exceptions\nFor: {0}\n"
                           "Signed by: Head of Complaints, 2026-06-30\nStatus: FINAL\n".format(eid))
    check(folder)
    out = check(folder)[1]
    expect("now filed as" not in out and "Filed under another id" not in out, "two identical files under two ids are no refiling", out[-900:])

    readme = pages("README.md")
    if readme is not None:
        at = readme.index("expectations in the finding tool")
        expect("Windows" in readme[at - 300:at + 400], "the front page says a system with no pseudo-terminal runs fewer finding expectations")


def test_larger_case_one(root):
    """What a larger invented finding showed, part one: system output counts on its as-at date, a typed page leaves the document's
    signature alone, size counts typed pages, no quarter prints empty, only cited pages are named as untyped, and a
    byte-identical pair is named."""
    folder = ia(root, "system-output")
    extract = folder / "evidence" / "EV-23-extract.csv"
    finding.write_text(extract, "Month,Received,On time\n2026-05,410,402\n")
    cover = folder / "evidence" / "EV-23-extract.csv.md"
    finding.write_text(cover, "What: EV-23 Complaint system extract\nFor: M1 EV-23\n"
                       "Produced by: complaint system timeliness report, 2026-05-31\nStatus: FINAL\n")
    edit(folder / "plan.md", "| EV-21 |", "| EV-21, EV-23 |")
    append_to(folder / "closure" / "memo.md", "\nThe extract shows 410 complaints received [EV-23 p1].")
    code, out, _ = check(folder)
    expect(line_of(out, "M1 ").endswith(" Present on 2026-05-31. EV-23 was produced by the complaint system timeliness "
                                        "report on 2026-05-31, with no signature.") and "Flagged commitments: none." in out,
           "system output counts as present on its as-at date, and the page says it carries no signature", line_of(out, "M1 "))
    expect("Memo check: 14 claims, 14 tie, 0 on the list." in out and only_the_signature(code, out),
           "its ties count like a signed file's, and it does not hold up sign", out[-700:])
    edit(cover, "2026-05-31", "2026-06-03")
    out = check(folder)[1]
    expect("Flagged commitments: M1 present 3 days after its commitment." in out, "lateness counts from its as-at date", out)
    finding.write_text(extract, "Month,Received,On time\n2026-05,410,399\n")
    out = check(folder)[1]
    expect("Present, unsigned: EV-23 changed since its as-at date." in line_of(out, "M1 "),
           "system output changed after its as-at date is unsigned", line_of(out, "M1 "))
    early = ia(root, "system-output-early")
    finding.write_text(early / "evidence" / "EV-23-extract.csv", "Month,Received\n2026-03,380\n")
    finding.write_text(early / "evidence" / "EV-23-extract.csv.md", "What: EV-23 Extract\nFor: EV-23\nSigned by:\n"
                       "Produced by: complaint system, 2026-04-01\nStatus: FINAL\n")
    typed_evidence(early, "EV-24-note.md", "EV-24", "A note.", "Produced by: complaint system, 2026-04-01\n")
    edit(early / "evidence" / "EV-24-note.md", "2026-07-01", "2026-04-02")
    edit(early / "evidence" / "E-PLAN-1-board-minutes.md", "Signed by: Company Secretary, 2026-04-24",
         "Produced by: board portal, 2026-04-24")
    out = check(early)[1]
    expect("Signed before the first check on 2026-04-17, so a change before then cannot be seen: EV-24.\nProduced by a "
           "system, with no signature, before the first check on 2026-04-17, so a change before then cannot be seen: "
           "EV-23.\n" in out and "Plan approval: proposed, because E-PLAN-1 carries no signature." in out,
           "an empty Signed by line leaves the Produced by line to count, a person's signature wins over one, the page "
           "never calls system output signed, and the board's minutes need a signature", out)

    typed = ia(root, "typed-signature")
    pdf = typed / "evidence" / "EV-30-listing.pdf"
    pdf.write_bytes(simple_pdf(["Listing page one.", "The sample held 1,284 items.", ""]))
    cover = typed / "evidence" / "EV-30-listing.pdf.md"
    finding.write_text(cover, "What: EV-30 Listing\nFor: M1 EV-30\nSigned by: Head of Complaints, 2026-05-30\nStatus: FINAL\n")
    edit(typed / "plan.md", "| EV-21 |", "| EV-21, EV-30 |")
    append_to(typed / "closure" / "memo.md", "\nThe third page held 77 items [EV-30 p3].")
    out = check(typed)[1]
    expect("and the check cannot read that page: the document has no text on that page. Type it into the cover under "
           "## Page 3. To rule" in out and "  EV-30 page 3 has no text and nothing typed.\n" in out,
           "a cited page with no text asks only to be typed, and is named", block_from(out, "Memo check:"))
    edit(cover, "Status: FINAL", "Status: FINAL\nChecked by: Associate 2, 2026-11-04")
    append_to(cover, "\n## Page 3\nThe third page held 77 items.")
    code, out, _ = check(typed)
    expect(line_of(out, "M1 ").endswith("Present and signed on 2026-05-30.") and "Flagged commitments: none." in out
           and "1 on a page typed into a cover, with a Checked by line." in out and only_the_signature(code, out),
           "typing a page leaves the signature and the lateness alone, and its Checked by line lets the tie count", out)
    edit(cover, "held 77 items.", "held 77 items in all.")
    code, out, _ = check(typed, "2026-11-05")
    expect(line_of(out, "M1 ").endswith("Present and signed on 2026-05-30.") and "1 with no Checked by line." in out
           and "  EV-30's typed pages changed at the check of 2026-11-05, after its Checked by line.\n" in out
           and "Ready to sign" not in out, "a typed page changed since its Checked by line waits on a fresh one, and the "
           "signature stands", block_from(out, "Memo check:"))
    edit(cover, "Associate 2, 2026-11-04", "Associate 2, 2026-11-05")
    code, out, _ = check(typed, "2026-11-05")
    expect("with a Checked by line." in out and only_the_signature(code, out),
           "a Checked by line dated on the check that first saw the change answers it", out[-400:])
    (typed / "evidence" / "EV-31-scan.png").write_bytes(b"\x89PNG not read")
    finding.write_text(typed / "evidence" / "EV-31-scan.png.md", "What: EV-31 Scan\nFor: EV-31\n"
                       "Signed by: Head of Complaints, 2026-05-30\nStatus: FINAL\n")
    code, out, _ = check(typed, "2026-11-05")
    expect("EV-31" not in out and only_the_signature(code, out), "a page the memo does not cite is not named as untyped", out[-600:])
    out = run(["size", str(typed)])[1]
    expect("typing and comparing 1 page 0.2," in out, "size counts the pages typed, and a cover with nothing typed counts none", out)
    append_to(typed / "closure" / "memo.md", "The scan shows 5 items [EV-31 p1].")
    out = check(typed, "2026-11-05")[1]
    expect("  EV-31 page 1 cannot be read by the check, and nothing is typed.\n" in out, "a cited page is named", out)
    pdf.write_bytes(simple_pdf(["Listing page one.", "The sample held 1,284 items in all.", ""]))
    out = check(typed, "2026-11-05")[1]
    expect("EV-30 changed since it was signed" in line_of(out, "M1 "), "a change to the document itself still unsigns it", line_of(out, "M1 "))

    files = dict(MRA_FILES, **{"finding.md": MRA_FILES["finding.md"].replace("Letter date: 2026-01-15", "Letter date: 2025-11-20")})
    out = check(fresh(root, "quarter-empty", files))[1]
    expect("Quarterly progress:\n  Quarter ending 2026-03-31: 2 milestones due" in out, "a quarter with no milestone due is left out", out)

    pair = ia(root, "same-bytes")
    for name in ("EV-30-minutes.pdf", "EV-31-Scan_0715.pdf"):
        (pair / "evidence" / name).write_bytes(simple_pdf(["Minutes of the July meeting."]))
    code, out, _ = run(["covers", str(pair)])
    expect("The engagement team: evidence/EV-30-minutes.pdf and evidence/EV-31-Scan_0715.pdf hold the same bytes.\n" in out,
           "covers names a byte-identical pair", out)
    for name in ("EV-30-minutes.pdf.md", "EV-31-Scan_0715.pdf.md"):
        edit(pair / "evidence" / name, "Signed by:", "Signed by: Head of Complaints, 2026-07-01")
        edit(pair / "evidence" / name, "Status: DRAFT", "Status: FINAL")
    code, out, _ = check(pair)
    expect("Needs a person:\n  Head of Complaints: the signature, which comes first.\n  The engagement team: the same bytes in "
           "EV-30 and EV-31.\n" + ready_line(pair) in out, "check names the pair for the engagement team, and it "
           "does not stop the signature", out[-500:])


def test_larger_case_two(root):
    """What a larger invented finding showed, part two: correct dates raise no rows, a version number is a label, eval lists
    every miss after the banner, the hidden-text warning counts words, and a refused file's cover says it was not read.
    For each, a wrong value still goes on the list."""
    def rows_for(folder, *claimed):
        out = check(folder)[1]
        return all(re.search(r"\n  Line \d+: {} (is cited to|has no cite)".format(re.escape(c)), out) for c in claimed), memo_block(out)

    split = simple_pdf(["The backlog was cleared on 27\nApril 2026, and the date moved to 18\nDecember 2026.\n"
                        "March 2026 412 12\nApril 2026 380 3\nPage 1 of 3\nMarch 2026 summary"])
    out = check(with_document(root, "split-date", "EV-30-report.pdf", split,
                              "The backlog was cleared on 2026-04-27 and the date moved to 2026-12-18 [EV-30 p1]."))[1]
    expect("Memo check: 15 claims, 15 tie, 0 on the list." in out, "a day, month and year split by one line break read as one date", memo_block(out))
    expect(*rows_for(with_document(root, "split-date-wrong", "EV-30-report.pdf", split, "The count fell on 2026-04-28, "
                                   "2026-04-12 and 2026-03-03 [EV-30 p1]."), "2026-04-28", "2026-04-12", "2026-03-03"),
           "a wrong day stays on the list, and a figure before a day, as in a table row or Page 1 of 3, makes no date")

    table = simple_pdf(["Month Awaiting Older\nJul-26 2,105 0\nAug-26 2,068 37\nSep-2026 2,029 0\nQ3 2026 report"])
    out = check(with_document(root, "mon-yy", "EV-30-mi.pdf", table,
                              "In August 2026, 37 alerts were older than the standard, and in September 2026 none was [EV-30 p1]."))[1]
    expect("Memo check: 16 claims, 16 tie, 0 on the list." in out, "Excel's Aug-26 and Sep-2026 read as months of 2026", memo_block(out))
    expect(*rows_for(with_document(root, "mon-yy-wrong", "EV-30-mi.pdf", table, "In October 2026, August 2025 and on "
                                   "2026-08-26 the count moved [EV-30 p1]."), "October 2026", "August 2025", "2026-08-26"),
           "a wrong month or year stays on the list, and Aug-26 is never the 26th of August")

    period = simple_pdf(["Reviews ran on 2026-04-24, 2026-05-15 and 2026-06-30, all in Q2 2026.\n"
                         "The March 2026 count, taken on 2026-03-31, was 7,184."])
    out = check(with_document(root, "many-in-period", "EV-30-report.pdf", period,
                              "Reviews ran in Q2 2026, and the count for March 2026 was 7,184 [EV-30 p1]."))[1]
    expect("Memo check: 16 claims, 16 tie, 0 on the list." in out, "a quarter or a month ties a page with several dates inside it", memo_block(out))
    expect(*rows_for(with_document(root, "many-in-period-wrong", "EV-30-report.pdf", period, "Reviews ran in Q3 2026, and "
                                   "the count for February 2026 was 7,148 [EV-30 p1]."), "Q3 2026", "February 2026", "7,148"),
           "a wrong quarter or month stays on the list, and so does a wrong figure in the same sentence")

    mail = email_bytes(("text/plain", "As at 16 October the reviews end on 18 December, and the report follows by 29 January."),
                       head="Date: Wed, 21 Oct 2026 20:05:33 +0000\n")
    out = check(with_document(root, "email-year", "EV-30-mail.eml", mail, "The figures were as at 2026-10-16, the reviews "
                              "end on 2026-12-18 and the report follows by 2027-01-29 [EV-30 p1]."))[1]
    expect("Memo check: 16 claims, 16 tie, 0 on the list." in out, "an email's day and month take the year nearest its own date", memo_block(out))
    expect(*rows_for(with_document(root, "email-year-wrong", "EV-30-mail.eml", mail, "The report follows by 2026-01-29 [EV-30 p1]."),
                     "2026-01-29"), "a day and month in an email with the wrong year stays on the list")
    expect(*rows_for(with_document(root, "no-year-pdf", "EV-30-report.pdf", simple_pdf(["The report follows by 29 January."]),
                                   "The report follows by 2027-01-29 [EV-30 p1]."), "2027-01-29"),
           "outside an email, a day and month with no year is read as before")

    letter = MRA_FILES["finding.md"].replace(", and extend the taxonomy", ", review all complaints closed without a final "
                                             "response, and extend the taxonomy").replace("has tested the remediation.",
                                             "has tested the remediation, and will say when the finding is closed and verified.")
    quoted = fresh(root, "closed-quoted", dict(MRA_FILES, **{"finding.md": letter}))
    append_to(quoted / "plan.md", "\nThe team will review all complaints closed without a final response.\n")
    out = check(quoted)[1]
    expect("closed in plan.md" not in out, "closed in the letter's own words raises no row", out[-900:])
    append_to(quoted / "plan.md", "Complaints closed without a reply are reviewed.\nThe finding is closed and verified.\n")
    out = check(quoted)[1]
    expect("closed in plan.md does not read as a claim" in out and "closed in plan.md claims the finding is closed" in out,
           "closed in other words stays a row, and a claim that the finding is closed stays one in the letter's words", out[-900:])

    label = simple_pdf(["Procedure version 3.0 was approved. The sample held 120 items."])
    out = check(with_document(root, "version-label", "EV-30-procedure.pdf", label, "The folder holds no approval of version "
                              "3.1, v3.2 or Rev. 4.\nThe approved version 3.0 held 120 items [EV-30 p1]."))[1]
    expect("Memo check: 14 claims, 14 tie, 0 on the list." in out, "a number after version, v or Rev. is a label", memo_block(out))
    expect(*rows_for(with_document(root, "version-label-wrong", "EV-30-procedure.pdf", label, "Under version 3.0, 125 items "
                                   "and 3.1 percent failed [EV-30 p1]."), "125", "3.1 percent"),
           "a wrong figure beside a version label stays on the list")

    many = with_memo(root, "eval-every-miss", "".join("Group {} held {} items [EV-42 p1].\n\n".format(i, 1000 + i) for i in range(40)))
    typed_evidence(many, "EV-42-note.md", "EV-42", " ".join("{} items.".format(1000 + i) for i in range(40)))
    code, out, err = run(["eval", str(many)])
    caught = re.search(r"Caught (\d+) of (\d+)\.", out)
    missed = int(caught.group(2)) - int(caught.group(1)) if caught else 0
    expect(missed > 12 and out.count(" still ties.\n") == missed and " more." not in out, "eval lists every miss", out[-600:])
    expect(err.startswith(finding.CONFIDENTIAL + "\n") and "Eval: 25 of " in err, "the banner comes before the progress lines", err[:300])
    expect("A figure with two digits swapped: 40 planted, 40 caught." in out, "a planted wrong figure is still caught", out[:900])

    bar = one_page_pdf(SHOWN + " 0 0 0 rg " + BAR + " 0 g BT /F1 14 Tf 72 620 Td (The sample held 1,284 items.) Tj ET")
    hidden = with_document(root, "hidden-count", "EV-30-bar.pdf", bar, "The listing held 9,999 items [EV-30 p1].")
    (hidden / "evidence" / "EV-31-clip.pdf").write_bytes(one_page_pdf(
        "q 0 0 130 792 re W n BT /F1 14 Tf 72 700 Td (Confidential) Tj ET Q BT /F1 14 Tf 72 620 Td (Held 7.) Tj ET", objects=WIDTHS))
    out = run(["covers", str(hidden)])[1]
    expect('evidence/EV-30-bar.pdf: 1 page, 1 with text; 5 words a reader cannot see left out on page 1: "The", "sample", '
           '"held", "9,999" and "items".' in out and 'evidence/EV-31-clip.pdf: 1 page, 1 with text; 1 word a reader cannot see left '
           'out on page 1: "tial".' in out, "the hidden-text warning says how many words were left out, and which", out)
    out = check(hidden)[1]
    expect("9,999 is cited to EV-30 p1, and the page does not hold it; the nearest figure on the page is 1,284. The page also "
           "holds 5 words a reader cannot see, which the check leaves out." in out, "a hidden figure stays on the list, and its "
           "row counts the words left out", memo_block(out))

    refused = ia(root, "refused-cover")
    (refused / "evidence" / "EV-31-report.docx").write_bytes(word_bytes(
        root, '<w:p><w:ins w:id="1" w:author="a" w:date="2026-01-01T00:00:00Z"><w:r><w:t>Held 7.</w:t></w:r></w:ins></w:p>'))
    out = run(["covers", str(refused)])[1]
    cover = refused / "evidence" / "EV-31-report.docx.md"
    text = cover.read_text(encoding="utf-8")
    expect("evidence/EV-31-report.docx: not read: the Word file still holds tracked changes. Draft cover written" in out
           and "Source: typed by a person, because the check did not read the file: the Word file still holds tracked changes\n" in text
           and "read from the document by the check" not in text and "The check cannot read this file. Type each page the memo cites" in text,
           "a refused file's cover says it was not read, why, and that a person types each cited page", text)
    finding.write_text(cover, text.replace("Signed by:\nStatus: DRAFT", "Signed by: Head of Complaints, 2026-07-01\nStatus: FINAL\n"
                                           "Checked by: Associate 2, 2026-07-02") + "\n## Page 1\nHeld 7.\n")
    append_to(refused / "closure" / "memo.md", "\nThe report held 8 items [EV-31 p1].\n")
    expect(*rows_for(refused, "8"), "a wrong figure against a refused file's typed page stays on the list")


def test_larger_case_three(root):
    """What a larger invented finding showed, part three: a title from the letter is no name, a refusal over a term the check
    took from the letter offers role-words.txt even in a file name, new takes a path outside the kit and writes no
    SYNTHETIC line, and a label number never becomes the day of a joined date."""
    names = finding.harvest_names({"Institution": "Wrenfield Example Bank"}, {"Concern": (
        "The bank's AML Alert Handling Procedure sets the standard, and the Lookback Methodology and the Quality Assurance "
        "Procedures say how. Priya Natarajan wrote the Customer Outcomes Policy. Plant Hire Services was not reviewed.")})
    expect("Priya Natarajan" in names and "Plant Hire Services" in names and not any(n in names for n in (
        "Alert Handling Procedure", "Lookback Methodology", "Quality Assurance Procedures", "Customer Outcomes Policy")),
           "a run holding a document word is a title and stays off the deny list, while a name stays on", str(names))

    titled = ia_with(root, "r3-title", lambda files: files.update({"finding.md": files["finding.md"].replace(
        "Customers who complain are", "Under the Complaint Handling Procedure, customers who complain are")}))
    (titled / "evidence" / "EV-60-Complaint Handling Procedure v3.csv").write_bytes(b"a,b\n1,2\n")
    out = run(["covers", str(titled)])[1]
    expect("Refused" not in out and "evidence/EV-60-Complaint Handling Procedure v3.csv: 1 page" in out,
           "covers runs on a file that keeps the institution's name, when the name holds a title from the letter", out)
    state = state_of(titled)
    state["deny"]["names"].append("Complaint Handling Procedure")
    finding.write_text(titled / finding.STATE_NAME, json.dumps(state, indent=2) + "\n")
    out = check(titled)[1]
    expect("Refused" not in out and "Deny list: 3 names." in out and "Refused" not in run(["covers", str(titled)])[1],
           "a title an earlier check saved clears too", out[-400:])

    person = ia_with(root, "r3-person", lambda files: files.update({"finding.md": files["finding.md"].replace(
        "Customers who complain are", "As Placeholder Person found, customers who complain are")}))
    (person / "evidence" / "EV-60-Placeholder Person notes.csv").write_bytes(b"a,b\n1,2\n")
    code, out, _ = run(["covers", str(person)])
    expect(code == 1 and out == refusal('Refused: "Placeholder Person" ' + IN_A_FILE_NAME),
           "a refusal over a run from the letter in a file name offers role-words.txt before a rename", out)
    finding.write_text(person / "role-words.txt", "Placeholder Person\n")
    (person / "evidence" / "EV-61-Wrenfield Example Bank extract.csv").write_bytes(b"a,b\n1,2\n")
    code, out, _ = run(["covers", str(person)])
    expect(code == 1 and out == refusal('Refused: "Wrenfield Example Bank" ' + RENAME),
           "role-words.txt clears the run, and the institution's full name in a file name keeps the rename refusal", out)

    work = root / "r3-new"
    work.mkdir()
    code, out, _ = run(["new", "run/MRA-OPS-09"], cwd=work)
    made = work / "run" / "MRA-OPS-09" / "finding.md"
    expect(code == 0 and out.startswith("Made run/MRA-OPS-09. Fill the header lines") and made.is_file()
           and made.read_text(encoding="utf-8").startswith("# Finding MRA-OPS-09\n"), "new takes a path whose last part is the id", out)
    code, out, _ = run(["new", "run/MRA-OPS-09"], cwd=work)
    expect(code == 1 and out == "Refused: run/MRA-OPS-09 already exists.\n", "new names the path it refuses", out)
    copy = kit_copy(root, "r3-kit")
    for cwd, arg in ((copy, "MRA-OPS-09"), (copy / "finding", "cases/MRA-OPS-09"), (work, str(copy / "library" / "MRA-OPS-09")),
                     (copy, "../findings/MRA-OPS-09")):
        proc = subprocess.run([sys.executable, "-I", str(copy / "finding" / "finding.py"), "new", arg], cwd=str(cwd),
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, input=b"")
        out = proc.stdout.decode("utf-8", "replace").replace("\r\n", "\n")
        inside = not arg.startswith("..")
        expect((proc.returncode, out) == ((1, "Refused: {} is inside the kit's own folders. Make the finding folder outside the kit, "
               "such as ../findings/MRA-OPS-09 from the kit root.\n".format(arg)) if inside else (0, out)) and inside != (
               root / "findings" / "MRA-OPS-09" / "finding.md").is_file() and not any(
               path.name == "MRA-OPS-09" for path in copy.rglob("*")), "new refuses a path inside the kit, and makes one outside it", out)

    pdf = simple_pdf(["Counts by month, see Table 3\nMarch 2026 412\nSee Page 2\nApril 2026 380\nSection 4\nMay 2026 377"])
    out = check(with_document(root, "r3-label-day", "EV-30-report.pdf", pdf, "The counts for March 2026, April 2026 and "
                              "May 2026 came from the monthly table [EV-30 p1]."))[1]
    expect("Memo check: 16 claims, 16 tie, 0 on the list." in out, "a month after a label number still reads as its month", memo_block(out))
    wrong = with_document(root, "r3-label-day-wrong", "EV-30-report.pdf", pdf, "The counts were taken on 2026-03-03, 2026-04-02 "
                          "and 2026-05-04 [EV-30 p1].")
    out = check(wrong)[1]
    expect(all(re.search(r"\n  Line \d+: {} is cited to EV-30 p1".format(d), out) for d in ("2026-03-03", "2026-04-02", "2026-05-04")),
           "a label number such as Table 3, Page 2 or Section 4 never becomes the day of a joined date", memo_block(out))

    found = pages("README.md", "finding/README.md", "finding/DEMO.md")
    if found is not None:
        expect(not any("Delete this line" in page for page in found) and "finding/finding new ../findings/DEMO-01" in found[2],
               "the pages show new writing no SYNTHETIC line, outside the kit")


def test_larger_case_four(root):
    """What a larger invented finding showed, part four: an evidence id comes only from the folder, an email's time and
    zone are no figures, a ruling left behind names the row that now prints its claim, and the left-out-text warning
    names the words."""
    intake = ia(root, "t2-intake")
    edit(intake / "plan.md", "| EV-22 |", "| EV-22, CHG-2026-03952 |")
    bank = ("MRA-OPS-09 response.csv", "IA-2026-22 audit report.csv", "MRM-2026-017 TM Scenario Validation Report FINAL.csv",
            "MRM-2026-017 final report and sign-off.msg")
    for k, name in enumerate(bank + ("CHG-2026-03952 change record.csv", "EV-40 backlog report.csv", "EV-40 sign-off.csv")):
        (intake / "evidence" / name).write_bytes("a,{}\n".format(k).encode())
    (intake / "evidence" / "EV-07 TM Alert Backlog MI - Mar 2026 v2 FINAL.xlsx").write_bytes(
        book_bytes(root, [("MI", None, '<sheetData><row r="1"><c r="A1"><v>4977</v></c></row></sheetData>')]))
    code, out, _ = run(["covers", str(intake)])
    rename = ". Rename it to start with an evidence id plan.md lists or an EV id, such as EV-12, and keep the file's own name after the id."
    expect(code == 1 and all(line_of(out, "evidence/" + name).endswith(rename) and not (intake / "evidence" / (name + ".md")).exists()
                             for name in bank), "an institution's own reference number raises no id, and the screen says what to do", out)
    expect(line_of(out, "evidence/EV-07 TM Alert").endswith("Draft cover written for evidence id EV-07.")
           and line_of(out, "evidence/CHG-2026-03952").endswith("Draft cover written for evidence id CHG-2026-03952."),
           "an EV id or an id the plan lists, with the file's own name after it, gets its cover", out)
    expect(all(line_of(out, "evidence/" + name).endswith(". Another file's name starts with EV-40 too, so this file gets no cover; "
                                                          "give each its own evidence id.") and not (intake / "evidence" / (name + ".md")).exists()
               for name in ("EV-40 backlog report.csv", "EV-40 sign-off.csv")), "two files that start with one id get no cover", out)
    out = check(intake)[1]
    uncounted = out.split("Not counted\n", 1)[-1].split("\n\n", 1)[0]
    expect(all("evidence/{}, which has no cover file".format(name) in uncounted for name in bank + ("EV-40 sign-off.csv",))
           and "EV-07 TM" not in uncounted and "CHG-2026" not in uncounted, "the check counts the files covers counts", uncounted)
    taken = ia(root, "t2-intake-taken")
    (taken / "evidence" / "EV-22 timeliness report signed.csv").write_bytes(b"a,9\n")
    code, out, _ = run(["covers", str(taken)])
    expect(code == 1 and line_of(out, "evidence/EV-22 timeliness").endswith(". evidence/EV-22-timeliness-report.md carries EV-22 "
           "already, so this file gets no cover; give each its own evidence id.") and "Not ready" not in check(taken)[1],
           "a document under an id a header already carries gets no cover, so the check still reads, and the screen names both", out)

    mail = email_bytes(("text/plain", "The backlog stood at 4,977 alerts."), head="Date: Wed, 21 Oct 2026 20:05:33 +0000\n")
    out = check(with_document(root, "t2-zone", "EV-30-mail.eml", mail, "On 2026-10-21 the backlog stood at 4,977 alerts [EV-30 p1]."))[1]
    expect("Memo check: 15 claims, 15 tie, 0 on the list." in out, "the date on an email's Date line still ties", memo_block(out))
    out = check(with_document(root, "t2-zone-wrong", "EV-30-mail.eml", mail, "The backlog stood at 0000 alerts, 33 of them old [EV-30 p1]."))[1]
    expect(all(re.search(r"\n  Line \d+: {} is cited to EV-30 p1".format(c), out) for c in ("0000", "33")),
           "the time and zone on an email's Date line are no figures", memo_block(out))

    left = fresh(root, "t2-ruling-left")
    append_to(left / "closure" / "rulings.md", "Line 10 | EV-12 draft #81b3b231 | fix the evidence | Head of Complaints | 2026-11-04 | "
              "The review needs its signature.\n")
    expect("names no row" not in check(left)[1], "a fix ruling that names its row is no stray")
    memo = left / "closure" / "memo.md"
    finding.write_text(memo, memo.read_text(encoding="utf-8").replace("This memo is a draft for the Head of Complaints. It records "
                       "the evidence held for each milestone so far. M2, M3 and M4 still lack signed evidence, so the memo is not ready "
                       "for internal audit.\n\n", "").replace(" that the earlier procedure had logged as service issues", "").replace(
                       " in its sample [EV-12 p2]", " [EV-12 p2]"))
    out = check(left)[1]
    expect(re.search(r"\n  Ruling at rulings\.md line 4 names no row: the row on line 6 prints March 2026 #[0-9a-f]{8}\.\n", out)
           and re.search(r"\n  Ruling at rulings\.md line 5 names no row: the row on line 8 prints EV-12 draft #[0-9a-f]{8}\.\n", out),
           "a ruling left behind when its row's mark changed names the row, a fix ruling too", memo_block(out))

    review = ia(root, "t2-left-out")
    finding.write_text(review / "denylist.txt", "Natarajan\n")
    (review / "evidence" / "EV-30-review.pdf").write_bytes(one_page_pdf("BT /F1 14 Tf 72 660 Td (Natarajan signed off 1,284 items in "
                                                                        "the sample review.) Tj ET 0 0 0 rg 60 650 500 30 re f BT /F1 14 Tf 72 600 Td (The review held 1,284 items.) Tj ET"))
    out = run(["covers", str(review)])[1]
    expect('1 page, 1 with text; 9 words a reader cannot see left out on page 1: "signed", "off", "1,284", "items", "in" and 4 more. '
           "Draft cover written" in out and "Natarajan" not in out, "the warning names up to five words, never one on the deny list", out)


def test_larger_case_five(root):
    """What a larger invented finding showed, part five: a document approved by a separate record counts on that
    record's date, material an institution never signs ties and never counts toward a milestone, and a milestone's date and
    lateness come from the file plan.md marks done."""
    folder = ia(root, "t2-approved")
    method, approval = folder / "evidence" / "EV-27-qa-method.md", folder / "evidence" / "EV-29-approval.md"
    finding.write_text(method, "What: EV-27 QA method\nFor: M1 EV-27\nApproved by: EV-29\nStatus: FINAL\n\n## Page 1\n\n"
                       "The QA method samples 40 complaints a month.\n")
    finding.write_text(approval, "What: EV-29 Approval of the QA method\nFor: EV-29\nSigned by: Head of Complaints, 2026-05-20\n"
                       "Status: FINAL\n\n## Page 1\n\nI approve the QA method.\n")
    edit(folder / "plan.md", "| EV-21 |", "| EV-21, EV-27 |")
    append_to(folder / "closure" / "memo.md", "\nThe QA method samples 40 complaints a month [EV-27 p1].")
    code, out, _ = check(folder)
    expect(line_of(out, "M1 ").endswith(" Present and signed on 2026-05-28. EV-27 was approved by EV-29 on 2026-05-20.")
           and "Memo check: 14 claims, 14 tie, 0 on the list." in out and only_the_signature(code, out),
           "a document approved by a separate record counts on its date, and the milestone line names the record", out)
    edit(approval, "2026-05-20", "2026-06-03")
    out = check(folder)[1]
    expect("Flagged commitments: M1 signed 3 days after its commitment." in out and line_of(out, "M1 ").endswith(
        "Present and signed on 2026-06-03. EV-27 was approved by EV-29 on 2026-06-03."), "lateness counts from the approval's date", out)
    for where, old, new, why in (
            (method, "Status: FINAL", "Status: FINAL\nRevised: 2026-06-10", "EV-27 was revised on 2026-06-10, after its approval of 2026-06-03"),
            (approval, "Status: FINAL", "Status: DRAFT", "EV-27 is approved by EV-29, and EV-29 is a draft"),
            (approval, "Signed by: Head of Complaints", "Produced by: complaint system", "EV-27 is approved by EV-29, which carries no signature"),
            (approval, "I approve", "I approved", "EV-27 is approved by EV-29, and EV-29 changed since it was signed"),
            (method, "40 complaints", "45 complaints", "EV-27 changed since it was approved")):
        edit(where, old, new)
        code, out, _ = check(folder)
        expect("Present, unsigned: {}. SLIPPED".format(why) in line_of(out, "M1 ") and "  Head of Complaints: M1" in out
               and "Ready to sign" not in out, "an approved document is unsigned when " + why, line_of(out, "M1 "))
        edit(where, new, old)
    expect(only_the_signature(*check(folder)[:2]), "each put back, it counts again")
    approval.unlink()
    edit(folder / "plan.md", "| EV-21, EV-27 |", "| EV-21 |")
    code, out, _ = check(folder)
    expect("is cited to EV-27 p1, which is not signed: EV-27 is approved by EV-29, which is missing." in out
           and "1 row before rulings" in run(["size", str(folder)])[1], "a cited approved document whose record is missing goes "
           "on the list, on the page and in size", memo_block(out))
    edit(folder / "plan.md", "| EV-21 |", "| EV-21, EV-27 |")
    code, out, _ = check(folder)
    expect("Present, unsigned: EV-27 is approved by EV-29, which is missing." in line_of(out, "M1 ") and code == 1
           and run(["sign", str(folder), "--today", NOW], stdin=answers())[0] == 1, "a missing record unsigns it, and sign refuses", out)
    early = ia(root, "t2-approved-early")
    finding.write_text(early / "evidence" / "EV-27-qa-method.md", method.read_text(encoding="utf-8"))
    finding.write_text(early / "evidence" / "EV-29-approval.md", "What: EV-29 Approval\nFor: EV-29\nSigned by: Head of Complaints, "
                       "2026-04-01\nStatus: FINAL\n\nI approve the QA method.\n")
    out = check(early)[1]
    expect("so a change before then cannot be seen: EV-27 (approved by EV-29) and EV-29.\n" in out,
           "the early list names the approving record beside the document", out[-900:])
    append_to(early / "closure" / "memo.md", "The QA method samples 45 complaints a month [EV-27 p1].")
    add_ruling(early, "45")
    edit(early / "evidence" / "EV-29-approval.md", "2026-04-01", "2026-11-05")
    out = check(early, "2026-11-05")[1]
    expect("does not count: EV-27 was approved by EV-29 on 2026-11-05, after the ruling's date of 2026-11-04" in out,
           "a ruling dated before the approving record names the record", memo_block(out))

    deck = ia(root, "t2-never")
    finding.write_text(deck / "evidence" / "EV-30-training-deck.md", "What: EV-30 Training deck\nFor: M1 EV-30\n"
                       "Never signed: training deck\nStatus: FINAL\n\n## Page 1\n\nThe training covers 12 disposition rules.\n")
    append_to(deck / "closure" / "memo.md", "\nThe training covers 12 disposition rules [EV-30 p1].")
    code, out, _ = check(deck)
    expect("Memo check: 14 claims, 14 tie, 0 on the list." in out and only_the_signature(code, out)
           and "14 claims on the memo check, 0 rows before rulings" in run(["size", str(deck)])[1],
           "a cited file never signed ties and puts no row on the list, on the page and in size", out[-900:])
    edit(deck / "plan.md", "| EV-21 |", "| EV-21, EV-30 |")
    code, out, _ = check(deck)
    expect(line_of(out, "M1 ").endswith(" Present and signed on 2026-05-28. Never signed: EV-30 (training deck).")
           and "Flagged commitments: none." in out and only_the_signature(code, out),
           "listed beside a signed file, it neither signs nor blocks the milestone, and the line names it", out)
    edit(deck / "plan.md", "| EV-22 |", "| EV-30 |")
    code, out, _ = check(deck)
    expect("Present, unsigned: EV-30 is never signed, so list in plan.md the file that shows M2 done." in line_of(out, "M2 ")
           and "  Complaints QA lead: M2.\n" in out and "Ready to sign" not in out and "Flagged commitments: M2 slipped" in out,
           "a milestone listing only such files reads unsigned and asks for the file that shows it done", out)
    code, out, _ = run(["sign", str(deck), "--today", NOW], stdin=answers())
    expect(code == 1 and out == refusal("Refused: M2 is below signed."), "sign refuses it", out)

    done = ia(root, "t2-done")
    ev = done / "evidence"
    finding.write_text(ev / "EV-27-roster.csv", "Analyst,Completed\nAnalyst 1,2026-05-15\n")
    finding.write_text(ev / "EV-27-roster.csv.md", "What: EV-27 Training roster\nFor: M1 EV-27\n"
                       "Produced by: learning system roster, 2026-05-15\nStatus: FINAL\n")
    finding.write_text(ev / "EV-28-training-report.md", "What: EV-28 Training completion report\nFor: M1 EV-28\n"
                       "Signed by: Head of Complaints, 2026-05-18\nStatus: FINAL\n\n## Page 1\n\nAll 14 analysts were trained.\n")
    edit(done / "plan.md", "| 2026-05-31 |", "| 2026-04-30 |")
    edit(done / "plan.md", "| EV-21 |", "| EV-28, EV-27 (done) |")
    code, out, _ = check(done)
    expect(line_of(out, "M1 ").endswith(" committed 2026-04-30. Present on 2026-05-15, the date of EV-27, which plan.md marks done. "
                                        "EV-27 was produced by the learning system roster on 2026-05-15, with no signature.")
           and "Flagged commitments: M1 present 15 days after its commitment." in out and only_the_signature(code, out),
           "a report signed 2026-05-18 beside a roster produced 2026-05-15 and marked done reads 15 days late", out)
    expect("2 milestones" in run(["size", str(done)])[1], "size reads a marked Evidence cell")
    edit(done / "plan.md", "EV-27 (done)", "EV-27")
    expect("Flagged commitments: M1 signed 18 days after its commitment." in check(done)[1], "with no mark the newest date counts")
    edit(done / "plan.md", "EV-27 |", "EV-27 (Done), EV-31 |")
    expect("Present, unsigned: EV-31 is missing." in line_of(check(done)[1], "M1 "), "every other listed file is still needed")
    finding.write_text(ev / "EV-31-deck.md", "What: EV-31 Deck\nFor: M1 EV-31\nNever signed: training deck\nStatus: FINAL\n\nRules.\n")
    edit(ev / "EV-28-training-report.md", "Status: FINAL", "Status: DRAFT")
    expect("Present, unsigned: EV-28 is a draft." in line_of(check(done)[1], "M1 "), "an unsigned file beside the mark keeps it unsigned")
    edit(ev / "EV-28-training-report.md", "Status: DRAFT", "Status: FINAL")
    code, out, _ = check(done)
    expect("Present on 2026-05-15, the date of EV-27" in line_of(out, "M1 ") and only_the_signature(code, out),
           "a never-signed file beside the mark does not block it", line_of(out, "M1 "))
    edit(done / "plan.md", "EV-27 (Done), EV-31 |", "EV-27, EV-31 (done) |")
    expect("Present, unsigned: EV-31 is never signed, so list in plan.md the file that shows M1 done." in line_of(check(done)[1], "M1 "),
           "a never-signed file cannot be the completion file")
    edit(done / "plan.md", "EV-28, EV-27, EV-31 (done) |", "EV-28 (done), EV-27 (done) |")
    code, out, _ = check(done)
    expect(out == refusal("Not ready: plan.md line 6 marks EV-28 and EV-27 done; mark only the file that completes M1."),
           "two marks in one cell are refused", out)
    edit(done / "plan.md", "EV-28 (done), EV-27 (done) |", "EV-28, EV-27 (done) |")
    expect(sign_folder(done)[0] == 0, "sign goes ahead on a marked plan")
    marked = ia(root, "t2-done-covers")
    edit(marked / "plan.md", "| EV-21 |", "| EV-21, EV-40 (done) |")
    (marked / "evidence" / "EV-40 roster.csv").write_bytes(b"Analyst,Completed\nAnalyst 1,2026-05-15\n")
    run(["covers", str(marked)])
    expect("For: M1 EV-40\n" in (marked / "evidence" / "EV-40 roster.csv.md").read_text(encoding="utf-8"),
           "covers finds the milestone of a file marked done")


def test_screens_in_detail(root):
    """The screens: an ambiguous row lists each distinct value once, covers, eval and size refuse --today in words, a
    draft What line keeps a date whole, covers says when a Word file's comments were not read, and code found repeated
    is written once."""
    folder = ia(root, "c5-ambiguous")
    typed_evidence(folder, "EV-30-note.md", "EV-30", "The rates were 0, 0, 0.0, 0.47 and 0 across the teams, and 5 thousand, "
                   "5,000, (5,000) and 4,600 items were held.")
    append_to(folder / "closure" / "memo.md", "\nThe error rate was 0 at the lowest team [EV-30 p1]. The team held 5 thousand items [EV-30 p1].")
    out = check(folder)[1]
    expect("is cited to EV-30 p1, and 2 different values on the page match it: 0 and 0.47. To rule" in out
           and "is cited to EV-30 p1, and 2 different values on the page match it: 5 thousand and 4,600. To rule" in out,
           "an ambiguous figure lists each value the engine counts as distinct once, so the count and the list agree", memo_block(out))

    drafts = ia(root, "c5-what")
    names = ("EV-30 Extract BRC minutes 2026-01-14 - plan approval - certified.csv", "EV-31 Pack 2026_02_03 _ final_v2 20260203.csv")
    for k, name in enumerate(names):
        (drafts / "evidence" / name).write_bytes("a,{}\n".format(k).encode())
    for verb in ("covers", "eval", "size"):
        for extra in (["--today", NOW], ["--today=" + NOW]):
            code, out, err = run([verb, str(drafts)] + extra)
            expect(code == 2 and out == "" and err == "finding: {} takes no --today\n{}\n".format(verb, finding.USAGE),
                   "{} {} is a usage error that names the verb".format(verb, extra[0]), err)
    expect(not any((drafts / "evidence" / (name + ".md")).exists() for name in names), "covers refused with --today writes no cover")
    run(["covers", str(drafts)])
    whats = [line_of((drafts / "evidence" / (name + ".md")).read_text(encoding="utf-8"), "What: ") for name in names]
    expect(whats == ["What: EV-30 Extract BRC minutes 2026-01-14 plan approval certified", "What: EV-31 Pack 2026_02_03 final v2 20260203"],
           "a draft What line keeps a date in the file name whole and one space between words", str(whats))

    word = ia(root, "c5-comments")
    comment = '<w:comment w:id="{}"><w:p><w:r><w:t>{}</w:t></w:r></w:p></w:comment>'
    for name, notes in (("EV-30 Lookback Interim Report v0.9 DRAFT.docx", ["Reviewer note one.", "Two.", "Three.", ""]),
                        ("EV-31 one comment.docx", ["Only one."]), ("EV-32 no comments.docx", None)):
        with zipfile.ZipFile(str(word / "evidence" / name), "w") as zf:
            zf.writestr("word/document.xml", "<w:document {}><w:body>{}</w:body></w:document>".format(
                WORD_NS, word_run("The lookback found {} items.".format(len(name)))))
            if notes is not None:
                zf.writestr("word/comments.xml", "<w:comments {}>{}</w:comments>".format(
                    WORD_NS, "".join(comment.format(k, text) for k, text in enumerate(notes))))
    out = run(["covers", str(word)])[1]
    expect(line_of(out, "evidence/EV-30 ").endswith(".docx: 1 page, 1 with text; 3 comments not read. Draft cover written for evidence id EV-30.")
           and line_of(out, "evidence/EV-31 ").endswith(".docx: 1 page, 1 with text; 1 comment not read. Draft cover written for evidence id EV-31.")
           and line_of(out, "evidence/EV-32 ").endswith(".docx: 1 page, 1 with text. Draft cover written for evidence id EV-32."),
           "covers says on a Word file's line how many comments holding text were not read", out)

    moved = ia(root, "c5-renamed-count")
    typed_evidence(moved, "EV-30-note.md", "EV-30", "The sample held 1,284 items.")
    append_to(moved / "closure" / "memo.md", "\nThe sample held 1,284 items [EV-30 p1].")
    check(moved)  # records EV-30 by its path and by its id
    (moved / "evidence" / "EV-30-note.md").rename(moved / "evidence" / "EV-30-renamed.md")
    edit(moved / "evidence" / "EV-30-renamed.md", "The sample held", "The sample still held")
    out = check(moved)[1]
    expect("which is not signed: EV-30 changed since it was signed." in out and "14 claims, 13 tie, 1 on the list." in out
           and "1 row before rulings" in run(["size", str(moved)])[1],
           "a signed file renamed and then changed counts the same in check and size", out[-600:])

    source = (HERE / "finding.py").read_text(encoding="utf-8")
    for pattern, most, label in (('if args[0] == "', 0, "main finds its verb in one table"),
                                 ("sys.path.insert", 1, "the kit's modules join the import path in one place"),
                                 ('"  Not checked: ', 1, "the figures in words, years and two-digit years print through one loop"),
                                 ("and the page does not hold it; the ", 1, "a figure or a date not found reads through one branch"),
                                 ("a file changed while sign was running", 3, "sign's last two refusals of a changed file are one"),
                                 ("files_now", 0, "sign keeps no list of files it never reads")):
        expect(source.count(pattern) == most, label, "{} times".format(source.count(pattern)))
    code, _, err = run(["nosuchverb"])
    expect(code == 2 and err == finding.USAGE + "\n", "a verb the table does not hold is still a usage error", err)


def test_pages_against_the_tool(root):
    """The pages: what the check compares and what a reviewer still reads for, what the claim count holds, the row no
    ruling answers, two files with the same bytes, the larger run on the front page, and pasted screens that are the
    tool's real output at this release."""
    record_mod = finding.engine()[0]
    lines = ("The ticket CHG-2026-04471 set S-07 for analyst E11471 at L2 [EV-21 p1].",
             'The letter\'s action 6 asked for "letters within 5 business days" [EV-21 p1].')
    claimed = [[c["claimed"] for c in finding.memo_claims(line + "\n", record_mod)[0]] for line in lines]
    expect(claimed == [[], ["6", '"letters within 5 business days"', "5"]],
           "a number joined to letters is no claim, and one standing apart counts, inside a quotation too", str(claimed))
    two = ia(root, "c5-claim-count")
    append_to(two / "closure" / "memo.md", "\n" + "\n".join(lines))
    out = check(two)[1]
    expect("Memo check: 16 claims," in out, "a two-line memo of ids and a quotation adds the three claims the rule names", memo_block(out))
    noted = ia(root, "c5-plan-note")
    unprinted = lambda screen: re.sub(r"fingerprint is \w+", "", screen)  # noqa: E731
    before = unprinted(check(noted)[1])
    append_to(noted / "plan.md", "\nEV-31 held the same bytes as EV-30, so it was moved out of the folder before the first check.")
    after = unprinted(check(noted)[1])
    expect(after == before, "a note below plan.md's table changes nothing on the page but the fingerprint", diff_hint(after, before))
    found = pages("README.md", "finding/README.md", "finding/DEMO.md", "assistant/draft-memo.md", "assistant/propose-rulings.md",
                  "assistant/draft-covers.md")
    if found is None:
        return
    readme, guide, demo, memo_page, rulings_page, covers_page = found

    said = "The check ties each figure, date and quotation to its cited page, and it does not compare documents with each other."
    part = page_section(guide, "## Check").strip()
    expect(part.startswith(said) and guide.count("does not compare documents") == 1 and "does not compare documents" not in readme
           and "](finding/README.md#check)" in readme,
           "the Check section opens with what the check compares, said once, and the front page points to it", part[:300])
    paras = part.split("\n\n")
    bullets = paras[1].splitlines() if len(paras) > 1 else []
    topics = ("later than the one approved", "disagree between documents", "scanned page", "before their training", "status report")
    expect(0 < len(bullets) <= 5 and all(b.startswith("- ") for b in bullets) and all(any(t in b for b in bullets) for t in topics)
           and not re.search(r"\d|EV-|MRA-", "".join(bullets)),
           "beside it, a reviewer's list of at most five lines in general words", "\n".join(bullets))
    expect("stands apart from letters" in memo_page and "E11471, L2, S-07 or CHG-2026-04471" in memo_page
           and "inside a quotation counts as well as the quotation" in memo_page and "without digits" not in memo_page,
           "the memo procedure says what the claim count holds, as the code reads it")
    expect("asks for a page to be typed" in rulings_page and "never by a ruling" in rulings_page and "Checked by" in rulings_page,
           "the rulings procedure answers a row that asks for a typed page by typing it, never by a ruling")
    expect(all(s in covers_page for s in ("same bytes", "keep one in evidence/", "move the other out of the finding folder",
                                          "below the table", "before the first check")),
           "the covers procedure says what to do with two files that hold the same bytes")
    status = page_section(readme, "## Status")
    expect(all(s in status for s in ("61 files and 173 pages", "1 of the 13 traps", "caught all 11 traps the run exercised",
                                     "the other 2 were never tried", "the same agent that drafted the memo", "no financial institution has used it",
                                     "built with AI assistance under the author's direction"))
           and "caught all 13" not in readme, "the front page states the larger run's result and who reviewed it", status[-500:])

    # The pasted screens: this release on every page, IA-CMP-02's fingerprint, and each line a line the tool prints.
    full = finding.kit_release()[0]
    version = full.partition("+site.")[0]
    numbered = lambda screen: screen.replace("kit release " + full + ".", "kit release " + version + ".")  # noqa: E731

    def real(block, screen):
        """True when every line of a pasted block, but a marked trim or an exit code, is a line of the screen."""
        lines = set(numbered(screen).splitlines())
        return bool(block.strip()) and all(line in lines for line in block.splitlines() if line != "..." and not line.startswith("[exit "))

    blocks = lambda text: text.split("```")[1::2]  # noqa: E731
    shown = re.findall(r"kit release (\S+?)\.\n", readme + demo)
    expect(len(shown) == 3 and set(shown) == {version} and "RegRem Engine {}`".format(version) in demo
           and "only on release {}.".format(version) in demo and "open in {} and".format(version) in guide
           and "such as {}+site.1".format(version) in guide and "such as {}+site.1".format(version) in readme,
           "the screens, the walk and the known limits name this release", ", ".join(shown))
    cases = root / "c5-cases"
    shutil.copytree(str(CASES), str(cases))
    ia_out, mra_out = check(cases / "IA-CMP-02")[1], check(cases / "MRA-CMP-07")[1]
    fp = finding.fingerprint(cases / "IA-CMP-02")
    printed = [x for group in re.findall(r"fingerprint is ([0-9a-f]{8})\b|Fingerprint ([0-9a-f]{64})|confirm: ([0-9a-f]{8})\n|"
                                         r"fingerprint ([0-9a-f]{8})\. Written", readme + demo) for x in group if x]
    if "+site." in full:
        # A site change can move the fingerprint, and the pages print the numbered release's. So a site version checks
        # that the pages print one fingerprint, and lets it stand in for this kit's own on the screens compared below.
        expect(len(printed) == 2 and len(set(printed)) == 1,
               "at a site version the pages print one fingerprint for IA-CMP-02, the numbered release's", ", ".join(printed))
        if printed:
            ia_out = ia_out.replace(fp[:8], printed[0])
    else:
        expect(len(printed) == 2 and all(fp.startswith(x) for x in printed),
               "the pages print IA-CMP-02's fingerprint at this release", "{} against {}".format(sorted(set(printed)), fp))
    step3 = page_section(demo, "## 3. Read the invented finding").split("```")[3]
    expect(step3.strip("\n") + "\n" == numbered(mra_out), "the walk's step 3 is the whole check screen",
           diff_hint(step3.strip("\n") + "\n", numbered(mra_out)))
    walk = cases / "MRA-CMP-07-ruled"
    shutil.copytree(str(cases / "MRA-CMP-07"), str(walk))
    append_to(walk / "closure" / "rulings.md", "Line 16 | sample period for M2 #106ddd50 | cleared | Head of Complaints | 2026-11-04 | "
              "The sample spans the fix on purpose, to compare error rates before and after it.")
    ruled = check(walk)[1]
    (walk / "closure" / "rulings.md").unlink()
    bare = check(walk)[1]
    sheet = cases / "MRA-CMP-07-pdf"
    shutil.copytree(str(cases / "MRA-CMP-07"), str(sheet))
    shutil.copy2(str(HERE / "samples" / "EV-30-sample-listing.pdf"), str(sheet / "evidence"))
    covered = run(["covers", str(sheet)])[1]
    shutil.rmtree(str(sheet))
    shutil.rmtree(str(walk))
    evaluated, sized = run(["eval", str(cases / "IA-CMP-02")])[1], run(["size", str(cases)])[1]
    front = [b for b in blocks(readme) if b.startswith("text\n")]
    checks = [("the front page's eval", next((b for b in front if "Eval of the memo check" in b), ""), evaluated),
              ("the front page's check", next((b for b in front if "Finding MRA-CMP-07" in b), ""), mra_out),
              ("the walk's step 6", blocks(page_section(demo, "## 6. A finding that waits only on people"))[1], ia_out),
              ("the walk's step 7", blocks(page_section(demo, "## 7. The list"))[2], bare),
              ("the walk's step 8", blocks(page_section(demo, "## 8. Rule on a row"))[1], ruled),
              ("the walk's step 11", blocks(page_section(demo, "## 11. A document instead of a text file"))[1], covered),
              ("the walk's step 12", blocks(page_section(demo, "## 12. Test the check"))[1], evaluated),
              ("the walk's step 13", blocks(page_section(demo, "## 13. Size the work"))[1], sized)]
    for label, block, screen in checks:
        expect(real(block.replace("text\n", "", 1), screen), label + " is the tool's own output", block[-300:])
    expect(numbered(evaluated).strip() == next((b for b in front if "Eval of the memo check" in b), "").replace("text\n", "", 1).strip(),
           "the front page's eval is the whole screen")
    library = run(["eval", "--library"])[1].strip().splitlines()[-1]
    expect("`{}`".format(library) in readme and "`{}`".format(library) in demo, "the front page and the walk quote the library run's "
           "last line as it prints", library)


def test_owner_and_signing(root):
    """What the finding owner meets: the sign screen, refusing, a change of owner, what a signature covers, and when a
    lost state file leaves a line in the log."""
    # The screen sign shows before it asks for the role prints each cleared row with its reason. A role left untyped
    # is refused and no signature is recorded, and a cleared line deleted or ruled another way puts its row back.
    folder = with_memo(root, "owner-sign", "A batch of 121 complaints was reviewed [EV-22 p1].\n")
    rulings = folder / "closure" / "rulings.md"
    base = rulings.read_text(encoding="utf-8")
    ruling = "Line 4 | {} | cleared | Head of Complaints | 2026-11-01 | The page counts the batch in words.\n".format(
        row_named(check(folder)[1], "121")[1])
    finding.write_text(rulings, base + ruling)
    record_before = (folder / "closure" / "record.md").read_text(encoding="utf-8")
    code, signing, _ = run(["sign", str(folder), "--today", NOW], stdin=answers(""))
    cleared = "  Cleared: line 4, 121, by the Head of Complaints on 2026-11-01: The page counts the batch in words.\n"
    prompt = "Type the finding owner's role to sign: "
    shown_first = cleared in signing and prompt in signing and signing.index(cleared) < signing.index(prompt)
    untyped = (code == 1 and signing.endswith("Refused: that is not the finding owner's role.\n")
               and (folder / "closure" / "record.md").read_text(encoding="utf-8") == record_before
               and state_of(folder).get("signature") is None)
    finding.write_text(rulings, base + ruling.replace("| cleared |", "| fix the memo |"))
    ruled_back = "1 on the list" in check(folder)[1]
    finding.write_text(rulings, base)
    deleted_back = "1 on the list" in check(folder)[1]
    finding.write_text(rulings, base + ruling)
    # A new owner role is refused with what to do. Started again, the folder no longer counts rulings in the old title,
    # and with no log yet the restart writes no line and makes no log.
    edit(folder / "finding.md", "Owner role: Head of Complaints", "Owner role: Director of Customer Care")
    told = ("internal audit decides whether to start .finding-state.json again, which drops the record of signed files and "
            "the signature." in check(folder)[1])
    (folder / finding.STATE_NAME).unlink()
    restarted = check(folder)[1]
    old_title = "does not count: the role it names is not the finding owner." in restarted and "1 on the list" in restarted
    no_log = not (folder / "closure" / finding.LOG_NAME).exists()
    # What a signature covers, and the prompts at the terminal.
    signed = ia(root, "owner-terminal")
    files = finding.fingerprint_files(signed)[0]
    fp = finding.fingerprint(signed)
    covered = (all(rel in files for rel in ("closure/memo.md", "closure/rulings.md", "finding.md", "plan.md", "closure/record.md",
                                            "finding.py", "finding/documents.py", "tieout/verify.py"))
               and any(rel.startswith("evidence/") for rel in files))
    unsigned = set(finding.UNSIGNED_RECORD_FIELDS)
    closers = (all(name in unsigned for name in finding.RECORD_FIELDS if name.startswith(("Internal audit", "Supervisor closure",
                                                                                          "Issue closure")))
               and not any(name.startswith("Board approval") for name in unsigned))
    code, out, _ = run(["sign", str(signed), "--today", NOW], stdin=answers("Head of Complaints", fp[:8]))
    prompts = code == 0 and prompt in out and "Fingerprint " + fp + "\nType its first eight characters to confirm: " in out
    # The first check records each counted file, and a later check names one that is gone; --names writes no state.
    gone = root / "owner-gone"
    shutil.copytree(str(CASES / "IA-CMP-02"), str(gone))
    (gone / "evidence" / "EV-22-timeliness-report.md").unlink()
    code, out, _ = check(gone)
    gone_named = code == 1 and "Gone since an earlier check\nevidence/EV-22-timeliness-report.md.\n" in out
    unchecked = build(root, "owner-names", IA_FILES, None)
    code, out, _ = run(["check", str(unchecked), "--names"])
    names_only = code == 0 and "Deny list for IA-CMP-02:" in out and not (unchecked / finding.STATE_NAME).exists()
    fixable = set(finding.FROZEN_FIELDS) - set(finding.LABEL_FIELDS) - {"Owner role"}
    ia_out = check(ia(root, "owner-leaves"))[1]
    leaves_printed = "\n  Not checked: " in ia_out and " rest on text a person typed: " in ia_out

    expect(shown_first, "the screen sign shows before it asks for the role prints each cleared row with its reason", signing[-600:])
    expect(untyped, "a role left untyped is refused and no signature is recorded", signing[-300:])
    expect(ruled_back and deleted_back, "a cleared line ruled another way or deleted puts its row back")
    expect(told and old_title, "a new owner title is refused with who decides, and a restarted folder stops counting rulings "
           "in the old title")
    expect(no_log, "a restart with no log yet writes no line and makes no log")
    expect(covered and closers, "one fingerprint covers the memo, rulings, letter, plan, record, evidence and the tool's code, "
           "and the closers' entries in the record stay outside it")
    expect(prompts, "sign prints the fingerprint and asks for its first eight characters")
    expect(gone_named, "a later check names an evidence file that is gone since an earlier check", out[-600:])
    expect(names_only and fixable == {"Identifier", "Letter date"}, "check --names writes no state, and --repaste can correct "
           "only the letter's text, identifier and date")
    expect(leaves_printed, "the page names what it did not check and how many ties rest on typed text")
    demo = pages("finding/DEMO.md")
    if demo is not None:
        version = finding.kit_release()[0].partition("+site.")[0]
        expect("The fingerprint changes with any release that changes the tool's code, and the Finding line names the release, "
               "so your screen matches this page only on release {}.".format(version) in demo, "the walk says when a screen matches it")


def test_site_copy_passes(root):
    """A whole copy of the kit with a changed tool file, marked a site version by release.py, passes this self-test with
    the page checks this run made, the front page's count included. docs/forward-deployed.md asks for that before a
    change is accepted. The run inside the copy checks that it reads a site version in place of starting another run."""
    if os.environ.get(SITE_RUN):
        expect("+site." in finding.kit_release()[0], "the run inside a site copy reads a site version", finding.kit_release()[0])
        return
    copy = root / "site-copy"
    shutil.copytree(str(HERE.parent), str(copy), ignore=shutil.ignore_patterns("__pycache__", ".git", ".DS_Store"))
    append_to(copy / "finding" / "finding.py", "# a site change")
    code, stepped = release_run(copy)
    proc = subprocess.run([sys.executable, "-I", str(copy / "finding" / "selftest.py")], stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, input=b"", env=dict(os.environ, **{SITE_RUN: "1"}))
    out = proc.stdout.decode("utf-8", "replace").replace("\r\n", "\n").strip()
    expect(code == 0 and "site version" in stepped and proc.returncode == 0
           and (out.splitlines() or [""])[-1].startswith("selftest: PASS (") and ("skipped" in out) == bool(SKIPPED),
           "a copy with a changed tool file, marked a site version, passes this self-test", stepped + out[-1500:])


def main():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for test in (test_new_and_usage, test_screens, test_proposed, test_refusal_parts,
                     test_closed_claim_row, test_refusal_names, test_evidence_states,
                     test_state_and_uncounted, test_plan_and_covers, test_memo_list, test_row_wording, test_sign,
                     test_needs_and_order, test_signing_order, test_release_and_network,
                     test_documents, test_reader_never_raises, test_reader_word, test_reader_caps,
                     test_reader_hidden_pdf, test_reader_excel, test_reader_xref, test_reader_typed_pages,
                     test_reader_email, test_reader_page_text, test_reader_text_file, test_reader_page_tree,
                     test_reader_decode_gaps, test_covers, test_eval_and_size,
                     test_evidence_ids, test_cover_by_name, test_header_stops, test_line_endings, test_record_case,
                     test_typed_count, test_fingerprint_covers_reader, test_kit_list, test_site_version,
                     test_test_assets, test_kit_note, test_malformed, test_role_words, test_deny_on_every_page,
                     test_names_harvested, test_list_one_folder_up, test_closed_word, test_state_lost, test_sign_date,
                     test_first_paste, test_memo_reads_every_line, test_control_dates_tie, test_figures_in_words,
                     test_quotation_and_date_readings, test_cited_files_outside_the_plan, test_rulings_bind,
                     test_board_fields, test_signature_on_the_page, test_tested_fingerprint, test_board_flags_late,
                     test_draft_rows, test_blank_pages_named, test_eval_honest, test_small_page_errors,
                     test_wrapper, test_shipped, test_measures_lines, test_size_fit, test_kinds_and_plan_columns,
                     test_library_case_errors, test_cover_names_checked_by, test_recheck_readers,
                     test_recheck_names_on_pages, test_recheck_typed_and_signed, test_recheck_rows, test_recheck_size,
                     test_recheck_pages, test_reader_bounds_and_styles, test_memo_reads_more_forms,
                     test_pages_match_the_tool, test_signing_record, test_page_counts, test_review_round_five,
                     test_month_points, test_long_page_list, test_dark_mode_and_at_rules, test_larger_case_one,
                     test_larger_case_two, test_larger_case_three, test_larger_case_four,
                     test_larger_case_five, test_screens_in_detail, test_pages_against_the_tool,
                     test_owner_and_signing, test_site_copy_passes):
            try:
                test(root)
            except Exception as exc:  # report and carry on, so one failure shows the rest
                FAILURES.append("{} raised {}: {}".format(test.__name__, type(exc).__name__, exc))
    # The front page quotes this run's count, this expectation included, so the page cannot drift from the tool.
    # A system with no pseudo-terminal runs fewer expectations, so only a posix run compares the number.
    front = pages("README.md")
    if front is not None:
        quoted = re.search(r"(\d[\d,]*) expectations in the finding tool", front)
        expect(quoted is not None and (os.name != "posix" or quoted.group(1).replace(",", "") == str(COUNT + 1)),
               "README.md quotes the count this self-test prints",
               "README.md says {}, this run made {}".format(quoted.group(1) if quoted else "nothing", COUNT + 1))
    if SKIPPED:
        print("selftest: note: {} skipped, because the documentation pages they read are not in this copy".format(
            finding.plural(len(SKIPPED), "page check")))
    if FAILURES:
        for line in FAILURES:
            print("FAIL " + line)
        print("selftest: FAIL ({} of {} expectations failed)".format(len(FAILURES), COUNT))
        return 1
    print("selftest: PASS ({} expectations)".format(COUNT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
