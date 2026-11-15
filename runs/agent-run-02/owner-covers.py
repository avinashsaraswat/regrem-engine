#!/usr/bin/env python3
"""owner-covers: the owner's step 8 in agent run 02, one cover at a time.

Purpose: walks the owner through each cover in run-01/MRA-PAM-05/evidence/, opens its document in Preview, and writes
  only what the owner types: the signature line (Signed by, Produced by, Approved by or Never signed), the Status
  line, a Checked by line, and a typed page under its "## Page N" heading. It never writes a What or For line and
  never chooses a value. Every write is shown first, waits for y, and is logged with the owner's words and the
  cover's new hash in run-01/owner-covers-log.jsonl.
Usage: python3 -I owner-covers.py            from the run02 folder; covers already at Status FINAL are skipped
       python3 -I owner-covers.py --all      shows every cover, FINAL ones too
Reads: the covers in run-01/MRA-PAM-05/evidence/, run-01/covers/covers-start.txt for the lines naming each file.
Writes: those covers, only as above; run-01/owner-covers-log.jsonl.
Standard library only.
"""
import datetime
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EVIDENCE = HERE / "run-01" / "MRA-PAM-05" / "evidence"
SCREEN = HERE / "run-01" / "covers" / "covers-start.txt"
LOG = HERE / "run-01" / "owner-covers-log.jsonl"
SIG_KEYS = ("Signed by:", "Produced by:", "Approved by:", "Never signed:")
DATED = re.compile(r"^.+, \d{4}-\d\d-\d\d$")
EVID = re.compile(r"^(EV-\d+|E-PLAN-\d+)$")


def covers():
    """Each cover that sits beside its document, in name order."""
    out = []
    for p in sorted(EVIDENCE.glob("*.md")):
        if (EVIDENCE / p.name[:-3]).is_file():
            out.append(p)
    return out


def split(text):
    lines = text.split("\n")
    end = next((i for i, line in enumerate(lines) if not line.strip()), len(lines))
    return lines[:end], lines[end:]


def field(head, key):
    return next((line for line in head if line.startswith(key)), None)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def log(path, action, typed):
    entry = {"t": datetime.datetime.now().astimezone().isoformat(timespec="seconds"), "file": path.name,
             "action": action, "typed": typed, "sha256_after": sha(path)}
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def confirm(path, show):
    print("\n  This will write in {}:\n{}".format(path.name, "\n".join("    " + s for s in show.split("\n"))))
    return input("  Write it? y or n: ").strip().lower() == "y"


def ask(prompt, pattern=None, hint=""):
    while True:
        value = input(prompt).strip()
        if not value:
            return None
        if pattern is None or pattern.match(value):
            return value
        print("  That does not fit the form{}. Try again, or press Enter to go back.".format(hint))


def set_header(path, key, value, replace_keys):
    head, rest = split(path.read_text(encoding="utf-8"))
    line = key + " " + value
    idx = next((i for i, s in enumerate(head) if s.startswith(replace_keys)), None)
    if idx is None:
        status = next((i for i, s in enumerate(head) if s.startswith("Status:")), len(head))
        head.insert(status, line)
    else:
        head[idx] = line
    path.write_text("\n".join(head + rest), encoding="utf-8")
    return line


def type_page(path):
    number = ask("  Page number: ", re.compile(r"^[1-9]\d*$"), ", a whole number")
    if number is None:
        return
    text = path.read_text(encoding="utf-8")
    if re.search(r"(?m)^## Page {}\s*$".format(number), text):
        print("  Page {} is already typed in this cover; edit the file by hand to change it.".format(number))
        return
    print("  Type or paste the page's text. End with a line holding only a full stop.")
    body = []
    while True:
        line = input()
        if line.strip() == ".":
            break
        body.append(line)
    block = "\n## Page {}\n\n{}\n".format(number, "\n".join(body).rstrip())
    if confirm(path, block.strip("\n")):
        path.write_text(text.rstrip("\n") + "\n" + block, encoding="utf-8")
        log(path, "typed page " + number, "\n".join(body))
        print("  Written.")


def screen_lines(name):
    if not SCREEN.is_file():
        return []
    return [s.strip() for s in SCREEN.read_text(encoding="utf-8").split("\n") if name[:-3] in s]


def show(path):
    head, _ = split(path.read_text(encoding="utf-8"))
    print("\n" + "=" * 100)
    print(path.name)
    for key in ("What:", "For:") + SIG_KEYS + ("Status:", "Checked by:", "Revised:", "Source:"):
        line = field(head, key)
        if line is not None:
            print("  " + line)
    for s in screen_lines(path.name):
        print("  covers screen: " + s)


MENU = ("  o open the document   s Signed by   p Produced by   a Approved by   n Never signed   f Status\n"
        "  t type a page   c Checked by   k next cover   q quit\n  Choice: ")


def work(path):
    while True:
        show(path)
        choice = input(MENU).strip().lower()
        if choice == "o":
            subprocess.run(["open", "-a", "Preview", str(EVIDENCE / path.name[:-3])], check=False)
        elif choice in ("s", "p", "a", "n"):
            key, pattern, hint = {
                "s": ("Signed by:", DATED, ", role, YYYY-MM-DD"),
                "p": ("Produced by:", DATED, ", system or report, YYYY-MM-DD"),
                "a": ("Approved by:", EVID, ", an evidence id such as EV-29"),
                "n": ("Never signed:", re.compile(r"^.{3,}$"), ", a few words of what it is"),
            }[choice]
            value = ask("  {} ".format(key), pattern, hint)
            if value and confirm(path, key + " " + value + "\n(in place of the cover's signature line)"):
                line = set_header(path, key, value, SIG_KEYS)
                log(path, key[:-1], value)
                print("  Written: " + line)
        elif choice == "f":
            value = ask("  Status (FINAL or DRAFT): ", re.compile(r"^(FINAL|DRAFT)$"), ", FINAL or DRAFT")
            if value and confirm(path, "Status: " + value):
                set_header(path, "Status:", value, ("Status:",))
                log(path, "Status", value)
                print("  Written: Status: " + value)
        elif choice == "c":
            value = ask("  Checked by: ", DATED, ", role, YYYY-MM-DD")
            if value and confirm(path, "Checked by: " + value + "\n(with the header lines at the top)"):
                set_header(path, "Checked by:", value, ("Checked by:",))
                log(path, "Checked by", value)
                print("  Written: Checked by: " + value)
        elif choice == "t":
            type_page(path)
        elif choice == "k":
            return True
        elif choice == "q":
            return False


def main(argv):
    every = "--all" in argv
    todo = [p for p in covers() if every or (field(split(p.read_text(encoding="utf-8"))[0], "Status:") or "")
            .split(":", 1)[-1].strip() != "FINAL"]
    print("{} covers to work through. Your words are written only after you answer y.".format(len(todo)))
    for p in todo:
        if not work(p):
            break
    print("\nStopped. Run it again to carry on; covers at Status FINAL are skipped.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
