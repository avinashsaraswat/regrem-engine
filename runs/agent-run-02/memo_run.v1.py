#!/usr/bin/env python3
"""memo_run: protocol steps 9 to 11 of agent run 02 for one memo run, started by the owner at their own terminal.

Purpose: makes memo run N from the folder frozen at step 8 and runs, in order and each in a fresh context: the memo
  job (drafter); if it finished, the first cross-read on a copy of the frozen folder holding the memo as first
  finished, the second cross-read on a copy holding the checked memo, and the proposed rulings job on the checked
  memo's folder (cross-reader). Before every job it runs the loop with --list-models, which sends the key and no case
  text and spends nothing; if that fails, no job starts. Once a job ends on the spend cap, no further job starts. No
  job is ever run twice: the script refuses when a job's output folder exists. It also writes the owner's reading
  copy for step 12: finding.md, plan.md, evidence/ and the checked memo, with no check page, eval output, findings
  file or proposed rulings in it.
Usage: python3 -I memo_run.py N      from the run02 folder, with MODEL_API_KEY set in that shell; N is 1 to 5, in order
Reads: manifest.json, prompts/, kit-0.7.1/, run-01/frozen/MRA-PAM-05, earlier memo runs' RUN.json.
Writes: run-01/memo-run-N/ (its finding folder, job outputs, copies for the cross-reads, RUN.json), and for the first
  memo run that finishes, run-01/owner-read/; the loop writes the run's ledger, spend-ledger.jsonl.
Standard library only.
"""
import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN = HERE / "run-01"
FROZEN = RUN / "frozen" / "MRA-PAM-05"
LOOP = ["python3", "-I", "tools/agent_loop.py", "--manifest", "manifest.json", "--repo", "kit-0.7.1"]
# A test of this script sets MEMO_RUN_MOCK to a replies file; the loop then makes no network call and keeps its own ledger.
MOCK = ["--mock", os.environ["MEMO_RUN_MOCK"]] if os.environ.get("MEMO_RUN_MOCK") else []
MEMO = "closure/memo.md"


def say(text):
    print("== " + text, flush=True)


def writable(root):
    for dirpath, dirnames, filenames in os.walk(root):
        for name in dirnames + filenames:
            p = Path(dirpath) / name
            p.chmod(p.stat().st_mode | stat.S_IWUSR)
    Path(root).chmod(Path(root).stat().st_mode | stat.S_IWUSR)


def copy_frozen(dest):
    shutil.copytree(FROZEN, dest)
    writable(dest)


def key_check():
    say("checking the key with --list-models (no case text, no spend)")
    done = subprocess.run(["python3", "-I", "tools/agent_loop.py", "--list-models", "--manifest", "manifest.json"] +
                          (["--mock", os.environ["MEMO_RUN_MOCK_MODELS"]] if MOCK else []),
                          cwd=HERE, stdout=subprocess.DEVNULL)
    if done.returncode != 0:
        say("the key check failed, so no job started; fix the key or wait, then run this again")
        sys.exit(2)


def summary(out):
    p = out / "summary.json"
    return json.loads(p.read_text()) if p.is_file() else {}


def allowed_change(out, path):
    p = out / "gate.json"
    if not p.is_file():
        return False
    return any(c.get("path") == path and c.get("verdict") == "allowed" for c in json.loads(p.read_text())["changed"])


def findings_written(out):
    """A cross-read is finished when it ends done and its transcript shows an accepted write of findings.tsv."""
    t = out / "transcript.jsonl"
    if not t.is_file():
        return False
    stopped, wrote = set(), set()
    for line in t.read_text().splitlines():
        e = json.loads(line)
        if e.get("type") == "tool_call" and e.get("name") == "write_file" and \
                str((e.get("args") or {}).get("path", "")).endswith("findings.tsv"):
            wrote.add(e.get("turn"))
        if e.get("type") == "stopped" and e.get("action") == "write":
            stopped.add(e.get("turn"))
    return bool(wrote - stopped) and (out / "findings.tsv").is_file()


def job(seat, name, folder, prompt, out):
    if out.exists():
        say("{} already exists; a job never runs twice".format(out.relative_to(HERE)))
        sys.exit(2)
    key_check()
    say("{} job, {} seat, on {}".format(name, seat, folder.relative_to(HERE)))
    subprocess.run(LOOP + MOCK + ["--seat", seat, "--job", name, "--folder", str(folder.relative_to(HERE)),
                           "--prompt", prompt, "--out", str(out.relative_to(HERE))], cwd=HERE)
    s = summary(out)
    say("{} job ended: {}, {} turns, ${:.4f} (run ${:.4f})".format(name, s.get("status"), s.get("turns"),
                                                                 s.get("usd", 0), s.get("run_usd_after", 0)))
    return s


def capped():
    for p in RUN.glob("**/summary.json"):
        if json.loads(p.read_text()).get("status") == "spend_cap":
            return True
    return False


def owner_copy(folder):
    dest = RUN / "owner-read"
    if dest.exists():
        return
    (dest / "closure").mkdir(parents=True)
    for name in ("finding.md", "plan.md"):
        shutil.copy2(folder / name, dest / name)
    shutil.copytree(folder / "evidence", dest / "evidence")
    shutil.copy2(folder / MEMO, dest / MEMO)
    say("the owner's reading copy is in run-01/owner-read: the checked memo, the letter, the plan and the evidence")


def main(argv):
    if len(argv) != 1 or argv[0] not in "12345" or len(argv[0]) != 1:
        print("usage: python3 -I memo_run.py N   (N is 1 to 5)")
        return 2
    n = int(argv[0])
    if not os.environ.get("MODEL_API_KEY"):
        print("MODEL_API_KEY is not set in this shell; set it first")
        return 2
    if not FROZEN.is_dir():
        print("the folder frozen at step 8 is missing: run-01/frozen/MRA-PAM-05")
        return 2
    if n > 1 and not (RUN / "memo-run-{}".format(n - 1) / "RUN.json").is_file():
        print("memo run {} has not run yet; memo runs go in order".format(n - 1))
        return 2
    if capped():
        print("a job has ended on the spend cap, so no further job starts")
        return 2
    base = RUN / "memo-run-{}".format(n)
    if base.exists():
        print("{} already exists".format(base.relative_to(HERE)))
        return 2
    base.mkdir()
    folder = base / "MRA-PAM-05"
    copy_frozen(folder)
    record = {"memo_run": n}

    s = job("drafter", "memo", folder, "prompts/memo.txt", base / "memo")
    finished = s.get("status") == "done" and allowed_change(base / "memo", MEMO)
    record["memo"] = {"status": s.get("status"), "finished": finished}
    first = base / "memo" / "first" / MEMO
    record["first_finished_has_memo"] = bool(first.is_file() and first.read_bytes() != (FROZEN / MEMO).read_bytes())
    if not finished:
        (base / "RUN.json").write_text(json.dumps(record, indent=1))
        say("memo run {} did not finish; it is published, and the next memo run starts from the frozen folder".format(n))
        return 0

    jobs = []
    if record["first_finished_has_memo"]:
        jobs.append(("cross-read-1", first))
    else:
        record["cross-read-1"] = "not run: the first-finished copy holds no memo the drafter wrote"
    jobs.append(("cross-read-2", folder / MEMO))
    for name, memo in jobs:
        if capped():
            record[name] = "not started: a job ended on the spend cap"
            continue
        copy = base / (name + "-folder") / "MRA-PAM-05"
        copy_frozen(copy)
        shutil.copy2(memo, copy / MEMO)
        out = base / name
        s = job("cross-reader", "cross-read", copy, "prompts/cross-read.txt", out)
        record[name] = {"status": s.get("status"), "finished": s.get("status") == "done" and findings_written(out)}

    if capped():
        record["proposed-rulings"] = "not started: a job ended on the spend cap"
    else:
        s = job("cross-reader", "proposed-rulings", folder, "prompts/proposed-rulings.txt", base / "proposed-rulings")
        record["proposed-rulings"] = {"status": s.get("status"),
                                      "finished": s.get("status") == "done" and
                                      allowed_change(base / "proposed-rulings", "closure/proposed-rulings.md")}
    (base / "RUN.json").write_text(json.dumps(record, indent=1))
    if not (RUN / "owner-read").exists():
        owner_copy(folder)
    say("memo run {} done: {}".format(n, json.dumps(record)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
