#!/usr/bin/env python3
"""gate_diff: what each job of the agent run may write, and a gate that checks what a job changed.

Purpose: holds the write rules for each job and seat in one place, and compares two snapshots of a finding folder
  file by file. Every changed path is checked against the job's allowlist. A change outside it can be reverted from
  a copy kept before the job. agent_loop.py imports these same rules for its write_file tool, so a refused write and
  a gate row rest on one test.
The jobs, from the protocol's job table:
  plan              drafter       plan.md, below its header row: the rows of the table and the lines below it
  covers            drafter       the What and For lines of each cover in evidence/ (the files ending in .md)
  memo              drafter       closure/memo.md
  cross-read        cross-reader  out/findings.tsv, the findings file in the job's output folder, outside the folder
  proposed-rulings  cross-reader  closure/proposed-rulings.md
  audit-answers     drafter       audit-answers.md, at the top of the finding folder
  The kit writes .finding-state.json and closure/finding-log.jsonl when the loop runs its commands. The owner
  writes everything else: signatures, Status lines, typed pages, closure/rulings.md and closure/record.md.
  In every file an agent writes, a new line that starts Signed by, Produced by, Approved by, Never signed,
  Checked by, Status, Revised, Signed on or Fingerprint, followed by a colon, is refused, because a person types it.
Usage:
  python3 -I tools/gate_diff.py snapshot <folder> --out <before.json> [--keep <copy folder>]
  python3 -I tools/gate_diff.py diff <before.json> <folder or after.json> --seat <seat> --job <job>
      [--out <gate.json>] [--revert <copy folder>]
  snapshot writes each file's SHA-256 and size, and the text of each small Markdown or text file, so the content
  rules can be applied later. --keep also copies the folder, for --revert. diff prints one summary line and writes
  the report as JSON to --out, or to standard output without it. --revert puts back, from the copy, every path whose
  change is outside the allowlist, and marks those rows reverted.
Reads: the folder, or two snapshots. Writes: only the --out file, the --keep copy and, with --revert, the reverted
  paths in the folder. Paths are printed relative to the run folder, the folder above tools/, or as a bare name.
Network: none. Standard library only, Python 3.9 and later.
Exit codes: 0 when every change is allowed or written by the kit, 1 when any change is outside the allowlist, 2 on
  usage or an unreadable input.
"""
import argparse
import collections
import hashlib
import json
import os
import re
import shutil
import sys
from pathlib import Path

RUN_DIR = Path(__file__).resolve().parent.parent

FINDINGS = "out/findings.tsv"
COVERS = "evidence/*.md"
# job: (the one seat that runs it, the paths it may write). A pattern ending in /*.md stands for the Markdown files
# directly inside that folder. Paths that start out/ sit in the job's output folder, outside the finding folder.
JOBS = {
    "plan": ("drafter", ("plan.md",)),
    "covers": ("drafter", (COVERS,)),
    "memo": ("drafter", ("closure/memo.md",)),
    "cross-read": ("cross-reader", (FINDINGS,)),
    "proposed-rulings": ("cross-reader", ("closure/proposed-rulings.md",)),
    "audit-answers": ("drafter", ("audit-answers.md",)),
}
SEATS = ("drafter", "cross-reader")
KIT_WRITES = (".finding-state.json", "closure/finding-log.jsonl")
OWNER_FILES = ("closure/rulings.md", "closure/record.md")
PERSON_LABELS = ("Internal audit tested fingerprint", "Signed by", "Produced by", "Approved by", "Never signed",
                 "Checked by", "Status", "Revised", "Signed on", "Fingerprint")
PERSON_LINE = re.compile(r"^(" + "|".join(re.escape(label) for label in PERSON_LABELS)
                         + r")\s*(?:\(role\))?\s*[*_]*\s*:", re.IGNORECASE)
# The header words a cover's first lines start with, as finding/finding.py reads them.
HEADER_KEYS = ("What:", "For:", "Status:", "Signed by:", "Produced by:", "Approved by:", "Never signed:", "Revised:",
               "Covers:", "Source:", "Checked by:")
PLAN_COLUMNS = ("Milestone", "Owner role", "Committed date", "What is true when done", "Evidence",
                "Internal audit will test")
TEXT_SUFFIXES = (".md", ".txt", ".tsv", ".json", ".jsonl")
TEXT_KEPT = 2 * 1024 * 1024  # bytes of text a snapshot keeps for one file


class Refusal(Exception):
    """A write or read the rules do not allow. rule names the test, kind the protocol's count, reason the words."""

    def __init__(self, rule, kind, reason):
        Exception.__init__(self, reason)
        self.rule, self.kind, self.reason = rule, kind, reason


# ---------------------------------------------------------------- paths


def normalize(path):
    """The path as the rules name it: forward slashes, no leading ./, no empty parts. "" names the folder itself.
    Raises Refusal for a path that is absolute or climbs out with .."""
    if not isinstance(path, str):
        raise Refusal("bad-path", "outside allowlist", "a path is text")
    text = path.strip()
    if "\0" in text or "\\" in text:
        raise Refusal("bad-path", "outside allowlist", "a path uses forward slashes and no control characters")
    if text.startswith(("/", "~")) or re.match(r"^[A-Za-z]:", text):
        raise Refusal("outside", "outside allowlist", "paths are relative to the finding folder; this one is not")
    parts = [part for part in text.split("/") if part not in ("", ".")]
    if ".." in parts:
        raise Refusal("outside", "outside allowlist", "the path climbs out of the finding folder")
    return "/".join(parts)


def matches(rel, pattern):
    if pattern.endswith("/*.md"):
        head = pattern[:-len("*.md")]
        rest = rel[len(head):]
        return rel.startswith(head) and "/" not in rest and rest.endswith(".md") and len(rest) > len(".md")
    return rel == pattern


def allowed(job):
    return JOBS[job][1]


def describe(patterns):
    words = {COVERS: "the What and For lines of the covers in evidence/"}
    names = [words.get(p, p) for p in patterns]
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


# ---------------------------------------------------------------- content rules


def _lines(text):
    lines = (text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
    while lines and not lines[-1].strip():
        lines.pop()
    return lines


def _clean(line):
    return line.strip().lstrip("#>*-+|_` \t").strip()


def person_label(line):
    found = PERSON_LINE.match(_clean(line))
    return found.group(1) if found else None


def _cover_parts(lines):
    """(every line but the What and For lines of the header, the header words of those lines, in order)."""
    probe = list(lines)
    if probe and probe[0].startswith("SYNTHETIC"):
        probe[0] = ""
    i = 0
    while i < len(probe) and not probe[i].strip():
        i += 1
    first = i
    while i < len(probe) and probe[i].strip().startswith(HEADER_KEYS):
        i += 1
    kept, words = [], []
    for k, line in enumerate(lines):
        stripped = line.strip()
        if first <= k < i and stripped.startswith(("What:", "For:")):
            words.append(stripped.split(":", 1)[0])
            continue
        kept.append(line)
    return kept, words


def cover_refusal(old, new):
    kept_old, _ = _cover_parts(_lines(old))
    kept_new, words = _cover_parts(_lines(new))
    if words.count("What") != 1 or words.count("For") != 1:
        return Refusal("cover-lines", "outside allowlist",
                       "a cover keeps one What line and one For line among its header lines at the top")
    if kept_old != kept_new:
        a, b = collections.Counter(kept_old), collections.Counter(kept_new)
        changed = list((a - b).elements()) + list((b - a).elements())
        moved = not changed  # the same lines in another order
        person = [label for label in (person_label(line) for line in changed) if label]
        if person:
            return Refusal("cover-lines", "person line", "a {} line on a cover is a person's to type; only the What "
                           "and For lines change".format(person[0]))
        return Refusal("cover-lines", "outside allowlist", "only the What and For lines of a cover change; every "
                       "other line stays as it is{}".format(", in its place" if moved else ""))
    return None


def _cells(line):
    s = line.strip()
    if not s.startswith("|"):
        return None
    return [cell.strip() for cell in s.strip("|").split("|")]


def _plan_header_end(lines):
    for i, line in enumerate(lines):
        cells = _cells(line)
        if cells is not None and set(PLAN_COLUMNS) <= set(cells):
            end = i + 1
            if end < len(lines):
                rule = _cells(lines[end])
                if rule and all(re.match(r"^:?-+:?$", c) for c in rule if c) and any(rule):
                    end += 1
            return end
    return None


def plan_refusal(old, new):
    old_lines, new_lines = _lines(old), _lines(new)
    end = _plan_header_end(old_lines)
    if end is not None and new_lines[:end] != old_lines[:end]:
        return Refusal("plan-header", "outside allowlist",
                       "the lines of plan.md down to the table's header row stay as they are")
    return None


def person_refusal(old, new):
    seen = set(_clean(line) for line in _lines(old))
    for line in _lines(new):
        if _clean(line) in seen:
            continue
        label = person_label(line)
        if label:
            return Refusal("person-line", "person line", "a {} line is a person's to type, never an agent's".format(label))
    return None


def write_refusal(seat, job, rel, old, new):
    """None when the seat may write new over old (None for a new file) at rel in this job, or the Refusal."""
    job_seat, patterns = JOBS[job]
    if seat != job_seat:
        return Refusal("seat", "outside allowlist", "the {} job runs in the {} seat".format(job, job_seat))
    if not any(matches(rel, p) for p in patterns):
        if rel in OWNER_FILES:
            return Refusal("owner-file", "owner file", "{} is the owner's to write".format(rel))
        if rel in KIT_WRITES:
            return Refusal("kit-file", "outside allowlist", "the kit writes {} when its commands run".format(rel))
        head = rel.split("/", 1)[0]
        if head in ("kit", "run"):
            return Refusal("read-only", "outside allowlist", "the kit's pages and the run's pages are read only")
        if head == "out":
            return Refusal("job", "outside allowlist", "the output folder takes only the file this job names")
        return Refusal("job", "outside allowlist", "the {} job may write only {}".format(job, describe(patterns)))
    if matches(rel, COVERS):
        if old is None:
            return Refusal("cover-new", "outside allowlist", "the covers job fills covers that exist; finding covers "
                           "makes them")
        return cover_refusal(old, new)
    if rel == "plan.md" and old is not None:
        refusal = plan_refusal(old, new)
        if refusal:
            return refusal
    return person_refusal(old, new)


# ---------------------------------------------------------------- snapshots and the gate


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def snapshot(folder):
    """{"version": 1, "files": {relative path: {"kind", "sha256", "size", "text"?}}}, with no link followed."""
    folder = Path(folder)
    files = {}
    for root, dirs, names in os.walk(str(folder), followlinks=False):
        dirs.sort()
        here = Path(root)
        for name in sorted(names) + [d for d in dirs if (here / d).is_symlink()]:
            path = here / name
            rel = path.relative_to(folder).as_posix()
            if path.is_symlink():
                files[rel] = {"kind": "link", "sha256": sha256_bytes(os.readlink(str(path)).encode("utf-8", "replace"))}
                continue
            data = path.read_bytes()
            entry = {"kind": "file", "sha256": sha256_bytes(data), "size": len(data)}
            if path.suffix.lower() in TEXT_SUFFIXES and len(data) <= TEXT_KEPT:
                try:
                    entry["text"] = data.decode("utf-8")
                except UnicodeDecodeError:
                    pass
            files[rel] = entry
    return {"version": 1, "files": files}


def _restore(folder, copy, rel, change):
    if ".." in rel.split("/") or rel.startswith("/"):
        return False
    target, source = Path(folder) / rel, Path(copy) / rel
    if target.is_symlink() or target.is_file():
        target.unlink()
    elif target.is_dir():
        shutil.rmtree(str(target))
    if change == "added":
        return True
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.is_symlink():
        os.symlink(os.readlink(str(source)), str(target))
    else:
        shutil.copy2(str(source), str(target))
    return True


def diff(before, after, seat, job, folder=None, revert_from=None):
    """The gate's report on what changed between two snapshots, judged against the job's allowlist."""
    if job not in JOBS or seat not in SEATS:
        raise ValueError("unknown seat or job")
    old, new = before["files"], after["files"]
    rows = []
    for rel in sorted(set(old) | set(new)):
        a, b = old.get(rel), new.get(rel)
        if a and b and a.get("kind") == b.get("kind") and a.get("sha256") == b.get("sha256"):
            continue
        change = "added" if a is None else "deleted" if b is None else "modified"
        row = {"path": rel, "change": change}
        if rel in KIT_WRITES and change != "deleted":
            row.update(verdict="kit", rule=None, kind=None, reason="written by the kit when the loop ran its commands")
        else:
            if change == "deleted":
                refusal = Refusal("deleted", "outside allowlist", "no seat deletes a file")
            elif b.get("kind") != "file":
                refusal = Refusal("link", "outside allowlist", "no seat makes a link")
            elif "text" not in b or (a is not None and "text" not in a):
                refusal = Refusal("binary", "outside allowlist", "no seat writes a file that is not UTF-8 text")
            else:
                refusal = write_refusal(seat, job, rel, a["text"] if a else None, b["text"])
            if refusal is None:
                row.update(verdict="allowed", rule=None, kind=None, reason=None)
            else:
                row.update(verdict="outside", rule=refusal.rule, kind=refusal.kind, reason=refusal.reason)
                if revert_from is not None and folder is not None:
                    row["reverted"] = _restore(folder, revert_from, rel, change)
        rows.append(row)
    counts = collections.Counter(row["verdict"] for row in rows)
    outside = counts.get("outside", 0)
    reverted = sum(1 for row in rows if row.get("reverted"))
    summary = "gate, {} job in the {} seat: {} changed, {} allowed, {} written by the kit, {} outside the job's " \
              "allowlist{}.".format(job, seat, _plural(len(rows), "path"), counts.get("allowed", 0),
                                    counts.get("kit", 0), outside,
                                    ", {} reverted".format(reverted) if reverted else "")
    return {"version": 1, "seat": seat, "job": job, "changed": rows,
            "counts": {"changed": len(rows), "allowed": counts.get("allowed", 0), "kit": counts.get("kit", 0),
                       "outside": outside, "reverted": reverted},
            "ok": outside == 0, "summary": summary}


def _plural(n, word):
    return "{} {}{}".format(n, word, "" if n == 1 else "s")


def show(path):
    """A path for printing: relative to the run folder, or its bare name."""
    path = Path(path).resolve()
    try:
        return path.relative_to(RUN_DIR).as_posix() or "."
    except ValueError:
        return path.name


def _write_json(path, data):
    with open(str(path), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(data, fh, indent=1, ensure_ascii=False)
        fh.write("\n")


def main(argv=None):
    parser = argparse.ArgumentParser(prog="gate_diff.py", description="Snapshot a finding folder, or check what a "
                                     "job changed against its allowlist.")
    sub = parser.add_subparsers(dest="command")
    snap = sub.add_parser("snapshot")
    snap.add_argument("folder")
    snap.add_argument("--out", required=True)
    snap.add_argument("--keep")
    dif = sub.add_parser("diff")
    dif.add_argument("before")
    dif.add_argument("after")
    dif.add_argument("--seat", required=True, choices=SEATS)
    dif.add_argument("--job", required=True, choices=sorted(JOBS))
    dif.add_argument("--out")
    dif.add_argument("--revert")
    args = parser.parse_args(argv)
    try:
        if args.command == "snapshot":
            folder = Path(args.folder)
            if not folder.is_dir():
                raise ValueError("no folder at " + show(folder))
            if args.keep:
                keep = Path(args.keep)
                if keep.exists():
                    raise ValueError(show(keep) + " exists already; name a new folder for the copy")
                shutil.copytree(str(folder), str(keep), symlinks=True)
            _write_json(args.out, snapshot(folder))
            print("snapshot of {} written to {}.".format(show(folder), show(args.out)))
            return 0
        if args.command == "diff":
            with open(args.before, encoding="utf-8") as fh:
                before = json.load(fh)
            after_path = Path(args.after)
            folder = after_path if after_path.is_dir() else None
            if folder is None:
                if args.revert:
                    raise ValueError("--revert needs the folder itself as the second argument")
                with open(args.after, encoding="utf-8") as fh:
                    after = json.load(fh)
            else:
                after = snapshot(folder)
            if args.seat != JOBS[args.job][0]:
                raise ValueError("the {} job runs in the {} seat".format(args.job, JOBS[args.job][0]))
            report = diff(before, after, args.seat, args.job, folder=folder,
                          revert_from=Path(args.revert) if args.revert else None)
            if args.out:
                _write_json(args.out, report)
            else:
                json.dump(report, sys.stdout, indent=1, ensure_ascii=False)
                sys.stdout.write("\n")
            print(report["summary"])
            return 0 if report["ok"] else 1
    except (OSError, ValueError, KeyError) as err:
        message = err.strerror if isinstance(err, OSError) and err.strerror else str(err)
        print("gate_diff: " + message, file=sys.stderr)
        return 2
    parser.print_usage(sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
