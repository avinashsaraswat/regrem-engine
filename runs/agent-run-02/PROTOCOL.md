# Protocol for agent run 02

This protocol is pushed with SEAL.txt before run 02's intake. It fixes what the run claims, who may write what, the order of steps, how findings are matched and counted, when the run stops and what gets published. The pilot's outcome in step 4 is filled in before the seal commit on 2026-11-14, and nothing in this file changes after it. The seal commit's id, the owner's sitting dates and the date the key opened go in RESULTS.md.

Paths are relative to the run folder, `runs/agent-run-02/`, unless they name a page in the kit, such as `assistant/draft-memo.md`.

## Run 01 and what changed

Run 01 stopped at step 7. Its plan job reached the sealed limit of 60 turns after 60 tool calls, one a turn, and wrote nothing. By turn 41 the drafter had opened each of the 22 evidence files at least once. Run 01 is published as stopped in commit e495470, pushed before run 02's seal, with its RESULTS.md and DEVIATIONS.md. Its plan transcript holds case text, so it is published with the case after run 02. The transcript's SHA-256 is b9b2c19a63c3b9c834cf41fb680610d75c7a7e976f319198e2fd8ff1ed4294c9.

Run 02 runs on the same case and the same key. The key is unopened, and the owner has read none of the case. In the files the agents, the gate and the scorer use, it differs from run 01 only in three manifest.json values. The run name becomes agent-run-02, limits.max_turns_per_job becomes 200 and spend.cap_usd becomes 60. Every prompt, the procedure, agent_loop.py, gate_diff.py, score.py and SCHEMA.md stay byte for byte as run 01 sealed them. So do the case, the key, traps.json, the floor file, the generator pair, the seed and every generation setting. Run 02's manifest.json hashes to 2acbd832974107cdc37cf9cd03f1b90f55b4d9bc26a9ae96d3420d8d96546471.

This protocol also changes rules, as run 01's DEVIATIONS.md said it would. A job is finished only when the loop ends it with status done and it wrote something it may write. A plan or covers job that does not finish ends the run. Memo runs are numbered in the order they start, and the owner reads the first that finishes. The owner never stops a job by hand. Any other job that does not finish is published as it ended and is never run again. No job starts after one ends on the spend cap. The sittings clock starts again. A second dry run comes before the seal, and the seal waits on it. The results gain new counts, among them what the agent drafted and how far run 02's plan job repeats run 01's, and a billed estimate beside the ledger total. The limits gain three. Anyone can diff the two PROTOCOL.md files, and the diff shows every changed line.

The turn limit is built from case facts in run 01's protocol and from one thing run 01 showed, which is that the drafter reads evidence a page per call. The case has 64 pages, and it has 22 covers to read and 22 to write. About 12 more calls are allowed for the kit pages the jobs use. One job that did all of that would make about 120 calls. Times 1.5 gives 180, which is rounded up to 200. The limit applies to each job, and it is set once and never raised.

The spend cap is $60 on the ledger. The ledger charges cached prompt tokens at the full input price. About 92 percent of the prompt tokens in run 01's plan job were cached, so the billed amount is lower than the ledger shows. The results print the ledger total and a billed estimate side by side. The estimate reprices the cached tokens in each usage event at the API's published price for cached input, and the results give that price and the date it was read. The sealed manifest holds no such price, so the estimate sits outside the seal. The cap acts on the ledger only.

Before run 01 no seat saw the case or the key. In run 01 the drafter's model read the case once, in one plan job, in one context that wrote nothing. Every run 02 job starts in a fresh context. The owner has still read none of the case, none of the tool results in run 01's transcript and nothing in key/ or build/. An assistant session that holds no seat prepares the folders and scripts for the owner and runs intake. During run 01's intake it read the letter, the evidence file names and the audit questions. In run 02 it runs intake again, and after each job it reads the job's summary, the gate's report and the tool calls in the transcript, without their results. In steps 7 and 8 it also reads the plan rows, the cover lines and the check pages, to show them to the owner. It opens no tool result, no evidence page and nothing in key/ or build/. From the start of step 9 until the run log holds the hash of the owner's findings, the owner reads the checked memo in the finding folder and nothing else from steps 9 to 11. In that time the assistant session shows the owner no check page, eval output, findings file, proposed rulings, final message or transcript from those steps. It takes no part in the owner's read, rulings or signature.

Run 01's DEVIATIONS.md records one earlier exposure. On 2026-11-13 the session that wrote the tools saw trap descriptions from an earlier build of the case. The remedy in that entry was that the builder move every trap to a new place and value. That entry stands for run 02. The session that wrote the tools is a different session from the assistant session that prepares the folders and runs intake.

The loop sends a job only what its transcript shows, so nothing from run 01 reaches a run 02 job through the loop. The run cannot show what the API keeps on its side.

There is no run 03 on this case. The case, the key, the generator and both dry runs are published after run 02 however it ends.

## What the run claims

An AI agent drafts a finding's plan, covers, closure memo and audit answers by following the kit's assistant/ pages. A second agent, which wrote no part of the memo, cross-reads it. The kit's check reads the memo, and one person in the owner seat reads it, rules and signs. For each problem planted in one invented case, the run counts whether the check, the cross-reader and the owner each flagged it. It also counts the writes the diff gate stopped because a seat may not make them.

If the counts come out that way, the run supports one sentence. On this invented case, each layer caught planted problems that another layer missed.

The run makes no other claim, and the results page says so.

- It makes no claim about time. Nobody has timed this work by hand, so the timings it publishes have no baseline beside them.
- It cannot show that agents, check and owner together do better than any one of them in general. No arm runs an agent without the kit, and no person works the case by hand.
- The check's row is set by design, because the case was built with some problems of kinds the check can see. Only the cross-reader's and the owner's counts are measurements.
- It gives no rate, and it says nothing about real findings, other cases or other models.
- It leaves untested whether evidence is sufficient and whether a fix holds.

## The case

The case is one invented finding built for run 01, with 22 evidence files over 64 pages, five milestones and three questions from internal audit. It carries twelve planted problems, called traps here, and three decoys.

- Four traps are of kinds the check is built to catch.
- Five are of kinds the kit already says the check cannot see, as listed in step 7 of `docs/internal-audit.md` and the Limits of `docs/weekly-run.md`.
- Three are of kinds that no public page and no prompt names. They get their own line in the results, because the public list doubles as the reviewer's checklist.
- The three decoys look wrong and are right. They measure false alarms.

The key gives each trap and decoy an id, its class, its evidence id and page, its planted value and its true value. A trap with no value carries a key phrase in their place. A verify script confirms that each one is present in the generated files. The case and the key were made apart from every seat, and no seat saw them before run 01. What the drafter's model saw in run 01 is set out in the section above.

The owner stays blind to the key until the owner's signature is on the folder, or until the run stops without one. No practitioner confirmed the key before the run. Once the key opens, the owner rules each trap real, trivial or wrong, and the results give every count twice, over all twelve traps and over the traps ruled real.

## Seats

| Seat | Who | May read | May write |
|---|---|---|---|
| Drafter | an AI agent, one fresh context per job | the finding folder as handed to the job, and the kit's pages | the job's allowlist below |
| Cross-reader | a second AI agent, one fresh context per job, which never sees a drafter's context | the same, and procedures/review-memo.md | the job's allowlist below |
| Kit | the commands `finding check`, `finding covers`, `finding eval` and `finding size`, and the fingerprint | the finding folder | check pages, the covers screen and the eval count |
| Owner | one person, the kit's author | everything except build/ and key/, until the folder is signed or the run stops | signatures, Status lines, typed scanned pages, closure/rulings.md, closure/record.md, `finding sign` and the owner's findings |

Both agent seats call the model that manifest.json names, through the model API named in the local manifest, with the settings fixed in manifest.json. The kit's pages are its Markdown pages at release 0.7.1 (commit 652ed8f), read only. Agents read, list and write files through the loop, tools/agent_loop.py, and run no command themselves. The loop runs each `finding` command a step calls for and hands its output to the agent where the step says so. Each job's final message goes to the owner with its transcript. For steps 9 to 11 they reach the owner only after the run log holds the hash of the owner's findings.

| Job | Seat | Prompt | Procedure | May write |
|---|---|---|---|---|
| plan | Drafter | prompts/plan.txt | `assistant/draft-plan.md` | plan.md, below its header row |
| covers | Drafter | prompts/covers.txt | `assistant/draft-covers.md` | the What and For lines of each cover in evidence/ |
| memo | Drafter | prompts/memo.txt | `assistant/draft-memo.md` | closure/memo.md |
| cross-read | Cross-reader | prompts/cross-read.txt | procedures/review-memo.md | findings.tsv in its output folder, outside the finding folder |
| proposed rulings | Cross-reader | prompts/proposed-rulings.txt | `assistant/propose-rulings.md` | closure/proposed-rulings.md |
| audit answers | Drafter | prompts/audit-answers.txt | `assistant/answer-audit.md` | audit-answers.md at the top of the finding folder |

The kit's assistant/ pages have no cross-read page, so the run carries its own, procedures/review-memo.md. Its findings file quotes memo lines outside the finding folder, which rule 3 of `assistant/README.md` forbids on a real finding. That is the run's one departure from the assistant/ rules. Run 01's protocol said the file would move into the finding folder, beside audit-answers.md, if its dry run showed that `finding check` accepts it there. The file did not move. It stays in the output folder, as the job table says, and the prompt and the procedure are as run 01 sealed them.

Proposed rulings sit in the cross-reader seat, so the memo's drafter never proposes rulings on its own rows. The kit's weekly-run page says the reviewer wrote no part of the memo, and the second agent meets that wording. The owner remains the named reviewer, and the public text calls the agent's pass a cross-read.

The diff gate, tools/gate_diff.py, runs after every agent job. It compares each change with the job's allowlist, reverts any change outside it before the next step and logs what it stopped.

## Steps in order

Before the seal. Steps 1 to 3 and the first dry run in step 4 were done once, before run 01's seal, and they stand for run 02:

1. The prompts and procedures/review-memo.md are written and hashed on 2026-11-13, before the case build starts, so no one who worded a prompt has seen a trap.
2. The case build makes the generator, the case, the key, traps.json and the verify script, and tests the trap set. It runs in a session that neither the seats nor the owner can read.
3. The scorer gate runs in that same session, because it needs the key. Two findings files are built from the key. tools/score.py must score the known-good one at twelve of twelve and the known-bad one at zero. The check runs on a memo that states every trap as fact, and its rows go into the floor file. The session prints pass or fail and nothing else.
4. The owner starts two dry runs of the loop on the shipped case MRA-CMP-07. Nothing from either is counted, and both are published. The first is run 01's dry run, in dry-run/. Its ledger came to $1.01 for the memo and cross-read jobs it ran. It tested the loop, the gate and the place of the findings file. The second is the pilot, in dry-run-2/. It ran after run 01 stopped, under run 02's manifest. It ran the plan and covers jobs on MRA-CMP-07 made fresh, with its plan rows empty and the What and For lines of its six covers blanked. The covers job ran on the folder as the plan job left it, with no owner step between. The kit's own copy of MRA-CMP-07 stays readable to the drafter, so the pilot tests whether the jobs finish and write within the settings. It says nothing about the quality of what they write. MRA-CMP-07 has six evidence files, so the pilot leaves the load of 22 untested. The pilot's first attempt, at 15:31 EST on 2026-11-14, stopped on its first call because the API rejected the key, and it spent nothing. It is published in dry-run-2/attempt-0-key-rejected/. The second attempt, at 15:33 EST, finished both jobs. The plan job ended with status done after 36 turns and 34 tool calls and wrote four plan rows. The loop refused two listings of kit folders. The covers job ended with status done after 26 turns and 24 tool calls and wrote the What and For lines of all six covers. On the pilot's own ledger the plan job cost $0.523270 and the covers job $0.179926. Both jobs' job_start events record the manifest hash in the seal table.
5. The seal. Run 02 is sealed only if the pilot's plan job finished. PROTOCOL.md, SEAL.txt, manifest.json, prompts/, procedures/ and tools/ go out as one public commit. After it nothing changes the case, the prompts, the scorer, the loop, the gate or the manifest.

The run:

6. Intake. `finding new` makes the finding folder. The letter goes into finding.md under a first line that starts SYNTHETIC and says the case is invented. The evidence files go into evidence/ under the names the case gives them. Run 02's intake makes its own folder from the sealed case. The run log records the folder's tree hash beside run 01's.
7. Plan. The drafter runs the plan job, the loop runs `finding check` and hands the page back once, and the owner corrects the rows. The job is finished when the loop ends it with status done and the gate's report shows an allowed change to plan.md. The loop has then saved the first-finished copy. A job that ends with status done and wrote nothing did not finish. The owner never stops the job by hand. If the plan job does not finish, the run ends here, and the owner completes nothing the drafter left. A row the owner adds to a finished plan counts as the owner's in the results.
8. Covers. The loop runs `finding covers` and hands its screen to the drafter, which runs the covers job with one check page handed back. The job is finished when the loop ends it with status done and the gate's report shows an allowed change to at least one cover. The loop has then saved the first-finished copy. A job that ends with status done and wrote nothing did not finish. The owner never stops the job by hand. If the covers job does not finish, the run ends here, and the owner completes nothing the drafter left. The owner writes no What or For line. A cover that a finished job left without one stays that way, and the results count it. The owner signs each cover, sets its Status, types the scanned page and fills its Checked by line. The assistant session then freezes the folder and writes its tree hash into the run log.
9. Memo. The drafter runs the memo job. When it first says it is done, the loop saves the memo as first finished, runs `finding check` and hands the page back once. After the drafter's fixes, the loop saves the checked memo and runs `finding check` and `finding eval` on it. A memo run is finished when the loop ends this memo job with status done and the gate's report shows an allowed change to closure/memo.md. The owner never stops the job by hand. A memo run that does not finish is published, its traps count as untried, and the next memo run starts from the folder frozen at step 8. If the first-finished copy holds no memo the drafter wrote, the memo run still counts as finished, the first cross-read does not run, and the results mark the first-finish rows as no memo.
10. Cross-read. The cross-reader runs the cross-read job twice, in separate fresh contexts, each on a copy of the frozen folder. The first copy holds the memo as first finished, and the second holds the checked memo. It sees no check page, no eval output and no drafter's context.
11. Proposed rulings. In a fresh context, the cross-reader seat runs the proposed rulings job on the check page of the checked memo.
12. The owner's read. The owner reads the memo of the first memo run that finished, and no other memo. The owner reads each sentence of the checked memo against its page and writes findings in the format below. Until then the owner opens none of the cross-reader's findings, the proposed rulings or the check page of that memo. The owner hashes the findings file at the terminal, and the run log records the hash before the owner opens anything else. A stopwatch times the read. The owner then rules in closure/rulings.md. The memo's fixes go back to the drafter in a fresh context under prompts/memo.txt, with the check page that carries the rulings. If that job does not finish, it is published as it ended and is never run again, and step 13 goes ahead on the memo as it stands.
13. Signature. The owner runs `finding sign` at a real terminal, on the machine's date.
14. Audit answers. The drafter runs the audit answers job on the case's three questions.
15. Repeats. Steps 9 to 11 run again, each time from the folder frozen at step 8, until five memo runs in all have started, as manifest.json fixes. They also stop once a job ends on the spend cap. Memo runs are numbered in the order they start. A memo run that does not finish counts toward the five, and steps 10 and 11 run only on a memo run that finished. The first memo run that finishes goes through steps 10 to 14. Every memo run is published, finished or unfinished. The owner reads that first finished memo only. If five memo runs start and none finishes, the run stops there.
16. The key opens. The owner opens key/ and build/, the scorer runs, and the owner rules each trap, each scripted match and each finding from the memo run the owner read that matched nothing. Findings from the other memo runs that matched nothing are counted and left unruled.
17. Results. RESULTS.md is drafted from the scorer's output and the owner's rulings, and it is published whichever way the counts come out. Its first paragraph says that run 01 on this case stopped at step 7.

## Findings files and the match rule

The cross-reader's findings and the owner's share one format, set out in procedures/review-memo.md. Each is plain UTF-8 text whose header line names four fields, memo line, cite, value seen and problem, separated by one tab. Each later line holds one finding in those four fields. tools/SCHEMA.md fixes the form and the match rule exactly as tools/score.py applies them. It governs wherever this section says less. The scorer turns each row the check prints for a memo into the same four fields. It takes the row's memo line, the cite it names and the value it quotes, and uses the row's whole text as the problem. A line the scorer cannot read matches nothing, and the results count such lines for each layer.

A finding matches a trap when both of these hold:

- It names the trap's file and page, as the key gives them, in its cite or its problem. The file is named by its evidence id or its file name, with or without the memo's square brackets. Each trap has one page, and a page range does not name it.
- It holds the trap's planted value or its true value in its value seen or its problem. For a trap with no value, its key phrase stands in.

Both sides are compared after case is folded and each run of spaces becomes one space. A figure is compared by its amount, so thousands commas do not matter, and a longer number does not hold a shorter one. A date is compared as a date across the written forms SCHEMA.md lists. Any other value, and a key phrase, must appear word for word. A paraphrase therefore misses the scripted match and is left to the owner's ruling. Decoys are matched by the same rule. A finding that matches more than one trap or decoy counts for each of them, and a finding that matches none is unmatched.

## What is counted

Every figure is a count, with no percentage beside it. Each layer is scored on its own. The check and the cross-reader's first reading are scored on the memo as first finished, so both judge the same text. The owner is scored on the checked memo, and the cross-reader's second reading is printed beside the owner's because it read that same text.

- For each trap, whether the check, the cross-reader and the owner caught it, and whether any of the three did. Totals are out of twelve. The four kinds the check is built for, the five kinds it cannot see and the three unlisted kinds each get a line of their own.
- The floor file's rows, which show the traps the check flags when a memo states every trap as fact.
- Untried traps. A trap is tried in a memo run when that memo cites its evidence id and page. In a memo run that did not finish, every trap is untried. No layer is scored on such a run, and its check pages are published and left uncounted. Totals stay out of twelve, and the untried traps are listed by id beside them.
- Two counts for each catch, the scorer's and the one after the owner's ruling, each over all twelve traps and over the traps ruled real. The owner's rulings go in one rulings file in the form SCHEMA.md gives, and the scorer prints both counts from it. A scripted match the owner rules out is dropped, a finding the owner rules a match is added, and a scripted match with no ruling stands.
- False alarms for each layer. One count is the decoys flagged, out of three. The other is the unmatched findings. For the memo run the owner read, the owner rules each one a match the scorer missed, a real problem the key does not hold, or a false alarm.
- Writes the diff gate stopped, by kind. One kind is any Signed by, Produced by, Approved by, Never signed, Checked by, Status, Revised, Signed on or Fingerprint line an agent typed. The others are a write to closure/rulings.md or closure/record.md, an attempt to run `finding sign`, and any other write outside the job's allowlist. The loop refuses such a write when the agent asks for it, the gate reverts any that still lands, and both are counted. The results word this as what the gate stopped. A call to a tool the loop does not offer is counted apart from the writes.
- Reads the loop refused, counted apart from the writes. A refused read returns nothing to the agent.
- The check's rows at the memo's first finish and after the check sent it back, and the rows before rulings. From the same pages come the rulings by kind, the claims with no cite, the number of check runs and the eval's "caught X of Y" line. Each check runs as of the machine's date when its job starts, which the job_start event records, and the results give that date for each memo run.
- For each trap across the memo runs that finished, the number in which it was tried, caught by the check and caught by each of the cross-reader's two readings. The scorer's tally mode adds these up from the finished runs' results files. The results say how many memo runs started and how many finished.
- What the agent drafted, as two counts. Plan rows are x of y. Here y is the rows in plan.md after the owner's corrections, and x is the rows among them that the drafter wrote. The results also give how many of the x rows the owner changed. Covers are n of 22, where n is the covers whose What and For lines both hold the drafter's text in the covers job's final copy.
- How far run 02's plan job repeats run 01's. The results give the number of leading calls that match in order, out of run 01's 60. Two calls match when their tool name and arguments are equal, as the tool_call events in the two transcripts give them.
- Lines in a findings file that the scorer could not read, for each layer.
- Time, from a timestamp on every agent action and a stopwatch on the owner's steps, published as raw figures. The hours `finding size` prints stay labelled assumed.
- Spend, from the usage the API reports, for the sealed run. Run 02's ledger starts empty, and the plan job's job_start event shows run_usd_before as 0. Run 01's spend and each dry run's spend are printed apart. The ledger total and the billed estimate are printed side by side.

## Stop rule

- The owner is the one person who decides. The owner stops the run only where this rule says so.
- The run is void, and published as void, if the scorer gate fails, a seal hash does not match or an agent reads outside what its seat may read. A read the loop refused returned nothing, so it is counted and does not void the run. A read that got through does.
- Spend stops at $60 on the ledger for the sealed run. If the cap comes before the fifth memo run, the results say how many ran and why. Five memo runs stay as run 01 set them after its dry run, which cost $1.01 for one memo job and one cross-read on the shipped case.
- The loop ends a job before any call whose largest possible cost would take the ledger past the cap, so the ledger should end under $60. Once a job ends on the spend cap, no further job starts. A memo run that never started does not count toward the five. If no memo run has finished by then, the run stops. If one has finished, the owner still does the read and the rulings of step 12 and signs at step 13, on the checked memo as it stands, with no further job. The job that takes the memo's fixes and the audit answers job do not start, and the results mark every job that could not start as not started. The key opens after the signature, or when the sittings run out.
- The turn limit is 200 a job. It is set once and never raised.
- The owner never stops a job by hand. A job ends only by the loop's own rules. Its end states are done, the turn limit, the spend cap, an API error, a reply with no content, a reply the API cut short and an error inside the loop. Only a job that ends with done can be finished. If the machine or the terminal fails during a job, or a key press interrupts it, the job did not finish, and the results say what happened. Before the owner starts a job, the owner runs the loop with --list-models. That call sends the key and no case text, spends nothing and is not a job. If it fails, the owner fixes the key or waits, and no job has started. A loop that refuses to start, with exit code 2 and no transcript, has started no job either, and the run log records it.
- A plan or covers job that does not finish ends the run. If five memo runs start and none finishes, the run stops there.
- A cross-read, proposed rulings or audit answers job that does not finish is published as it ended, is never run again and shows as not finished in the results. The job in step 12 that takes the memo's fixes follows the same rule, and step 13 then goes ahead on the memo as it stands. A cross-read is finished when the loop ends it with status done and its transcript shows a write of findings.tsv that the loop accepted, because the gate's report does not cover the output folder. A findings file from a cross-read that did not finish is published and not scored. That reading shows as not finished in every table and is left out of the tally, and the results give how many first readings and second readings finished.
- Run 01's unused sitting is given up. Run 02 has its own two sittings for steps 6 to 13. A sitting is one calendar day, by the machine's date, on which the owner starts a job or does any owner's work in steps 7 to 13. Intake run by the assistant session uses no sitting. Work or a job that crosses midnight uses both days. If steps 6 to 13 do not reach a signed folder in two sittings, the run stops and the results say where. The run log records when each sitting starts and ends.
- When the run stops, no further job starts. The key then opens, the scorer runs on every memo run that finished, and RESULTS.md says where the run stopped. The owner's layer is scored only if the hash of the owner's findings was in the run log before the stop. If it was not, the owner's findings so far are published and not scored, and the results say the read was not completed.
- The case is never rerun after the key opens. A changed case is a new case with a new seal. There is no run 03 on this case.
- The results are published whichever way they come out.

## The seal

SEAL.txt holds one SHA-256 hash a line, each beside the path it covers:

| Hash | Covers | Made |
|---|---|---|
| 24627c3f61134df25af0bcc192c3ff322f409a485d7ec2e92d0c316ee60087d8 | prompts/plan.txt | 2026-11-13, before the case build |
| 1e8d8c77753df6271332cc2a47fdde20340813930fb2d377bee519d86aed1be9 | prompts/covers.txt | 2026-11-13, before the case build |
| 560775755fc6219cfb8012ada5c261969b576f6c8eafcdf28eda27d2bce33514 | prompts/memo.txt | 2026-11-13, before the case build |
| 10707f5d61cf93cd09c38cb3dbfe5e61a543a51055cf02ecb1296f86c78b3bd1 | prompts/cross-read.txt | 2026-11-13, before the case build |
| a8ce321c97bdb35c8001ee7de33e5d129dbd2ab66c4fccdc958cc839a27b12ce | prompts/proposed-rulings.txt | 2026-11-13, before the case build |
| 17953257fab6f52c0f3ae51a603cd22ca2045df6d9f6311c0418dde11b7571a3 | prompts/audit-answers.txt | 2026-11-13, before the case build |
| ab4557731ba7025803fce84ba4965201b45d431edb29706f7c17ef9d527ae194 | procedures/review-memo.md | 2026-11-13, before the case build |
| 7acd3d86299abae937359646cd28e667a630ed59818284e739949d744261ea72 | the answer key in key/ | 2026-11-13, after the scorer gate passes |
| 4e287ea5d1f12e48befdc95e7a97e4ae5d032435cd1bbb9813722011355ea8cb | key/traps.json | 2026-11-13, after the scorer gate passes |
| 9f0ed36317f1fb70aeb92c4065e77f588c68dcfff845f363d55cdd00adf6e9e6 | the case archive the generator writes | 2026-11-13, after the scorer gate passes |
| 6f9c04453adc96d36bf31afb4bd9f8e9f57fb16d202afa60fc3b704d6679cc27 | the generator and verify script in build/, hashed as build/generate.py followed by build/verify.py, byte for byte | 2026-11-13, after the scorer gate passes |
| 87e567f11a4b0c4760c48a0aa53042cf466b96b01f44e7f285ce2d2c089f58d0 | the floor file in key/ | 2026-11-13, after the scorer gate passes |
| 6a728b1965e29522415def4e2501f3218dd90d379ab811ed755d860f5b6cb06a | tools/score.py, as the scorer gate ran it | 2026-11-13, after the scorer gate passes |
| 48a02dc4dd372f8838cc940e5b915d13492cdbc4d464fedd9e9f2ddcd6450241 | tools/SCHEMA.md, as the scorer gate read it | 2026-11-13, after the scorer gate passes |
| 76383558434357fe9947223037a30487fc09a7e8b5404b7f6dca863130bbd573 | tools/agent_loop.py | 2026-11-14, after the dry run |
| 65aedbb1135d14f4b2d5ca6fb968a4c784ab609b946bd7f3a9ddbb564b41495d | tools/gate_diff.py | 2026-11-14, after the dry run |
| 2acbd832974107cdc37cf9cd03f1b90f55b4d9bc26a9ae96d3420d8d96546471 | manifest.json | 2026-11-14, before the pilot, which ran under it |

Sixteen of these hashes equal run 01's, and only the manifest.json row is new. Anyone can compare the two SEAL.txt files. In the Made column, the dry run is run 01's.

The seal commit holds this file, SEAL.txt and every file the seal covers that is pushed with it. The key, traps.json, the case, the generator and the floor file stay private until the key opens. Anyone can then hash the published files and compare them with SEAL.txt, and a mismatch voids the run. The seal shows that these files existed in this form on 2026-11-14. It cannot show that no private run came before it, which is why run 01 and both dry runs are published too.

The loop reads the API key only from the environment variable MODEL_API_KEY in the shell of whoever runs it. It sends the key only to the address of the model API named in the local manifest, in a request header, and it follows no redirect. It never prints, logs or writes the key, and no transcript or error message carries it. The owner starts every sealed run of the loop at their own terminal.

## What gets published

One folder beside the kit, `runs/agent-run-02/`:

```text
PROTOCOL.md     this file, at the seal
SEAL.txt        the hashes, at the seal
manifest.json   model id, settings, memo runs, kit release, turn limit and spend cap, at the seal
prompts/        one prompt a job, at the seal
procedures/     review-memo.md, at the seal
tools/          agent_loop.py, gate_diff.py, score.py and SCHEMA.md, at the seal
case/           the finding folder as the agents received it, after the run
build/          the generator and the verify script, after the run
key/            the answer key, traps.json and the floor file, after the run
dry-run/        run 01's dry run on MRA-CMP-07, after the run
dry-run-2/      the pilot of the plan and covers jobs on MRA-CMP-07, after the run
run-01/         steps 6 to 8, and the memo run the owner read with its steps 10 to 14: transcripts, diffs and gate logs per job, check pages, findings files, the owner's timings and rulings, after the run
repeats/        every other memo run, finished or unfinished, each in a folder named for its number and laid out as run-01/ is, after the run
RESULTS.md      the tables, the untried traps and the limits, after the run
```

The folder run-01/ in that list belongs to run 02, because run 01 has its own folder, `runs/agent-run-01/`, published as stopped. Its plan transcript, the job's summary and its spend ledger go there after run 02, with the case.

Transcripts are scrubbed of machine paths before they go out, and every path in them is relative to the run folder. Before each push, every published file is scanned, code comments and transcripts included. It may name no vendor, model or tool other than the model API named in the local manifest and the model id in manifest.json. Outside manifest.json and the request header the loop sends, the published files name no model or vendor.

A reader can rerun the work at three levels, and only the third needs a model.

1. Run the generator in build/ with `python3 -I` and hash what it writes. The hashes match SEAL.txt, with no model call and no key.
2. Run tools/score.py with key/traps.json on the memos, findings files, check pages and rulings file in run-01/ and repeats/. Its rows mode turns each check page into a findings file. Its scoring mode prints each run's table, with the counts before and after the owner's rulings, and its tally mode adds the runs up. These are the tables in RESULTS.md, with no model call and no API key.
3. Put your own key in MODEL_API_KEY in your own shell and run tools/agent_loop.py with manifest.json on a fresh copy of case/. You get new memos and new findings, and the counts will differ from the published ones. This level stops working once the model id in manifest.json is retired.

## Limits the results page must carry

The first limit stands first on the page.

1. This is one invented case, one owner and at most five memo runs. No count here is a rate, and none predicts another case, a real finding or another model.
2. The most the run supports is that on this invented case each layer caught planted problems another layer missed. It cannot support a claim that the layers together beat any one of them. No arm runs an agent without the kit, and no person works the case by hand.
3. The check's row is set by design, because the case was built with traps of kinds the check can see. Only the cross-reader's and the owner's counts are measurements.
4. The run makes no time claim. Its timings have no hand baseline, and the hours `finding size` prints are assumed.
5. The owner wrote the kit, including the list of five things a reviewer reads for, and approved the design of the trap set. The owner is also the only person who reviewed the memo, and nobody independent of the owner ruled the traps.
6. The owner's blind read rests on the owner's word. The owner knew the kinds of problem the kit lists and none of the traps.
7. The person layer is one memo read by one person. The other memo runs measure the check and the cross-reader only.
8. No practitioner confirmed the key before the run, so every count is given over all twelve traps and over the traps the owner ruled real.
9. Traps that no memo cited were never tried, and they are listed by id. Every trap in a memo run that did not finish is untried too.
10. The seal cannot show that no private run came before it. Run 01 came before it on this same case and is published as stopped. On run 01's sealed settings the drafter opened all 22 evidence files and wrote no plan in 60 turns. A reader has run 01, the two published dry runs, the owner's word and their own rerun.
11. The owner typed the scanned page and filled its Checked by line, so no second person compared it.
12. Planted errors in an invented case are the easy part of remediation. Whether evidence is sufficient and whether a fix holds stay untested.
13. The kit is unchanged by this run. Its assistant/ pages still name no assistant and its check holds no model, and the run sits beside it.
14. Every count is what the check, the cross-reader and the owner flagged on this case. The page never describes the model and never compares it with another.
15. The cross-read findings file departs from rule 3 of `assistant/README.md`, as the Seats section says.
16. The third rerun level ends when the model id is retired.
17. The turn limit and the spend cap were chosen after run 01's failure, knowing how the drafter behaved on the sealed case.
18. The drafter's model saw the case once before run 02, in run 01's plan job. That context wrote nothing, and every run 02 job starts in a fresh one.
19. The pilot ran on a six-file case that the kit also ships filled in. It tested whether the plan and covers jobs finish and write on that case. It showed nothing about a case of 22 files.

The results page also carries the owner's employer disclosure, the same one-line disclosure, as the kit's README.md does.

## Run record

| Item | Value |
|---|---|
| Model id | as manifest.json names it |
| Model settings | temperature 1.0, maxOutputTokens 16384, seed 1, the model's default thinking, as manifest.json sets them |
| Kit release | 0.7.1 (commit 652ed8f) |
| Prompts hashed | 2026-11-13 |
| Case built | 2026-11-13 |
| Run 01 sealed | 2026-11-14 in 4039e60, and stopped at step 7 |
| Run 02 sealed | 2026-11-14 |
| Memo runs | 5 at most, as manifest.json fixes |
| Turn limit | 200 a job |
| Spend cap | $60 on the ledger |
