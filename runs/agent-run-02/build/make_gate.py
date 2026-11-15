#!/usr/bin/env python3
"""The scorer gate for agent run 01: the floor file, the known-good and known-bad findings files, and the gate run.

Purpose: builds a finding folder from case/ the way the run's intake would (the duplicate moved out, the file named
  by a reference number given an id), writes a plan, fills and signs each cover as a person would and types the
  scanned page, then writes a memo that states every trap's planted value as fact with the cite of the trap's page.
  It runs the kit's check on that memo, turns the check's rows into the floor file with tools/score.py --rows, writes
  the two gate files from key/traps.json and runs tools/score.py --gate, which prints PASS or FAIL.
  With --probe it also checks a memo of the true values against the same folder, which should leave no row on the
  list, and prints only how many rows it left.
Usage: python3 -I build/make_gate.py --repo <a scratch copy of the kit> [--today 2026-07-10] [--probe]
Reads: case/, key/traps.json, ../tools/score.py. Writes: build/scratch/floor/ (replaced whole),
  build/scratch/floor-check.txt, key/floor.tsv, gate/known-good.tsv, gate/known-bad.tsv.
Network: none. Standard library only. The kit's commands run as `python3 -I finding/finding.py` in the repo given.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

SEALED = Path(__file__).resolve().parent.parent
RUN = SEALED.parent
SCORE = RUN / "tools" / "score.py"
FID = "MRA-PAM-05"
CHG_NAME = "CHG-2026-04417 HR leaver feed go-live record.pdf"
CHG_ID = "EV-04"

PLAN_ROWS = [
    ("M1 Revise and approve the access management standard", "Chief Information Security Officer", "2026-03-31",
     "The standard sets a leaver deadline and a quarterly privileged access review, approved by the Board Risk Committee",
     "EV-01 (done), EV-02, EV-20", "The standard in force matches the version the committee approved"),
    ("M2 Automate leaver notices and remove every leaver's access within one business day", "Head of Identity Services",
     "2026-04-30", "The HR feed is live and a sample of leavers shows access removed within one business day",
     "EV-04, EV-05, EV-06 (done), EV-07, EV-14, EV-18", "Recompute the sample from the HR, contractor and identity records"),
    ("M3 Remove or assign an owner to every orphaned privileged account", "Head of Infrastructure", "2026-05-31",
     "Every orphaned account in the baseline has an outcome", "EV-08 (done), EV-09",
     "Compare the baseline extract with the outcomes, account by account"),
    ("M4 Train reviewers and complete the first quarterly privileged access review", "Head of Identity Services",
     "2026-06-30", "Every reviewer is trained and the first review is signed",
     "EV-03, EV-10, EV-11, EV-12 (done), EV-13, EV-19", "Compare training dates with each reviewer's first decision"),
    ("M5 Extend the quarterly review to the cloud hosting platform", "Head of Cloud Engineering", "2026-09-30",
     "The cloud hosting platform's privileged accounts are in a signed quarterly review", "EV-15, EV-16, EV-17, EV-21 (done)",
     "Sample cloud accounts in the review extract"),
]

# The signature line a person types on each cover, and any Checked by line, by evidence id.
SIGNATURES = {
    "E-PLAN-1": "Signed by: Company Secretary, 2026-02-19",
    "EV-01": "Signed by: Chief Information Security Officer, 2026-03-27",
    "EV-02": "Signed by: Board Risk Committee chair, 2026-04-23",
    "EV-03": "Signed by: Chief Information Security Officer, 2026-03-30",
    "EV-04": "Signed by: Change advisory board chair, 2026-03-23",
    "EV-05": "Produced by: identity governance MI report, 2026-06-30",
    "EV-06": "Approved by: EV-07",
    "EV-07": "Signed by: Head of IT Risk, 2026-05-08",
    "EV-08": "Signed by: Head of Infrastructure, 2026-06-05",
    "EV-09": "Produced by: directory outcomes extract, 2026-05-29",
    "EV-10": "Never signed: training deck",
    "EV-11": "Signed by: Head of Identity Services, 2026-04-27",
    "EV-12": "Signed by: Head of Identity Services, 2026-05-12",
    "EV-13": "Produced by: review tool extract, 2026-05-11",
    "EV-14": "Signed by: Head of Identity Services, 2026-03-13",
    "EV-15": None,
    "EV-16": "Signed by: Chief Information Security Officer, 2026-07-03",
    "EV-17": "Never signed: email",
    "EV-18": "Produced by: HR to identity feed run log, 2026-03-31",
    "EV-19": "Never signed: quick reference card",
    "EV-20": "Signed by: Company Secretary, 2025-11-20",
}
TYPED = {"EV-08": ("Checked by: Infrastructure risk lead, {today}",
                   "## Page 4\n\nSign-off sheet\nOrphaned privileged accounts: clean-up report\nM3 of the remediation plan\n"
                   "I have read this report and I confirm that it records the clean-up as it was carried out.\n"
                   "Role: Head of Infrastructure\nSignature: (signed)\nDate: 2026-06-05\n")}

FLOOR_MEMO = """# Closure memo MRA-PAM-05

M1, the access management standard.
The standard requires that "every orphaned account is removed or given a named owner within 90 days" [EV-01 p6].

M2, the leaver feed.
There were 348 employee leavers in April 2026 [EV-05 p3].
1,112 of 1,135 leavers had their access removed within one business day [EV-05 p1].
The Head of IT Risk approved the sample test by email on 2026-05-06 [EV-06 p3].
The leaver feed ran every business day from 2026-03-16 to 2026-03-31 [EV-18 p1].
Since 2026-04-01, 100% of leavers were removed within one business day [EV-16 p3].

M3, orphaned privileged accounts.
M3 was committed for 2026-06-30 [E-PLAN-1 p2].
Platform teams completed the owner assignment briefing on 2026-04-14 [EV-11 p3].

M4, reviewer training and the first quarterly review.
The main reviewer training session was held on 2026-03-02 [EV-11 p2].
The first quarterly review followed the review method, version 2.4 [EV-12 p2].
Break-glass accounts were outside the review under exception EXC-2026-007, approved on 2026-01-05 [EV-12 p4].

M5, the cloud hosting platform.
The cloud hosting platform holds 54 privileged accounts [EV-17 p1].
"""

PROBE_MEMO = """# Closure memo MRA-PAM-05

M1, the access management standard.
An orphaned account "is removed, or assigned a named owner, within 120 days of the date it was found" [EV-01 p6].
M5 was committed for 2026-09-30 [E-PLAN-1 p4].
The board heard an estimate of about 240 orphaned accounts [E-PLAN-1 p2].

M2, the leaver feed.
There were 384 employee leavers in April 2026 [EV-05 p3].
The share removed within the deadline was 98.0% [EV-05 p1].
The Head of IT Risk approved the sample test on 2026-05-08 [EV-07 p1].
By the end of April the feed had processed 621 leavers [EV-06 p1].
The sample test found 39 of the 40 leavers removed in time [EV-06 p3].

M3, orphaned privileged accounts.
M3 was committed for 2026-05-31 [E-PLAN-1 p2].
The clean-up removed 131 accounts and assigned a named owner to 83 [EV-08 p3].

M4, reviewer training and the first quarterly review.
The main reviewer training session was held on 2026-04-02 [EV-11 p2].
The review method was approved on 2026-03-30 [EV-03 p1].
The review followed version 2.4 of 2026-04-01 [EV-12 p2].
The cloud exception was approved on 2026-03-31 [EV-12 p2].
The last revocation was completed on 2026-05-08 [EV-12 p4].

M5, the cloud hosting platform.
The cloud hosting platform holds 64 privileged accounts [EV-17 p1].
"""


def run(cmd, cwd):
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)


def kit(repo, *args):
    return run([sys.executable, "-I", "finding/finding.py"] + list(args), repo)


def build_folder(repo, today):
    base = SEALED / "build" / "scratch" / "floor"
    if base.exists():
        shutil.rmtree(base)
    base.mkdir(parents=True)
    folder = base / FID
    r = kit(repo, "new", str(folder))
    if r.returncode != 0:
        raise SystemExit("finding new failed:\n" + r.stdout + r.stderr)
    shutil.copyfile(SEALED / "case" / "finding.md", folder / "finding.md")
    ev = folder / "evidence"
    ev.mkdir(exist_ok=True)
    for p in sorted((SEALED / "case" / "evidence").iterdir()):
        if p.name.endswith(" (1).pdf"):
            continue  # the duplicate goes out of the folder before the first check
        name = "{} {}".format(CHG_ID, p.name) if p.name == CHG_NAME else p.name
        shutil.copyfile(p, ev / name)
    plan = (folder / "plan.md").read_text(encoding="utf-8").rstrip("\n") + "\n"
    plan += "".join("| {} |\n".format(" | ".join(row)) for row in PLAN_ROWS)
    plan += ("\nThe duplicate copy of the board minutes, E-PLAN-1 Board minutes 2026-02-12 (1).pdf, holds the same bytes "
             "and was moved out before the first check.\nOwners and dates are from E-PLAN-1 p2, with M5 as amended on "
             "E-PLAN-1 p4.\n")
    (folder / "plan.md").write_text(plan, encoding="utf-8")
    r = kit(repo, "covers", str(folder))
    for cover in sorted(ev.glob("*.md")):
        lines = cover.read_text(encoding="utf-8").split("\n")
        eid = re.match(r"For: (?:\S+ )?(\S+)$", next(l for l in lines if l.startswith("For:"))).group(1)
        sig = SIGNATURES[eid]
        out = []
        for line in lines:
            if line.startswith("Signed by:") and sig:
                out.append(sig)
                if eid in TYPED:
                    out.append(TYPED[eid][0].format(today=today))
            elif line.startswith("Status:") and sig:
                out.append("Status: FINAL")
            else:
                out.append(line)
        text = "\n".join(out)
        if eid in TYPED:
            text = text.rstrip("\n") + "\n\n" + TYPED[eid][1]
        cover.write_text(text, encoding="utf-8")
    return folder


def check(repo, folder, memo, today, keep):
    (folder / "closure" / "memo.md").write_text(memo, encoding="utf-8")
    r = kit(repo, "check", str(folder), "--today", today)
    if "Memo check:" not in r.stdout:
        raise SystemExit("the check printed no memo block:\n" + r.stdout + r.stderr)
    if keep:
        keep.write_text(r.stdout, encoding="utf-8")
    return r.stdout


def cite(e):
    return "{} p{}".format(e["file_id"], e["page"])


def gate_files(traps):
    good = ["memo_line\tcite\tvalue_seen\tproblem"]
    bad = ["memo_line\tcite\tvalue_seen\tproblem"]
    n = 0
    for e in traps:
        n += 1
        if e["decoy"]:
            # flagging a decoy is a false alarm, and catches no trap
            bad.append("{}\t{}\t{}\tThe page looks wrong at this value.".format(n, cite(e), e["planted_value"] or e["key_phrase"]))
            continue
        seen = e["planted_value"] or e["key_phrase"]
        true = e["true_value"]
        problem = "The memo states {} on [{}], and the folder does not support it{}.".format(
            seen, cite(e), "; the folder supports {}".format(true) if true else "")
        good.append("{}\t[{}]\t{}\t{}".format(n, cite(e), seen, problem))
        # the right page with no trap value, and the trap's value on a page that is not the trap's
        other = "EV-19 p1"
        bad.append("{}\t{}\t-\tThis sentence needs a second look against its page.".format(n, cite(e)))
        bad.append("{}\t{}\t{}\tThe value on this line is not on the cited page.".format(n, other, seen))
    return "\n".join(good) + "\n", "\n".join(bad) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description="The scorer gate for agent run 01.")
    ap.add_argument("--repo", required=True, help="a scratch copy of the kit, the folder that holds finding/")
    ap.add_argument("--today", default="2026-07-10")
    ap.add_argument("--probe", action="store_true", help="also check a memo of the true values; prints its row count")
    args = ap.parse_args(argv)
    repo = Path(args.repo).resolve()
    folder = build_folder(repo, args.today)
    check(repo, folder, FLOOR_MEMO, args.today, SEALED / "build" / "scratch" / "floor-check.txt")
    floor = SEALED / "key" / "floor.tsv"
    r = run([sys.executable, "-I", str(SCORE), "--rows", str(SEALED / "build" / "scratch" / "floor-check.txt"),
             "--write", str(floor)], RUN)
    if r.returncode != 0:
        raise SystemExit("score.py --rows failed: " + r.stderr)
    traps = json.loads((SEALED / "key" / "traps.json").read_text(encoding="utf-8"))["traps"]
    good, bad = gate_files(traps)
    (SEALED / "gate" / "known-good.tsv").write_text(good, encoding="utf-8")
    (SEALED / "gate" / "known-bad.tsv").write_text(bad, encoding="utf-8")
    r = run([sys.executable, "-I", str(SCORE), "--validate", str(SEALED / "gate" / "known-good.tsv"),
             str(SEALED / "gate" / "known-bad.tsv"), str(floor)], RUN)
    if r.returncode != 0:
        raise SystemExit("score.py --validate refused a gate file: " + r.stderr)
    if args.probe:
        out = check(repo, folder, PROBE_MEMO, args.today, None)
        m = re.search(r"Memo check: .*", out)
        print("probe: " + (m.group(0) if m else "no memo block"))
        (folder / "closure" / "memo.md").write_text(FLOOR_MEMO, encoding="utf-8")
    r = run([sys.executable, "-I", str(SCORE), "--gate", "--traps", str(SEALED / "key" / "traps.json"),
             "--good", str(SEALED / "gate" / "known-good.tsv"), "--bad", str(SEALED / "gate" / "known-bad.tsv"),
             "--floor", str(floor)], RUN)
    print(r.stdout.strip())
    return r.returncode


if __name__ == "__main__":
    sys.exit(main())
