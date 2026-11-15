#!/bin/sh
# memo_runs_4_5: memo runs 4 and 5 of agent run 02, in order, with memo_run.py. Memo run 5 starts only if memo run 4
# did not finish, because the first memo run that finishes goes through steps 10 to 14 before any repeat. If neither
# finishes, five memo runs have started and none finished, and the run stops there (step 15 and the stop rule).
# No memo run starts after 23:00, so no job crosses midnight.
# Usage: sh memo_runs_4_5.sh      from the run02 folder, with MODEL_API_KEY set in that shell
set -u
here=$(cd "$(dirname "$0")" && pwd)
cd "$here"
if [ -z "${MODEL_API_KEY:-}" ]; then echo "MODEL_API_KEY is not set in this shell; set it first"; exit 2; fi
finished() { python3 -I -c "import json,sys; sys.exit(0 if json.load(open('run-01/memo-run-$1/RUN.json'))['memo']['finished'] else 1)"; }
for n in 4 5; do
  if [ -f "run-01/memo-run-$n/RUN.json" ]; then
    if finished "$n"; then echo "== memo run $n has finished; the owner's read is next. Tell the assistant session."; exit 0; fi
    continue
  fi
  if [ "$(date +%H)" -ge 23 ]; then echo "== It is after 23:00, so memo run $n waits. Tell the assistant session."; exit 2; fi
  python3 -I memo_run.py "$n" || { echo "== memo run $n stopped before it ended. Tell the assistant session."; exit 2; }
  if finished "$n"; then echo "== memo run $n finished; the owner's read is next. Tell the assistant session."; exit 0; fi
done
echo "== Five memo runs have started and none finished, so the run stops here. Tell the assistant session."
