# Run log, agent run 01

One entry per step, with the time, what ran and the hashes the protocol asks for. Tree hashes are SHA-256 over each file's path relative to the folder, a zero byte and the file's own SHA-256, in sorted path order.

## 2026-11-14 13:52 EST, before step 6: seal and case checked

Every hash in SEAL.txt for a file the seal pushed matches: the six prompts, procedures/review-memo.md, tools/agent_loop.py, tools/gate_diff.py, tools/score.py, tools/SCHEMA.md and manifest.json. The case archive hashes to 9f0ed36317f1fb70aeb92c4065e77f588c68dcfff845f363d55cdd00adf6e9e6, as SEAL.txt gives it, and its unpacked files match sealed/case/ byte for byte. Nothing in key/, build/ or the scorer gate's files was opened.

## 2026-11-14 13:52 EST, step 6: intake

`finding new run-01/MRA-PAM-05` from kit-0.7.1. The case's finding.md, whose first line starts SYNTHETIC, replaced the template, and the case's 22 evidence files went into evidence/ under the names the case gives them. audit-questions.md stays out of the folder until step 14. The folder as the agents receive it is copied to case/.

Tree hash of run-01/MRA-PAM-05 and of case/, 28 files: 5e10090dae682912bed3d83b55fd74bdb57c4a667f1715178ea2ff81d9a15e81

## 2026-11-14 14:44 to 14:48 EST, step 7: plan job, first attempt

The owner started `sh sitting2.sh plan` in his own Terminal with a fresh key from his personal project, read with read -s. The job ran on kit-0.7.1 on the machine's date, 2026-11-14, and stopped at the manifest's turn limit: 60 turns, 60 tool calls, one call a turn. It wrote nothing; the gate found 0 paths changed. The loop refused one read, a listing of kit/finding, as outside the seat. The model read the board minutes and most evidence files a page per call, though read_file returns a whole document when no page is given, and it read kit pages the plan does not need. Prompt tokens per call grew from 698 at turn 1 to 76,831 at turn 60, with about 97 percent of the late prompts reported as cached; the ledger charges cached tokens at the full input price. The final check page reads "Not ready: plan.md has no milestone rows yet." (page sha256 e64f08bcadc0b19976a6e76abdaefa4514b5b32616b6e32aefcdb9b658183de9). Outputs are in run-01/plan/. The ledger spend for the job is $1.626723, and the run total is $1.63 of $20. How the run proceeds is the owner's decision, recorded next.

## 2026-11-14 15:13 EST: the owner stops run 01

The owner ruled, in a live session: stop run 01 at step 7 and publish it as stopped, pilot the plan and covers jobs on the shipped case under run 02's settings, then seal run 02 on the same unopened case with a turn limit of 200 and a ledger cap of $60. DEVIATIONS.md carries the full entry. Hashes at the stop: run-01/plan/transcript.jsonl b9b2c19a63c3b9c834cf41fb680610d75c7a7e976f319198e2fd8ff1ed4294c9, run-01/plan/check-final.txt e64f08bcadc0b19976a6e76abdaefa4514b5b32616b6e32aefcdb9b658183de9, spend-ledger.jsonl 4e92160f9e4a57c9061f0d0248f6af58414bc11dd22013484d6d173ce8bd8d96 (60 lines).
