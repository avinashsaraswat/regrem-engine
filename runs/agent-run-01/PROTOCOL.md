# Protocol for agent run 01

This protocol is pushed with SEAL.txt before any agent seat or the owner sees the case. It fixes what the run claims, who may write what, the order of steps, how findings are matched and counted, when the run stops and what gets published. Names in braces, such as the model id, are filled in before the seal commit on 2026-11-14, and nothing in this file changes after it. The seal commit's id, the owner's sitting dates and the date the key opened go in RESULTS.md.

Paths are relative to the run folder, `runs/agent-run-01/`, unless they name a page in the kit, such as `assistant/draft-memo.md`.

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

The case is one invented finding built for this run, with 22 evidence files over 64 pages, five milestones and three questions from internal audit. It carries twelve planted problems, called traps here, and three decoys.

- Four traps are of kinds the check is built to catch.
- Five are of kinds the kit already says the check cannot see, as listed in step 7 of `docs/internal-audit.md` and the Limits of `docs/weekly-run.md`.
- Three are of kinds that no public page and no prompt names. They get their own line in the results, because the public list doubles as the reviewer's checklist.
- The three decoys look wrong and are right. They measure false alarms.

The key gives each trap and decoy an id, its class, its evidence id and page, its planted value and its true value. A trap with no value carries a key phrase in their place. A verify script confirms that each one is present in the generated files. The case and the key were made apart from every seat, and no seat saw them before the run.

The owner stays blind to the key until the owner's signature is on the folder. No practitioner confirmed the key before the run. Once the key opens, the owner rules each trap real, trivial or wrong, and the results give every count twice, over all twelve traps and over the traps ruled real.

## Seats

| Seat | Who | May read | May write |
|---|---|---|---|
| Drafter | an AI agent, one fresh context per job | the finding folder as handed to the job, and the kit's pages | the job's allowlist below |
| Cross-reader | a second AI agent, one fresh context per job, which never sees a drafter's context | the same, and procedures/review-memo.md | the job's allowlist below |
| Kit | the commands `finding check`, `finding covers`, `finding eval` and `finding size`, and the fingerprint | the finding folder | check pages, the covers screen and the eval count |
| Owner | one person, the kit's author | everything except build/ and key/, until the folder is signed | signatures, Status lines, typed scanned pages, closure/rulings.md, closure/record.md, `finding sign` and the owner's findings |

Both agent seats call the model that manifest.json names, through the model API named in the local manifest, with the settings fixed in manifest.json. The kit's pages are its Markdown pages at release 0.7.1 (commit 652ed8f), read only. Agents read, list and write files through the loop, tools/agent_loop.py, and run no command themselves. The loop runs each `finding` command a step calls for and hands its output to the agent where the step says so. Each job's final message goes to the owner with its transcript.

| Job | Seat | Prompt | Procedure | May write |
|---|---|---|---|---|
| plan | Drafter | prompts/plan.txt | `assistant/draft-plan.md` | plan.md, below its header row |
| covers | Drafter | prompts/covers.txt | `assistant/draft-covers.md` | the What and For lines of each cover in evidence/ |
| memo | Drafter | prompts/memo.txt | `assistant/draft-memo.md` | closure/memo.md |
| cross-read | Cross-reader | prompts/cross-read.txt | procedures/review-memo.md | findings.tsv in its output folder, outside the finding folder |
| proposed rulings | Cross-reader | prompts/proposed-rulings.txt | `assistant/propose-rulings.md` | closure/proposed-rulings.md |
| audit answers | Drafter | prompts/audit-answers.txt | `assistant/answer-audit.md` | audit-answers.md at the top of the finding folder |

The kit's assistant/ pages have no cross-read page, so the run carries its own, procedures/review-memo.md. Its findings file quotes memo lines outside the finding folder, which rule 3 of `assistant/README.md` forbids on a real finding. That is the run's one departure from the assistant/ rules. The dry run tests whether `finding check` accepts the file inside the finding folder, beside audit-answers.md. If it does, the file moves there before the seal, and the prompt and the procedure change in that one path.

Proposed rulings sit in the cross-reader seat, so the memo's drafter never proposes rulings on its own rows. The kit's weekly-run page says the reviewer wrote no part of the memo, and the second agent meets that wording. The owner remains the named reviewer, and the public text calls the agent's pass a cross-read.

The diff gate, tools/gate_diff.py, runs after every agent job. It compares each change with the job's allowlist, reverts any change outside it before the next step and logs what it stopped.

## Steps in order

Before the seal:

1. The prompts and procedures/review-memo.md are written and hashed on 2026-11-13, before the case build starts, so no one who worded a prompt has seen a trap.
2. The case build makes the generator, the case, the key, traps.json and the verify script, and tests the trap set. It runs in a session that neither the seats nor the owner can read.
3. The scorer gate runs in that same session, because it needs the key. Two findings files are built from the key. tools/score.py must score the known-good one at twelve of twelve and the known-bad one at zero. The check runs on a memo that states every trap as fact, and its rows go into the floor file. The session prints pass or fail and nothing else.
4. The owner starts a dry run of the loop on the shipped case MRA-CMP-07. It tests the loop, the gate and the place of the findings file. Nothing from it is counted, and it is published in dry-run/.
5. The seal. PROTOCOL.md, SEAL.txt, manifest.json, prompts/, procedures/ and tools/ go out as one public commit. After it nothing changes the case, the prompts, the scorer, the loop, the gate or the manifest.

The run:

6. Intake. `finding new` makes the finding folder. The letter goes into finding.md under a first line that starts SYNTHETIC and says the case is invented. The evidence files go into evidence/ under the names the case gives them.
7. Plan. The drafter runs the plan job, the loop runs `finding check` and hands the page back once, and the owner corrects the rows.
8. Covers. The loop runs `finding covers` and hands its screen to the drafter, which runs the covers job with one check page handed back. The owner signs each cover, sets its Status, types the scanned page and fills its Checked by line. The loop then freezes the folder and writes its hash into the run log.
9. Memo. The drafter runs the memo job. When it first says it is done, the loop saves the memo as first finished, runs `finding check` and hands the page back once. After the drafter's fixes, the loop saves the checked memo and runs `finding check` and `finding eval` on it.
10. Cross-read. The cross-reader runs the cross-read job twice, in separate fresh contexts, each on a copy of the frozen folder. The first copy holds the memo as first finished, and the second holds the checked memo. It sees no check page, no eval output and no drafter's context.
11. Proposed rulings. In a fresh context, the cross-reader seat runs the proposed rulings job on the check page of the checked memo.
12. The owner's read. The owner reads each sentence of the checked memo against its page and writes findings in the format below. Until then the owner opens none of the cross-reader's findings, the proposed rulings or the check page of that memo. The loop writes the hash of the owner's findings into the run log before the owner opens anything else. A stopwatch times the read. The owner then rules in closure/rulings.md. The memo's fixes go back to the drafter in a fresh context under prompts/memo.txt, with the check page that carries the rulings.
13. Signature. The owner runs `finding sign` at a real terminal, on the machine's date.
14. Audit answers. The drafter runs the audit answers job on the case's three questions.
15. Repeats. Steps 9 to 11 run four more times, each from the folder frozen at step 8, for five memo runs in all, as manifest.json fixes. Every repeat is published. The owner reads the first memo only.
16. The key opens. The owner opens key/ and build/, the scorer runs, and the owner rules each trap, each scripted match and each finding from the first run that matched nothing. Findings from the repeats that matched nothing are counted and left unruled.
17. Results. RESULTS.md is drafted from the scorer's output and the owner's rulings, and it is published whichever way the counts come out.

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
- Untried traps. A trap is tried in a memo run when that memo cites its evidence id and page. Totals stay out of twelve, and the untried traps are listed by id beside them.
- Two counts for each catch, the scorer's and the one after the owner's ruling, each over all twelve traps and over the traps ruled real. The owner's rulings go in one rulings file in the form SCHEMA.md gives, and the scorer prints both counts from it. A scripted match the owner rules out is dropped, a finding the owner rules a match is added, and a scripted match with no ruling stands.
- False alarms for each layer. One count is the decoys flagged, out of three. The other is the unmatched findings. For the first run the owner rules each one a match the scorer missed, a real problem the key does not hold, or a false alarm.
- Writes the diff gate stopped, by kind. One kind is any Signed by, Produced by, Approved by, Never signed, Checked by or Status line an agent typed. The others are a write to closure/rulings.md or closure/record.md, an attempt to run `finding sign`, and any other write outside the job's allowlist. The loop refuses such a write when the agent asks for it, the gate reverts any that still lands, and both are counted. The results word this as what the gate stopped.
- Reads the loop refused, counted apart from the writes. A refused read returns nothing to the agent.
- The check's rows at the memo's first finish and after the check sent it back, and the rows before rulings. From the same pages come the rulings by kind, the claims with no cite, the number of check runs and the eval's "caught X of Y" line.
- For each trap across the five memo runs, the number in which it was tried, caught by the check and caught by each of the cross-reader's two readings. The scorer's tally mode adds these up from the five runs' results files.
- Lines in a findings file that the scorer could not read, for each layer.
- Time, from a timestamp on every agent action and a stopwatch on the owner's steps, published as raw figures. The hours `finding size` prints stay labelled assumed.
- Spend, from the usage the API reports, for the sealed run and for the dry run apart.

## Stop rule

- The owner is the one person who decides.
- The run is void, and published as void, if the scorer gate fails, a seal hash does not match or an agent reads outside what its seat may read. A read the loop refused returned nothing, so it is counted and does not void the run. A read that got through does.
- Spend stops at $20 for the sealed run. If the cap comes before the fifth memo run, the results say how many ran and why. The owner set five runs under the $20 cap after the dry run, which cost $1.01 for one memo job and one cross-read on the shipped case.
- If steps 6 to 13 do not reach a signed folder in two sittings, the run stops and the results say where.
- The case is never rerun after the key opens. A changed case is a new case with a new seal.
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
| 03398c08c58bf769479e8f1c754e3b812c3d9ec00c9efd5beb5c0fdcdde791a0 | manifest.json | 2026-11-14, after the dry run |

The seal commit holds this file, SEAL.txt and every file the seal covers that is pushed with it. The key, traps.json, the case, the generator and the floor file stay private until the key opens. Anyone can then hash the published files and compare them with SEAL.txt, and a mismatch voids the run. The seal shows that these files existed in this form on 2026-11-14. It cannot show that no private run came before it, which is why the dry run is published too.

The loop reads the API key only from the environment variable MODEL_API_KEY in the shell of whoever runs it. It sends the key only to the address of the model API named in the local manifest, in a request header, and it follows no redirect. It never prints, logs or writes the key, and no transcript or error message carries it. The owner starts every sealed run of the loop at their own terminal.

## What gets published

One folder beside the kit, `runs/agent-run-01/`:

```text
PROTOCOL.md     this file, at the seal
SEAL.txt        the hashes, at the seal
manifest.json   model id, settings, memo runs, kit release and spend cap, at the seal
prompts/        one prompt a job, at the seal
procedures/     review-memo.md, at the seal
tools/          agent_loop.py, gate_diff.py, score.py and SCHEMA.md, at the seal
case/           the finding folder as the agents received it, after the run
build/          the generator and the verify script, after the run
key/            the answer key, traps.json and the floor file, after the run
dry-run/        the dry run on MRA-CMP-07, after the run
run-01/         transcripts, diffs and gate logs per job, check pages, findings files, the owner's timings and rulings, after the run
repeats/        the four memo repeats, laid out as run-01/ is, after the run
RESULTS.md      the tables, the untried traps and the limits, after the run
```

Transcripts are scrubbed of machine paths before they go out, and every path in them is relative to the run folder. Before each push, every published file is scanned, code comments and transcripts included. It may name no vendor, model or tool other than the model API named in the local manifest and the model id in manifest.json. The published files name no model or vendor, and the run record points to the model id in a way the owner approves at handover.

A reader can rerun the work at three levels, and only the third needs a model.

1. Run the generator in build/ with `python3 -I` and hash what it writes. The hashes match SEAL.txt, with no model call and no key.
2. Run tools/score.py with key/traps.json on the memos, findings files, check pages and rulings file in run-01/ and repeats/. Its rows mode turns each check page into a findings file. Its scoring mode prints each run's table, with the counts before and after the owner's rulings, and its tally mode adds the runs up. These are the tables in RESULTS.md, with no model call and no API key.
3. Put your own key in MODEL_API_KEY in your own shell and run tools/agent_loop.py with manifest.json on a fresh copy of case/. You get new memos and new findings, and the counts will differ from the published ones. This level stops working once the model id in manifest.json is retired.

## Limits the results page must carry

The first limit stands first on the page.

1. This is one invented case, one owner and five memo runs. No count here is a rate, and none predicts another case, a real finding or another model.
2. The most the run supports is that on this invented case each layer caught planted problems another layer missed. It cannot support a claim that the layers together beat any one of them. No arm runs an agent without the kit, and no person works the case by hand.
3. The check's row is set by design, because the case was built with traps of kinds the check can see. Only the cross-reader's and the owner's counts are measurements.
4. The run makes no time claim. Its timings have no hand baseline, and the hours `finding size` prints are assumed.
5. The owner wrote the kit, including the list of five things a reviewer reads for, and approved the design of the trap set. The owner is also the only person who reviewed the memo, and nobody independent of the owner ruled the traps.
6. The owner's blind read rests on the owner's word. The owner knew the kinds of problem the kit lists and none of the traps.
7. The person layer is one memo read by one person. The repeats measure the check and the cross-reader only.
8. No practitioner confirmed the key before the run, so every count is given over all twelve traps and over the traps the owner ruled real.
9. Traps that no memo cited were never tried, and they are listed by id.
10. The seal cannot show that no private run came before it. A reader has the published dry run, the owner's word and their own rerun.
11. The owner typed the scanned page and filled its Checked by line, so no second person compared it.
12. Planted errors in an invented case are the easy part of remediation. Whether evidence is sufficient and whether a fix holds stay untested.
13. The kit is unchanged by this run. Its assistant/ pages still name no assistant and its check holds no model, and the run sits beside it.
14. Every count is what the check, the cross-reader and the owner flagged on this case. The page never describes the model and never compares it with another.
15. The cross-read findings file departs from rule 3 of `assistant/README.md`, as the Seats section says.
16. The third rerun level ends when the model id is retired.

The results page also carries the owner's employer disclosure, the same one-line disclosure, as the kit's README.md does.

## Run record

| Item | Value |
|---|---|
| Model id | as manifest.json names it |
| Model settings | temperature 1.0, maxOutputTokens 16384, seed 1, the model's default thinking, as manifest.json sets them |
| Kit release | 0.7.1 (commit 652ed8f) |
| Prompts hashed | 2026-11-13 |
| Case built | 2026-11-13 |
| Seal pushed | 2026-11-14 |
| Memo runs | 10 |
| Spend cap for the sealed run | $20 |
