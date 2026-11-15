#!/usr/bin/env python3
"""probe_verdict: reads the probe jobs in one dry-run-3/probe-N folder and prints GO, MORE or WAIT under the rule in
DEVIATIONS.md (2026-11-14 19:05 ET), with counts only and no text from any reply.

A reply is empty when it holds no tool call and no text, as the replies that ended memo runs 1 and 2 did. A trigger
reply is one that follows a turn in which the drafter made three or more tool calls, the only place an empty reply
has come.
  WAIT  any reply in any probe job was empty, or a probe job ended with a status other than done.
  MORE  no reply was empty but fewer than 6 trigger replies came, so the trigger was not tested enough; with --final
        this becomes GO, since the probe then saw no empty reply in four jobs.
  GO    no reply was empty, every probe job ended done and at least 6 trigger replies came.
Usage: python3 -I diagnostics/probe_verdict.py dry-run-3/probe-N [--final]     exit 0 GO, 1 WAIT, 3 MORE
Standard library only.
"""
import json
import sys
from pathlib import Path


def tally(out):
    prev, replies, empty, trigger, trigger_empty = None, 0, 0, 0, 0
    for line in (out / "transcript.jsonl").read_text(encoding="utf-8").splitlines():
        e = json.loads(line)
        if e.get("type") != "response":
            continue
        cands = e["body"].get("candidates") or []
        parts = ((cands[0].get("content") or {}).get("parts") or []) if cands else []
        calls = sum(1 for p in parts if isinstance(p, dict) and "functionCall" in p)
        blank = calls == 0 and not "".join(p.get("text", "") for p in parts if isinstance(p, dict)).strip()
        replies += 1
        empty += blank
        if prev is not None and prev >= 3:
            trigger += 1
            trigger_empty += blank
        prev = calls
    s = json.loads((out / "summary.json").read_text()) if (out / "summary.json").is_file() else {}
    gate = json.loads((out / "gate.json").read_text()) if (out / "gate.json").is_file() else {"changed": []}
    wrote = any(c.get("path") == "closure/memo.md" and c.get("verdict") == "allowed" for c in gate["changed"])
    return {"job": out.name, "status": s.get("status") or "no summary", "turns": s.get("turns"), "replies": replies,
            "empty": empty, "trigger_replies": trigger, "trigger_empty": trigger_empty, "wrote_memo": wrote,
            "usd": s.get("usd", 0)}


def main(argv):
    final = "--final" in argv
    argv = [a for a in argv if a != "--final"]
    if len(argv) != 1:
        print(__doc__)
        return 2
    probe = Path(argv[0])
    rows = [tally(p) for p in sorted(probe.glob("memo-*")) if (p / "transcript.jsonl").is_file()]
    if not rows:
        print("no probe job ran")
        return 1
    for r in rows:
        print("{job}: {status}, {turns} turns, {replies} replies, {empty} empty; {trigger_replies} after three or more "
              "calls, {trigger_empty} of them empty; memo written: {wrote_memo}; ${usd:.4f}".format(**r))
    empty = sum(r["empty"] for r in rows)
    trigger = sum(r["trigger_replies"] for r in rows)
    if empty or any(r["status"] != "done" for r in rows):
        verdict, code = "WAIT", 1
    elif trigger < 6 and not final:
        verdict, code = "MORE", 3
    else:
        verdict, code = "GO", 0
    record = {"verdict": verdict, "final": final, "empty": empty, "trigger_replies": trigger, "jobs": rows}
    (probe / "verdict.json").write_text(json.dumps(record, indent=1) + "\n", encoding="utf-8")
    print("{}: {} empty replies in {} jobs; {} replies after three or more calls".format(verdict, empty, len(rows), trigger))
    return code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
