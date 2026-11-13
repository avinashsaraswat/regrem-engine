"""finding: one folder per finding, and the commands that read it.

Purpose: `finding new` makes a finding folder from the templates below, outside the kit. `finding check` reads
  the folder (finding.md, plan.md, evidence/ and closure/) and prints each milestone's state from
  its evidence files, a draft board summary, the institution's commitment table and the memo check: every
  figure and date written in digits and every quotation in closure/memo.md tied to the evidence page
  it cites by the kit's own engine (tieout/verify.py, imported unchanged), with what did not tie on
  one list that a person's ruling in closure/rulings.md can clear. It refuses when the issuer's text changed after
  the first check, or when a name on the deny list would print. Until the closer has recorded its entry, each use of
  the word closed is a row on the list, and a line saying the finding itself is closed is a row no ruling clears,
  so the line must be reworded. `check --names` prints the deny list, for the person who asks. `check --repaste` records a
  corrected paste of the letter. `finding sign` lets the finding owner sign at a terminal once the
  list is empty, and records a fingerprint of everything signed.
Reads: the finding folder. The first line of any file is ignored when it starts with SYNTHETIC.
Writes: `new` writes the new folder. `check` writes .finding-state.json in the folder, and only
  when something in it changed: the five parts' hashes and the frozen header lines on the first check,
  each evidence file's hash by path and by evidence id when first seen or signed again, the plan's
  committed dates when the board's approval first counts, and names added to the deny list or cleared
  from it. When the state file is gone and closure/finding-log.jsonl is there, it
  also appends one line to that log saying the record restarted. `check --repaste` appends a line
  too. `sign` writes the signature into .finding-state.json and its four lines into
  closure/record.md. `covers` writes draft
  covers beside documents in evidence/ and reads them with documents.py. `eval` plants errors in the
  memo text in memory and writes nothing, and `eval --library` runs library/cases in a temporary
  folder. `size` prints counts and assumed hours, reads an optional size-assumptions.txt beside the finding or
  one folder up, and writes nothing. Nothing writes to closure/memo.md.
Network: none. Standard library only, Python 3.9 and later.
Exit codes: 0 when nothing needs a person (for sign, when signed), 1 when something does or on a refusal,
  2 on usage.
"""
import datetime
import decimal
import hashlib
import json
import re
import sys
import tempfile
import unicodedata
from pathlib import Path

CONFIDENTIAL = (
    "This folder may hold confidential supervisory information. Keep it on a machine the institution "
    "has approved, and share nothing from it outside the institution."
)
USAGE = ("usage: finding new [<path>/]<id> | finding check [<folder>] [--today YYYY-MM-DD] [--names | --repaste] | "
         "finding sign <folder> [--today YYYY-MM-DD] | finding covers <folder> | "
         "finding eval <folder> | finding eval --library | finding size <folder> | finding --version")
STATE_NAME = ".finding-state.json"
PARTS = ("Concern", "Cause", "Consequence", "Corrective action", "Commitment")
FIELDS = ("Identifier", "Institution", "Issuer", "Letter date", "Kind of matter", "Owner role")
SUPERVISORY = "supervisory finding"
INTERNAL = "internal audit finding"
# A weakness the institution found on its own. Its issue-management owner closes it.
SELF_IDENTIFIED = "self-identified issue"
KINDS = (SUPERVISORY, INTERNAL, SELF_IDENTIFIED)
PLAN_COLUMNS = (
    "Milestone",
    "Owner role",
    "Committed date",
    "What is true when done",
    "Evidence",
    "Internal audit will test",
)
RECORD_FIELDS = (
    "Internal audit reference",
    "Internal audit date",
    "Internal audit recorded by (role)",
    "Internal audit tested fingerprint",
    "Supervisor closure notice",
    "Supervisor closure date",
    "Supervisor closure recorded by (role)",
    "Issue closure reference",
    "Issue closure date",
    "Issue closure recorded by (role)",
    "Board approval reference",
    "Board approval date",
    "Board approval recorded by (role)",
    "Signed by (role)",
    "Signed on",
    "Fingerprint",
    "Kit release",
)
SIGNATURE_FIELDS = ("Signed by (role)", "Signed on", "Fingerprint")
# Lines a signature does not cover: its own, and what internal audit and the Supervisor enter after it.
UNSIGNED_RECORD_FIELDS = SIGNATURE_FIELDS + (
    "Kit release",
    "Internal audit reference",
    "Internal audit date",
    "Internal audit recorded by (role)",
    "Internal audit tested fingerprint",
    "Supervisor closure notice",
    "Supervisor closure date",
    "Supervisor closure recorded by (role)",
    "Issue closure reference",
    "Issue closure date",
    "Issue closure recorded by (role)",
)
# The owner role freezes too: the owner rules on the list and signs, so a relabelled owner would rule on its own.
FROZEN_FIELDS = ("Identifier", "Issuer", "Letter date", "Kind of matter", "Owner role")
LABEL_FIELDS = ("Issuer", "Kind of matter")
HOURS_RE = re.compile(r"[0-9]+(?:\.[0-9]+)?")  # ASCII digits, with part hours, so 37.5 counts and 1,240 is named
HEADER_KEYS = ("What:", "For:", "Status:", "Signed by:", "Produced by:", "Approved by:", "Never signed:", "Revised:", "Covers:",
               "Source:", "Checked by:")
LOG_NAME = "finding-log.jsonl"
EVIDENCE_ID_RE = re.compile(r"^([A-Za-z][A-Za-z]*(?:-[A-Za-z]+)*-\d+(?:-\d+(?![A-Za-z0-9]))*)")
# The assumptions `finding size` prints, in the words a size-assumptions.txt uses for them. Timed figures go in that
# file, beside the finding or one folder up, so replacing one changes no fingerprint. Both sides carry a person's
# work: with the kit, one read of each claim against its page before signature and one rework round, until timed.
SIZE_ASSUMPTIONS = (
    ("minutes a claim by hand", 10),
    ("memo versions", 3),
    ("hours a status report", 2),
    ("minutes to find a signed file", 30),
    ("hours a rework round", 8),
    ("minutes a cover", 10),
    ("minutes a ruling", 15),
    ("minutes to read a claim", 10),
    ("rework rounds with the kit", 1),
    ("minutes a status report with the kit", 15),
    ("minutes to type and compare a page", 15),
)
SIZE_FILE = "size-assumptions.txt"
BOARD_FIELDS = ("Board approval reference", "Board approval date", "Board approval recorded by (role)")
KIT = Path(__file__).resolve().parent.parent
# The files a finding's page depends on. RELEASE.json holds their hashes; finding/release.py reads this list.
KIT_FILES = (
    "finding/documents.py",
    "finding/finding",
    "finding/finding.py",
    "tieout/claims.py",
    "tieout/docx_reader.py",
    "tieout/record.py",
    "tieout/verify.py",
    "tieout/words.py",
)
# The rest of the kit's code. Any other code in these two folders could run on import, so every page names it.
KIT_CODE = KIT_FILES + (
    "finding/release.py",
    "finding/selftest.py",
    "tieout/gate.py",
    "tieout/measure.py",
    "tieout/providers.py",
    "tieout/selftest.py",
    "tieout/tieout.py",
)
# What the self-test and the library eval rest on. RELEASE.json holds their hashes under "tests", and only --version
# reads them. No documentation page is one, so a kit brought in without its pages still matches its release.
TEST_ASSETS = ("finding/selftest.py", "finding/release.py", "finding/cases/**/*", "finding/samples/*", "library/cases/*.json")
PAGE_RE = re.compile(r"^#{1,6}\s*Page\s+(\d+)\s*$", re.IGNORECASE)
DIGIT_RUN = re.compile(r"\d+")  # a run of digits, as the reader counts figures
CITE_RE = re.compile(r"\[(?P<id>[A-Za-z][A-Za-z0-9-]*)(?: p(?P<page>\d+))?\]")
# A cite written another way, such as [EV-21, p2], (EV-21 p. 2), [EV-21 page 2], [ EV-21 p2 ], [EV-21 pp. 1-2] or
# [EV-21 p2, EV-22 p1]. It is no cite, and its page numbers are no claim, and the row for a claim before it names
# the form the check reads. Each later part reads one way, a page such as p2 never as an id, so a long list that does
# not close reads in one pass.
_NEAR_ID = r"[A-Za-z]+(?:-[A-Za-z]+)*-?\d+"
_NEAR_PAGE = r"(?:p|pp|pg|page|pages)\.?\s?\d+(?:\s?[-\u2013]\s?\d+)?"
NEAR_CITE_RE = re.compile(
    r"[\[(]\s*(?:see\s)?(?P<id>" + _NEAR_ID + r")(?:,?\s*(?:p|pp|pg|page|pages)\.?\s?(?P<page>\d+)(?P<range>\s?[-\u2013]"
    r"\s?\d+)?)?(?P<more>(?:\s*(?:,|;|&|\band\b)\s*(?:(?!(?:p|pp|pg|page|pages)\d)" + _NEAR_ID + r"(?:\s*" + _NEAR_PAGE
    + r")?|" + _NEAR_PAGE + r"))*)\s*[\])]", re.IGNORECASE)
# A sentence ends at a mark followed by any space, a line break included, and then a capital, a quote mark, a digit
# or a bracket that opens no cite, so a hard-wrapped line never lends its cite to the sentence before it.
SENTENCE_END_RE = re.compile(r"[.?!][\"”'’)\]]*(?=\s+(?:[A-Z0-9\"“‘']|\((?!\s*(?i:see\s)?" + _NEAR_ID + r")))")
# Short forms whose point is no sentence end before a digit, as in approx. 120, No. 5, p. 2 or Feb. 2, 2026. May is a
# full word, so May. ends a sentence.
ABBREVIATIONS = {"approx", "no", "nos", "p", "pp", "pg", "fig", "figs", "vs", "v", "c", "ca", "e.g", "i.e", "eg", "ie",
                 "etc", "sec", "art", "para", "ref", "vol", "ch", "op", "cf", "est", "max", "min", "avg", "nr", "jan",
                 "feb", "mar", "apr", "jun", "jul", "aug", "sep", "sept", "oct", "nov", "dec", "rev"}
QUOTE_RE = re.compile(r'"([^"\n]+)"')
QUOTE_MARKS = '"“”„'  # every mark the engine's norm_text turns into a straight double quote
SINGLE_MARKS = "'‘’"  # a quotation in single marks, straight or curly, as British style writes one
NOT_IN_WORDS = "'‘’\"“”„–—…"  # characters past ASCII that never count as part of a word
# A heading's marks and any section number before its words. A number is a section number when a point, bracket,
# colon or dash follows it or brackets enclose it, so "## 2. Letters" and "## (1) Testing" read no figure, and
# "## 125 Complaints Sampled" and "## 120 complaints" each read one. SECTION_RE reads the rest of the forms in
# memo_blocks: 2.1 before a capital, or 1, or the number after the last heading's, such as 3 after 2.
HEADING_RE = re.compile(r"^\s*#+\s*(?:\((?P<a>\d+)(?:\.\d+)*\)\s+|(?P<b>\d+)(?:\.\d+)*(?:[.)]\s+|\s*[:\u2013\u2014-]\s+))?")
SECTION_RE = re.compile(r"(?P<top>\d{1,2})(?P<dots>(?:\.\d{1,2})*)\s+(?=[A-Z])(?!(?i:per\s?cent|percent)\b)")
# A number that labels a part of the memo in a heading, such as Part 3 or Appendix 1, is no figure either, unless it
# is a percentage, as in "Section 98.3 percent on time". A number straight after version, v or Rev. is a label anywhere.
_LABELS = r"milestone|part|appendix|annex|section|chapter|step|schedule|stage|phase|attachment|item|table|figure"
LABEL_NUMBER_RE = re.compile(r"(?i)\b(?:" + _LABELS + r")\s+(\d+(?:\.\d+)*)(?!\d|[.,]\d|\s?%|\s+per\s?cent\b)")
VERSION_RE = re.compile(r"(?i)(?<![\w.])(?:version\s+|v\.?\s?|rev\.?\s?)(\d+(?:\.\d+)*)(?!\d|[.,]\d|\s?%|\s+per\s?cent\b)")
# A list number at the start of a line, 1. or 1) or (1), when the line before ends a sentence, opens the block or is
# part of a list item, and the number is 1 or the one after the last list number, so (12) or 119. opening a line
# is a figure. A bullet, - or * or +, opens a list item at the start of any line.
LIST_NUMBER_RE = re.compile(r"^\s*(?:\((?P<a>\d{1,3})\)|(?P<b>\d{1,3})[.)])(?=\s)")
BULLET_RE = re.compile(r"^\s*[-*+\u2022\u2023\u25e6\u25aa\u2013\u2014](?=\s)")
# A reference id such as BM-2026-07: letters, then parts joined by hyphens. The engine already skips a number after
# a letter and a hyphen, and this keeps it from reading the 07 after 2026-.
REFERENCE_ID_RE = re.compile(r"(?<![\w.\-/])[A-Za-z][A-Za-z0-9]*(?:-[A-Za-z0-9]+)*-[0-9]+-[0-9][A-Za-z0-9-]*(?![\w\-])")
# Date forms the engine does not read, read here so their numbers are not taken for figures: 01-Aug-2026 (and
# 1-Jul-26, whose century would be a guess, so it is named and not read), 1 July, 2026, the 1st of June 2026 and the
# months 2026-01, June, 2026 and Excel's Aug-26 and Aug-2026, a month of 20YY. Each reads at the precision written.
_MON = (r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?|Aug(?:ust)?|Sept?(?:ember)?|"
        r"Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)")
EXTRA_DATE_RE = re.compile(
    r"(?<![\w/.\-\x00])(?P<dd>\d{1,2})(?P<sep>[-/])(?P<mon>(?i:" + _MON + r"))(?P=sep)(?P<yy>\d{4}|\d{2})"
    r"(?![\w/\-]|\.\d)"
    r"|(?<![\w.,\x00])(?P<d>\d{1,2})(?:st|nd|rd|th)?(?P<of> of)? (?P<month>" + _MON + r")(?(of),?|,) (?P<y>\d{4})\b"
    r"|(?<![\w/.\-\x00])(?P<iy>(?:19|20)\d\d)-(?P<im>0[1-9]|1[0-2])(?![\w/\-]|\.\d)"
    r"|(?<![\w.,\x00])(?P<mm>" + _MON + r"), (?P<my>\d{4})\b"
    r"|(?<![\w/.\-\x00])(?P<xm>(?i:" + _MON + r"))-(?P<xy>\d{4}|\d{2})(?![\w/\-]|\.\d)")
NO_YEAR_RE = re.compile(r"(?<![\w.,/\-\x00])(?:(?P<d>\d{1,2})(?:st|nd|rd|th)? (?P<m>" + _MON + r")|(?P<n>" + _MON
                        + r") (?P<e>\d{1,2})(?:st|nd|rd|th)?)\b(?!,? ?\d)")  # 29 January or January 29, no year
TIME_RE = re.compile(r"\d+:\d\d(?::\d\d)?(?:\.\d+)?(?:\s*[+-]\d{4})?")  # 20:05:33 +0000 on an email's Date line
COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
RULINGS = ("cleared", "fix the memo", "fix the evidence")
PLAN_ID = "E-PLAN-1"
TEXT_SUFFIXES = (".md", ".txt")
# Files whose line endings a sync or a Windows checkout may rewrite. Their hash folds line endings. Any other
# file, such as a PDF or a workbook, is hashed byte for byte.
FOLDED_SUFFIXES = TEXT_SUFFIXES + (".csv", ".eml")
MONTH_WORDS = {
    "January", "February", "March", "April", "May", "June", "July", "August", "September",
    "October", "November", "December",
}
ROLE_WORDS = {
    "Supervisor", "Bank", "Board", "Committee", "Head", "Chief", "Officer", "Internal", "Audit",
    "Risk", "Complaints", "Digital", "Lead",
} | MONTH_WORDS
# Words that open a sentence ahead of a name or a date, so "In March" and "The Consumer Duty" read right.
SENTENCE_OPENERS = {
    "The", "This", "That", "These", "Those", "Our", "Its", "Their", "An", "In", "On", "At", "By", "For", "From",
    "Since", "During", "After", "Before", "Until", "Under", "Over", "With", "Within", "When", "While", "As", "If",
    "Once", "Upon", "Per", "Between", "Following", "Each", "Every", "All", "Some", "Both", "Most", "Many", "Several",
}
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]*$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
CLOSED_RE = re.compile(r"(?<![A-Za-z0-9])closed(?![A-Za-z0-9])", re.IGNORECASE)
CLOSURE_RE = re.compile(
    r"(?<![A-Za-z0-9])(?:closure\s+(?:(?:is|was|has|been|now|fully|formally)\s+)*(?:achieved|complete|completed)"
    r"|(?:achieved|completed)\s+(?:[A-Za-z]+\s+){0,2}?closure)(?![A-Za-z0-9])", re.IGNORECASE)
# The words that make a sentence about closing mean this finding. An institution that uses another word adds it here.
CLOSED_SUBJECTS = {"finding", "matter", "remediation", "mra", "mria"}
NEGATIONS = {"not", "never", "no", "cannot", "neither", "nor"}
# Words before the subject that make a sentence a condition or a report of someone else's call.
CLOSED_CONDITIONS = NEGATIONS | {
    "until", "unless", "before", "after", "once", "if", "when", "while", "whether", "pending", "upon", "only", "say", "says",
}
# The only words that may stand between the subject and closed, as in "the finding has been reviewed and closed".
CLOSED_LINKS = {
    "is", "was", "are", "were", "has", "have", "had", "been", "be", "being", "now", "hereby", "formally", "fully",
    "officially", "therefore", "considered", "deemed", "effectively", "successfully", "and", "reviewed", "validated",
    "tested", "confirmed", "remediated", "complete", "completed", "status", "marked", "recorded", "as",
}
# The only words that may stand between closed and the subject, as in "we closed out this supervisory finding".
BE_WORDS = {"is", "was", "are", "were", "been", "be", "being"}
DETERMINERS = {"the", "a", "an", "this", "that", "these", "those", "its", "our", "their", "all", "each", "every", "any"}
CLOSED_FILLERS = {"out", "off", "down", "the", "this", "that", "our", "its", "said", "above", "supervisory", "internal",
                  "audit", "regulatory", "whole"}
SENTENCE_CUT_RE = re.compile(r"[.;!?]+[\"”')\]]*\s|\n[ \t]*\n|\|")
# The issuer words that mean the Supervisor wrote this. An institution whose Supervisor goes by another name adds it here.
SUPERVISOR_WORDS = ("supervisor",)
# A capitalised word: an upper-case letter, then letters with at least one lower-case letter,
# optionally joined by hyphens or apostrophes. "MRA" and "I" are not capitalised words.
# Words in a run are separated by spaces or a single line break, so a name wrapped onto the
# next line of a paragraph is still one run; a blank line ends the run.
_CAP = r"[A-Z][A-Za-z]*[a-z][A-Za-z]*(?:['’-][A-Za-z]+)*"
_GAP = r"(?:[ \t]+\n?[ \t]*|\n[ \t]*)"
RUN_RE = re.compile(r"(?<![A-Za-z0-9'’-])" + _CAP + r"(?:" + _GAP + _CAP + r")*(?![A-Za-z0-9])")
# A run holding a document word is a title, such as Alert Handling Procedure, and never a name.
TITLE_RE = re.compile(r"\b(?:Procedure|Polic(?:y|ie)|Report|Plan|Standard|Framework|Committee|Minute|Programme|Program|"
                      r"Register|Charter|Manual|Methodolog(?:y|ie)|Assessment)s?\b")
ROLE_FIX = " If it is an ordinary word or a title, add it to role-words.txt."

SHIPPED_LINE = "SYNTHETIC. Everything in this folder is invented."  # the first line of each shipped case

TEMPLATE_FINDING = """# Finding {id}
Fill the lines below, then paste each part of the letter under its heading. The first full check fixes this text, so compare it with the letter first.
Identifier: {id}
Institution:
Issuer: the Supervisor
Letter date:
Kind of matter: supervisory finding
Owner role:

## Concern

## Cause

## Consequence

## Corrective action

## Commitment
"""

TEMPLATE_PLAN = """# Plan {id}

One row per milestone. Start each Milestone cell with its id, such as M1. Committed dates are
YYYY-MM-DD, and the Evidence cell lists evidence ids separated by commas, such as EV-03, EV-04.
Put (done) after the file whose date is the milestone's, the one that completes it, as in EV-04 (done).

| Milestone | Owner role | Committed date | What is true when done | Evidence | Internal audit will test |
|---|---|---|---|---|---|
"""

TEMPLATE_MEMO = """# Closure memo {id}

<!-- Write the memo in paragraphs below. Put a bracketed cite such as [EV-12 p2] after every figure, date and quotation: the evidence id from the file's For: line, a space, p and the page number from its "## Page 2" heading. A file with no page headings is cited as [EV-12 p1]. For each control internal audit will test, add a block of three lines in this form, each date cited to the evidence page that holds it:

Tested control: M1, the acknowledgement letter procedure
Fix effective: 2026-05-04 [EV-21 p1]
Sample period: 2026-05-04 to 2026-05-22 [EV-21 p2]
-->
"""

TEMPLATE_RECORD = """Internal audit reference:
Internal audit date:
Internal audit recorded by (role):
Internal audit tested fingerprint:
Supervisor closure notice:
Supervisor closure date:
Supervisor closure recorded by (role):
Issue closure reference:
Issue closure date:
Issue closure recorded by (role):
Board approval reference:
Board approval date:
Board approval recorded by (role):
Signed by (role):
Signed on:
Fingerprint:
Kit release:
"""

TEMPLATE_MEASURES = """# Measures {id}

<!-- What the Measures line on the check page counts. Hours booked to this finding, one line a month. One line each time internal audit sends something back, ending in missed by the check when the check had passed it:
Hours | 2026-10 | 38
Sent back | 2026-11-02 | Line 8 | the figure was the draft's | missed by the check
Part hours such as 37.5 count. A line the check cannot read is named on the page and counts for nothing. -->
"""

TEMPLATE_RULINGS = """# Rulings {id}

<!-- One line per row on the list, in this form, with the line number and the words after "To rule, name:" as the screen prints them:
Line 8 | March 2026 #1a2b3c4d | cleared | Head of Complaints | 2026-11-04 | The page says January to March, and the plan year is 2026.
The ruling is cleared, fix the memo or fix the evidence. Only a cleared ruling by the finding owner's role, dated and with a reason, takes a row off the list. The mark after the # stands for the claim, its cite and its sentence, so a ruling clears that claim and no other. If the memo moves, a cleared ruling follows its claim to the new line. Change the sentence or the cite and the row returns to the list. -->
"""


class UsageError(Exception):
    """Bad command line: exit 2."""


class Stop(Exception):
    """A refusal or a folder that is not ready: print the confidentiality line and this, exit 1."""


# ---------------------------------------------------------------- the kit's release


def text_digest(path):
    """A file's hash with line endings folded, so a Windows checkout gives the same answer."""
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def read_release():
    """RELEASE.json as a dict, or None when it is missing or holds something else."""
    try:
        doc = json.loads((KIT / "RELEASE.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return doc if isinstance(doc, dict) else None


def kit_release():
    """(version, [what differs from that release]); ("unknown", []) when RELEASE.json cannot be read.
    A kit file missing from the list and code the kit does not ship count as differences too, so an
    emptied list or a planted module never reads as a match."""
    doc = read_release()
    if doc is None or "version" not in doc or not isinstance(doc.get("files"), dict):
        return "unknown", []
    files = doc["files"]
    changed = [rel + " (not listed)" for rel in sorted(set(KIT_FILES) - set(files))]
    for rel in sorted(files):
        target = KIT / rel
        if not target.is_file() or text_digest(target) != files[rel]:
            changed.append(rel)
    for folder in ("finding", "tieout"):
        for found in sorted((KIT / folder).glob("*")):
            rel = folder + "/" + found.name
            if (found.suffix in (".py", ".pyc") or found.name == "__pycache__") and rel not in KIT_CODE:
                changed.append(rel + " (not part of the kit)")
    return str(doc["version"]), changed


def kit_note():
    """The line a page prints when the kit differs from its release, or nothing."""
    version, changed = kit_release()
    return ["Kit files changed since release {}: {}.".format(version, ", ".join(changed))] if changed else []


def kit_label():
    """The release as a record or a log keeps it, with anything that differs from it."""
    version, changed = kit_release()
    return "{}, changed: {}".format(version, ", ".join(changed)) if changed else version


def test_asset_files():
    """Every test asset on disk, as kit paths in order."""
    found = set()
    for pattern in TEST_ASSETS:
        for path in KIT.glob(pattern):
            # A repaste on a shipped case writes its log there, and a log line is no change to a test.
            if path.is_file() and "__pycache__" not in path.parts and path.name not in (".DS_Store", LOG_NAME):
                found.add(path.relative_to(KIT).as_posix())
    return sorted(found)


def tests_changed():
    """Test assets missing, added or changed since the release."""
    doc = read_release() or {}
    listed = doc["tests"] if isinstance(doc.get("tests"), dict) else {}
    found = test_asset_files()
    return sorted(rel for rel in set(listed) | set(found)
                  if rel not in listed or rel not in found or text_digest(KIT / rel) != listed[rel])


def cmd_version(args):
    if args:
        raise UsageError()
    version, changed = kit_release()
    print("RegRem Engine " + version)
    if version == "unknown":
        print("RELEASE.json beside this kit is missing or cannot be read, so its files cannot be checked.")
        return 1
    tests = tests_changed()
    if changed:
        print("Changed since this release: " + ", ".join(changed) + ".")
    if tests:
        print("Test files changed since this release: " + ", ".join(tests) + ".")
    if changed or tests:
        return 1
    print("Every file matches this release.")
    return 0


# ---------------------------------------------------------------- what an institution fits


def fit_lines(folder, name):
    """Lines of an optional list beside finding.md and one level up, for the whole engagement."""
    lines = []
    for base in (folder, folder.resolve().parent):
        path = base / name
        if path.is_file():
            for line in read_lines(path):
                s = line.strip()
                if s and not s.startswith("#") and s not in lines:
                    lines.append(s)
    return lines


# ---------------------------------------------------------------- small helpers


def parse_date(text):
    text = (text or "").strip()
    if not DATE_RE.match(text):
        return None
    try:
        return datetime.date.fromisoformat(text)
    except ValueError:
        return None


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def read_lines(path):
    """The file's lines, with a first line starting SYNTHETIC blanked so line numbers hold."""
    try:
        text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        raise Stop("Refused: {} is not UTF-8 text.".format(path.name))
    lines = text.splitlines()
    if lines and lines[0].startswith("SYNTHETIC"):
        lines[0] = ""
    return lines


def plural(n, word):
    return "{} {}{}".format(n, word, "" if n == 1 else "s")


def with_the(role):
    role = role.strip()
    return role if role.lower().startswith("the ") else "the " + role


def possessive(issuer):
    return issuer.strip() + "'s"


def capital_first(text):
    return text[:1].upper() + text[1:]


def write_text(path, text):
    with open(str(path), "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


# ---------------------------------------------------------------- finding.md


def parse_finding(folder):
    lines = read_lines(folder / "finding.md")
    fields = {}
    parts = {}
    current = None
    seen_part_heading = False
    for line in lines:
        if line.startswith("## "):
            seen_part_heading = True
            name = line[3:].strip()
            current = name if name in PARTS else None
            if current is not None:
                parts[current] = []
            continue
        if current is not None:
            parts[current].append(line)
            continue
        if not seen_part_heading:
            m = re.match(r"^([A-Za-z ]+):(.*)$", line)
            if m and m.group(1).strip() in FIELDS and m.group(1).strip() not in fields:
                fields[m.group(1).strip()] = m.group(2).strip()
    texts = {name: "\n".join(body).strip() for name, body in parts.items()}
    return fields, texts


def require_ready(fields, parts):
    for key in FIELDS:
        if key not in fields:
            raise Stop(
                "Not ready: finding.md has no {} line, so its template lines were replaced. Put them back at the "
                "top, as finding new writes them, and paste each part of the letter under its heading.".format(key)
            )
        if not fields[key]:
            raise Stop("Not ready: finding.md has no {} yet. Fill that line, then check again.".format(key))
    if parse_date(fields["Letter date"]) is None:
        raise Stop('Not ready: finding.md gives Letter date as "{}"; use YYYY-MM-DD.'.format(
            fields["Letter date"]))
    if fields["Kind of matter"] not in KINDS:
        raise Stop(
            'Not ready: finding.md gives Kind of matter as "{}"; use {}.'.format(
                fields["Kind of matter"], or_list(KINDS))
        )
    for name in PARTS:
        if not parts.get(name):
            raise Stop(
                "Not ready: finding.md has no text under ## {} yet. Paste that part of the letter under its "
                "heading; if the letter has no such heading, put the matching passage there.".format(name)
            )


# ---------------------------------------------------------------- plan.md


def split_row(line):
    s = line.strip()
    if not s.startswith("|"):
        return None
    s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [cell.strip() for cell in s.split("|")]


def parse_plan(folder):
    path = folder / "plan.md"
    if not path.is_file():
        raise Stop("Not ready: there is no plan.md in this folder yet.")
    lines = read_lines(path)
    start = None
    for i, line in enumerate(lines):
        cells = split_row(line)
        if cells is not None and set(PLAN_COLUMNS) <= set(cells):  # a column the institution adds, in any place, is kept
            start, header = i, cells
            break
    if start is None:
        raise Stop(
            "Not ready: plan.md has no table with the columns " + ", ".join(PLAN_COLUMNS) + "."
        )
    rows = []
    seen = {}
    for i in range(start + 1, len(lines)):
        cells = split_row(lines[i])
        if cells is None:
            break
        if all(re.match(r"^:?-+:?$", c) for c in cells if c) and any(cells):
            continue
        if not any(cells):
            continue
        lineno = i + 1
        if len(cells) != len(header):
            raise Stop("Not ready: plan.md line {} has {} cells; the table has {} columns.".format(
                lineno, len(cells), len(header)))
        row = {name: cells[header.index(name)] for name in PLAN_COLUMNS}  # read by name, never by place
        milestone, owner, committed, evidence = (row["Milestone"], row["Owner role"], row["Committed date"],
                                                 row["Evidence"])
        if not milestone:
            raise Stop("Not ready: plan.md line {} has no milestone.".format(lineno))
        if not owner:
            raise Stop("Not ready: plan.md line {} has no owner role.".format(lineno))
        date = parse_date(committed)
        if date is None:
            raise Stop('Not ready: plan.md line {} gives committed date "{}"; use YYYY-MM-DD.'.format(
                lineno, committed))
        mid = milestone.split()[0]
        if mid in seen:
            raise Stop("Not ready: plan.md line {} repeats milestone {} from line {}; give each "
                       "milestone its own id.".format(lineno, mid, seen[mid]))
        seen[mid] = lineno
        ids, done = [], []
        for item in evidence.split(","):  # EV-27 (done) marks the file whose date is the milestone's
            item, mark = re.subn(r"\s*\(done\)$", "", item.strip(), flags=re.IGNORECASE)
            done += [item] if mark and item else []
            if item and item not in ids:
                ids.append(item)
        if len(done) > 1:
            raise Stop("Not ready: plan.md line {} marks {} done; mark only the file that completes {}.".format(
                lineno, and_list(done), mid))
        rows.append({
            "cell": milestone,
            "id": mid,
            "owner": owner,
            "date": date,
            "ids": ids,
            "done": done[0] if done else None,
        })
    if not rows:
        raise Stop("Not ready: plan.md has no milestone rows yet.")
    return rows


# ---------------------------------------------------------------- closure/


def is_record_line(line, key):
    """True when a line of closure/record.md holds this field, whatever case it was typed in."""
    return line.strip().lower().startswith(key.lower() + ":")


def parse_record(folder):
    record = {key: "" for key in RECORD_FIELDS}
    path = folder / "closure" / "record.md"
    if not path.is_file():
        return record
    for line in read_lines(path):
        for key in RECORD_FIELDS:
            if is_record_line(line, key):
                record[key] = line.strip()[len(key) + 1:].strip()
    return record


def memo_present(folder):
    path = folder / "closure" / "memo.md"
    if not path.is_file():
        return False
    text = "\n".join(read_lines(path))
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    for line in text.splitlines():
        s = line.strip()
        if s and not s.startswith("#"):
            return True
    return False


def plain_words(text):
    return [word.lower() for word in re.findall(r"[A-Za-z0-9][A-Za-z0-9'’-]*", text)]


def is_negated(word):
    return word in NEGATIONS or word.endswith(("n't", "n’t"))


def says_finding_closed(text, start, end, word, identifier):
    """True when the word at text[start:end] claims the finding itself is closed: "the finding is closed",
    "we closed the matter", "closure achieved for the finding". Any doubt reads as False, because a use that
    is not a claim goes on the list, where it still stops the signature until the owner rules on it."""
    subjects = CLOSED_SUBJECTS | {identifier.lower()}
    head = plain_words(SENTENCE_CUT_RE.split(text[:start])[-1])
    tail = plain_words(SENTENCE_CUT_RE.split(text[end:])[0])
    found = [i for i, w in enumerate(head) if w in subjects]
    if not CLOSED_RE.fullmatch(word):
        if tail[:1] == ["of"] and not subjects & set(tail):  # closure of the exception list closes something else
            return False
        return bool(found or subjects & set(tail)) and not any(w in CLOSED_CONDITIONS or is_negated(w) for w in head)
    if text[end:end + 1] in "-‐‑":  # closed-loop is another word
        return False
    if any(w in CLOSED_CONDITIONS or is_negated(w) for w in (head[:found[-1]] if found else head)):
        return False
    if found and all(w in CLOSED_LINKS for w in head[found[-1] + 1:]):
        between = head[found[-1] + 1:]
        rest = [w for w in tail if w not in ("out", "off", "down")]
        # "The remediation closed the gap" closes something else: closed is a verb with its own object, and no
        # form of be makes it the subject's state.
        if not BE_WORDS & set(between) and len(rest) > 1 and rest[0] in DETERMINERS and rest[1] not in subjects:
            return False
        return True
    for w in tail:
        if w in subjects:
            return True
        if w not in CLOSED_FILLERS:
            return False
    return False


# The three lines of each entry a closer or the board makes in closure/record.md: reference, date and role.
IA_FIELDS = ("Internal audit reference", "Internal audit date", "Internal audit recorded by (role)")
SUPERVISOR_FIELDS = ("Supervisor closure notice", "Supervisor closure date", "Supervisor closure recorded by (role)")
ISSUE_FIELDS = ("Issue closure reference", "Issue closure date", "Issue closure recorded by (role)")
CLOSER_FIELDS = {INTERNAL: IA_FIELDS, SELF_IDENTIFIED: ISSUE_FIELDS, SUPERVISORY: SUPERVISOR_FIELDS}
ENTRY_WORDS = ("reference", "date", "role")
# A value that holds a place for an entry still to come. Such a line counts as empty. The first words hold a place
# with more words after them, as in "to be tabled", unless a hyphen joins them into an id such as TBC-2026-1; the
# second hold a place only alone, so NA-2026-07, None-2026 and Later minutes 2026-07 count.
PLACEHOLDER_RE = re.compile(r"(?i)^(?:tbd|tbc|tba|n/a|pending|awaiting|to follow|to come|to be|not yet)(?![A-Za-z0-9-])"
                            r"|^(?:na|n\.a\.?|none|nil|unknown|later)\.?$|x{3}|_{3}|\.{3}|…")


def is_placeholder(value, reference=False):
    """True for a value that holds a place: TBD, TBC, N/A, pending, to follow, XXX, anything with a question mark or
    angle brackets, anything under three characters, and as a reference, anything with no digit, such as in
    progress or see email."""
    v = collapse(value)
    return (len(v) < 3 or any(ch in v for ch in "?<>") or PLACEHOLDER_RE.search(v) is not None
            or (reference and not any(ch.isdigit() for ch in v)))


def entry_problems(record, keys, first_check=None, today=None):
    """What keeps one entry in closure/record.md from counting, as phrases for the page and for sign; [] when its
    reference, date and role each have a real form. A placeholder counts as nothing, and a date after the check date
    does not count. A date before the first check counts, and entry_line says the check cannot see when it was made."""
    blank, held, other = [], [], []
    for key, word in zip(keys, ENTRY_WORDS):
        value = record[key].strip()
        if not value:
            blank.append(word)
        elif is_placeholder(value, word == "reference"):
            held.append(word)
        elif word == "date":
            date = parse_date(value)
            if date is None:
                other.append("the date is not written as YYYY-MM-DD")
            elif today is not None and date > today:
                other.append("the date {} is after the check date".format(date.isoformat()))
    out = ["the {} {}".format(and_list(held), "is a placeholder" if len(held) == 1 else "are placeholders")] if held else []
    if blank:
        out.append("no " + and_list(blank))
    return out + other


def entry_line(label, record, keys, problems, what="reference", first_check=None):
    """The page's line for one entry: none recorded, recorded in full, or not counted with the reason. An entry dated
    before the first check counts, as a file signed before it does, and the line says so."""
    if not any(record[key].strip() for key in keys):
        return "{}: none recorded.".format(label)
    if problems:
        return "{}: not counted ({}).".format(label, "; ".join(problems))
    date = parse_date(record[keys[1]])
    early = " It is dated before the first check on {}, so the check cannot see when it was made.".format(
        first_check.isoformat()) if first_check is not None and date is not None and date < first_check else ""
    return "{}: {}{}{}".format(label, what + " " if what else "", recorded(record[keys[0]], record[keys[1]], record[keys[2]]),
                               early)


def closer_recorded(kind, record, first_check=None, today=None):
    """True once closure/record.md holds the full entry of whoever closes this kind of finding, each line in a real
    form."""
    return not entry_problems(record, CLOSER_FIELDS.get(kind, SUPERVISOR_FIELDS), first_check, today)


def state_dates(folder, today=None):
    """(first check, check date) for a verb that reads the record outside a check: the state's first check, or the
    check date when no check has run, and the machine's date when none is given."""
    today = today or datetime.date.today()
    try:
        state = load_state(folder) or {}
    except Stop:
        state = {}
    return parse_date(str(state.get("first_check", ""))) or today, today


# Who closes each kind of finding, for the row on a line that claims the finding is closed.
CLOSES = {INTERNAL: "internal audit closes an internal audit finding", SUPERVISORY: "the Supervisor closes a supervisory "
          "finding", SELF_IDENTIFIED: "the institution's issue-management owner closes a self-identified issue"}


def closed_rows(folder, today=None):
    """[(line, claim, row, source line)] for each use of closed in the plan and the memo, comments left out, until the
    closer's entry is in the record. A line that claims the finding is closed has no source line, because no ruling
    clears its row; rewording the line does. Any other use is a row the finding owner rules on."""
    fields, _ = parse_finding(folder)
    kind = fields.get("Kind of matter")
    if closer_recorded(kind, parse_record(folder), *state_dates(folder, today)):
        return []
    rows, seen, words = [], set(), lambda text: re.findall(r"[a-z0-9]+", text.lower())
    letter = " {} ".format(" ".join(words("\n".join(read_lines(folder / "finding.md")))))
    for rel in ("plan.md", "closure/memo.md"):
        text = blank_comments("\n".join(read_lines(folder / rel))) if (folder / rel).is_file() else ""
        for m in sorted(list(CLOSED_RE.finditer(text)) + list(CLOSURE_RE.finditer(text)), key=lambda m: m.start()):
            line = text.count("\n", 0, m.start()) + 1
            word = " ".join(m.group(0).split())
            claim = "{} in {}".format(word.lower(), rel)
            claims = says_finding_closed(text, m.start(), m.end(), word, fields.get("Identifier", ""))
            near = words(text[max(0, m.start() - 99):m.start()])[-2:] + words(text[m.start():m.end() + 99])[:3]
            quoted = not claims and word.lower() == "closed" and len(near) == 5 and " {} ".format(" ".join(near)) in letter
            if (rel, line, claims) not in seen and not quoted:  # closed with two words either side as the letter has them
                seen.add((rel, line, claims))
                rows.append((line, claim, "Line {}: {} claims the finding is closed, and only {}. Reword the line, as no "
                             "ruling clears this row.".format(line, claim, CLOSES.get(kind, CLOSES[SUPERVISORY])), None)
                            if claims else (line, claim, "Line {}: {} does not read as a claim that the finding is closed, "
                                            "so the finding owner rules on it.".format(line, claim), text.split("\n")[line - 1]))
    return rows


# ---------------------------------------------------------------- evidence/


def parse_signed(value):
    v = value.strip()
    if v.lower() in ("", "none"):
        return "", None
    if "," in v:
        role, tail = v.rsplit(",", 1)
        date = parse_date(tail)
        if date is not None:
            role = role.strip()
            return ("" if role.lower() == "none" else role), date
    return v, None


def header_end(lines):
    """Where the evidence header stops: after the first run of header lines, past any blank lines
    before it. A body line that starts with a header word stays in the body. One line more counts:
    a dated Revised: line, first after a blank, because a revised file must never read as signed."""
    i = 0
    while i < len(lines) and not lines[i].strip():
        i += 1
    first = i
    while i < len(lines) and lines[i].strip().startswith(HEADER_KEYS):
        i += 1
    after = i
    while after < len(lines) and not lines[after].strip():
        after += 1
    if first < i < after < len(lines):
        s = lines[after].strip()
        if s.startswith("Revised:") and parse_date(s[len("Revised:"):]) is not None:
            return after + 1
    return i


def parse_header(path):
    """The four-line evidence header, or None when the file does not start with one. A key typed twice keeps its
    first value, except that the latest Revised date wins and any DRAFT Status makes the file a draft, so a second
    line can never make a file read as signed."""
    try:
        lines = read_lines(path)
    except Stop:
        return None
    values = {}
    revisions, statuses = [], []
    for line in lines[:header_end(lines)]:
        s = line.strip()
        if s:
            key = next(k for k in HEADER_KEYS if s.startswith(k))
            values.setdefault(key, s[len(key):].strip())
            if key == "Revised:":
                revisions.append(s[len(key):].strip())
            elif key == "Status:":
                statuses.append(s[len(key):].strip().upper())
    if not all(k in values for k in HEADER_KEYS[:3]) or not any(k in values for k in HEADER_KEYS[3:7]):
        return None
    what, for_value = values["What:"], values["For:"]
    if any(status not in ("FINAL", "DRAFT") for status in statuses) or not for_value.split():
        return None
    status = "DRAFT" if "DRAFT" in statuses else "FINAL"
    revised = None
    if revisions:
        dates = [parse_date(value) for value in revisions]
        if None in dates:
            return None
        revised = max(dates)
    # In place of a person's signature, which wins where both stand: the evidence id of a separate record that approved
    # the document, then a few words for material an institution never signs, then the system and as-at date of system output.
    signed = parse_signed(values.get("Signed by:", ""))
    approved = "" if signed[0] else (re.findall(r"[^\s,;]+", values.get("Approved by:", "")) or [""])[0]
    never = "" if signed[0] or approved else values.get("Never signed:", "")
    produced = "Produced by:" in values and not (signed[0] or approved or never)
    role, date = parse_signed(values["Produced by:"]) if produced else signed
    return {
        "what": what,
        "id": for_value.split()[-1],
        "role": role,
        "date": date,
        "status": status,
        "revised": revised,
        "checked_by": values.get("Checked by:", ""),
        "produced": produced,
        "approved": approved,
        "never": never,
    }


def covered_name(path, lines):
    """The file a cover names: its Covers: line in the header, or the name without .md for X.pdf.md."""
    for line in lines[:header_end(lines)]:
        s = line.strip()
        if s.startswith("Covers:") and s[len("Covers:"):].strip():
            return s[len("Covers:"):].strip()
    if path.suffix.lower() == ".md":
        inner = Path(path.name[: -len(path.suffix)])
        if inner.suffix.lower() == ".txt" and (path.parent / inner.name).is_file():
            return inner.name
        if inner.suffix and inner.suffix.lower() not in TEXT_SUFFIXES and inner.suffix[1:].isalpha():
            return inner.name
    return None


def is_plain_document(path):
    """True for a .txt that is a document, such as a system export: it holds no evidence header and
    names no covered file. Its bytes stay as they came, and a cover beside it carries the header."""
    if path.suffix.lower() != ".txt" or parse_header(path) is not None:
        return False
    try:
        return covered_name(path, read_lines(path)) is None
    except Stop:
        return True


def named_by_cover(path):
    """(the file this text file covers, the name it gives), or (None, None)."""
    try:
        name = covered_name(path, read_lines(path))
    except Stop:
        return None, None
    if not name:
        return None, None
    return path.parent / Path(name.replace("\\", "/")).name, name


def evidence_files(ev_dir):
    """Every file under evidence/, leaving out dot files and dot folders."""
    return [p for p in ev_dir.rglob("*") if p.is_file()
            and not any(part.startswith(".") for part in p.relative_to(ev_dir).parts)]


def covered_files(files):
    """The documents that some text file among these names as covered."""
    has_cover = set()
    for p in files:
        if p.suffix.lower() in TEXT_SUFFIXES:
            target = named_by_cover(p)[0]
            if target is not None and target.is_file():
                has_cover.add(target)
    return has_cover


def evidence_digest(path):
    """The hash the state file and a signature keep for one evidence file."""
    return text_digest(path) if path.suffix.lower() in FOLDED_SUFFIXES else sha256_bytes(path.read_bytes())


def scan_evidence(folder):
    """Counted evidence entries and the files that are not counted, in path order."""
    ev_dir = folder / "evidence"
    entries = []
    uncounted = []
    if not ev_dir.is_dir():
        return entries, uncounted
    files = evidence_files(ev_dir)
    files.sort(key=lambda p: p.relative_to(folder).as_posix())
    has_cover = covered_files(files)
    for p in files:
        rel = p.relative_to(folder).as_posix()
        if p.suffix.lower() in TEXT_SUFFIXES and not is_plain_document(p):
            header = parse_header(p)
            covered, name = named_by_cover(p)
            is_cover = covered is not None and covered.is_file()
            if covered is not None and not is_cover:
                uncounted.append((rel, "whose covered file {} is missing".format(name)))
                continue
            if header is None:
                uncounted.append((rel, "whose first lines are not the evidence header"))
                if is_cover:
                    uncounted.append((covered.relative_to(folder).as_posix(),
                                      "whose cover file has no evidence header"))
                continue
            entry = dict(header, hashed=[(rel, evidence_digest(p))])
            if is_cover:  # a signature keeps the cover's header; the pages typed below it answer to its Checked by line
                lines = read_lines(p)
                head = [s for s in lines[:header_end(lines)] if not s.strip().startswith(("Source:", "Checked by:"))]
                body = COMMENT_RE.sub("", "\n".join(lines[header_end(lines):])).strip()
                entry.update(whole=entry["hashed"][0][1], pages=sha256_bytes(body.encode("utf-8")), hashed=[
                    (rel, sha256_bytes("\n".join(head).encode("utf-8"))), (covered.relative_to(folder).as_posix(), evidence_digest(covered))])
            entries.append(entry)
        elif p not in has_cover:
            cover = p.with_name(p.name + ".md")
            uncounted.append((rel, "which {} does not cover".format(cover.name) if cover.is_file()
                              else "which has no cover file " + cover.name))
    held = {entry["id"]: entry for entry in entries}
    for entry in (e for e in entries if e["approved"] in held):  # an approved document counts on its record's role and date
        entry["approver"] = held[entry["approved"]]
        entry["role"], entry["date"] = entry["approver"]["role"], entry["approver"]["date"]
    return entries, uncounted


def update_evidence_state(entries, state_ev, today, state_ids=None):
    """Record new files, re-record files signed again, and flag files changed since signing. A file re-recorded keeps
    the rest of its record. With state_ids, each signed file's hashes are kept by its evidence id as well as by its
    path, so a signed file renamed and changed, or another file put in its place under the same id, reads as changed.
    A cover's typed pages keep the date of the check that first saw them change, and a Checked by line dated before
    it answers for none of them."""
    for entry in entries:
        signed = entry["date"].isoformat() if entry["date"] else None
        changed = False
        for rel, sha in entry["hashed"]:
            old = state_ev.get(rel)
            if not isinstance(old, dict) or "sha256" not in old:
                state_ev[rel] = {"sha256": sha, "signed": signed}
                continue
            old_signed = old.get("signed")
            if old["sha256"] in (sha, entry.get("whole")):  # an earlier check hashed a cover whole
                state_ev[rel] = dict(old, sha256=sha, signed=max(signed or "", old_signed or "") or None)
                continue
            if old_signed is None or (signed is not None and signed > old_signed):
                state_ev[rel] = dict(old, sha256=sha, signed=signed)
            else:
                changed = True
        entry["changed"] = changed
        record, checked = state_ev[entry["hashed"][0][0]], parse_signed(entry["checked_by"])[1]
        if "pages" in entry and record.setdefault("pages", entry["pages"]) != entry["pages"]:
            record.update(pages=entry["pages"], seen=today.isoformat())
        if record.get("seen") and entry["checked_by"] and not (checked and checked.isoformat() >= record["seen"]):
            entry["checked_by"], entry["stale"] = "", record["seen"]
    if state_ids is None:
        return
    ids = [entry["id"] for entry in entries]
    for entry in entries:
        if entry["date"] is None or ids.count(entry["id"]) > 1:  # two files under one id stop the memo check anyway
            continue
        signed = entry["date"].isoformat()
        hashes = sorted(sha for _, sha in entry["hashed"])
        whole = sorted([entry.get("whole") or entry["hashed"][0][1]] + [sha for _, sha in entry["hashed"][1:]])
        old = state_ids.get(entry["id"])
        if not (isinstance(old, dict) and isinstance(old.get("sha256"), list) and isinstance(old.get("signed"), str)):
            state_ids[entry["id"]] = {"sha256": hashes, "signed": signed}
        elif old["sha256"] in (hashes, whole) or signed > old["signed"]:
            state_ids[entry["id"]] = {"sha256": hashes, "signed": max(signed, old["signed"])}
        else:
            entry["changed"] = True


def same_bytes(named):
    """Each group of two or more names, from (name, hash) pairs, whose files hold the same bytes, in words."""
    groups = {}
    for name, sha in named:
        groups.setdefault(sha, []).append(name)
    return [and_list(names) for names in groups.values() if len(names) > 1]


def filed_elsewhere(entries, state_ids):
    """[(path, id it was signed under, date of that signature, id it sits under now)] for each file whose bytes were
    signed under one evidence id and now sit under another, not signed again since. While a file under the first id
    still holds those bytes, the second file is a copy, and nothing was refiled."""
    out = []
    held = {(entry["id"], sha) for entry in entries for _, sha in entry["hashed"]}
    for entry in entries:
        for rel, sha in entry["hashed"]:
            for eid in sorted(state_ids):
                item = state_ids[eid]
                if (eid != entry["id"] and isinstance(item, dict) and sha in (item.get("sha256") or ())
                        and (eid, sha) not in held
                        and (entry["date"] is None or entry["date"].isoformat() <= str(item.get("signed")))):
                    out.append((rel, eid, item.get("signed"), entry["id"]))
                    break
    return out


def late_arrivals(entries, state, gone, before, ids_before):
    """[(path, the page's words after it)] for each file that came in under the evidence id of a signed file gone
    before it came in, with a signature dated on or before the last check that still saw the file that went. That is
    a backdated swap, so it is signed again before it counts. A file signed before it came in is how evidence arrives,
    and a file that came in before a file went is never flagged. A gone file keeps that last check and its id from the
    check that first finds it gone, and a flagged file keeps the date its signature must pass."""
    recorded, went = state["evidence"], {}
    for rel in gone:
        item = recorded[rel]
        if isinstance(item, dict) and item.get("signed"):
            if "last" not in item:
                item["last"] = state.get("checked") or state["first_check"]
                item["id"] = next((eid for eid, held in sorted(ids_before.items()) if isinstance(held, dict)
                                   and item.get("sha256") in (held.get("sha256") or ())), None)
            went[item.get("id")] = max(went.get(item.get("id"), ""), str(item["last"]))
    out = []
    for entry in entries:
        rel, signed = entry["hashed"][0][0], entry["date"].isoformat() if entry["date"] else ""
        if rel not in before and signed and signed <= went.get(entry["id"], ""):
            recorded[rel]["after"] = went[entry["id"]]
        if signed and signed <= str(recorded[rel].get("after", "")):
            out.append((rel, " came in under {} after the signed file under that id went, with a signature dated {}, on "
                             "or before {}, the last check that saw the file that went. Sign it again.".format(
                                 entry["id"], signed, recorded[rel]["after"])))
    return out


def file_reason(entry, today):
    """Why one evidence file is not signed, or None when it is. System output answers by its as-at date, an approved
    document first by its approving record, which needs a signature of its own, and a file never signed never blocks."""
    eid, made, by = entry["id"], entry["produced"], entry.get("approver")
    if entry["status"] == "DRAFT" or entry["never"]:
        return "{} is a draft".format(eid) if entry["status"] == "DRAFT" else None
    why = entry["approved"] and ("which is missing" if by is None else "which carries no signature"
                                 if by["produced"] or by["approved"] or by["never"]
                                 else (reason := file_reason(by, today)) and "and " + reason)
    if why:
        return "{} is approved by {}, {}".format(eid, entry["approved"], why)
    if not entry["role"]:
        return "{} names no {}".format(eid, "system" if made else "role")
    if entry["date"] is None:
        return "{} gives no {} date".format(eid, "as-at" if made else "signature")
    if entry["date"] > today:
        return "{} carries {} {}, after the check date".format(
            eid, "an as-at date of" if made else "a signature dated", entry["date"].isoformat())
    if entry["revised"] is not None and entry["revised"] > entry["date"]:
        return "{} was revised on {}, after its {} of {}".format(eid, entry["revised"].isoformat(), "as-at date" if made else
                                                                 "approval" if entry["approved"] else "signature", entry["date"].isoformat())
    if entry.get("changed"):
        return "{} changed since {}".format(eid, "its as-at date" if made else "it was approved" if entry["approved"] else "it was signed")
    return None


def loose_id(eid):
    """An evidence id with case and leading zeros set aside, so EV-021, ev-21 and EV-21 read alike."""
    return re.sub(r"(?<![0-9])0+(?=[0-9])", "", eid.upper())


def plan_hint(row, entries, rows):
    """Words for a milestone whose evidence id has no file: the file evidence/ holds under a near id that no
    milestone lists, as when plan.md says EV-021 and the file says EV-21."""
    listed = {eid for other in rows for eid in other["ids"]} | {PLAN_ID}
    have = {entry["id"] for entry in entries}
    hints = []
    for eid in row["ids"]:
        if eid in have:
            continue
        near = [entry for entry in entries if entry["id"] not in listed and loose_id(entry["id"]) == loose_id(eid)]
        if near:
            hints.append("plan.md names {} and evidence/ holds {} in {}, which no milestone lists".format(
                eid, near[0]["id"], near[0]["hashed"][0][0]))
    return " " + "; ".join(hints) + "." if hints else ""


def milestone_state(row, by_id, today):
    """('not started' | 'unsigned' | 'signed', reason or None, the file that dates it or None). The file plan.md marks done
    dates it, else the newest, a signed one before system output of the same date. A file never signed never counts."""
    if not any(by_id.get(i) for i in row["ids"]):
        return "not started", None, None
    for eid in row["ids"]:
        reason = next((r for r in (file_reason(e, today) for e in by_id.get(eid, ())) if r), None)
        if reason or not by_id.get(eid):
            return "unsigned", reason or "{} is missing".format(eid), None
    ids = [i for i in row["ids"] if i == (row["done"] or i)]
    dating = [e for i in ids for e in by_id[i] if not e["never"]]
    if not dating:
        return "unsigned", "{} {} never signed, so list in plan.md the file that shows {} done".format(
            and_list(ids), "is" if len(ids) == 1 else "are", row["id"]), None
    return "signed", None, max(dating, key=lambda e: (e["date"], not e["produced"]))


# ---------------------------------------------------------------- deny list


def institution_words(institution):
    """The words of the institution's name that count alone: four letters or more, all capitals such as QX, or
    holding an ampersand such as R&K."""
    words = re.findall(r"[A-Za-z][A-Za-z0-9&'’-]*", institution)
    return [w for w in words if w.upper() != "BANK" and (len(w) >= 4 or "&" in w or (len(w) >= 2 and w.isupper()))]


def bank_name(fields):
    """The institution's full name, folded for comparison. role-words.txt never clears it."""
    return fold(fields.get("Institution", "").strip()).casefold()


def role_words_for(folder, fields):
    """The lines of role-words.txt, less the institution's full name. A line may clear one word of it."""
    return {line for line in fit_lines(folder, "role-words.txt") if fold(line).casefold() != bank_name(fields)}


def harvest_names(fields, parts, role_words=()):
    """The institution's full name, each word of it that counts alone, and the runs of capitalised words in the letter
    that hold no role word and no document word. role_words drops a run or a word of the institution's name, and never its
    full name."""
    names = []
    institution = fields.get("Institution", "").strip()
    if institution:
        names.append(institution)
        for word in institution_words(institution):
            if word not in names and word not in role_words:
                names.append(word)
    for name in PARTS:
        text = parts.get(name, "")
        for m in RUN_RE.finditer(text):
            words = m.group(0).split()
            if words[0] in SENTENCE_OPENERS and starts_sentence(text, m.start()):
                words = words[1:]
            if not 2 <= len(words) <= 3:
                continue
            words[-1] = re.sub(r"['’]s$", "", words[-1])
            bare = [re.sub(r"['’]s$", "", w) for w in words]
            if all(w in MONTH_WORDS for w in bare) or " ".join(bare) in role_words or TITLE_RE.search(" ".join(bare)):
                continue
            if any((w in ROLE_WORDS and w not in MONTH_WORDS) or w in role_words for w in bare):
                continue
            run = " ".join(words)
            if run not in names:
                names.append(run)
    return names


def starts_sentence(text, pos):
    line_prefix = text[:pos].split("\n")[-1]
    line_prefix = re.sub(r"^\s*(?:(?:[-*+>#]+|\d+[.)])\s*)*", "", line_prefix)
    stripped = line_prefix.rstrip(" \t\"'“‘([")
    if not stripped:
        return True
    return stripped[-1] in ".!?"


def first_denied(screen, names, flags=0):
    """The term that starts first on the page, the longest where two start together, so a quotation of the institution's
    full name is named as the full name, never as its first word."""
    best = None
    for name in names:
        if not name:
            continue
        pattern = r"(?<![A-Za-z0-9])" + re.escape(name) + r"(?![A-Za-z0-9])"
        m = re.search(pattern, screen, flags)
        if m is None:
            continue
        key = (m.start(), -len(name))
        if best is None or key < best[0]:
            best = (key, name)
    return best[1] if best else None


def fold(text):
    """Text with its accents taken off, so a listed Société also stops Societe."""
    return "".join(ch for ch in unicodedata.normalize("NFD", text) if unicodedata.category(ch) != "Mn")


def listed_terms(folder):
    """The lines of denylist.txt."""
    return fit_lines(folder, "denylist.txt")


def cleared_name(name, fields, role_words):
    """True when role-words.txt clears a term the check took for a name. The institution's full name never clears, and
    denylist.txt wins, because page_names adds its lines back afterwards."""
    if fold(name).casefold() == bank_name(fields):
        return False  # a title an earlier check saved clears too, since the letter no longer gives it
    return bool(TITLE_RE.search(name)) or name in role_words or any(word in role_words for word in name.split())


def deny_of(state):
    return state["deny"] if isinstance(state.get("deny"), dict) else {}


def page_names(folder, fields, parts, state):
    """Every name a page must not print: what a check saved, what the letter gives, and denylist.txt, less
    what role-words.txt clears. The one list for check, covers and eval. Reads only."""
    role_words = role_words_for(folder, fields)
    saved = deny_of(state).get("names")
    names = [n for n in (saved if isinstance(saved, list) else [])
             if isinstance(n, str) and not cleared_name(n, fields, role_words)]
    for name in harvest_names(fields, parts, role_words) + listed_terms(folder):
        if name not in names and name != fields.get("Identifier"):
            names.append(name)
    return names


def page_denied(folder, screen, names, identifier=None):
    """The first deny-list term a page would print. A word from the letter matches as written or in capitals,
    because Trust in an institution's name must leave the word trust alone. A run of words from the letter, such as the
    institution's full name, matches in any letter case. A line a person wrote in denylist.txt matches in any letter
    case and with or without accents."""
    if identifier:
        screen = screen.replace(identifier, " ")
    words = [n for n in names if len(n.split()) < 2]
    capitals = {w.upper(): w for w in words if w.upper() != w}
    word = first_denied(screen, words + list(capitals))
    found = [capitals.get(word, word), first_denied(screen, [n for n in names if len(n.split()) >= 2], re.I),
             first_denied(fold(screen), [fold(t) for t in listed_terms(folder)], re.I)]
    found = [term for term in found if term is not None]
    if not found:
        return None
    first = first_denied(fold(screen), [fold(term) for term in found], re.I)
    return next(term for term in found if fold(term) == first)


def named_file(folder, screen, term):
    """True when the page would print the term inside the name of a file in the folder."""
    pattern = re.compile(r"(?<![A-Za-z0-9])" + re.escape(fold(term)) + r"(?![A-Za-z0-9])", re.I)
    try:
        return any(pattern.search(fold(path.name)) and path.name in screen for path in folder.rglob("*"))
    except OSError:
        return False


def deny_refusal(folder, fields, term, screen=""):
    """role-words.txt clears neither denylist.txt nor the institution's full name, so their refusal never offers it. An institution's
    file keeps its own name, so a refusal over any other term offers role-words.txt before a rename."""
    fix = "" if fold(term).casefold() in {fold(t).casefold() for t in listed_terms(folder)} | {bank_name(fields)} else ROLE_FIX
    if screen and named_file(folder, screen, term):
        return ('Refused: "{}" is on this finding\'s deny list, and the page would print it in the name of a file in this '
                'folder.{} {}ename the file using roles only.'.format(term, fix, "Otherwise r" if fix else "R"))
    return 'Refused: "{}" is on this finding\'s deny list and would be printed. Use roles only.{}'.format(term, fix)


def left_out_names(fields, parts, names):
    """The runs and words of the letter that role-words.txt keeps off the deny list."""
    return [n for n in harvest_names(fields, parts) if n not in names]


def deny_line(names, fields, parts):
    """The count line for the check page: the names and what role-words.txt took off."""
    left = left_out_names(fields, parts, names)
    bank = [w for w in institution_words(fields.get("Institution", "")) if w in left]
    said = (["left out {}".format(len(left) - len(bank))] if len(left) > len(bank) else []) + (
        ["cleared {} of the institution's name".format(plural(len(bank), "word"))] if bank else [])
    return "Deny list: {}{}.".format(plural(len(names), "name"), "; role-words.txt " + " and ".join(said) if said else "")


# ---------------------------------------------------------------- quarters


def quarter_end(d):
    month = ((d.month - 1) // 3 + 1) * 3
    return datetime.date(d.year, month, 31 if month in (3, 12) else 30)


def quarter_ends(first, last):
    ends = []
    q = quarter_end(first)
    stop = quarter_end(max(first, last))
    while q <= stop:
        ends.append(q)
        q = quarter_end(q + datetime.timedelta(days=1))
    return ends


# ---------------------------------------------------------------- state file


STATE_RESET = ("the next check then counts as the first, and the first-check date, the record of signed files and "
               "the signature are gone.")


def load_state(folder):
    path = folder / STATE_NAME
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeDecodeError):
        raise Stop(
            "Refused: {} is not valid JSON. Delete it to start the record again; {}".format(STATE_NAME, STATE_RESET)
        )
    if not isinstance(data, dict):
        raise Stop("Refused: {} does not hold a state record. Delete it to start the record "
                   "again; {}".format(STATE_NAME, STATE_RESET))
    if not state_well_formed(data):
        raise Stop("Refused: {} holds a value no check writes. Restore it, or delete it to start the "
                   "record again; {}".format(STATE_NAME, STATE_RESET))
    return data


def state_well_formed(data):
    """False when the state file holds a date, name or fingerprint no check writes, as a hand edit or a
    bad merge can leave. An absent value is fine, because a check fills it in."""
    def is_date(value):
        return isinstance(value, str) and parse_date(value) is not None

    for key in ("first_check", "repasted", "checked"):
        if key in data and not is_date(data[key]):
            return False
    signature = data.get("signature")
    if isinstance(signature, dict) and signature.get("fingerprint") is not None:
        if not isinstance(signature["fingerprint"], str) or not is_date(signature.get("date")):
            return False
    deny = data.get("deny")
    if isinstance(deny, dict):
        for key in ("names",):
            if isinstance(deny.get(key), list) and not all(isinstance(item, str) for item in deny[key]):
                return False
    evidence = data.get("evidence")
    if isinstance(evidence, dict):
        for item in evidence.values():
            if isinstance(item, dict) and any(item.get(k) is not None and not is_date(item[k]) for k in ("signed", "seen")):
                return False
    ids = data.get("ids")
    if isinstance(ids, dict):
        for item in ids.values():
            if isinstance(item, dict) and not (is_date(item.get("signed")) and isinstance(item.get("sha256"), list)):
                return False
    plan = data.get("plan")
    if plan is not None:
        if not (isinstance(plan, dict) and is_date(plan.get("approved")) and isinstance(plan.get("dates"), dict)
                and all(is_date(value) for value in plan["dates"].values()) and isinstance(plan.get("late", []), list)
                and all(isinstance(move, list) and len(move) == 3 for move in plan.get("late", []))):
            return False
        first = plan.get("first")
        if first is not None and not (isinstance(first, dict) and is_date(first.get("approved"))
                                      and isinstance(first.get("dates"), dict)
                                      and all(is_date(value) for value in first["dates"].values())):
            return False
    if isinstance(signature, dict) and signature.get("machine_date") is not None and not is_date(signature["machine_date"]):
        return False
    return True


def part_hashes(parts):
    """Hashes of the five parts with runs of whitespace collapsed, so re-wrapped lines are no change."""
    return {name: sha256_bytes(" ".join(parts[name].split()).encode("utf-8")) for name in PARTS}


def dump_state(state):
    deny = {"identifier": state["deny"]["identifier"], "names": list(state["deny"]["names"])}
    ordered = {"version": 1, "first_check": state["first_check"]}
    for key in ("repasted", "checked"):  # the latest check, so a file that goes keeps the last check that saw it
        if state.get(key):
            ordered[key] = state[key]
    ordered.update({
        "parts": {name: state["parts"].get(name) for name in PARTS},
        "frozen": {name: state["frozen"].get(name) for name in FROZEN_FIELDS},
        "evidence": {key: state["evidence"][key] for key in sorted(state["evidence"])},
        "ids": {key: state["ids"][key] for key in sorted(state.get("ids") or {})},
    })
    if state.get("plan"):
        ordered["plan"] = state["plan"]
    ordered.update({
        "deny": deny,
        "signature": state.get("signature"),
    })
    return json.dumps(ordered, indent=2, ensure_ascii=False) + "\n"


# ---------------------------------------------------------------- check


def check(folder, today):
    """Build the screen in memory. Returns (text, exit code); raises Stop on a refusal."""
    screen, code, _info = run_check(folder, today)
    return screen, code


def frozen_refusal(name, first_check, issuer):
    """The refusal for text that moved after the first check. A wrong paste of the letter has a way to be corrected.
    The issuer and the kind of matter decide what may leave the institution, and the owner role decides who rules and signs,
    so only people can undo them."""
    if name == "Owner role":
        return ("Refused: the Owner role in finding.md is not the role first checked on {}. The owner rules on the list "
                "and signs, so the role does not change after the first check; restore it. If the institution has named a new "
                "owner, internal audit decides whether to start {} again, which drops the record of signed files and the "
                "signature.".format(first_check, STATE_NAME))
    lead = "Refused: the {} in finding.md is not the text first checked on {}. {} words do not change; restore them".format(
        name, first_check, capital_first(possessive(issuer)))
    if name in LABEL_FIELDS:
        return lead + (". If the first paste was wrong, the finding owner and the institution's lawyers decide whether to start "
                       "{} again, which drops the record of signed files and the signature.".format(STATE_NAME))
    return lead + ", or run check --repaste if the first paste was wrong."


def frozen_moved(name, frozen, fields):
    """True when a frozen field no longer reads as first checked. The owner role is compared with runs of spaces
    collapsed, as sign compares it."""
    if frozen.get(name) is None:
        return False
    if name == "Owner role":
        return collapse(str(frozen[name])) != collapse(fields.get(name) or "")
    return frozen[name] != fields.get(name)


def require_frozen(fields, frozen, first_check, issuer):
    for name in FROZEN_FIELDS:
        if frozen_moved(name, frozen, fields):
            raise Stop(frozen_refusal(name, first_check, issuer))


def repaste_letter(folder, today):
    """check --repaste: record a corrected paste of the letter, its identifier and its date. The evidence
    record, the deny list and the signature stay. The page and the log say it happened, and a signature then
    reads as changed, because finding.md is fingerprinted. The issuer and the kind of matter stay frozen."""
    fields, parts = parse_finding(folder)
    require_ready(fields, parts)
    state = load_state(folder)
    if state is None:
        raise Stop("Refused: no check has recorded this letter yet, so there is nothing to correct. Run check.")
    frozen = state.get("frozen") if isinstance(state.get("frozen"), dict) else {}
    first = state.get("first_check", "the first check")
    for name in LABEL_FIELDS + ("Owner role",):
        if frozen_moved(name, frozen, fields):
            raise Stop(frozen_refusal(name, first, fields["Issuer"]))
    stored = state.get("parts") if isinstance(state.get("parts"), dict) else {}
    hashes = part_hashes(parts)
    moved = [name for name in PARTS if name in stored and stored[name] != hashes[name]]
    moved += [name for name in ("Identifier", "Letter date") if name in frozen and frozen[name] != fields[name]]
    if not moved:
        return
    state["parts"] = hashes
    state["frozen"] = dict(frozen, **{name: fields[name] for name in ("Identifier", "Letter date")})
    if isinstance(state.get("deny"), dict):
        state["deny"]["identifier"] = fields["Identifier"]
    state["repasted"] = today.isoformat()
    write_text(folder / STATE_NAME, json.dumps(state, indent=2, ensure_ascii=False) + "\n")
    append_log(folder, today, mode="repaste", outcome="letter text corrected", changed=moved)


def run_check(folder, today):
    """The check, with what sign needs to know: (text, exit code, info). Raises Stop."""
    fields, parts = parse_finding(folder)
    require_ready(fields, parts)
    issuer = fields["Issuer"]
    identifier = fields["Identifier"]
    kind = fields["Kind of matter"]
    letter = parse_date(fields["Letter date"])

    old_state = load_state(folder)
    hashes = part_hashes(parts)
    if old_state is None:
        if kind != SUPERVISORY and any(word in issuer.lower() for word in SUPERVISOR_WORDS):
            raise Stop('Refused: finding.md gives the Issuer as "{}" and the Kind of matter as "{}". What the Supervisor '
                       "wrote is a {}. Correct one of the two lines.".format(issuer, kind, SUPERVISORY))
        state = {
            "version": 1,
            "first_check": today.isoformat(),
            "parts": hashes,
            "frozen": {name: fields[name] for name in FROZEN_FIELDS},
            "evidence": {},
            "ids": {},
            "deny": {"identifier": identifier, "names": []},
        }
    else:
        state = json.loads(json.dumps(old_state))
        state.setdefault("first_check", today.isoformat())
        stored = state.get("parts")
        if not isinstance(stored, dict) or not stored:
            stored = dict(hashes)
        state["parts"] = stored
        if not isinstance(state.get("evidence"), dict):
            state["evidence"] = {}
        if not isinstance(state.get("ids"), dict):
            state["ids"] = {}
        deny = state.get("deny")
        if not isinstance(deny, dict):
            deny = {}
        deny.setdefault("identifier", identifier)
        if not isinstance(deny.get("names"), list):
            deny["names"] = []
        state["deny"] = deny
        for name in PARTS:
            if name in stored and stored[name] != hashes[name]:
                raise Stop(frozen_refusal(name, state["first_check"], issuer))
            stored.setdefault(name, hashes[name])
        frozen = state.get("frozen") if isinstance(state.get("frozen"), dict) else {}
        state["frozen"] = frozen
        for name in FROZEN_FIELDS:
            if frozen.get(name) is None:  # a field a check before this release did not freeze freezes now
                frozen[name] = fields[name]
        require_frozen(fields, frozen, state["first_check"], issuer)

    rows = parse_plan(folder)
    record = parse_record(folder)
    first_date = parse_date(state["first_check"])
    problems = {keys: entry_problems(record, keys, first_date, today)
                for keys in (IA_FIELDS, SUPERVISOR_FIELDS, ISSUE_FIELDS, BOARD_FIELDS)}

    entries, uncounted = scan_evidence(folder)
    before, ids_before = set(state["evidence"]), dict(state["ids"])
    update_evidence_state(entries, state["evidence"], today, state["ids"])
    by_id = {}
    for entry in entries:
        by_id.setdefault(entry["id"], []).append(entry)

    names = state["deny"]["names"] = page_names(folder, fields, parts, state)
    went = gone_files(folder, state, entries, uncounted)
    gone = [shown_path(folder, rel, names) for rel in went]
    moved_ids = filed_elsewhere(entries, state["ids"])
    arrived = late_arrivals(entries, state, went, before, ids_before)
    state["checked"] = today.isoformat()

    plan_files = by_id.get(PLAN_ID, [])
    plan_reasons = [r for r in (PLAN_ID + " carries no signature" if e["produced"] or e["approved"] or e["never"]
                                else file_reason(e, today) for e in plan_files) if r]
    plan_signed = bool(plan_files) and not plan_reasons
    proposed = not plan_signed
    # The board's approval freezes the committed dates: a later edit to plan.md shows as a move, and lateness counts
    # from the date the board approved. Minutes signed again later approve the plan as it then stands, and the first
    # approval stays in the state, so a date moved then still shows. A move is flagged, and stays flagged, when the
    # approval that first carried the new date came after the old date had passed.
    approved, approved_on, first_on, first_dates, late_moves = {}, None, None, {}, []
    if plan_signed:
        latest = max(e["date"] for e in plan_files).isoformat()
        kept = state.get("plan")
        if not (isinstance(kept, dict) and isinstance(kept.get("dates"), dict) and str(kept.get("approved")) >= latest):
            dates = {row["id"]: row["date"].isoformat() for row in rows}
            old = kept if isinstance(kept, dict) and isinstance(kept.get("dates"), dict) else None
            kept = state["plan"] = {"approved": latest, "dates": dates}
            if old is not None:
                kept["first"] = old.get("first") or {"approved": old["approved"], "dates": dict(old["dates"])}
                kept["late"] = old.get("late", []) + [[mid, date, latest] for mid, date in sorted(old["dates"].items())
                                                      if dates.get(mid, date) != date and latest > date]
        approved_on, late_moves = kept["approved"], kept.get("late", [])
        approved = {mid: parse_date(str(date)) for mid, date in kept["dates"].items()}
        if isinstance(kept.get("first"), dict):
            first_on = kept["first"]["approved"]
            first_dates = {mid: parse_date(str(date)) for mid, date in kept["first"]["dates"].items()}
    plan_changes = []
    for row in rows:
        row["committed"] = approved.get(row["id"]) or row["date"]
        row["added"] = approved_on is not None and row["id"] not in approved
        if row["added"]:
            plan_changes.append(row["id"] + " added")
        elif row["committed"] != row["date"]:
            plan_changes.append("{} moved to {}".format(row["id"], row["date"].isoformat()))
    taken_out = sorted(set(approved) - {row["id"] for row in rows})  # stops the signature until the board approves
    plan_changes += ["{} taken out".format(mid) for mid in taken_out]

    def show(d, row=None):
        return d.isoformat() + (" proposed" if proposed or (row is not None and row["added"]) else "")

    def committed(row):
        """The committed date as the page shows it: the approved date, and where plan.md moved it since, and the date
        the board first approved when it approved a moved date later."""
        if row["committed"] != row["date"]:
            text = "{}, moved to {} in plan.md after the board approved the plan".format(
                row["committed"].isoformat(), row["date"].isoformat())
        else:
            text = show(row["date"], row)
        first = first_dates.get(row["id"])
        if first is not None and first != row["committed"]:
            text += ", first committed {} when the board approved the plan on {}".format(first.isoformat(), first_on)
        return text

    needs = NeedsByRole()
    below = []
    out = [CONFIDENTIAL, ""]
    article = "an" if kind[:1].lower() in "aeiou" else "a"
    out.append("Finding {}, {} {} from {} dated {}. Owner: {}. Checked as of {}, kit release {}.".format(
        identifier, article, kind, issuer, letter.isoformat(), fields["Owner role"],
        today.isoformat(), kit_release()[0]))
    out.extend(kit_note())
    if state.get("repasted"):
        out.append("The letter's text was corrected on {}, after the first check on {}. The log holds the change.".format(
            state["repasted"], state["first_check"]))
    out.append("")

    out.append("Milestones")
    flags = ["{} moved from {} by the board's approval on {}, after that date had passed".format(*move) for move in late_moves]
    signed_on = {}
    for row in rows:
        state_name, reason, newest = milestone_state(row, by_id, today)
        line = "{}. {}, committed {}. ".format(row["cell"].rstrip("."), row["owner"], committed(row))
        date = row["committed"]
        if state_name == "signed":
            latest = signed_on[row["id"]] = newest["date"]
            made = ["{} was produced by {} on {}".format(e["id"], with_the(e["role"]), e["date"].isoformat())
                    for i in row["ids"] for e in by_id[i] if e["produced"]]
            okayed = ["{} was approved by {} on {}".format(e["id"], e["approved"], e["date"].isoformat())
                      for i in row["ids"] for e in by_id[i] if e["approved"]]
            never = ["{} ({})".format(e["id"], e["never"]) for i in row["ids"] for e in by_id[i] if e["never"]]
            line += "Present{} on {}{}.".format("" if newest["produced"] else " and signed", latest.isoformat(), ", the date of {}, "
                                               "which plan.md marks done".format(row["done"]) if row["done"] else "") + (
                " {}, with no signature.".format(and_list(made)) if made else "") + (" {}.".format(and_list(okayed)) if okayed else "") + (
                " Never signed: {}.".format(and_list(never)) if never else "")
            if latest > date:
                flags.append("{} {} {} after its commitment".format(
                    row["id"], "present" if newest["produced"] else "signed", plural((latest - date).days, "day")))
        else:
            if state_name == "not started":
                line += "Not started."
            else:
                line += "Present, unsigned: {}.".format(reason)
            line += plan_hint(row, entries, rows)
            needs.add(row["owner"], row["id"])
            below.append(row["id"])
            if today > date:
                late = (today - date).days
                line += " SLIPPED by {}.".format(plural(late, "day"))
                flags.append("{} slipped {}".format(row["id"], plural(late, "day")))
            elif (date - today).days <= 14:
                due = (date - today).days
                line += " AT RISK, due in {}.".format(plural(due, "day"))
                flags.append("{} at risk, due in {}".format(row["id"], plural(due, "day")))
        out.append(line)
    out.append("")

    if uncounted:
        out.append("Not counted")
        for rel, why in uncounted:
            out.append("{}, {}.".format(rel, why))
            needs.add("The engagement team", "the uncounted file " + rel)
        out.append("")
    if gone:
        out.append("Gone since an earlier check")
        out.extend((rel if "/" in rel else capital_first(rel)) + "." for rel in gone)
        out.append("")
    if moved_ids:
        out.append("Filed under another id since signing")
        for rel, was, signed, now in moved_ids:
            shown = shown_path(folder, rel, names)
            out.append("{} holds what was signed as {} on {}, and is now filed as {}.".format(
                shown if "/" in shown else capital_first(shown), was, signed, now))
            needs.add("The engagement team", "{}, signed as {}".format(shown, was))
        out.append("")
    if arrived:
        out.append("Came in after a signed file went")
        for rel, words in arrived:
            shown = shown_path(folder, rel, names)
            out.append((shown if "/" in shown else capital_first(shown)) + words)
            needs.add("The engagement team", "{}, signed again".format(shown))
        out.append("")

    for pair in same_bytes((entry["id"], entry["hashed"][-1][1]) for entry in entries):  # such as a scan filed twice
        needs.add("The engagement team", "the same bytes in " + pair)
    if proposed:
        needs.add("The board", "its approval of the plan")
    elif plan_changes:
        needs.add("The board", "its approval of the changes to the plan since {} ({})".format(
            approved_on, and_list([change.split()[0] for change in plan_changes])))

    out.append("Board summary, a draft for the finding owner")
    out.append("Flagged commitments: {}.".format(", ".join(flags) if flags else "none"))
    out.append("Quarterly progress:")
    last = max(row["committed"] for row in rows)
    for end in quarter_ends(min(row["committed"] for row in rows), last):
        due = [row for row in rows if row["committed"] <= end]
        signed = [row for row in due if row["id"] in signed_on and signed_on[row["id"]] <= end]
        out.append("  Quarter ending {}: {} due, {} signed, {} below signed.".format(
            end.isoformat(), plural(len(due), "milestone"), len(signed), len(due) - len(signed)))
    if plan_signed:
        latest_plan = max(plan_files, key=lambda e: e["date"])
        out.append("Plan approval: board minutes {}, signed by {} on {}.{}{}".format(
            PLAN_ID, with_the(latest_plan["role"]), latest_plan["date"].isoformat(),
            " The board first approved the plan on {}.".format(first_on) if first_on and first_on != approved_on else "",
            " Changed in plan.md since: {}.".format(and_list(plan_changes)) if plan_changes else ""))
    elif plan_reasons:
        out.append("Plan approval: proposed, because {}.".format(plan_reasons[0]))
    else:
        out.append("Plan approval: proposed, no signed board minutes {} yet.".format(PLAN_ID))
    out.append("")

    out.append("Commitment table, the institution's response in {} five-part form, from plan.md".format(
        possessive(issuer)))
    out.append("Concern, Cause and Consequence: as written in finding.md.")
    out.append("Corrective action:")
    out.append("| Milestone | Owner role | Committed date |")
    for row in rows:
        out.append("| {} | {} | {} |".format(row["cell"], row["owner"], show(row["date"], row) if row["committed"] == row["date"]
                                           else "{}, moved to {}".format(row["committed"].isoformat(), row["date"].isoformat())))
    out.append("Commitment: full remediation by {}.".format(show(last)))
    out.append("")

    def entry_need(keys, what):
        """What a closer still owes: its entry, or the parts of it that do not count yet."""
        if not any(record[key].strip() for key in keys):
            return what + " in closure/record.md"
        return "{} in closure/record.md ({})".format(what, "; ".join(problems[keys]))

    if memo_present(folder):
        if not problems[IA_FIELDS]:
            out.append("Closure memo: present, checked by internal audit on {}.".format(record["Internal audit date"]))
        else:
            out.append("Closure memo: present, not tested by internal audit yet.")
    else:
        out.append("Closure memo: nothing written yet." if (folder / "closure" / "memo.md").is_file()
                   else "Closure memo: missing.")
        needs.add("The engagement team", "the closure memo")
    out.append(entry_line("Internal audit", record, IA_FIELDS, problems[IA_FIELDS], first_check=first_date))
    if problems[IA_FIELDS]:
        needs.add("Internal audit", entry_need(IA_FIELDS, "its reference"))
    if kind != SUPERVISORY:
        out.append("Supervisor closure: not applicable to {} {}.".format(article, kind))
    else:
        out.append(entry_line("Supervisor closure", record, SUPERVISOR_FIELDS, problems[SUPERVISOR_FIELDS], "notice",
                              first_date))
        if problems[SUPERVISOR_FIELDS]:
            needs.add(capital_first(issuer), "its closure notice" if not any(
                record[key].strip() for key in SUPERVISOR_FIELDS) else entry_need(SUPERVISOR_FIELDS, "its closure notice"))
    if kind == SELF_IDENTIFIED:
        out.append(entry_line("Issue closure", record, ISSUE_FIELDS, problems[ISSUE_FIELDS], first_check=first_date))
        if problems[ISSUE_FIELDS]:
            needs.add("The issue-management owner", entry_need(ISSUE_FIELDS, "its closure reference"))

    board = not problems[BOARD_FIELDS]
    out.append(entry_line("Board approval", record, BOARD_FIELDS, problems[BOARD_FIELDS], "", first_date))
    if not board:
        needs.add("The board", "its approval of closure" + board_missing(record, problems[BOARD_FIELDS]))

    has_memo = memo_present(folder)
    memo = None
    if has_memo or closed_rows(folder, today):
        memo = memo_check(folder, entries, fields["Owner role"], text=None if has_memo else "", today=today,
                          listed=listed_ids(rows))
    if memo is None:
        out.append("Memo check: no memo.")
    else:
        out.append("Memo check: {}, {} tie, {} on the list{}.".format(
            plural(memo["claims"], "claim"), memo["tie"], memo["left"],
            ", {} cleared".format(memo["cleared"]) if memo["cleared"] else ""))
        out.extend("  " + row for row in memo["rows"])
        out.extend("  " + row for row in memo["cleared_rows"])
        if memo["typed_ties"]:  # only a page typed into a cover asks for a second person's Checked by line
            plain, cover, bare = memo["typed_ties"] - memo["typed_cover"], memo["typed_cover"], memo["cover_unchecked"]
            out.append("  {} on text a person typed: {}{} on {} typed into a cover{}.".format(
                "1 tie rests" if memo["typed_ties"] == 1 else "{} ties rest".format(memo["typed_ties"]),
                "{} in plain-text evidence, ".format(plain) if plain else "", cover or "none", "pages" if cover > 1 else "a page",
                ", {} with no Checked by line".format(bare) if bare else ", with a Checked by line" if cover else ""))
        out.extend("  {} was not read: {}.".format(eid, why) for eid, why in sorted(memo["unread"].items()))
        out.extend("  " + line for line in memo["blank"])
        for kind, noun, label in (("spelled", "figure", "written in words"), ("year", "number", "read as a year"),
                                  ("short", "date", "with a two-digit year")):
            found = memo["spelled"] if kind == "spelled" else [(line, text) for line, text, k in memo["not_read"] if k == kind]
            if found:
                shown = ["line {} ({})".format(line, text) for line, text in found[:12]] + (
                    ["{} more".format(len(found) - 12)] if len(found) > 12 else [])
                out.append("  Not checked: {} {}, {}.".format(
                    plural(len(found), noun), label if len(found) == 1 else label.replace("a year", "years"), and_list(shown)))
        out.extend("  Ruling at rulings.md line {} names no row{}.".format(k, ": " + memo["stray_hints"][k] if k in memo["stray_hints"] else "")
                   for k in memo["stray"])
        out.extend("  Ruling at rulings.md line {} does not count: {}.".format(k, why) for k, why in memo["unmet"])
        if memo["cover_unchecked"]:
            needs.add("The engagement team", "a second person's Checked by line on {} typed into a cover".format(
                plural(memo["cover_unchecked"], "tie")))
        if memo["left"]:
            needs.add(fields["Owner role"], "the list ({})".format(plural(memo["left"], "row")))

    for made, lead in ((False, "Signed"), (True, "Produced by a system, with no signature,")):
        early = sorted({e["id"] + (" (approved by {})".format(e["approved"]) if e["approved"] else "") for e in entries
                        if e["date"] and e["produced"] == made and e["date"].isoformat() < state["first_check"]})
        if early:
            out.append("{} before the first check on {}, so a change before then cannot be seen: {}.".format(
                lead, state["first_check"], and_list(early)))
    signature = state.get("signature")
    changed = []
    held = None
    if isinstance(signature, dict) and signature.get("fingerprint"):
        files, _ = fingerprint_files(folder)
        old_files = signature.get("files") if isinstance(signature.get("files"), dict) else {}
        changed = sorted(path for path in set(files) | set(old_files)
                         if files.get(path) != old_files.get(path))
        if record_signature(folder) != (signature.get("role"), signed_on_text(signature),
                                        signature.get("fingerprint")):
            if "closure/record.md" not in changed:
                changed = sorted(changed + ["closure/record.md"])
        out.append("Signed by {} on {}, fingerprint {}.".format(
            with_the(str(signature.get("role", ""))), signed_on_text(signature),
            str(signature.get("fingerprint"))[:8]))
        if changed:
            out.append("Changed since signing: {}.".format(", ".join(changed)))
            needs.add(fields["Owner role"], "a fresh signature")
    else:
        signature = None
        out.append("Signature: none yet.")
        if record_signature(folder)[2]:
            held = record_signature(folder)
            current = fingerprint_files(folder)[1]
            out.append("closure/record.md holds a signature by {} on {}, fingerprint {}, and {} holds none. The folder "
                       "now reads {}.".format(with_the(held[0]) if held[0] else "no named role", held[1] or "no date",
                                              held[2][:8], STATE_NAME, current[:8]))
            if current != held[2]:
                needs.add(fields["Owner role"], "a fresh signature")
    tested = record["Internal audit tested fingerprint"]
    if tested:
        current = fingerprint_files(folder)[1]
        if len(tested) < 8 or not current.lower().startswith(tested.lower()):
            out.append("Internal audit tested fingerprint {}; the folder is now {}.".format(tested[:8], current[:8]))
            needs.add("Internal audit", "a fresh test")
    measures = read_measures(folder)
    if measures["seen"]:
        elapsed = max(0, ((parse_date(str(signature.get("date"))) if signature else today)
                          - parse_date(state["first_check"])).days)
        out.append("Measures: {} booked, {} since the first check, {} sent back by internal audit, {} missed by "
                   "the check.".format(hours_text(measures["hours"]), plural(elapsed, "day"),
                                       measures["sent_back"], measures["missed"]))
    if measures["unread"]:
        where = unread_measures(measures["unread"])
        out.append("Measures: {} cannot be read and {} not counted. Write each line in a form its comment "
                   "shows.".format(where, "is" if len(measures["unread"]) == 1 else "are"))
        needs.add("The engagement team", where)
    out.append(deny_line(names, fields, parts))
    out.append("")
    # The same conditions as cmd_sign's refusals. What internal audit and the issuer enter comes after the signature.
    ready = (signature is None and held is None and has_memo and not memo["left"] and not memo["cover_unchecked"]
             and not below and board and not proposed and not taken_out and not uncounted and not moved_ids and not arrived)
    if ready:
        needs.first(fields["Owner role"], "the signature, which comes first")
    if needs:
        out.append("Needs a person:")
        out.extend(needs.lines())
        if ready:
            out.append("Ready to sign: the folder's fingerprint is {}. Internal audit records this as what it "
                       "tests.".format(fingerprint_files(folder)[1][:8]))
    else:
        out.append("Nothing needs a person.")
    screen = "\n".join(out)

    if old_state is None and (folder / "closure" / LOG_NAME).is_file():
        append_log(folder, today, mode="check", outcome="record restarted", reason="the state file was gone",
                   first_check=today.isoformat())
    if old_state is None or json.loads(dump_state(state)) != old_state:
        write_text(folder / STATE_NAME, dump_state(state))

    denied = page_denied(folder, screen, names, identifier)
    if denied is not None:
        raise Stop(deny_refusal(folder, fields, denied, screen))
    info = {
        "fields": fields,
        "left": memo["left"] if memo else 0,
        "rows": memo["rows"] if memo else [],
        "cover_unchecked": memo["cover_unchecked"] if memo else 0,
        "memo": has_memo,
        "below": below,
        "board": board,
        "board_missing": board_missing(record, problems[BOARD_FIELDS]),
        "signed": signature is not None,
        "proposed": proposed,
        "plan_reason": plan_reasons[0] if plan_reasons else None,
        "taken_out": taken_out,
        "approved_on": approved_on,
        "moved_ids": moved_ids,
        "late": arrived,
        "uncounted": uncounted,
        "changed": changed,
        "names": names,
        "identifier": identifier,
    }
    return screen, (1 if needs else 0), info


class NeedsByRole:
    """What needs a person, grouped by who, in the order the page meets them."""

    def __init__(self):
        self.groups = {}

    def add(self, role, item):
        self.groups.setdefault(role.strip(), []).append(item)

    def first(self, role, item):
        """Add this and put the role at the head of the list."""
        role = role.strip()
        rest = {r: items for r, items in self.groups.items() if r != role}
        self.groups = dict({role: self.groups.get(role, []) + [item]}, **rest)

    def __bool__(self):
        return bool(self.groups)

    def lines(self):
        return ["  {}: {}.".format(capital_first(role), ", ".join(items)) for role, items in self.groups.items()]


def read_measures(folder):
    """Hours and send-backs from closure/measures.md, which no signature covers. Hours add exactly, part hours
    included, and a line that starts with Hours or Sent back but cannot be read is kept by its line number."""
    out = {"hours": decimal.Decimal(0), "sent_back": 0, "missed": 0, "seen": False, "unread": []}
    path = folder / "closure" / "measures.md"
    if not path.is_file():
        return out
    text = blank_comments("\n".join(read_lines(path)))
    for k, line in enumerate(text.split("\n"), 1):
        cells = split_row(line) or [c.strip() for c in line.split("|")]  # a table row reads the same
        label = cells[0].lower()
        if label == "hours" and len(cells) >= 3 and HOURS_RE.fullmatch(cells[2]):
            out["hours"] += decimal.Decimal(cells[2])
            out["seen"] = True
        elif label == "sent back" and len(cells) >= 2:
            out["sent_back"] += 1
            out["seen"] = True
            if "missed by the check" in cells[-1].lower():
                out["missed"] += 1
        elif re.match(r"(?:hours|sent back)\b", label):
            out["unread"].append(k)
    return out


def hours_text(hours):
    """50.5 hours, 1 hour, 38 hours: the exact total, with no trailing zeros."""
    text = format(hours, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return "{} hour{}".format(text, "" if hours == 1 else "s")


def unread_measures(lines):
    return "closure/measures.md line{} {}".format("" if len(lines) == 1 else "s", and_list([str(k) for k in lines]))


def board_missing(record, problems):
    """What a board approval with any line filled still lacks, in words for the page and for sign's refusal."""
    return " ({})".format("; ".join(problems)) if problems and any(record[key].strip() for key in BOARD_FIELDS) else ""


def recorded(ref, date_text, role):
    text = ref
    date = parse_date(date_text)
    if date is not None:
        text += " dated " + date.isoformat()
    if role.strip():
        text += ", recorded by " + with_the(role)
    return text + "."


# ---------------------------------------------------------------- the memo check


def kit_path(folder):
    """One of the kit's folders on the import path once, ahead of the rest, with no cache files left in it."""
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))
    sys.dont_write_bytecode = True


def engine():
    """The kit's tie-out engine, tieout/record.py and tieout/verify.py, imported unchanged."""
    kit_path(KIT / "tieout")
    import record as engine_record  # noqa: E402
    import verify as engine_verify  # noqa: E402
    return engine_record, engine_verify


def words_module():
    """The kit's reader for figures written in words, tieout/words.py, imported unchanged."""
    engine()
    import words as engine_words  # noqa: E402
    return engine_words


def blank_comments(text):
    """HTML comments blanked character for character, so line numbers and positions hold."""
    return COMMENT_RE.sub(lambda m: re.sub(r"[^\n]", " ", m.group(0)), text)


def evidence_pages(path, doubt=None):
    """[(page number, text, line of its marker)] for one evidence file. A file with no page
    marker is page 1, everything after the header. A Markdown page has its tags blanked and what a
    rendered page may not show left out, and with doubt, a set, the number of each page that left
    out text is added to it. A page heading typed twice, as for a correction, keeps the text under both."""
    lines = blank_comments("\n".join(read_lines(path))).split("\n")
    if path.suffix.lower() == ".md":
        docs = documents_module()
        styled = docs.markdown_styled("\n".join(lines))  # a style sheet anywhere in the file may reach any page

        def shown(text, n):
            text, left = docs.markdown_read(text, styled)
            if left and doubt is not None:
                doubt.add(n)
            return text
    else:
        def shown(text, n):
            return text
    marks = []
    for i, line in enumerate(lines):
        m = PAGE_RE.match(line.strip())
        if m:
            marks.append((i, int(m.group(1))))
    if marks:
        pages = {}
        for k, (i, n) in enumerate(marks):
            end = marks[k + 1][0] if k + 1 < len(marks) else len(lines)
            text = shown("\n".join(lines[i + 1:end]), n)
            pages[n] = (n, pages[n][1] + "\n" + text, pages[n][2]) if n in pages else (n, text, i + 1)
        return list(pages.values())
    start = header_end(lines)
    while start < len(lines) and not lines[start].strip():
        start += 1
    return [(1, shown("\n".join(lines[start:]), 1), start + 1)]


def bates_parts(eid):
    """What tells two evidence ids apart for the memo check: their letters, and their digits with leading zeros dropped."""
    return re.sub(r"[^A-Z]", "", eid.upper()), re.sub(r"[^0-9]", "", eid).lstrip("0")


def documents_module():
    kit_path(Path(__file__).resolve().parent)
    import documents  # noqa: E402
    return documents


DOCUMENT_CACHE = {}


def read_document(path):
    """The document's own pages, read once per run."""
    key = str(path)
    if key not in DOCUMENT_CACHE:
        DOCUMENT_CACHE[key] = documents_module().read(path)
    return DOCUMENT_CACHE[key]


def cover_pages(cover, doubt=None):
    """The pages typed into a cover, under their ## Page headings. A note in a cover is not a page of the document."""
    if not any(PAGE_RE.match(line.strip()) for line in blank_comments("\n".join(read_lines(cover))).split("\n")):
        return []
    return evidence_pages(cover, doubt)


def entry_pages(folder, entry):
    """[(page, text, line, typed)] for one counted file. A file with no document behind it counts as
    typed, because the check cannot tell a text export from retyping. A .txt with a cover of its own is the
    document's own text, as a PDF's text layer is. For a covered document the check reads the document's own page. A typed page in the cover stands only under a ## Page heading, inside
    the document's page count, and only where the document has no text or was read only in part; there
    it stands beside the document's text and the page counts as typed."""
    rel = entry["hashed"][0][0]
    entry["markup_pages"] = set()
    typed = evidence_pages(folder / rel, entry["markup_pages"])
    if len(entry["hashed"]) < 2:
        return [(n, text, line, True) for n, text, line in typed], None
    covered = folder / entry["hashed"][1][0]
    if covered.suffix.lower() not in documents_module().READABLE:
        return [(n, text, line, True) for n, text, line in typed], "this file type has no reader"
    read = read_document(covered)
    entry["markup_pages"] = set()
    typed = cover_pages(folder / rel, entry["markup_pages"])
    entry["partly_pages"] = set(read["partly"])
    entry["hidden_pages"] = dict(read["hidden"])
    entry["unused_typed"] = set()
    if read["problem"]:
        return [(n, text, line, True) for n, text, line in typed] or [(1, "", 0, False)], read["problem"]
    pages = {i + 1: (i + 1, text, 0, False) for i, text in enumerate(read["pages"]) if text.strip()}
    numbers = set(range(1, len(read["pages"]) + 1)) or {1}
    for n, text, line in typed:
        if n not in numbers or not text.strip():
            continue
        if n not in pages:
            pages[n] = (n, text, line, True)
        elif n in entry["partly_pages"]:
            pages[n] = (n, pages[n][1] + "\n" + text, line, True)
        else:
            entry["unused_typed"].add(n)
    return [pages.get(n, (n, "", 0, False)) for n in sorted(numbers)], None


def build_index(folder, entries):
    """The engine's index over the counted evidence files, one exhibit per evidence id."""
    record_mod, _ = engine()
    idx = record_mod.Index(str(folder), None)
    by_label = {}
    seen = {}
    docs = documents_module()
    text_left, figures_left = docs.MAX_TEXT, docs.MAX_FIGURES  # the reader's caps for one file hold for all of them
    # Page numbers are internal and never printed: cites and screens use the label. Numbering each id in
    # turn keeps them inside what the engine reads, however many digits an institution's id holds.
    for entry in entries:
        eid = entry["id"]
        prefix, digits = bates_parts(eid)
        if not 1 <= len(prefix) <= 8:
            raise Stop("Not ready: evidence id {} cannot be read by the memo check; give it one to "
                       "eight letters and its digits, such as EV-12.".format(eid))
        key = (prefix, digits)
        if key in seen and seen[key] != eid:
            raise Stop("Not ready: evidence ids {} and {} cannot be told apart by the memo check; "
                       "rename one.".format(seen[key], eid))
        if key in seen:
            raise Stop("Not ready: two files in evidence/ carry evidence id {}, and the memo check reads one "
                       "document per id; give each its own id.".format(eid))
        seen[key] = eid
        number = len(seen)
        rel = entry["hashed"][0][0]
        pages, problem = entry_pages(folder, entry)
        if max(n for n, _, _, _ in pages) > 999:
            raise Stop("Not ready: {} has more than 999 pages, more than the memo check can cite.".format(eid))
        for n, text, line, _typed in pages:
            text_left -= len(text)
            figures_left -= len(DIGIT_RUN.findall(text))
            if text_left < 0 or figures_left < 0:
                raise Stop("Not ready: the files in evidence/ hold more text between them than the memo check can hold; "
                           "cite shorter extracts of the largest.")
            before = len(idx.order)
            idx.add_page(text, rel, line, "%s%07d" % (prefix, number * 1000 + n))
            if len(idx.order) > before:
                read_extra_dates(idx.pages[idx.order[-1]], text, entry["hashed"][-1][0].lower().endswith(".eml"))
        idx.exhibits[record_mod.label_norm(eid)] = {
            "label": eid, "title": entry["what"], "prefix": prefix, "first": number * 1000 + 1,
            "last": number * 1000 + max(n for n, _, _, _ in pages), "width": 7, "file": "", "line": 0}
        entry["typed_pages"] = {n for n, text, _, typed in pages if typed and text.strip()}
        entry["blank_pages"] = {n for n, text, _, _ in pages if not text.strip()}
        entry["read_problem"] = problem
        by_label[record_mod.label_norm(eid)] = entry
    return idx, by_label


def memo_paragraphs(text):
    """[(first line number, paragraph text)], paragraphs split at blank lines."""
    paras = []
    current = []
    start = 0
    for i, line in enumerate(text.split("\n")):
        if line.strip():
            if not current:
                start = i + 1
            current.append(line)
        elif current:
            paras.append((start, "\n".join(current)))
            current = []
    if current:
        paras.append((start, "\n".join(current)))
    return paras


LIST_LEADS = (".", ":", ";", "!", "?", "]", ")", '"', "”", "'", "’")  # how a line before a list number ends


def memo_blocks(text):
    """([(first line, text)] to read for claims, [(first line, text)] of the Tested control blocks). A heading line
    is read alone, with its marks and section number blanked so positions hold. A Tested control block is its line
    and the Fix effective and Sample period lines after it, each read alone. A list item, after a bullet or a list
    number, is a block of its own, so it never lends its cite to the item before it. Any other line is ordinary memo
    text with its true line number, a list number or bullet at its start blanked."""
    blocks, controls = [], []
    section, listed = None, None  # the last heading's section number and the last list number
    for first, para in memo_paragraphs(text):
        current, start, control, item = [], first, None, False
        for k, line in enumerate(para.split("\n")):
            s = line.strip()
            if control is not None and s.startswith(("Fix effective:", "Sample period:")):
                control[1].append(line)
                blocks.append((first + k, line))
                continue
            if control is not None:
                controls.append((control[0], "\n".join(control[1])))
                control = None
            if s.startswith(("#", "Tested control:")):
                if current:
                    blocks.append((start, "\n".join(current)))
                    current = []
                item = False
                if s.startswith("#"):
                    head = HEADING_RE.match(line)
                    mark, number = head.end(), head.group("a") or head.group("b")
                    listed = None
                    loose = None if number else SECTION_RE.match(line, mark)
                    if loose and (loose.group("dots") or int(loose.group("top")) == 1
                                  or (section is not None and int(loose.group("top")) == section + 1)):
                        mark, number = loose.end(), loose.group("top")
                    if number:
                        section = int(number)
                    rest = LABEL_NUMBER_RE.sub(lambda m: m.group(0)[:m.start(1) - m.start()] + " " * len(m.group(1)),
                                               line[mark:])
                    blocks.append((first + k, " " * mark + rest))
                else:
                    control = (first + k, [line])
                    blocks.append((first + k, line))
                continue
            marker = LIST_NUMBER_RE.match(line) or BULLET_RE.match(line)
            before = para.split("\n")[k - 1].rstrip() if k else ""
            number = marker is not None and marker.re is LIST_NUMBER_RE and int(marker.group("a") or marker.group("b"))
            if marker and number and not ((not current or item or before.endswith(LIST_LEADS))
                                          and (number == 1 or (listed is not None and number == listed + 1))):
                marker = None
            if marker:
                if number:
                    listed = number
                if current:
                    blocks.append((start, "\n".join(current)))
                    current = []
                item = True
                line = " " * marker.end() + line[marker.end():]  # a list number is no figure, and positions hold
            if not current:
                start = first + k
            current.append(line)
        if control is not None:
            controls.append((control[0], "\n".join(control[1])))
        if current:
            blocks.append((start, "\n".join(current)))
    return blocks, controls


def quote_spans(para):
    """[(open, close)] for each pair of double quote marks, straight or curly, in a block."""
    marks = [i for i, ch in enumerate(para) if ch in QUOTE_MARKS]
    return [(marks[k], marks[k + 1]) for k in range(0, len(marks) - 1, 2)]


def is_word_char(ch):
    """True for a letter or digit, the same on every Python: an ASCII character by its own test, any other one
    unless it is a space, a quote mark or a dash, so no Unicode table decides."""
    if ch.isascii():
        return ch.isalnum()
    return not ch.isspace() and ch not in NOT_IN_WORDS


def single_spans(block, skip=()):
    """[(open, close)] for each quotation in single marks, straight or curly, of three words or more. The opening
    mark starts a word and the closing mark ends one, so an apostrophe inside or after a word, as in the institution's or
    the institutions', opens nothing. A pair inside a quotation in double marks is part of that quotation."""
    spans, start = [], None
    for i, ch in enumerate(block):
        if ch not in SINGLE_MARKS:
            continue
        before = block[i - 1] if i else " "
        after = block[i + 1] if i + 1 < len(block) else " "
        if start is None:
            if ch != "’" and not is_word_char(before) and before not in SINGLE_MARKS and (is_word_char(after) or after in "[("):
                start = i
        elif ch != "‘" and (is_word_char(before) or before in ".,;:!?)]") and not is_word_char(after):
            if len(block[start + 1:i].split()) >= 3 and not any(a < start < b for a, b in skip):
                spans.append((start, i))
            start = None
    return spans


def abbreviated(para, point):
    """True when the point at `point` closes a short form such as approx or No."""
    word = re.search(r"[A-Za-z.]*$", para[:point]).group(0).strip(".").lower()
    return word in ABBREVIATIONS


def memo_pieces(para, singles=()):
    """[(start, end, cite match or None, cite written another way or None)]: the block cut at every cite, cite
    written another way and sentence end outside a quotation in double marks. Inside a quotation in single marks
    only a bracket that cannot be a cite, such as [not], is passed over, since its marks may be apostrophes."""
    spans = quote_spans(para)

    def inside(pos):
        return any(a < pos < b for a, b in spans)

    def inserted(m):
        return EVIDENCE_ID_RE.match(m.group("id")) is None and any(a < m.start() < b for a, b in singles)

    cites = [m for m in CITE_RE.finditer(para) if not inside(m.start()) and not inserted(m)]
    cuts = [(m.start(), m.end(), m, None) for m in cites]
    cuts += [(m.start(), m.end(), None, m) for m in NEAR_CITE_RE.finditer(para) if not inside(m.start())
             and EVIDENCE_ID_RE.fullmatch(m.group("id")) and not any(c.start() < m.end() and m.start() < c.end() for c in cites)]
    cuts += [(m.end(), m.end(), None, None) for m in SENTENCE_END_RE.finditer(para) if not inside(m.end())
             and not (para[m.end():].lstrip()[:1].isdigit() and abbreviated(para, m.start()))]
    cuts.sort(key=lambda c: (c[0], c[2] is None and c[3] is None))
    pieces = []
    prev = 0
    for a, b, m, near in cuts:
        if a < prev:
            continue
        pieces.append((prev, a, m, near))
        prev = b
    pieces.append((prev, len(para), None, None))
    return pieces


MONTH_INDEX = {name: k for k, name in enumerate(
    ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), 1)}


def extra_date_values(m):
    """[(precision, value)] for an EXTRA_DATE_RE match, as the engine gives them, [] for a date with a two-digit
    year, or None when it names no real day."""
    g = m.groupdict()
    if g["iy"]:
        return [("m", (int(g["iy"]), int(g["im"])))]
    if g["my"] or g["xy"]:
        y = int(g["my"] or g["xy"])
        return [("m", (y + 2000 if y < 100 else y, MONTH_INDEX[(g["mm"] or g["xm"])[:3].lower()]))]
    if g["dd"]:
        if len(g["yy"]) == 2:
            return []
        y, mo, d = int(g["yy"]), MONTH_INDEX[g["mon"][:3].lower()], int(g["dd"])
    else:
        y, mo, d = int(g["y"]), MONTH_INDEX[g["month"][:3].lower()], int(g["d"])
    try:
        return [("d", datetime.date(y, mo, d))]
    except ValueError:
        return None


def extra_dates(text, sent=None):
    """[(start, end, values)] for each date in a form the engine does not read, and each reference id such as
    BM-2026-07 with values None, so their numbers are not read as figures. Positions hold across line breaks, so a day,
    month and year split by one line break read as one date, unless a figure or a label word stands before the day, as
    in a table row, Page 1 of 3 or Table 3. Given an email's own date, a day and month with no year take the year that
    puts them nearest it."""
    flat, rec = text.replace("\n", " "), engine()[0]
    found = []
    for m in EXTRA_DATE_RE.finditer(flat):
        values = extra_date_values(m)
        if values is not None:
            found.append((m.start(), m.end(), values))
    found += [(m.start(), m.end(), None) for m in REFERENCE_ID_RE.finditer(flat)]
    found += [m.span() + (days,) for m in rec.DATE.finditer(flat) if text.count("\n", *m.span()) == 1
              and not re.search(r"(?i)(?:\d (of )?|\b(?:" + _LABELS + r"|page|p|pp|no|version|v|rev)\.? )$", flat[max(0, m.start() - 16):m.start()])
              and (days := [v for v in rec.date_values(m) if v[0] == "d"])]
    for m in NO_YEAR_RE.finditer(flat) if sent else ():
        mo, day = MONTH_INDEX[(m.group("m") or m.group("n"))[:3].lower()], int(m.group("d") or m.group("e"))
        near = [x for k in (-1, 0, 1) if (x := datetime.date(sent.year + k, mo, 1) + datetime.timedelta(day - 1)).month == mo]
        found += [m.span() + ([("d", min(near, key=lambda x: abs(x - sent)))],)] if near else []
    return sorted(found)


def read_extra_dates(page, text, email=False):
    """Add to one evidence page of the engine's index the dates in forms the engine does not read, and drop the
    figures and part dates the engine took from them and from reference ids. An email's page dates by its Date line,
    whose time and zone, such as 20:05:33 +0000, are no figures."""
    head = re.search(r"^Date: (.+)$", text.split("\n\n", 1)[0], re.M) if email else None
    found = extra_dates(text, head and next((v for d in engine()[0].scan(head.group(1))["dates"]
                                             for p, v in d["values"] if p == "d"), None))
    found += [m.span() + (None,) for m in TIME_RE.finditer(text, head.start(), head.end())] if head else []
    if not found:
        return
    inside = lambda pos: any(a <= pos < b for a, b, _ in found)  # noqa: E731
    page["figures"] = [fig for fig in page["figures"] if not inside(fig["start"])]
    page["dates"] = sorted([d for d in page["dates"] if not inside(d["start"])]
                           + [{"raw": text[a:b], "values": values, "start": a} for a, b, values in found if values],
                           key=lambda d: d["start"])


def row_key(*parts):
    """A row's short mark. The same claim, cite and sentence give the same mark on any line of the memo."""
    return sha256_bytes("\n".join(collapse(str(part)) for part in parts).encode("utf-8"))[:8]


def insertion(inner):
    """What a quotation holds that the engine passes over: "an insertion" for a bracketed word, "an ellipsis", or ""."""
    marks = re.findall(r"\[[^\]]*\]|\.(?:\s?\.){2}", inner)
    if not marks:
        return ""
    return "an insertion" if any(mark.startswith("[") for mark in marks) else "an ellipsis"


def memo_claims(text, record_mod):
    """Every figure, date and quotation in the memo with its line, claimed text, cite and mark, the Tested control
    blocks, [(line, phrase)] for each figure written in words, and [(line, text, kind)] for each number read as a
    year and each date with a two-digit year. The check ties neither of the last two."""
    claims = []
    spelled = []
    unread = []
    blocks, controls = memo_blocks(text)
    for first, block in blocks:
        doubles = quote_spans(block)
        singles = single_spans(block, doubles)
        taken = doubles + singles
        skipped = []  # (position in the block, text, kind) for each year and two-digit-year date
        for a, b, m, near in memo_pieces(block, singles):
            piece = block[a:b]
            masked = list(piece.replace("\n", " "))  # a date wrapped onto the next line still reads
            for v in VERSION_RE.finditer(piece):  # a version number is a label, as a section number is
                masked[v.start(1):v.end(1)] = "\x00" * len(v.group(1))
            found = []
            for start, end, values in extra_dates(piece):
                masked[start:end] = "\x00" * (end - start)
                if values:
                    found.append((start, "date", {"raw": piece[start:end], "values": values, "start": start},
                                  collapse(piece[start:end]), ""))
                elif values is not None:
                    skipped.append((a + start, piece[start:end], "short"))
            masked = "".join(masked)
            scanned = record_mod.scan(masked)
            for fig in scanned["figures"]:
                if record_mod.is_bare_year(fig):
                    skipped.append((a + fig["start"], fig["raw"].strip(), "year"))
                else:
                    found.append((fig["start"], "figure", fig, fig["raw"].strip(), ""))
            for d in scanned["dates"]:
                found.append((d["start"], "date", d, d["raw"], ""))
            skipped += [(a + start, piece[start:end], "short")
                        for start, end, _ in record_mod.not_figures(masked, kinds=("short_date",))]
            normed = record_mod.norm_text(piece)
            marks = [i for i, ch in enumerate(piece) if ch in QUOTE_MARKS]
            for q in QUOTE_RE.finditer(normed):
                if len(q.group(1).split()) < 2:
                    continue
                k = normed[:q.start()].count('"')
                pos = marks[k] if k < len(marks) else 0
                found.append((pos, "quotation", q.group(0), q.group(0), insertion(q.group(1))))
            for o, c in singles:  # a quotation in single marks takes the cite of the sentence it ends in
                if a <= c < b:
                    inner = record_mod.norm_text(block[o + 1:c])
                    found.append((o - a, "quotation", '"' + inner + '"', record_mod.norm_text(block[o:c + 1]),
                                  insertion(inner)))
            for pos, kind, value, claimed, inserted in found:
                where = a + pos
                if kind != "quotation":
                    taken.append((where, where + len(claimed)))
                claims.append({
                    "line": first + block[:where].count("\n"),
                    "pos": (first, where),
                    "kind": kind,
                    "value": value,
                    "claimed": claimed,
                    "cite": m,
                    "near": near,
                    "insertion": inserted,
                    "single": kind == "quotation" and claimed[:1] == "'",
                    "key": row_key(claimed, m.group(0) if m else (near.group(0) if near else ""), piece, pos),
                })
        unread += [(first + block[:where].count("\n"), collapse(shown), kind) for where, shown, kind in skipped]
        taken += [(where, where + len(shown)) for where, shown, _ in skipped]
        for a, b, _reading in words_module().find(block):
            if not any(x < b and a < y for x, y in taken):
                spelled.append((first + block[:a].count("\n"), collapse(block[a:b])))
    claims.sort(key=lambda c: (c["line"], c["pos"]))
    spelled.sort(key=lambda s: s[0])
    unread.sort(key=lambda s: s[0])
    return claims, controls, spelled, unread


def and_list(items, word="and"):
    items = [i for i in items if i]
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " " + word + " " + items[-1]


def or_list(items):
    return and_list(items, "or")


def hint_items(hint):
    return [part.strip() for part in hint.split(":", 1)[-1].split("; ")]


def page_notes(entry, number):
    """What a row adds about the cited page when the reader has more to say about it."""
    notes = ""
    if number in entry.get("hidden_pages", ()):
        notes += " The page also holds {} a reader cannot see, which the check leaves out.".format(
            plural(len(entry["hidden_pages"][number]), "word"))
    if number in entry.get("markup_pages", ()):
        notes += (" The page also holds marked-up text a rendered page may not show, which the check leaves out; "
                  "write it as plain text if it shows.")
    if number in entry.get("unused_typed", ()):
        notes += " The typed page {} in the cover was not used, because the check read the document's own text there.".format(number)
    elif number in entry.get("partly_pages", ()) and number not in entry.get("typed_pages", ()):
        notes += " The check read this page only in part; if the page shows it, type it into the cover under ## Page {}.".format(number)
    return notes


PRECISION = {"d": (0, "day"), "m": (1, "month"), "q": (2, "quarter")}


def coarser_page_date(values, located, record_mod):
    """(the page's precision, its date as written, the claim's precision) in words, for a page date that holds the
    claimed date only to the month or the quarter, or None."""
    for _, scanned, _ in located["texts"]:
        for d in scanned["dates"]:
            for page_value in d["values"]:
                for value in values:
                    if PRECISION[page_value[0]][0] > PRECISION[value[0]][0] and record_mod.date_ties(page_value, value):
                        return PRECISION[page_value[0]][1], d["raw"], PRECISION[value[0]][1]
    return None


def row_text(fail, eid, n_pages, known):
    """The rest of a row's sentence for an engine failure."""
    code, reason, hint = fail.code, fail.reason, fail.hint or ""
    if code == "location_missing":
        if not known:
            return "and there is no evidence file {}.".format(eid)
        return "and {} has {}.".format(eid, plural(n_pages, "page"))
    if code == "pin_missing":
        return "and {} has {}, so the cite needs a page.".format(eid, plural(n_pages, "page"))
    if code in ("figure_not_found", "date_not_found"):
        noun = code.split("_")[0]
        if hint.startswith("nearest values on the page:" if noun == "figure" else "dates on the page:"):
            items = hint_items(hint)
            return "and the page does not hold it; the {}{} on the page {} {}.".format("nearest " if noun == "figure" else "",
                   noun if len(items) == 1 else noun + "s", "is" if len(items) == 1 else "are", and_list(items))
        return "and the page holds no {}.".format(noun)
    if code == "misquote":
        m = re.match(r'segment "(.*)" is not on ', reason)
        if m:
            text = 'and the page does not hold "{}"'.format(m.group(1))
            h = re.match(r'the page reads: "(.*)"$', hint)
            if h:
                text += '; the page reads "{}"'.format(h.group(1))
            return text + "."
    if code == "ambiguous_tie":
        m = re.search(r" matches (\d+) distinct ", reason)
        if m:  # the engine lists every match and counts a figure's values apart by their size, so each prints once
            record_mod, shown = engine()[0], {}
            for raw in (x.strip() for x in reason.rsplit(": ", 1)[-1].split("; ")):
                fig = " distinct values " in reason and record_mod.FIGURE.fullmatch(raw)
                shown.setdefault(abs(record_mod.parse_figure(fig)["value"]) if fig else raw, raw)
            return "and {} different values on the page match it: {}.".format(m.group(1), and_list(list(shown.values())))
    prefix = "the check could not run: "
    if reason.startswith(prefix):
        reason = reason[len(prefix):]
    return "and the check could not run: {}.".format(reason.rstrip("."))


def control_rows(controls):
    """[(line, claimed, row)] from the Tested control blocks: missing lines, bad dates, and a
    sample period that starts before the fix took effect."""
    rows = []
    for first, para in controls:
        lines = para.split("\n")
        value = CITE_RE.sub("", lines[0].strip()[len("Tested control:"):]).strip()
        cid = value.split()[0].rstrip(",") if value.split() else "with no id"
        found = {}
        for k, line in enumerate(lines):
            for key in ("Fix effective", "Sample period"):
                if line.strip().startswith(key + ":") and key not in found:
                    found[key] = (first + k, CITE_RE.sub("", line.strip()[len(key) + 1:]).strip())
        for key in ("Fix effective", "Sample period"):
            if key not in found:
                rows.append((first, "tested control " + cid,
                             "Line {}: the tested control {} has no {} line.".format(first, cid, key)))
        fix = None
        if "Fix effective" in found:
            line, text = found["Fix effective"]
            fix = parse_date(text)
            if fix is None:
                rows.append((line, 'Fix effective date "{}"'.format(text),
                             'Line {}: the Fix effective date "{}" is not YYYY-MM-DD.'.format(line, text)))
        start = None
        if "Sample period" in found:
            line, text = found["Sample period"]
            m = re.match(r"^(\S+)\s+to\s+(\S+)$", text)
            bad = text
            if m:
                start, end = parse_date(m.group(1)), parse_date(m.group(2))
                bad = m.group(1) if start is None else (m.group(2) if end is None else None)
                if end is None:
                    start = None
                elif start is not None and end < start:  # a period written end first starts at its earlier date
                    start = end
            if bad is not None:
                start = None
                rows.append((line, 'Sample period date "{}"'.format(bad),
                             'Line {}: the Sample period date "{}" is not YYYY-MM-DD.'.format(line, bad)))
            if fix is not None and start is not None and start < fix:
                rows.append((line, "sample period for " + cid,
                             "Line {}: the sample period for {} starts {}, before the fix took effect on "
                             "{}, so the sample mixes items from before and after the fix.".format(
                                 line, cid, start.isoformat(), fix.isoformat())))
    return rows


def read_rulings(folder, loose=False):
    """[(rulings.md line, cells)] for every line starting "Line ". With loose, the numbers of the other lines that
    read as a ruling, a cell of cleared, fix the memo or fix the evidence among them, so the page can say why each
    counts for nothing."""
    path = folder / "closure" / "rulings.md"
    if not path.is_file():
        return []
    text = blank_comments("\n".join(read_lines(path)))
    out = []
    for k, line in enumerate(text.split("\n"), 1):
        if line.startswith("Line "):
            if not loose:
                out.append((k, [cell.strip() for cell in line.split("|", 5)]))
        elif loose and "|" in line and any(cell.strip().lower() in RULINGS for cell in line.split("|")):
            out.append(k)
    return out


def collapse(text):
    return " ".join(text.split())


def memo_text(folder):
    return blank_comments("\n".join(read_lines(folder / "closure" / "memo.md")))


def listed_ids(rows):
    """The evidence ids a plan row or the plan approval already answers for on the page."""
    return {eid for row in rows for eid in row["ids"]} | {PLAN_ID}


def as_the_check_reads(folder, entries, today=None):
    """(today, listed ids), this machine's date unless a date is given, once files changed since signing are flagged as
    the check flags them, so size and eval put the same rows on the list as the check. Writes nothing."""
    today = today or datetime.date.today()
    state = load_state(folder) or {}
    update_evidence_state(entries, json.loads(json.dumps(state.get("evidence") or {})), today,
                          json.loads(json.dumps(state.get("ids") or {})))
    try:
        listed = listed_ids(parse_plan(folder))
    except Stop:
        listed = {PLAN_ID}
    return today, listed


def memo_check(folder, entries, owner, text=None, use_rulings=True, today=None, listed=(), built=None, closed=None):
    """Tie every claim in closure/memo.md to its cited evidence page. Never writes the memo. With today, a cited file
    no plan row lists goes on the list when it is not signed, and a ruling dated later does not count. The rows for
    a use of closed come with the rulings unless closed says otherwise, as size asks for them with no rulings."""
    record_mod, verify_mod = engine()
    idx, by_label = built or build_index(folder, entries)
    if text is None:
        text = memo_text(folder)
    claims, controls, spelled, not_read = memo_claims(text, record_mod)
    rows = []  # (line, order, claimed, sentence, mark, claims the row stands for)
    waiting = {}
    typed_ties = 0
    typed_cover = 0
    cover_unchecked = 0
    stale = set()  # the covers whose typed pages changed since their Checked by line, with a tie on one
    unread = {}
    tied = []
    relies = {}  # a row's order: the evidence file its claim cites, so a ruling dated before its signature stops
    for n, claim in enumerate(claims):
        m = claim["cite"]
        head = "Line {}: {}".format(claim["line"], claim["claimed"])
        if m is None:
            near = claim["near"]
            several = near is not None and (near.group("range") or near.group("more").strip())
            hint = "" if near is None else " Write {} as {}[{}{}], the form the check reads.".format(
                near.group(0), "one cite for each page, such as " if several else "", near.group("id"),
                " p" + near.group("page") if near.group("page") else "")
            rows.append((claim["line"], n, claim["claimed"], head + " has no cite." + hint, claim["key"], 1))
            continue
        eid, page = m.group("id"), m.group("page")
        shown = eid + (" p" + page if page else "")
        head += " is cited to {}, ".format(shown)
        entry = by_label.get(record_mod.label_norm(eid))
        relies[n] = entry
        draft = entry is not None and entry["status"] == "DRAFT"
        if draft:
            head += "which is a draft, "
        elif entry is not None and today is not None and entry["id"] not in listed:
            reason = file_reason(entry, today)
            if reason:
                rows.append((claim["line"], n, claim["claimed"], head + "which is not signed: {}.".format(reason),
                             claim["key"], 1))
                continue
        cite = {"type": "exhibit", "text": shown, "label": eid, "written": eid,
                "pin": {"pages": [int(page), int(page)]} if page else None}
        flags = set()
        located = None
        try:
            located = verify_mod.guarded(verify_mod.locate, cite, idx)
            if claim["kind"] == "figure":
                verify_mod.guarded(verify_mod.check_figure, claim["value"], located, flags)
            elif claim["kind"] == "date":  # a month or a quarter ties any date inside it on the page, however many
                shown = [v for _, scanned, _ in located["texts"] for d in scanned["dates"] for v in d["values"]]
                for value in claim["value"]["values"]:  # a date that reads two ways ties only if both are on the page
                    if value[0] == "d" or not any(record_mod.date_ties(value, v) for v in shown):
                        verify_mod.guarded(verify_mod.check_date, value, claim["claimed"], located, flags)
            else:
                verify_mod.guarded(verify_mod.check_quote, claim["value"], located, flags)
        except verify_mod.Fail as fail:
            ex = idx.exhibit(eid)
            n_pages = ex["last"] - ex["first"] + 1 if ex else 0
            number = int(page) if page else 1
            if entry is not None and fail.code != "pin_missing" and number in entry.get("blank_pages", ()):
                unseen = "the document has no text a reader can see on that page"
                why = "this file type has no reader" if entry.get("read_problem") == "this file type has no reader" else (
                    entry.get("read_problem")
                    or (unseen if number in entry.get("hidden_pages", ()) else "the document has no text on that page"))
                sentence = head + "and the check cannot read that page: {}. Type it into the cover under ## Page {}.".format(
                    why, number)
            else:
                sentence = head + row_text(fail, eid, n_pages, ex is not None)
                if entry is not None and n_pages >= number:
                    sentence += page_notes(entry, number)
                held = coarser_page_date(claim["value"]["values"], located, record_mod) if (
                    fail.code == "date_not_found" and located is not None) else None
                if held is not None:
                    sentence = head + "and the page gives only the {}, {}, so it cannot show the {}.".format(*held)
                if fail.code == "date_not_found" and len(claim["value"]["values"]) > 1:
                    sentence += " This date reads two ways, so write it as YYYY-MM-DD."
            rows.append((claim["line"], n, claim["claimed"], sentence, claim["key"], 1))
            continue
        if claim["kind"] == "quotation" and claim["insertion"]:  # the engine passes over a bracket or an ellipsis
            rows.append((claim["line"], n, claim["claimed"], head + "and holds {} the check cannot compare.".format(
                claim["insertion"]), claim["key"], 1))
            continue
        tied.append(n)
        if draft:
            waiting.setdefault(entry["id"], []).append(dict(claim, entry=entry))
            continue
        if entry is not None and (int(page) if page else 1) in entry.get("typed_pages", ()):
            typed_ties += 1
            if len(entry["hashed"]) > 1:  # a page typed into the cover over a document, not plain-text evidence
                typed_cover += 1
                cover_unchecked += not entry.get("checked_by")
                stale |= {entry["id"]} if entry.get("stale") else set()
            problem = entry.get("read_problem")
            if problem and problem != "this file type has no reader" and entry["id"] not in unread:
                unread[entry["id"]] = problem
    for line, claimed, sentence, context in ([row + ("",) for row in control_rows(controls)]
                                             + (closed_rows(folder, today) if (use_rulings if closed is None else closed)
                                                else [])):
        rows.append((line, len(claims) + len(rows), claimed, sentence,
                     None if context is None else row_key(claimed, re.sub(r"^Line \d+: ", "", sentence), context), 0))
    for eid in sorted(waiting):  # one row per draft cover, however many of its claims match its pages
        held = waiting[eid]
        line = held[0]["line"]
        words = ("claim", "matches", "waits") if len(held) == 1 else ("claims", "match", "wait")
        lines = sorted({c["line"] for c in held})
        where = "" if lines == [line] else ", on lines {},".format(and_list([str(k) for k in lines]))
        relies[len(claims) + len(rows)] = held[0].get("entry")
        rows.append((line, len(claims) + len(rows), eid + " draft",
                     "Line {}: {}, which is a draft, holds {} {}{} that {} its pages and {} on a person's signature.".format(
                         line, eid, len(held), words[0], where, words[1], words[2]),
                     row_key(eid, *sorted(c["key"] for c in held)), len(held)))
    rows.sort(key=lambda r: (r[0], r[1]))

    rulings = read_rulings(folder) if use_rulings else []
    used = set()
    spent = set()
    counted = set()  # the rulings that cleared a row
    cleared_rows = []

    def signed_after(cells, entry):
        """The cited file's signature date when it is later than the ruling's date, else None."""
        date = parse_date(cells[4]) if len(cells) >= 5 else None
        if entry is not None and entry.get("date") is not None and date is not None and entry["date"] > date:
            return entry["date"]
        return None

    def valid(cells, entry=None):
        date = parse_date(cells[4]) if len(cells) == 6 else None
        return (date is not None and (today is None or date <= today) and cells[2].lower() == "cleared"
                and collapse(cells[3]) == collapse(owner) and bool(cells[5]) and signed_after(cells, entry) is None)

    def named(claimed, key):
        return "{} #{}".format(collapse(claimed), key)

    def why_not(cells, entry=None):
        """Why a ruling that names a row does not clear it, in words."""
        date = parse_date(cells[4]) if len(cells) >= 5 else None
        if len(cells) != 6 or not cells[5]:
            return "it needs six parts, the last a reason"
        if cells[2].lower() != "cleared":
            return "its ruling is not cleared, fix the memo or fix the evidence"
        if date is None:
            return "its date is not written as YYYY-MM-DD"
        if today is not None and date > today:
            return "it is dated {}, after the check date".format(date.isoformat())
        if collapse(cells[3]) != collapse(owner):
            if collapse(cells[3]).lower() == collapse(owner).lower():
                return "its role is written in another letter case from the finding owner's role, {}".format(collapse(owner))
            return "the role it names is not the finding owner"
        later = signed_after(cells, entry)
        return "{} was {} on {}, after the ruling's date of {}, so the page it rests on may have changed".format(
            entry["id"], "approved by " + entry["approved"] if entry["approved"] else "produced" if entry["produced"] else "signed",
            later.isoformat(), date.isoformat())

    def note(line, claimed, cells, moved_from=None):
        moved = " (ruled at memo line {})".format(moved_from) if moved_from else ""
        return "Cleared: line {}{}, {}, by {} on {}: {}".format(
            line, moved, claimed, with_the(cells[3]), cells[4], cells[5])

    remaining = []
    named_by = {}  # a ruling's line: the file its row relies on, for the reason it does not count
    for line, order, claimed, sentence, key, _held in rows:
        ruling = None
        for k, cells in rulings if key else ():
            if k in spent or len(cells) < 2 or cells[0] != "Line {}".format(line) or collapse(cells[1]) != named(claimed, key):
                continue
            used.add(k)
            named_by[k] = relies.get(order)
            if valid(cells, relies.get(order)):
                ruling = k, cells
        if ruling is not None:
            spent.add(ruling[0])
            counted.add(ruling[0])
            cleared_rows.append((line, note(line, claimed, ruling[1])))
        else:
            remaining.append((line, claimed, sentence, key and named(claimed, key), order))
    # A cleared ruling follows its claim, cite and sentence to a new line when the memo holds them once, the line it
    # names no longer does, and no ruling on the row says to fix something.
    holders = [named(c["claimed"], c["key"]) for c in claims] + [named(r[2], r[4]) for r in rows if r[1] >= len(claims)]
    fixes = {(cells[0], collapse(cells[1])) for _, cells in rulings
             if len(cells) >= 3 and cells[2].lower() in ("fix the memo", "fix the evidence")}
    for k, cells in rulings:
        if k in used or not valid(cells) or re.fullmatch(r"Line \d+", cells[0]) is None:
            continue
        name = collapse(cells[1])
        same = [r for r in remaining if r[3] == name]
        if len(same) == 1 and holders.count(name) == 1 and ("Line {}".format(same[0][0]), name) not in fixes:
            used.add(k)
            named_by[k] = relies.get(same[0][4])
            if valid(cells, named_by[k]):
                counted.add(k)
                remaining.remove(same[0])
                cleared_rows.append((same[0][0], note(same[0][0], same[0][1], cells, cells[0][len("Line "):])))
    left = [r[2] + (" To rule, name: " + r[3] if r[3] else "") for r in remaining]
    # A ruling left behind names the row on the list that prints its claim: one with no mark, the row on its line, and
    # one whose mark or line moved, the row anywhere. A fix ruling stays without a word only when no such row is left.
    stray_hints = {}
    for k, cells in rulings:
        claim, _, mark = collapse(cells[1] if len(cells) >= 2 else "").partition(" #")
        same = [r for r in remaining if r[1] and collapse(r[1]) == claim and (r[3] if mark else "Line {}".format(r[0]) == cells[0])]
        if k not in used and same:
            stray_hints[k] = "no ruling clears the row on that line" if not same[0][3] else "the row on line {} prints {}".format(
                same[0][0], same[0][3]) if mark else "it has no # mark, and the row on that line prints " + same[0][3]
    acted = [k for k, cells in rulings if k not in used and k not in stray_hints and len(cells) >= 3
             and cells[2].lower() in ("fix the memo", "fix the evidence")]
    stray = [k for k, _ in rulings if k not in used and k not in acted]
    # A ruling that names a row and still does not clear it says why, so a mistyped year is not taken for a ruling.
    unmet = [(k, why_not(cells, named_by.get(k))) for k, cells in rulings if k in used and k not in counted and not (
        len(cells) >= 3 and cells[2].lower() in ("fix the memo", "fix the evidence"))]
    if use_rulings:  # a line that reads as a ruling but does not start with its memo line counts for nothing, and says so
        unmet = sorted(unmet + [(k, "it does not start with Line and the memo line number, such as Line 8")
                                for k in read_rulings(folder, loose=True)])
    cleared_rows.sort(key=lambda r: r[0])
    blank = ["{}'s typed pages changed at the check of {}, after its Checked by line.".format(e["id"], e["stale"])
             for e in sorted(entries, key=lambda e: e["id"]) if e["id"] in stale]
    cited = {(record_mod.label_norm(c["cite"].group("id")), int(c["cite"].group("page") or 1)) for c in claims if c["cite"]}
    for entry in sorted(entries, key=lambda e: e["id"]):  # a page the memo cites, as only a cited page is typed
        pages = sorted(n for n in entry.get("blank_pages", ()) if (record_mod.label_norm(entry["id"]), n) in cited)
        if pages:
            if entry.get("read_problem"):  # a file the check cannot read, a .msg say, may hold text all the same
                blank.append("{} {} cannot be read by the check, and nothing is typed.".format(entry["id"], page_list(pages)))
            else:
                blank.append("{} {} {} no text and nothing typed.".format(
                    entry["id"], page_list(pages), "has" if len(pages) == 1 else "have"))
    return {"claims": len(claims), "tie": len(claims) - sum(r[5] for r in rows), "left": len(left),
            "cleared": len(cleared_rows), "rows": left, "stray": stray, "stray_hints": stray_hints, "unmet": unmet, "blank": blank, "spelled": spelled,
            "not_read": not_read,
            "draft_rows": len(waiting), "draft_claims": sum(len(held) for held in waiting.values()),
            "cleared_rows": [r[1] for r in cleared_rows], "rulings": len(rulings),
            "typed_ties": typed_ties, "typed_cover": typed_cover, "cover_unchecked": cover_unchecked,
            "unread": unread,
            "tied": [claims[n] for n in tied], "index": idx, "by_label": by_label}


# ---------------------------------------------------------------- the signature


def fingerprint_files(folder):
    """({path: sha256}, fingerprint) over everything a signature covers."""
    empty = sha256_bytes(b"")
    files = {}
    for rel in ("closure/memo.md", "closure/rulings.md", "finding.md", "plan.md"):
        path = folder / rel
        files[rel] = text_digest(path) if path.is_file() else empty
    record_path = folder / "closure" / "record.md"
    if record_path.is_file():
        kept = [line for line in record_path.read_text(encoding="utf-8-sig").splitlines()
                if not any(is_record_line(line, key) for key in UNSIGNED_RECORD_FIELDS)]
        files["closure/record.md"] = sha256_bytes("\n".join(kept).encode("utf-8"))
    else:
        files["closure/record.md"] = empty
    ev_dir = folder / "evidence"
    if ev_dir.is_dir():
        for p in evidence_files(ev_dir):
            files[p.relative_to(folder).as_posix()] = evidence_digest(p)
    files["finding.py"] = text_digest(Path(__file__).resolve())
    for rel in ("finding/documents.py", "tieout/claims.py", "tieout/docx_reader.py", "tieout/record.py",
                "tieout/verify.py", "tieout/words.py"):
        target = KIT / rel
        files[rel] = text_digest(target) if target.is_file() else empty
    listing = "".join("{} {}\n".format(path, files[path]) for path in sorted(files))
    return files, sha256_bytes(listing.encode("utf-8"))


def fingerprint(folder):
    return fingerprint_files(Path(folder))[1]


def record_signature(folder):
    record = parse_record(folder)
    return tuple(record[key] or None for key in SIGNATURE_FIELDS)


def signed_on_text(signature):
    """The signature date as the page and record.md give it. A date typed with --today says so, with the machine's
    own date beside it."""
    date = str(signature.get("date"))
    if signature.get("machine_date"):
        return "{}, a date typed with --today on a machine dated {}".format(date, signature["machine_date"])
    return date


def write_signature(folder, role, date, fp):
    path = folder / "closure" / "record.md"
    raw = path.read_bytes() if path.is_file() else b""
    newline = "\r\n" if b"\r\n" in raw else "\n"
    lines = raw.decode("utf-8-sig").splitlines()
    values = {"Signed by (role)": role, "Signed on": date, "Fingerprint": fp, "Kit release": kit_label()}
    for key in SIGNATURE_FIELDS + ("Kit release",):
        for i, line in enumerate(lines):
            if is_record_line(line, key):
                lines[i] = "{}: {}".format(key, values[key])
                break
        else:
            lines.append("{}: {}".format(key, values[key]))
    write_text(path, newline.join(lines) + newline)


def ask(prompt):
    sys.stdout.write(prompt)
    sys.stdout.flush()
    line = sys.stdin.readline()
    return line.rstrip("\r\n")


def refuse(text):
    """A Not ready or Refused page: the banner, the changed-kit line when the kit differs from its release, the words."""
    print(CONFIDENTIAL)
    print()
    for line in kit_note():
        print(line)
    print(text)
    return 1


def is_synthetic(folder):
    """True while finding.md opens with a shipped case's SYNTHETIC line, word for word. `finding new` writes no
    SYNTHETIC line, and any other line does not count, so a real finding signs on this machine's date."""
    try:
        lines = (folder / "finding.md").read_text(encoding="utf-8-sig").splitlines()
    except (OSError, UnicodeDecodeError):
        return False
    return bool(lines) and lines[0].strip() == SHIPPED_LINE


def cmd_sign(args):
    folder, today = parse_folder_args(args, need_folder=True)
    if not sys.stdin.isatty():
        return refuse("Refused: sign needs a terminal.")
    machine = datetime.date.today()
    if today != machine and not is_synthetic(folder):
        return refuse("Refused: a real finding is signed on this machine's date; drop --today.")
    try:
        # The fingerprint is taken on both sides of the check, so what is signed is what the check read.
        files, fp = fingerprint_files(folder)
        screen, _code, info = run_check(folder, today)
        if fingerprint_files(folder)[1] != fp:
            return refuse("Refused: a file changed while sign was running; run it again.")
    except Stop as stop:
        return refuse(stop.args[0])
    reword = [row for row in info["rows"] if " To rule, name: " not in row]  # a claim the finding is closed
    if info["left"] and len(reword) == info["left"]:
        return refuse("Refused: " + re.sub(r"^Line (\d+): .* in (\S+) claims", r"\2 line \1 claims", reword[0]))
    if info["left"]:
        return refuse("Refused: {} on the list; rule on {} first.".format(
            "1 row is" if info["left"] == 1 else "{} rows are".format(info["left"]), "it" if info["left"] == 1 else "them"))
    if not info["memo"]:
        return refuse("Refused: closure/memo.md holds no memo yet.")
    if info["cover_unchecked"]:
        return refuse("Refused: {} on text typed into a cover with no Checked by line.".format(
            "1 tie rests" if info["cover_unchecked"] == 1 else "{} ties rest".format(info["cover_unchecked"])))
    if info["below"]:
        return refuse("Refused: {} {} below signed.".format(
            and_list(info["below"]), "is" if len(info["below"]) == 1 else "are"))
    if not info["board"]:
        return refuse("Refused: closure/record.md holds no board approval{}.".format(info["board_missing"]))
    if info["proposed"]:
        if info["plan_reason"]:
            return refuse("Refused: the plan approval is still proposed, because {}.".format(info["plan_reason"]))
        return refuse("Refused: the plan approval is still proposed; board minutes {} are not signed.".format(PLAN_ID))
    if info["taken_out"]:
        return refuse("Refused: {} {} taken out of plan.md after the board approved the plan on {}. Sign the board minutes {} "
                      "again once the board approves the changed plan.".format(and_list(info["taken_out"]), "was" if len(
                          info["taken_out"]) == 1 else "were", info["approved_on"], PLAN_ID))
    if info["uncounted"]:
        return refuse("Refused: {} is not counted; give it a cover or take it out.".format(info["uncounted"][0][0]))
    if info["moved_ids"]:
        rel, was, _signed, now = info["moved_ids"][0]
        return refuse("Refused: {} holds what was signed as {} and is now filed as {}. Take it out, or sign it again "
                      "under that id.".format(shown_path(folder, rel, info["names"]), was, now))
    if info["late"]:
        return refuse("Refused: " + shown_path(folder, info["late"][0][0], info["names"]) + info["late"][0][1])
    if info["signed"] and not info["changed"]:
        return refuse("Refused: this finding is signed already and nothing has changed since.")
    owner = info["fields"]["Owner role"]
    print(screen)
    print()
    if collapse(ask("Type the finding owner's role to sign: ")) != collapse(owner):
        return refuse("Refused: that is not the finding owner's role.")
    if fingerprint_files(folder)[1] != fp:
        return refuse("Refused: a file changed while sign was running; run it again.")
    print("Fingerprint " + fp)
    typed = re.sub(r"\s", "", ask("Type its first eight characters to confirm: "))
    if typed.casefold() != fp[:8].casefold():
        return refuse("Refused: the characters typed do not match the fingerprint.")
    try:  # fingerprint_files raises no Stop, so only a state file that cannot be read lands here
        state = load_state(folder) if fingerprint_files(folder)[1] == fp else None
    except Stop:
        state = None
    if state is None:
        return refuse("Refused: a file changed while sign was running; run it again.")
    role = collapse(owner)
    state["signature"] = {"role": role, "date": today.isoformat(), "fingerprint": fp, "files": files,
                          "signed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")}
    if today != machine:  # a typed date, which only a shipped case's SYNTHETIC line allows, shows on the page and in the record
        state["signature"]["machine_date"] = machine.isoformat()
    write_text(folder / STATE_NAME, dump_state(state))
    write_signature(folder, role, signed_on_text(state["signature"]), fp)
    print("Signed by {} on {}, fingerprint {}. Written to closure/record.md.".format(
        with_the(role), signed_on_text(state["signature"]), fp[:8]))
    return 0


# ---------------------------------------------------------------- the folder's log and gone files


def append_log(folder, today, **values):
    """One receipt line for the institution's own log, naming the finding's kind, its issuer and its first check, so
    close-out can read a relabel or a restart from the log. A log that cannot be written stops the run."""
    try:
        fields = parse_finding(folder)[0]
    except Stop:
        fields = {}
    try:
        state = load_state(folder) or {}
    except Stop:
        state = {}
    entry = {"checked": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
             "as_of": today.isoformat(), "release": kit_label(), "kind": fields.get("Kind of matter"),
             "issuer": fields.get("Issuer"), "first_check": state.get("first_check")}
    entry.update(values)
    try:
        (folder / "closure").mkdir(exist_ok=True)
        with open(str(folder / "closure" / LOG_NAME), "a", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError as exc:
        raise Stop("Refused: closure/{} cannot be written: {}.".format(LOG_NAME, exc.strerror or "error"))


def shown_path(folder, rel, names):
    """A path as a page prints it, or words for it when its name holds a term on the deny list."""
    return "an evidence file whose name holds a term on the deny list" if page_denied(folder, rel, names) else rel


def gone_files(folder, state, entries, uncounted):
    """The evidence files a check recorded that are no longer in the folder under any name."""
    recorded = state.get("evidence") if isinstance(state.get("evidence"), dict) else {}
    present = {sha for entry in entries for _, sha in entry["hashed"]}
    present |= {evidence_digest(folder / rel) for rel, _ in uncounted if (folder / rel).is_file()}
    return [rel for rel in sorted(recorded) if not (folder / rel).is_file()
            and not (isinstance(recorded[rel], dict) and recorded[rel].get("sha256") in present)]


# ---------------------------------------------------------------- covers


def cover_lines(path, eid, rows, problem=None):
    # A date in the name, as 2026-01-14 or 2026_01_14, stays whole, and every other dash or underscore reads as a space.
    stem = collapse(re.sub(r"(?<!\d)(\d{4}[-_]\d\d[-_]\d\d)(?!\d)|[-_]", lambda m: m.group(1) or " ",
                           path.stem[len(eid):].strip(" -_")))
    what = (eid + " " + capital_first(stem)).strip()
    milestone = next((row["id"] for row in rows if eid in row["ids"]), None)
    readable = path.suffix.lower() in documents_module().READABLE
    if readable and not problem:
        source, where = ("read from the document by the check", "The check reads this document's own text. Type a page "
                         "here only where the reader found no text or read the page only in part")
    else:  # a file the reader refused or has no reader for: every cited page is typed, as a scan's is
        source, where = ("typed by a person, because the check " + ("did not read the file: " + problem if readable else
                         "has no reader for this file type"), "The check cannot read this file. Type each page the memo "
                         "cites here")
    return ("What: {}\nFor: {}\nSigned by:\nStatus: DRAFT\nSource: {}\n\n"
            "<!-- {}, under a heading of its page number. A person fills Signed by as role, "
            "YYYY-MM-DD and sets Status to FINAL. A second person who compared a typed page adds Checked by: role, "
            "YYYY-MM-DD with the lines at the top, above the blank line; below it, the line is not read. -->\n").format(
                what, (milestone + " " + eid) if milestone else eid, source, where)


def page_list(numbers):
    return "page{} {}".format("" if len(numbers) == 1 else "s", ", ".join(str(n) for n in numbers[:12])
                              + (" and more" if len(numbers) > 12 else ""))


def describe_read(result, names=()):  # a word left out that is on the deny list is counted and never shown
    if result["problem"]:
        return "not read: {}".format(result["problem"]), True
    pages = result["pages"]
    blank = [i + 1 for i, text in enumerate(pages) if not text.strip()]
    text = "{}, {} with text".format(plural(len(pages), "page"), len(pages) - len(blank))
    if blank:
        text += "; no text on {}".format(page_list(blank))
    if result["partly"]:
        text += "; read only in part: {}".format(page_list(result["partly"]))
    if result["hidden"]:
        words = [w for n in sorted(result["hidden"]) for w in result["hidden"][n]]
        deny = set(re.findall(r"\w+", fold(" ".join(names)).casefold()))
        bare = [re.sub(r"^\W+|\W+$", "", w) for w in words]  # a word as it reads, with no mark around it
        shown = ['"{}"'.format(w) for w in bare if w and not deny & set(re.findall(r"\w+", fold(w).casefold()))][:5]
        more = ["{} more".format(len(words) - len(shown))] if len(words) > len(shown) else []
        text += "; {} a reader cannot see left out on {}{}".format(plural(len(words), "word"), page_list(sorted(result["hidden"])),
                                                                  ": " + and_list(shown + more) if shown else "")
    text += "".join("; " + note for note in result["notes"])
    return text, bool(blank or result["partly"])


def file_evidence_id(name, rows):
    """The evidence id a document's file name starts with, or None: one plan.md or the plan approval names, or an EV
    id, so an institution's own reference number at the start of its name is no id. Every number group after EV belongs to
    the id, so EV-2026-0042 stays whole. Where the plan lists a shorter id the name starts with, as with EV-12 on
    EV-12-2026-03-14-minutes.pdf, the plan's id wins, because a date can follow an id."""
    m = EVIDENCE_ID_RE.match(name)
    eid = m.group(1) if m else ""
    listed = [i for i in listed_ids(rows) if eid == i or eid.startswith(i + "-")]
    return max(listed, key=len) if listed else (eid if re.match(r"EV-\d", eid) else None)


def cmd_covers(args):
    folder, _today = parse_folder_args(args, need_folder=True)
    try:
        fields, parts = parse_finding(folder)
        try:
            rows = parse_plan(folder)
        except Stop:
            rows = []
        ev_dir = folder / "evidence"
        ev_dir.mkdir(exist_ok=True)
        has_cover = covered_files(evidence_files(ev_dir))
        cover_of = {named_by_cover(q)[0]: q for q in evidence_files(ev_dir) if q.suffix.lower() in TEXT_SUFFIXES}
        taken = {h["id"]: q.relative_to(folder).as_posix() for q in evidence_files(ev_dir)  # ids a header already carries
                 if q.suffix.lower() in TEXT_SUFFIXES for h in [parse_header(q)] if h}
        out = [CONFIDENTIAL, ""] + kit_note()
        needs = False
        drafts, held = [], []
        names = page_names(folder, fields, parts, load_state(folder) or {})
        files = sorted(p for p in evidence_files(ev_dir) if p.suffix.lower() not in TEXT_SUFFIXES or is_plain_document(p))
        ids = [file_evidence_id(p.name, rows) for p in files]
        for p, eid in zip(files, ids):
            rel = p.relative_to(folder).as_posix()
            held.append((rel, evidence_digest(p)))
            cover = p.with_name(p.name + ".md")
            result = read_document(p)
            description, gap = describe_read(result, names)
            if gap and p in cover_of and not result["problem"]:  # a page typed into its cover is no longer a gap
                typed = {n for n, text, _ in cover_pages(cover_of[p]) if text.strip()}
                wanted = [i + 1 for i, text in enumerate(result["pages"]) if not text.strip()] + list(result["partly"])
                gap = any(n not in typed for n in wanted)
            needs = needs or gap
            if p in has_cover:
                out.append("{}: {}. It has a cover already.".format(rel, description))
                continue
            if cover.is_file():
                out.append("{}: {}. {} names another file, so this file has no cover.".format(rel, description, cover.name))
                needs = True
                continue
            if eid is None or ids.count(eid) > 1 or eid in taken:
                out.append("{}: {}. {}".format(rel, description, "Rename it to start with an evidence id plan.md lists or an "
                           "EV id, such as EV-12, and keep the file's own name after the id." if eid is None else (
                               "Another file's name starts with {} too".format(eid) if ids.count(eid) > 1 else
                               "{} carries {} already".format(taken[eid], eid)) + ", so this file gets no cover; give each its own evidence id."))
                needs = True
                continue
            drafts.append((cover, cover_lines(p, eid, rows, result["problem"])))
            out.append("{}: {}. Draft cover written for evidence id {}.".format(rel, description, eid))
        out.extend("The engagement team: {} hold the same bytes.".format(pair) for pair in same_bytes(held))
        needs = needs or bool(same_bytes(held))
        if not files:
            out.append("There are no documents in evidence/ without a text header.")
        else:
            out.append("")
            out.append("A person checks the evidence id, fills Signed by and sets Status to FINAL on each cover. Type a page only where it has "
                       "no text, was read only in part or is in a file the check has no reader for.")
            out.append("A PDF page is its printed page. A Word, CSV, email or text file is always page 1, so a cite "
                       "does not say where in the file a figure sits. A workbook page is a visible sheet, in workbook "
                       "order, and an Excel percent or date reads as its stored fraction or serial number.")
        screen = "\n".join(out)
        denied = page_denied(folder, screen, names, fields.get("Identifier"))
        if denied is not None:
            raise Stop(deny_refusal(folder, fields, denied, screen))
        for cover, text in drafts:  # only now: a refused run leaves no cover
            write_text(cover, text)
    except Stop as stop:
        return refuse(stop.args[0])
    print(screen)
    return 1 if needs else 0


# ---------------------------------------------------------------- evals


MONTH_NAMES = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
               "November", "December")
EVAL_KINDS = (
    ("figure_digit", "A figure with one digit changed"),
    ("figure_swap", "A figure with two digits swapped"),
    ("figure_same_page", "A figure swapped for another on the same page"),
    ("date_moved", "A date moved"),
    ("quote_changed", "A quotation with one word dropped"),
    ("cite_moved", "A cite moved to another page"),
)


def plant_figure_digit(raw):
    digits = [i for i, ch in enumerate(raw) if ch.isdigit()]
    if not digits:
        return None
    i = digits[-1]
    return raw[:i] + str((int(raw[i]) + 1) % 10) + raw[i + 1:]


def plant_figure_swap(raw):
    digits = [i for i, ch in enumerate(raw) if ch.isdigit()]
    for a, b in zip(digits, digits[1:]):
        if raw[a] != raw[b]:
            chars = list(raw)
            chars[a], chars[b] = chars[b], chars[a]
            return "".join(chars)
    return None


def plant_date(raw):
    d = parse_date(raw)
    if d is not None:
        return (d + datetime.timedelta(days=31)).isoformat()
    for k, name in enumerate(MONTH_NAMES):
        if name in raw:
            return raw.replace(name, MONTH_NAMES[(k + 1) % 12])
    return None


def plant_quote(raw):
    words = raw.split(" ")
    if len(words) < 3:
        return None
    return " ".join(words[:1] + words[2:])


def eval_plants(text, tied, record_mod, by_label, idx):
    """([(kind, line, claimed, planted text, planted value)] for each claim that ties today, [(line, claimed)] for each
    such claim that took no error of its own kind)."""
    lines = text.split("\n")
    plants = []
    bare = []

    def planted(claim, new):
        first, where = claim["pos"]
        start = sum(len(line) + 1 for line in lines[:first - 1]) + where
        if claim["kind"] == "quotation":  # by position, because the memo's marks may be curly and its lines wrapped
            marks = SINGLE_MARKS if claim["single"] else QUOTE_MARKS
            end = next((i for i in range(start + 1, len(text)) if text[i] in marks
                        and (not claim["single"] or not is_word_char(text[i + 1:i + 2] or " "))), -1)
            if end < 0 or text[start] not in marks:
                return None
            return text[:start] + new + text[end + 1:]
        at = text.find(claim["claimed"], start)
        if at < 0:
            return None
        return text[:at] + new + text[at + len(claim["claimed"]):]

    for claim in tied:
        raw = claim["claimed"]
        m = claim["cite"]
        eid, page = m.group("id"), m.group("page")
        options = []
        if claim["kind"] == "figure":
            options.append(("figure_digit", plant_figure_digit(raw)))
            options.append(("figure_swap", plant_figure_swap(raw)))
            ex = idx.exhibit(eid)
            if ex and page:
                others = page_figures(ex, int(page), record_mod, raw)
                if others:
                    options.append(("figure_same_page", others[0]))
        elif claim["kind"] == "date":
            options.append(("date_moved", plant_date(raw)))
        else:
            options.append(("quote_changed", plant_quote(raw)))
        own = 0
        for kind, new in options:
            if new and new != raw:
                body = planted(claim, new)
                if body is not None:
                    plants.append((kind, claim["line"], raw, body, new))
                    own += 1
        if not own:
            bare.append((claim["line"], raw))
        if page:
            ex = idx.exhibit(eid)
            if ex and ex["last"] > ex["first"]:
                target = int(page) + 1 if ex["first"] + int(page) <= ex["last"] else int(page) - 1
                cite = m.group(0)
                first, where = claim["pos"]
                start = sum(len(line) + 1 for line in lines[:first - 1]) + where
                at = text.find(cite, start)
                if at >= 0:
                    body = text[:at] + "[{} p{}]".format(eid, target) + text[at + len(cite):]
                    plants.append(("cite_moved", claim["line"], raw, body, "{} p{}".format(eid, target)))
    return plants, bare


def page_figures(ex, page, record_mod, raw):
    """Other figures on the cited page, as printed there."""
    text = EXHIBIT_TEXT.get((ex["label"], page), "")
    same = record_mod.norm_figure(raw)
    out = []
    for fig in record_mod.scan(text)["figures"]:
        shown = fig["raw"].strip()
        if not record_mod.is_bare_year(fig) and record_mod.norm_figure(shown) != same and shown not in out:
            out.append(shown)
    return out


EXHIBIT_TEXT = {}
PROGRESS_FROM = 100  # a long eval says how far it has got, on stderr, so the printed page stays the same


def run_eval(folder):
    """(results by kind, misses, count of claims that tie or match a draft, fields, parts, claims with no plant of
    their own kind, count of claims that match a draft). Writes nothing."""
    fields, parts = parse_finding(folder)
    require_ready(fields, parts)
    if not memo_present(folder):
        raise Stop("There is no memo to test yet.")
    entries, _ = scan_evidence(folder)
    owner = fields["Owner role"]
    text = memo_text(folder)
    today, listed = as_the_check_reads(folder, entries)
    base = memo_check(folder, entries, owner, text=text, use_rulings=False, today=today, listed=listed)
    EXHIBIT_TEXT.clear()
    for entry in entries:
        pages, _problem = entry_pages(folder, entry)
        for n, page_text, _line, _typed in pages:
            EXHIBIT_TEXT[(entry["id"], n)] = page_text
    record_mod, _ = engine()
    plants, bare = eval_plants(text, base["tied"], record_mod, base["by_label"], base["index"])
    results = {kind: [0, 0] for kind, _ in EVAL_KINDS}
    misses = []
    built = (base["index"], base["by_label"])  # the evidence does not change between plants, so read it once
    if len(plants) >= PROGRESS_FROM:  # the banner leads the progress lines too
        print(CONFIDENTIAL, file=sys.stderr, flush=True)
    for count, (kind, line, raw, body, new) in enumerate(plants, 1):
        got = memo_check(folder, entries, owner, text=body, use_rulings=False, built=built, today=today, listed=listed)
        results[kind][0] += 1
        # A draft's one row can go while its plant takes a row of its own, so its rows do not count here.
        if got["left"] - got["draft_rows"] > base["left"] - base["draft_rows"]:
            results[kind][1] += 1
        else:
            misses.append((line, kind, raw, new))
        if len(plants) >= PROGRESS_FROM and count % 25 == 0:
            print("Eval: {} of {} planted errors run.".format(count, len(plants)), file=sys.stderr, flush=True)
    return results, misses, len(base["tied"]), fields, parts, bare, base["draft_claims"]


def cmd_eval(args):
    if args == ["--library"]:
        return eval_library()
    if len(args) != 1 or args[0].startswith("-"):
        raise UsageError()
    folder = Path(args[0])
    if not (folder / "finding.md").is_file():
        raise UsageError("no finding.md in " + args[0])
    try:
        results, misses, tied, fields, parts, bare, drafts = run_eval(folder)
        planted = sum(r[0] for r in results.values())
        caught = sum(r[1] for r in results.values())
        out = [CONFIDENTIAL, ""] + kit_note() + [
               "Eval of the memo check on {}. Nothing in the folder changed.".format(fields["Identifier"]),
               "Planted {}, one at a time, in the {} that {} today{}.".format(
                   plural(planted, "error"), plural(tied, "claim"), "ties" if tied == 1 else "tie",
                   " or {} a draft's pages".format("matches" if tied == 1 else "match") if drafts else "")]
        for kind, label in EVAL_KINDS:
            if results[kind][0]:
                out.append("  {}: {} planted, {} caught.".format(label, results[kind][0], results[kind][1]))
        out.append("Caught {} of {}.".format(caught, planted))
        if bare:
            shown = ["line {} {}".format(line, raw) for line, raw in bare]
            out.append("{} no error of {} own kind planted, so read {} by hand: {}.".format(
                "1 claim had" if len(bare) == 1 else "{} claims had".format(len(bare)),
                "its" if len(bare) == 1 else "their", "it" if len(bare) == 1 else "these", "; ".join(shown)))
        if misses:
            out.append("What the check did not catch, for a person to look for:")
            out.extend("  Line {}: {} {} {} still ties.".format(line, raw, "with its cite moved to" if kind == "cite_moved"
                                                                else "changed to", new) for line, kind, raw, new in misses)
        screen = "\n".join(out)
        names = page_names(folder, fields, parts, load_state(folder) or {})
        denied = page_denied(folder, screen, names, fields["Identifier"])
        if denied is not None:
            raise Stop(deny_refusal(folder, fields, denied, screen))
    except Stop as stop:
        return refuse(stop.args[0])
    print(screen)
    return 0


LIBRARY_LETTER = """Identifier: LIB-1
Institution: Library Example
Issuer: the Supervisor
Letter date: 2026-01-01
Kind of matter: internal audit finding
Owner role: Head of Example

## Concern
x
## Cause
x
## Consequence
x
## Corrective action
x
## Commitment
x
"""


def run_library_case(case):
    """(rows on the list, the rows) for one library case, in a temporary folder."""
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp) / "case"
        (folder / "evidence").mkdir(parents=True)
        (folder / "closure").mkdir()
        write_text(folder / "finding.md", LIBRARY_LETTER)
        for ev in case["evidence"]:
            head = "What: {0} Evidence\nFor: {0}\nSigned by: Head of Example, 2026-02-01\nStatus: {1}\n\n".format(
                ev["id"], ev.get("status", "FINAL"))
            body = "".join("## Page {}\n{}\n\n".format(i + 1, text) for i, text in enumerate(ev["pages"]))
            write_text(folder / "evidence" / (ev["id"] + ".md"), head + body)
        entries, _ = scan_evidence(folder)
        memo = memo_check(folder, entries, "Head of Example", text=case["memo"], use_rulings=False)
        return memo["left"], memo["rows"]


def eval_library():
    cases_dir = KIT / "library" / "cases"
    paths = sorted(cases_dir.glob("*.json")) if cases_dir.is_dir() else []
    if not paths:
        print("There is no library of cases beside this kit.")
        return 1
    wrong = []
    limits = 0
    for path in paths:
        try:
            case = json.loads(path.read_text(encoding="utf-8"))
            left, rows = run_library_case(case)
            expect = case["expect"]
            ok = left == expect["list"] and all(any(word in row for row in rows) for word in expect.get("contains", []))
            limits += 1 if case.get("known_limit") else 0
            if not ok:
                wrong.append("  {}: expected {} on the list, got {}: {}".format(path.stem, expect["list"], left, "; ".join(rows)))
        except Exception as err:  # any case file a person typed wrong, named, counted wrong and passed over
            wrong.append("  {}: this case cannot be run: {}".format(path.stem, os_refusal(err)[len("Refused: "):]
                                                                    if isinstance(err, OSError)
                                                                    else str(err) or type(err).__name__))
    for line in kit_note():
        print(line)
    print("Library cases: {}, {} as expected, {} of them a known limit.".format(
        len(paths), len(paths) - len(wrong), limits))
    for line in wrong:
        print(line)
    return 1 if wrong else 0


# ---------------------------------------------------------------- size


def size_assumptions(places):
    """({assumption: value}, the assumptions a size-assumptions.txt set), reading [(folder, where)] in order. The
    first line for an assumption wins, so a finding's own file wins over the engagement's one folder up."""
    values, fitted = {}, set()
    names = [name for name, _ in SIZE_ASSUMPTIONS]
    for base, where in places:
        path = base / SIZE_FILE
        if not path.is_file():
            continue
        for k, line in enumerate(read_lines(path), 1):
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            m = re.fullmatch(r"(.+?)\s*[:=]\s*([0-9]+(?:\.[0-9]+)?)", s)
            name = " ".join(m.group(1).lower().split()) if m else None
            if name not in names:
                raise Stop("Refused: line {} of the {} {} cannot be read. Each line names one assumption, a colon and "
                           "a number, such as minutes a claim by hand: 7. The assumptions are {}.".format(
                               k, SIZE_FILE, where, and_list(names)))
            if name not in values:
                values[name] = float(m.group(2))
                fitted.add(name)
    for name, default in SIZE_ASSUMPTIONS:
        values.setdefault(name, default)
    return values, fitted


def size_one(folder, a):
    """The counts and assumed hours for one finding folder, with the assumptions a."""
    fields, parts = parse_finding(folder)
    require_ready(fields, parts)
    rows = parse_plan(folder)
    entries, uncounted = scan_evidence(folder)
    documents = sum(1 for e in entries if len(e["hashed"]) > 1)
    claims = left = 0
    if memo_present(folder) or closed_rows(folder):  # every row the check would list, before any ruling
        today, listed = as_the_check_reads(folder, entries)
        memo = memo_check(folder, entries, fields["Owner role"], text=None if memo_present(folder) else "",
                          use_rulings=False, today=today, listed=listed, closed=True)
        claims, left = memo["claims"], memo["left"]
    # Pages a person typed into a cover over a document, a scan's or a file type with no reader: work only the kit asks.
    typed = sum(len(e.get("typed_pages", ())) for e in entries
                if len(e["hashed"]) > 1 and not e["hashed"][1][0].lower().endswith(".txt"))
    letter = parse_date(fields["Letter date"])
    last = max(row["date"] for row in rows)
    months = max(1, (last.year - letter.year) * 12 + last.month - letter.month + 1)
    files = len(entries) + len(uncounted)
    hand = {
        "claims": claims * a["minutes a claim by hand"] * a["memo versions"] / 60.0,
        "reports": months * a["hours a status report"],
        "finding": files * a["minutes to find a signed file"] / 60.0,
        "rework": a["hours a rework round"],
    }
    kit = {
        "reading": claims * a["minutes to read a claim"] / 60.0,
        "covers": files * a["minutes a cover"] / 60.0,
        "typed": typed * a["minutes to type and compare a page"] / 60.0,
        "rulings": left * a["minutes a ruling"] / 60.0,
        "reports": months * a["minutes a status report with the kit"] / 60.0,
        "rework": a["rework rounds with the kit"] * a["hours a rework round"],
    }
    # Each part is rounded as printed and the total is their sum, so the printed parts add up to the printed total.
    hand = {k: round(v, 1) for k, v in hand.items()}
    kit = {k: round(v, 1) for k, v in kit.items()}
    return {"id": fields["Identifier"], "milestones": len(rows), "files": files, "documents": documents,
            "claims": claims, "left": left, "months": months, "hand": hand, "kit": kit, "typed": typed,
            "by_hand": round(sum(hand.values()), 1), "with_kit": round(sum(kit.values()), 1)}


def number_text(value):
    return "{:g}".format(value)


def assumption_text(name, value):
    """One assumption as the closing line prints it, such as 7 minutes a claim by hand."""
    if value == 1:
        name = re.sub(r"^(minute|hour|memo version|rework round)s\b", r"\1", name)
    return "{} {}".format(number_text(value), name)


def cmd_size(args):
    if len(args) != 1 or args[0].startswith("-"):
        raise UsageError()
    root = Path(args[0])
    if not root.is_dir():
        raise UsageError("no folder " + args[0])
    one = (root / "finding.md").is_file()
    folders = [root] if one else sorted(p for p in root.iterdir() if p.is_dir() and (p / "finding.md").is_file())
    if not folders:
        raise UsageError("no finding.md in {} or the folders under it".format(args[0]))
    try:  # one set of assumptions a run: beside the finding and one folder up, or in the folder of findings
        a, fitted = size_assumptions([(root, "beside the finding"), (root.resolve().parent, "one folder up")] if one
                                     else [(root, "in this folder of findings")])
    except Stop as stop:
        return refuse(stop.args[0])
    sizes = []
    not_ready = []
    for folder in folders:
        try:
            own, mine = a, set()
            if not one and (folder / SIZE_FILE).is_file():  # a finding's own line wins over the folder's, as alone
                mine = size_assumptions([(folder, "beside " + folder.name)])[1]
                own = size_assumptions([(folder, "beside " + folder.name), (root, "in this folder of findings")])[0]
            sizes.append(dict(size_one(folder, own), mine=mine, values=own))
        except Stop as stop:
            if one:
                return refuse(stop.args[0])
            not_ready.append("{}: {}".format(folder.name, stop.args[0]))
    if not sizes:
        return refuse("\n".join(not_ready))
    out = [CONFIDENTIAL, ""] + kit_note()
    for s in sizes:
        out.append("{}: {}, {} ({} with a separate cover), {} on the memo check, {} before rulings, {}.".format(
            s["id"], plural(s["milestones"], "milestone"), plural(s["files"], "evidence file"), s["documents"],
            plural(s["claims"], "claim"), plural(s["left"], "row"), plural(s["months"], "month")))
        out.append("  By hand, assumed: {:.1f} hours. Checking claims {:.1f}, status reports {:.1f}, finding signed "
                   "files {:.1f}, one rework round {:.1f}.".format(s["by_hand"], s["hand"]["claims"], s["hand"]["reports"],
                                                                 s["hand"]["finding"], s["hand"]["rework"]))
        out.append("  With the kit, assumed: {:.1f} hours. Reading each claim against its page {:.1f}, cover lines "
                   "{:.1f}, {}rulings {:.1f}, status reports {:.1f}, rework {:.1f}.".format(
                       s["with_kit"], s["kit"]["reading"], s["kit"]["covers"],
                       "typing and comparing {} {:.1f}, ".format(plural(s["typed"], "page"), s["kit"]["typed"])
                       if s["typed"] else "", s["kit"]["rulings"], s["kit"]["reports"], s["kit"]["rework"]))
        if s["mine"]:
            out.append("  {} from its own {}.".format(plural(len(s["mine"]), "assumption"), SIZE_FILE))
    out.extend(not_ready)
    if len(sizes) > 1 or not_ready:
        out.append("")
        out.append("{}: {:.1f} hours by hand, {:.1f} with the kit, assumed.".format(
            plural(len(sizes), "finding"), sum(s["by_hand"] for s in sizes), sum(s["with_kit"] for s in sizes)))
    if not_ready:
        out.append("{} not ready and left out of these hours.".format(plural(len(not_ready), "finding")))
    out.append("")
    t = {name: number_text(value) for name, value in a.items()}
    # A finding's own values, which the folder's line above does not show, so each part can be rebuilt from the screen.
    own_lines = "".join(" {} takes {} from its own {}.".format(
        s["id"], and_list([assumption_text(name, s["values"][name]) for name, _ in SIZE_ASSUMPTIONS if name in s["mine"]]),
        SIZE_FILE) for s in sizes if s["mine"])
    out.append("These hours are assumptions{}: {} minutes a claim by hand over {} memo versions, {} hours a monthly "
               "status report, {} minutes to find a signed file, {} hours a rework round, {} minutes a cover, {} "
               "minutes a ruling, and with the kit {} minutes to read a claim once against its page, {} minutes to "
               "type and compare a page, {} minutes to review a status report the kit drafts and {} rework round{}.{} "
               "Replace them with timed figures in a {} {}, which changes no fingerprint.".format(
                   ", {} of them from {}".format(len(fitted), SIZE_FILE) if fitted else "",
                   t["minutes a claim by hand"], t["memo versions"], t["hours a status report"],
                   t["minutes to find a signed file"], t["hours a rework round"], t["minutes a cover"],
                   t["minutes a ruling"], t["minutes to read a claim"], t["minutes to type and compare a page"],
                   t["minutes a status report with the kit"], t["rework rounds with the kit"],
                   "" if a["rework rounds with the kit"] == 1 else "s", own_lines, SIZE_FILE,
                   "beside the finding or one folder up" if one else "beside a finding or in this folder of findings"))
    print("\n".join(out))
    return 1 if not_ready else 0


# ---------------------------------------------------------------- commands


def cmd_new(args):
    """Make the folder at the path given, whose last part is the id, and never inside the kit's own folders."""
    if len(args) != 1 or args[0].startswith("-"):
        raise UsageError()
    target = Path.cwd() / args[0]
    ident = target.name
    if not ID_RE.match(ident):
        raise UsageError("an id holds only letters, digits and hyphens, and ends the path")
    if target.exists():
        print("Refused: {} already exists{}.".format(args[0], " here" if args[0] == ident else ""))
        return 1
    if KIT == target.resolve() or KIT in target.resolve().parents:
        print("Refused: {} is inside the kit's own folders. Make the finding folder outside the kit, such as "
              "../findings/{} from the kit root.".format(args[0], ident))
        return 1
    (target / "evidence").mkdir(parents=True)
    (target / "closure").mkdir()
    values = {"id": ident}
    write_text(target / "finding.md", TEMPLATE_FINDING.format(**values))
    write_text(target / "plan.md", TEMPLATE_PLAN.format(**values))
    write_text(target / "closure" / "memo.md", TEMPLATE_MEMO.format(**values))
    write_text(target / "closure" / "record.md", TEMPLATE_RECORD.format(**values))
    write_text(target / "closure" / "rulings.md", TEMPLATE_RULINGS.format(**values))
    write_text(target / "closure" / "measures.md", TEMPLATE_MEASURES.format(**values))
    print("Made {}. Fill the header lines in finding.md and paste each part of the letter under its heading, then "
          "fill plan.md.".format(args[0]))
    return 0


def parse_folder_args(args, need_folder=False):
    """(folder Path, today) from [<folder>] [--today YYYY-MM-DD]; raises UsageError."""
    today = None
    folder = None
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--today" or arg.startswith("--today="):
            if arg == "--today":
                if i + 1 >= len(args):
                    raise UsageError()
                value = args[i + 1]
                i += 2
            else:
                value = arg.split("=", 1)[1]
                i += 1
            if today is not None:
                raise UsageError()
            today = parse_date(value)
            if today is None:
                raise UsageError('--today needs a date as YYYY-MM-DD, not "{}"'.format(value))
            continue
        if arg.startswith("-") or folder is not None:
            raise UsageError()
        folder = arg
        i += 1
    if today is None:
        today = datetime.date.today()
    if folder is None:
        if need_folder:
            raise UsageError()
        path = Path.cwd()
        if not (path / "finding.md").is_file():
            raise UsageError("no finding.md in the current folder; name the finding folder")
    else:
        path = Path(folder)
        if not (path / "finding.md").is_file():
            raise UsageError("no finding.md in " + folder)
    return path, today


def names_screen(folder):
    """check --names: the deny list itself, for the person who asked. Every other page prints only its counts."""
    fields, parts = parse_finding(folder)
    require_ready(fields, parts)
    state = load_state(folder) or {}
    names = page_names(folder, fields, parts, state)
    left = left_out_names(fields, parts, names)
    out = [CONFIDENTIAL, "", "Deny list for {}: {}.".format(fields["Identifier"], plural(len(names), "name"))]
    out.extend("  " + name for name in names)
    if left:
        out.append("Left out by role-words.txt:")
        out.extend("  " + item for item in left)
    return "\n".join(out)


def cmd_check(args):
    flags = [arg for arg in args if arg in ("--names", "--repaste")]
    if len(flags) > 1:
        raise UsageError()
    path, today = parse_folder_args([arg for arg in args if arg not in flags])
    try:
        if flags == ["--names"]:
            print(names_screen(path))
            return 0
        if flags == ["--repaste"]:
            repaste_letter(path, today)
        screen, code = check(path, today)
    except Stop as stop:
        return refuse(stop.args[0])
    print(screen)
    return code


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    try:
        if not args:
            raise UsageError()
        if args[0] in ("-h", "--help", "help") and len(args) == 1:
            print(USAGE)
            return 0
        verbs = {"--version": cmd_version, "new": cmd_new, "check": cmd_check, "sign": cmd_sign, "covers": cmd_covers,
                 "eval": cmd_eval, "size": cmd_size}
        if args[0] not in verbs:
            raise UsageError()
        if args[0] in ("covers", "eval", "size") and any(arg.split("=")[0] == "--today" for arg in args[1:]):
            raise UsageError("{} takes no --today".format(args[0]))  # none of the three uses a typed date
        return verbs[args[0]](args[1:])
    except UsageError as err:
        if err.args:
            print("finding: " + err.args[0], file=sys.stderr)
        print(USAGE, file=sys.stderr)
        return 2
    except OSError as err:
        return refuse(os_refusal(err))


def os_refusal(err):
    """Such as evidence that is a file. Only the last name prints: a full path can carry a finding's identifier."""
    name = Path(str(err.filename)).name if err.filename else "a file"
    return "Refused: could not read or write {}: {}.".format(name, (err.strerror or "an error").lower())


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass
    sys.exit(main())
