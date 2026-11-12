# Delivering the kit through a forward-deployed team

Forward-deployed engineering is the software industry's name for engineers placed inside a customer's organisation, with the people who use a product, to fit it to their work. The engineer changes the tool where it runs and takes what the placement teaches back to the product. Vendors and consultancies use it with clients. A financial institution could run the same function internally, placing engineers from a central group with a business team. This page uses the term as a concept only. It sets out the three controls an institution would need before such a team changes this kit, and claims no deployment.

## Why remediation suits it

Each institution keeps its findings and evidence in its own formats, under its own role titles, and the people who assemble a closure package are rarely engineers. A check that ties a memo to its evidence helps only once it reads that institution's files and knows which of its words must never print. That fitting happens beside the team, which is what a forward-deployed function is for. Some of it needs no code, through the three lists the front page describes under [Fitting it to a financial institution](../README.md#fitting-it-to-a-financial-institution).

## Three controls for a team that changes the tool

A team that can change the tool that checks closure evidence is a risk as well as a help. Before an institution lets placed engineers do that, its control function should have the three controls below. Nobody has worked this arrangement, and the kit supplies only part of each one.

### Every change visible

RELEASE.json holds the sha256 of every file a finding's page depends on. Until that file is refreshed, `--version` and every check page name each kit file that differs from the release. Running `python3 -I finding/release.py` then marks the kit as a site version, such as 0.7.0+site.1, and each later signature records it. A changed kit therefore never reads as the published release. From then on the kit shows only that it is a site version. It keeps no log of site changes, so the list of changed files has to live in a log the institution keeps. The version and the file names show which files changed and say nothing of what a change does, so someone other than the engineer still reads each one.

### The builder never accepts

The person who built a change should never be the one who accepts it. The kit cannot enforce that, so the institution names someone outside the build to accept each change. The kit gives that person two reruns anyone can read. The self-test must print PASS, and `python3 -I finding/finding.py eval --library` must print every case as expected. A site version still passes the self-test when the tool behaves as before. A change that alters what the tool prints also changes the self-test's expected screens and the pages that quote them, and the person who accepts reads those edits too. A code change also moves every finding's fingerprint, so a folder that was already signed asks for a fresh signature.

### Miss counts in the open

The eval plants errors in a memo one at a time and lists each miss by line. On the invented case here it catches 30 of 38, and none of the 6 figures swapped for another on the same page. Of the library's 21 cases, 6 record a known limit. After a change both run again, and the counts go to the people who rely on the check. In use, `closure/measures.md` records what internal audit sends back, and the check page counts what the check had passed.

## Why this could change how remediation is delivered

Proving a fix is checking work, and people do it. A tracker can be typed by hand, evidence gathered from shared folders and email, and a memo checked against its sources by eye the night before it is due. A small placed team that fits a deterministic check to an institution's files moves that checking into code. People then spend their time on the rows that do not tie and on whether the fix works.

The institution keeps the fitted kit, its log of site changes and the miss counts, so it can rerun and measure the practice after the team leaves. If each change is visible and accepted by someone who did not build it, internal audit can see how the tool reached its current state. The fitting is done once for a programme and each later finding reuses it, so the cost of proof would fall with every finding closed this way.

## Its limits

The argument rests on a check that is only a floor under a reviewer's reading. It compares each claim with its cited page only, so a figure swapped for another on the same page passes, as do two documents that disagree. The kit has never run on a real finding, and no institution has used it. Its controls are change control, independent acceptance and stated test results, which are old controls in financial institutions, applied to a new arrangement, so the argument claims no invention. Nobody has timed any of this, so the page gives no size for the saving. A placed team also brings risks of its own, such as a fit only its builder understands and site changes that never reach a published release. Nothing from a finding may leave the institution, which limits what a team takes to its next placement.
