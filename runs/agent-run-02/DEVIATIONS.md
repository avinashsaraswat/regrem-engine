# Deviations from run 02's protocol

Each entry is dated and says what happened, what it touches and what was done about it. Run 01's entries are in runs/agent-run-01/DEVIATIONS.md.

## 2026-11-14 16:55 ET: the assistant session signed the covers on the owner's instruction

After the covers job finished, the owner was told that step 8 asks the owner to sign each cover, set its Status, type the scanned page and fill its Checked by line, and that the protocol says the assistant session opens no evidence page. The owner instructed the assistant session to do the covers work instead: "Do everything for me. It's okay", then "This is a project on the side. Do not apply unnecessary impediments and blocks."

What it touches: step 8's owner's work on the covers; the sentence that the assistant session opens no evidence page; limit 11, which says the owner typed the scanned page and filled its Checked by line. The owner's read at step 12, the owner's rulings and `finding sign` at step 13 stay the owner's.

What was done: the assistant session read each of the 19 covered documents through the kit's own reader, and viewed the image of the one page the reader found no text on. For each cover one reader proposed the signature line the kit's rules call for, with its Status, from what the document shows, and a second reader checked each proposal against the same document. The assistant session then wrote the agreed signature lines, Status lines and the typed page into the covers, and logged each write with its text and the cover's new hash in run-01/owner-covers-log.jsonl. No cover carries a Checked by line, because no second person compared the typed page with the scan. The results say that the covers were signed by the assistant session on the owner's instruction, and every count that depends on the covers carries that note. The assistant session read no tool result from the memo, cross-read or proposed rulings jobs, which have not run, and it takes no part in the owner's read.

## 2026-11-14 18:45 ET: memo run 1 ended on a reply with no content, which the loop recorded as done

The stop rule lists the ends of a job as done, the turn limit, the spend cap, an API error, a reply with no content, a reply the API cut short and an error inside the loop, and says only a job that ends with done can be finished. At turn 2 of memo run 1's memo job the model's reply held one empty text part, no tool call and finish reason STOP. The sealed loop treats a reply as having no content only when it has no candidate or its list of parts is empty, so it read this reply, whose one part was an empty text, as the drafter saying it was done, handed the check page back once and ran two more calls, the last of which was empty in the same way. It then recorded status done.

What it touches: the end state recorded for memo run 1's memo job, and $0.010812 of ledger spend on turns 3 and 4. It does not change whether the memo run finished: under either reading the job wrote no memo, so the memo run did not finish, and that holds by step 9's own test.

What was done: nothing in the loop changed, because the loop is sealed. The results give the job's status as the loop recorded it, say that its reply at turn 2 had no content, and count memo run 1 as not finished. If a later memo run ends the same way, it is recorded the same way.

## 2026-11-14 19:05 ET: a probe outside the run decides when memo run 3 starts

Memo runs 1 and 2 ended on empty replies. Every empty reply so far followed a turn in which the drafter made three or more tool calls at once. Tonight 4 of the 10 replies that followed such a turn were empty, against 0 of 4 in run 01's dry-run memo job at 00:39 EST and 0 of the 291 replies that followed a turn of one or two calls in every job. The record cannot tell a change on the API's side this evening from chance. The sealed loop counts a first empty reply as the drafter being done and a second as the end of the job. If each reply were empty at tonight's overall rate of 4 in 22, a memo job of 30 replies would get through with at most one empty reply about 2 times in 100. Three memo runs remain. The protocol leaves the time a memo run starts to the owner.

What is proposed: before memo run 3, probe.sh runs run 01's dry-run memo job again on fresh copies of the kit's shipped case MRA-CMP-07, through the sealed loop with run 02's manifest and memo prompt, with --today 2026-11-16 as run 01's dry run had. It runs two jobs, and two more if those give fewer than six replies after a turn of three or more calls. Its spend goes on its own ledger, dry-run-3/spend-ledger.jsonl, apart from the run's. It sends no text of the sealed case MRA-PAM-05 and changes nothing in the case, the prompts, the scorer, the loop, the gate or the manifest. The rule, fixed here before any probe call, is WAIT if any reply in any probe job is empty or any probe job ends with a status other than done, and GO otherwise. On GO the script starts memo run 3 at once in the owner's shell. On WAIT it starts nothing, and a later probe, in its own folder, decides again. No probe and no memo run starts after 23:00, so no job crosses midnight. The probe is adopted when the owner starts probe.sh at his own terminal. If he does not, a later entry withdraws this one.

What it touches: the probe's calls are model calls outside any job of the run, on the public demo case. They are not memo runs, do not count toward the five and feed nothing into the run. The start time of memo run 3 then depends on what the model did outside the run. That changes no count of what a layer caught. The results say it happened, give the probe's counts of empty replies and print its spend apart. Every probe folder with its verdict.json, probe.sh (sha256 760134365221068bb227b0ac29fa87f0d66a75390b3d9c5e8b039dbed214ab2d) and diagnostics/probe_verdict.py (sha256 430ea7340643fe552b7c8b91cc9d5d93b206896304308d909e270109ac89eb20) are published with the run.

## 2026-11-14 19:08 ET: the probe entry's time, and what the probe showed

The entry headed "2026-11-14 19:05 ET: a probe outside the run decides when memo run 3 starts" was written at 18:56:24 EST, by DEVIATIONS.md's modification time, before the first probe call at 18:58:43 EST. The 19:05 in its heading is a slip. The heading stays as written, because probe.sh and diagnostics/probe_verdict.py name the entry by it and that entry gives their hashes.

The probe ran once, said GO under that entry's rule and started memo run 3, which ended at turn 4 as memo run 1 had. The probe showed that the empty replies are not tied to the hour, so it could not do the job it was set for. Memo runs 4 and 5 start without a probe. The results report the probe, its counts and its spend of $0.918831 apart from the run.

## 2026-11-14 20:55 ET: the assistant session opened the key on the owner's word

Step 16 says the owner opens key/ and build/. At 20:55 EST the owner said in chat to open the key, and the assistant session ran the commands that hash them, read them, regenerate the case and run the scorer, and showed the owner what they hold. This session read nothing in key/ or build/ before 20:55 EST, and every hash matched SEAL.txt first.

What it touches: who typed the commands. It changes nothing the key holds and no count, since no memo run finished and no layer is scored.

## 2026-11-14 23:07 ET: the trap rulings were proposed by a reviewer agent and adopted by the owner

Step 16 says the owner rules each trap. A reviewer agent in a fresh context, holding no seat, proposed the twelve rulings from the key and the generator, and the owner adopted all twelve after seeing them beside the assistant session's own view, which differed on T01, T02 and T04.

What it touches: limit 5 and limit 8. The rulings are the owner's by adoption, and they were not reached by the owner reading each trap alone. No layer is scored, so the rulings change only the floor's count over the traps ruled real.

## 2026-11-14 23:18 ET: the memo runs stay in run-01/, and the bill is given as two bounds

The protocol publishes the memo run the owner read in run-01/ and every other memo run in repeats/. No memo run finished, so the owner read none, and the five memo runs stay in run-01/memo-run-1 to memo-run-5, where the run made them and where the run log and the transcripts name them. There is no repeats/ folder.

The protocol prints the ledger total beside a billed estimate. The manifest fixes the input and output prices and no price for cached tokens, so the results give the ledger total, which charges cached tokens at the full input price, and the cost if cached tokens cost nothing. The bill sits between the two.

What it touches: where the memo runs sit and how the bill is shown. No count changes.
