#!/bin/sh
# Agent run 02, protocol steps 7 and 8. The owner runs it in their own Terminal, with MODEL_API_KEY set in that shell
# (read -s, never typed on a command line).
#   sh sitting.sh plan     the drafter drafts plan.md; the loop runs finding check and hands its page back once.
#   sh sitting.sh covers   the loop runs finding covers, the drafter drafts each cover's What and For lines, and the
#                          loop hands one check page back. Runs only after the plan job finished and the owner has
#                          corrected the plan rows.
# Before each job the script runs the loop with --list-models, which sends the key and no case text and spends
# nothing. If that check fails, no job starts, as the protocol says.
# Both jobs run on the kit copy frozen at release 0.7.1 (kit-0.7.1/), on the machine's date, and charge run 02's
# ledger, spend-ledger.jsonl beside the manifest, under the manifest's cap. The owner never stops a job by hand.
# Reads: manifest.json, prompts/, kit-0.7.1/, the finding folder run-01/MRA-PAM-05, run-01/plan/ for the covers guard.
# Writes: the finding folder, only where the job's allowlist lets it; run-01/<job>/; spend-ledger.jsonl.
set -eu
here=$(cd "$(dirname "$0")" && pwd)
cd "$here"
job=${1:-}
case "$job" in plan|covers) ;; *) echo "usage: sh sitting.sh plan   or   sh sitting.sh covers"; exit 2 ;; esac
if [ -z "${MODEL_API_KEY:-}" ]; then echo "MODEL_API_KEY is not set in this shell; set it first"; exit 2; fi
if [ ! -d run-01/MRA-PAM-05 ]; then echo "run-01/MRA-PAM-05 is missing; intake comes first"; exit 2; fi
if [ -e "run-01/$job" ]; then echo "run-01/$job already exists; this job has already run"; exit 2; fi
if [ "$job" = plan ] && [ -s spend-ledger.jsonl ]; then echo "spend-ledger.jsonl is not empty; run 02's ledger starts empty"; exit 2; fi
if [ "$job" = covers ]; then
  python3 -I -c 'import json,sys
s=json.load(open("run-01/plan/summary.json")); g=json.load(open("run-01/plan/gate.json"))
sys.exit(0 if s.get("status")=="done" and any(r["path"]=="plan.md" and r["verdict"]=="allowed" for r in g["changed"]) else 1)' \
    || { echo "the plan job did not finish, so the run ended at step 7; covers does not run"; exit 2; }
  if [ ! -e run-01/owner-plan-corrected.txt ]; then
    echo "the owner's plan corrections are not recorded yet (run-01/owner-plan-corrected.txt); covers waits for them"
    exit 2
  fi
fi
echo "== checking the key with --list-models (no case text, no spend)"
python3 -I tools/agent_loop.py --list-models --manifest manifest.json > /dev/null \
  || { echo "the key check failed, so no job started; fix the key or wait, then run this again"; exit 2; }
echo "== $job job, drafter seat, started $(date '+%Y-%m-%d %H:%M %Z')"
python3 -I tools/agent_loop.py --manifest manifest.json --seat drafter --job "$job" \
  --folder run-01/MRA-PAM-05 --repo kit-0.7.1 --prompt "prompts/$job.txt" --out "run-01/$job" \
  || echo "$job job exit code $?"
echo "== $job job ended $(date '+%Y-%m-%d %H:%M %Z'); the assistant session reads run-01/$job next"
