#!/usr/bin/env python3
"""Confirm that every trap and decoy in key/traps.json is present in the generated case.

Purpose: reads each evidence page through the kit's own reader, finding/documents.py, and compares values with the
  match rule's own normal form, from tools/score.py. For every entry it confirms the file and page exist, then:
  - a trap the check sees (check_sees true): the true value is on the trap's page, the planted value is not, and the
    planted value is on another page of the case, the page a memo would copy it from;
  - any other trap: the planted value, or the key phrase, is on the trap's page, and the true value is written on a
    page of the case or follows from the pages, as the per-entry checks below set out;
  - a decoy: the value that looks wrong is on its page, and the case shows why it is right.
  It also confirms that gate/case.tar holds case/ byte for byte.
Usage: python3 -I build/verify.py --repo <the kit, the folder that holds finding/> [--case <case folder>]
Reads: case/, key/traps.json, gate/case.tar, ../tools/score.py and the kit's finding/documents.py. Writes nothing.
Network: none. Standard library only. Exit 0 when every entry is confirmed, 1 otherwise.
"""
import argparse
import csv
import importlib.util
import io
import json
import sys
import tarfile
from pathlib import Path

sys.dont_write_bytecode = True  # importing the scorer and the kit's reader leaves no cache beside them
SEALED = Path(__file__).resolve().parent.parent
RUN = SEALED.parent


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Case:
    def __init__(self, folder, documents):
        self.folder = folder
        self.pages = {}
        for p in sorted((folder / "evidence").iterdir()):
            got = documents.read(p)
            self.pages[p.name] = got["pages"] if not got["problem"] else None

    def page(self, name, n):
        pages = self.pages.get(name)
        if not pages or not 1 <= n <= len(pages):
            return None
        return pages[n - 1]

    def where(self, test):
        return [(name, k + 1) for name, pages in sorted(self.pages.items()) if pages
                for k, text in enumerate(pages) if test(text)]

    def rows(self, name):
        return list(csv.reader(io.StringIO((self.folder / "evidence" / name).read_text(encoding="utf-8"))))


# The key gives no true value for a trap the check sees, so that a check row on another claim cannot match it by echoing
# the page. What the trap's page holds in its place, which a memo that copies the planted value contradicts:
CHECK_TRUE = {"T01": "384", "T02": "2026-04-02",
              "T03": "is removed, or assigned a named owner, within 120 days of the date it was found", "T04": "64"}


def make_holder(score):
    def held(value, text):
        if value is None or text is None:
            return False
        kind, target = score.value_kind(score.bare(value))
        return score.holds(kind, target, score.norm(text))
    return held


def extra_checks(case, held):
    """Per-entry checks of what a true value rests on when no page writes it, and why each decoy is right."""
    import datetime
    out = {}
    page = case.page
    ev12 = "EV-12 First quarterly privileged access review report.pdf"
    window_start = datetime.date(2026, 4, 7)
    # T11: the break-glass exception's own term, 90 days from 2026-01-05, ended before the review window opened.
    lapsed = datetime.date(2026, 1, 5) + datetime.timedelta(days=90)
    out["T11"] = (lapsed == datetime.date(2026, 4, 5) and lapsed < window_start and held("90 days", page(ev12, 4))
                  and held("2026-04-07", page(ev12, 2))
                  and held("for up to 90 days", page("EV-01 Access Management Standard v4.0 SIGNED.pdf", 7)))
    # D02: the cloud exception's term, 90 days from 2026-03-31, ran past the end of the window, and it was renewed.
    covered = datetime.date(2026, 3, 31) + datetime.timedelta(days=90)
    out["D02"] = (covered == datetime.date(2026, 6, 29) and covered > datetime.date(2026, 4, 17)
                  and held("2026-04-17", page(ev12, 2))
                  and held("2026-03-31", page(ev12, 2))
                  and held("approved exception EXC-2026-014", page("EV-17 Cloud hosting platform and the July review.eml", 1)))
    # T08: the briefing came after owners were already being assigned.
    orphans = case.rows("EV-09 Orphaned accounts baseline and outcomes 2026-05-29.csv")[1:]
    assigned = sorted(r[5] for r in orphans if r[4] == "assigned")
    out["T08"] = (assigned[0] == "2026-03-09" and sum(day < "2026-04-14" for day in assigned) >= 20
                  and held("before assigning any owner", page("EV-08 Orphaned privileged accounts clean-up report.pdf", 2)))
    # T12: the MI measures the directory account only; other accounts are removed by task.
    out["T12"] = held("raises a task", page("EV-14 Leaver access removal procedure v2.pdf", 2)) and held(
        "a leaver's access", page("EV-01 Access Management Standard v4.0 SIGNED.pdf", 4))
    # T10: the run log is from a test environment and its counts are not the live feed's.
    log = page("EV-18 HR to identity feed run log 2026-03-16 to 2026-03-31.txt", 1)
    out["T10"] = held("notices received 48", log) and held("136", page("EV-05 Leaver removal MI as at 2026-06-30.xlsx", 2))
    # T07: the review followed a later version than the one approved, and no approval of it is in the folder.
    method = page("EV-03 Privileged access review method v2.3.pdf", 1)
    out["T07"] = (held("2026-04-01", page(ev12, 2)) and held("2.3", method) and held("2026-03-30", method)
                  and not case.where(lambda t: held("2.4", t) and "approv" in t.lower() and t is not page(ev12, 2)))
    # D01: the board heard an estimate on 2026-02-12, before the baseline of 2026-02-27 counted 214.
    minutes = page("E-PLAN-1 Board minutes 2026-02-12.pdf", 2)
    out["D01"] = (held("estimated", minutes) and held("214", page("EV-08 Orphaned privileged accounts clean-up report.pdf", 2))
                  and len(orphans) == 214)
    # D03: 621 is the March and April leaving-month totals of the MI.
    monthly = page("EV-05 Leaver removal MI as at 2026-06-30.xlsx", 3)
    out["D03"] = held("237", monthly) and held("384", monthly) and 237 + 384 == 621 and held(
        "leaving dates up to the end of the test period", page("EV-06 Leaver removal sample test April 2026.pdf", 1))
    # T05: M3's committed date is 2026-05-31 and M4's 2026-06-30, on the same page.
    out["T05"] = all(held(v, page("E-PLAN-1 Board minutes 2026-02-12.pdf", 2)) for v in ("2026-05-31", "2026-06-30"))
    return out


def tar_matches(folder, tar_path):
    files = {p.relative_to(folder.parent).as_posix(): p.read_bytes() for p in folder.rglob("*") if p.is_file()}
    seen = {}
    with tarfile.open(str(tar_path)) as tf:
        for m in tf.getmembers():
            if m.isfile():
                seen[m.name] = tf.extractfile(m).read()
    return seen == files


def main(argv=None):
    ap = argparse.ArgumentParser(description="Confirm each trap and decoy is present in the generated case.")
    ap.add_argument("--repo", required=True, help="the kit, the folder that holds finding/")
    ap.add_argument("--case", default=str(SEALED / "case"))
    args = ap.parse_args(argv)
    documents = load("regrem_documents", Path(args.repo).resolve() / "finding" / "documents.py")
    score = load("regrem_score", RUN / "tools" / "score.py")
    case = Case(Path(args.case).resolve(), documents)
    held = make_holder(score)
    entries = json.loads((SEALED / "key" / "traps.json").read_text(encoding="utf-8"))["traps"]
    extra = extra_checks(case, held)
    failed = 0
    for e in entries:
        text = case.page(e["file"], e["page"])
        problems = []
        if text is None:
            problems.append("the file or its page is missing")
        elif e["decoy"]:
            if not held(e["planted_value"] or e["key_phrase"], text):
                problems.append("the value or key phrase is not on its page")
            if not extra.get(e["id"], False):
                problems.append("the case does not show why the value is right")
        elif e.get("check_sees"):
            if not held(e["true_value"] or CHECK_TRUE.get(e["id"]), text):
                problems.append("the true value is not on the trap's page")
            if held(e["planted_value"], text):
                problems.append("the planted value is on the trap's page")
            lure = [w for w in case.where(lambda t: held(e["planted_value"], t)) if w != (e["file"], e["page"])]
            if not lure:
                problems.append("the planted value is on no other page")
        else:
            if not held(e["planted_value"] or e["key_phrase"], text):
                problems.append("the planted value or key phrase is not on the trap's page")
            if e["true_value"] is not None:
                written = case.where(lambda t: held(e["true_value"], t))
                if not written and not extra.get(e["id"], False):
                    problems.append("the true value is neither written in the case nor shown by its pages")
            if e["id"] in extra and not extra[e["id"]]:
                problems.append("the entry's own check failed")
        failed += bool(problems)
        print("{} {}{}".format(e["id"], "confirmed" if not problems else "NOT CONFIRMED: ", "; ".join(problems)))
    tar_ok = tar_matches(case.folder, SEALED / "gate" / "case.tar")
    print("gate/case.tar {}".format("matches case/ byte for byte" if tar_ok else "DOES NOT MATCH case/"))
    print("{} of {} entries confirmed.".format(len(entries) - failed, len(entries)))
    return 0 if not failed and tar_ok else 1


if __name__ == "__main__":
    sys.exit(main())
