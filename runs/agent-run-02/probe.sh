#!/bin/sh
# probe: the go or wait check before memo run 3 of agent run 02, outside the sealed run (DEVIATIONS.md, 2026-11-14 19:05 ET).
# Runs run 01's dry-run memo job again on fresh copies of the kit's shipped case MRA-CMP-07, through the sealed loop
# with run 02's manifest and memo prompt, on its own ledger, dry-run-3/spend-ledger.jsonl. It sends no text of the
# sealed case and touches no folder of the run. Two jobs first, two more if diagnostics/probe_verdict.py says MORE.
# On GO it starts memo run 3 at once, in this shell, with memo_run.py. On WAIT it starts nothing.
# Usage: sh probe.sh      from the run02 folder, with MODEL_API_KEY set in that shell. A later probe gets its own folder.
set -u
here=$(cd "$(dirname "$0")" && pwd)
cd "$here"
if [ -z "${MODEL_API_KEY:-}" ]; then echo "MODEL_API_KEY is not set in this shell; set it first"; exit 2; fi
if [ -e run-01/memo-run-3 ]; then echo "memo run 3 already exists, so there is nothing to probe for"; exit 2; fi
late() { [ "$(date +%H)" -ge 23 ]; }
if late; then echo "It is after 23:00. A job that crosses midnight uses sitting 2, so nothing starts tonight."; exit 2; fi
n=1; while [ -e "dry-run-3/probe-$n" ]; do n=$((n+1)); done
d="dry-run-3/probe-$n"
mkdir -p "$d"
echo "== probe $n, in $d"
job() {
  python3 -I tools/agent_loop.py --list-models --manifest manifest.json > /dev/null || {
    echo "== the key check failed, so no probe job started; fix the key or wait, then run sh probe.sh again"; exit 2; }
  cp -R kit-0.7.1/finding/cases/MRA-CMP-07 "$d/case-${1}" && chmod -R u+w "$d/case-${1}"
  echo "== probe memo job $1 on the shipped case MRA-CMP-07"
  python3 -I tools/agent_loop.py --manifest manifest.json --seat drafter --job memo --folder "$d/case-${1}" \
    --repo kit-0.7.1 --prompt prompts/memo.txt --out "$d/memo-$1" --today 2026-11-16 \
    --ledger dry-run-3/spend-ledger.jsonl > /dev/null || echo "== probe memo job $1 exit code $?"
}
job a
job b
python3 -I diagnostics/probe_verdict.py "$d"; v=$?
if [ "$v" = 3 ]; then
  job c
  job d
  python3 -I diagnostics/probe_verdict.py "$d" --final; v=$?
fi
if [ "$v" != 0 ]; then
  echo "== WAIT: memo run 3 was not started. Tell the assistant session; the next probe is in about an hour, or on the day of sitting 2."
  exit 1
fi
if late; then echo "== GO, but it is now after 23:00, so memo run 3 waits for the day of sitting 2"; exit 1; fi
echo "== GO: starting memo run 3 now"
exec python3 -I memo_run.py 3
