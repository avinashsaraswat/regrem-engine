#!/bin/sh
# Pilot of the plan and covers jobs for agent run 02, published as its second dry run (dry-run-2/). The owner runs it
# in their own Terminal with MODEL_API_KEY set in that shell. Nothing from it is counted.
# The case is the shipped MRA-CMP-07 made fresh with `finding new`, its plan rows empty and the What and For lines of
# its six evidence files blanked. The kit's own copy of that case stays readable to the drafter, as in any job, so the
# pilot tests whether the jobs finish and write within the run 02 settings, not the quality of what they write.
# The plan job runs first, then the covers job on the same folder with no owner step between them.
# Reads: manifest.json (run 02's settings, not yet sealed), prompts/, kit-0.7.1/, dry-run-2/MRA-CMP-07.
# Writes: dry-run-2/ only; spend goes to dry-run-2/spend-ledger.jsonl, apart from the run's ledger.
set -eu
here=$(cd "$(dirname "$0")" && pwd)
cd "$here"
if [ -z "${MODEL_API_KEY:-}" ]; then echo "MODEL_API_KEY is not set in this shell; set it first"; exit 2; fi
if [ ! -d dry-run-2/MRA-CMP-07 ]; then echo "dry-run-2/MRA-CMP-07 is missing"; exit 2; fi
if [ -e dry-run-2/plan ] || [ -e dry-run-2/covers ]; then echo "the pilot has already run; move dry-run-2/plan and covers aside to run again"; exit 2; fi
for job in plan covers; do
  echo "== pilot $job job, drafter seat, started $(date '+%Y-%m-%d %H:%M %Z')"
  python3 -I tools/agent_loop.py --manifest manifest.json --seat drafter --job "$job" \
    --folder dry-run-2/MRA-CMP-07 --repo kit-0.7.1 --prompt "prompts/$job.txt" --out "dry-run-2/$job" \
    --ledger dry-run-2/spend-ledger.jsonl || echo "pilot $job job exit code $?"
done
echo "== pilot finished $(date '+%Y-%m-%d %H:%M %Z'); the assistant session reads dry-run-2/ next"
