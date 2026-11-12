# An engineer's first week

This page is for the one engineer, on the bank's staff or brought in by it, who fits RegRem Engine to the bank in a week. By day 5 the tool runs on the bank's approved machine and refuses to print any name on its deny list. You also know which of the bank's evidence formats it reads, and any code change shows as a site version. Every case and name below is invented.

Every command here runs from the kit root, where finding/ sits. Windows users replace `finding/finding` with `py -I finding\finding.py`. Keep findings beside the kit, such as in `../findings`, because `finding new` refuses a path inside it.

## Day 1: run it on the invented cases

On the approved machine, confirm the copy matches its release and passes both self-tests:

```sh
finding/finding --version
python3 -I finding/selftest.py
python3 -I tieout/selftest.py
```

Expect `RegRem Engine 0.7.0`, then `selftest: PASS (1166 expectations)` and `selftest: PASS (77 expectations)`. Save a baseline outside the kit, checking a copy of the case. A check with a new date rewrites a shipped case's state file, and `--version` then names it as a changed test file.

```sh
mkdir -p ../acceptance/cases
cp -R finding/cases/MRA-CMP-07 ../acceptance/cases/
finding/finding check ../acceptance/cases/MRA-CMP-07 --today 2026-11-04 > ../acceptance/MRA-CMP-07.txt
finding/finding eval finding/cases/IA-CMP-02 > ../acceptance/eval-IA-CMP-02.txt
finding/finding eval --library > ../acceptance/library.txt
```

Pass the same `--today` each time you save a check, or the day counts on the milestone lines will differ. The eval catches 30 of 38 planted errors, and the library reports all 21 cases as expected, 6 of them known limits.

## Day 2: the deny list and role words

Run `finding/finding new ../findings/TRY-01` and fill finding.md and plan.md with an invented letter in the bank's style, using its role titles and system names. Then:

```sh
finding/finding check ../findings/TRY-01 --today 2026-11-04
finding/finding check ../findings/TRY-01 --names
```

The first full check puts the bank's name and its distinctive words on the deny list. It also adds runs of capitalised words from the letter, such as a system's name. Pages print only a count, and `--names` prints the list.

Ask the finding owner's office for every term that must never print, such as legal and trading names, systems and projects. Write them one a line in `denylist.txt`, beside finding.md for one finding or in `../findings/` for all of them. Matching ignores case and accents.

Ordinary words the check collected, such as a team called Records Desk, go in `role-words.txt` in either place. The page then reads `Deny list: 6 names; role-words.txt left out 1.` The deny list wins over role words, and the bank's full name never clears. One word in `role-words.txt` clears every run holding it, so the owner's office reads the `--names` output.

## Day 3: evidence and size assumptions

Copy invented documents in the bank's real formats into evidence/, each name starting with its evidence id, and draft the covers:

```sh
finding/finding covers ../findings/TRY-01
```

A file name holding a deny-list term stops it. In a trial run, `EV-02 Case Tracker aging export.csv` was refused, and covers ran once Case Tracker went into `role-words.txt`. Put a system name there only when the owner's office agrees it may print, because renaming the file instead breaks its link to the bank's records.

`finding size` prints assumed hours by hand and with the kit. Put timed figures in `size-assumptions.txt`, beside the finding or one folder up, using the wording in finding/README.md:

```text
minutes a claim by hand: 12
hours a status report: 3
```

`finding/finding size ../findings` then says how many values came from the file. The file changes no fingerprint and no release hash.

## Day 4: templates and record fields

A plan column the bank adds needs no code, because the check reads past it. Templates, plan columns and record fields are constants near the top of `finding/finding.py`, such as TEMPLATE_PLAN, PLAN_COLUMNS and RECORD_FIELDS. A new record line goes in both RECORD_FIELDS and TEMPLATE_RECORD. The owner's signature covers it unless it is also added to UNSIGNED_RECORD_FIELDS, and the page prints nothing from it until code does. Renaming a field the check reads needs code and a self-test case.

Then refresh the release file:

```sh
finding/finding --version
python3 -I finding/release.py
```

Before the refresh, `--version` prints `Changed since this release: finding/finding.py.`, each check page names the file, and the self-test fails. The refresh prints `RELEASE.json: 0.7.0+site.1, 8 files, 45 test files`, and a later change steps to 0.7.0+site.2. From then on every full check page and every signature names the site version. Copy RELEASE.json aside before each refresh to keep the old hashes.

A code change moves every fingerprint too, so make it between findings, before anyone signs.

## Day 5: acceptance and the log

Someone other than you accepts each change by rerunning three things:

1. Both self-tests from day 1 end in PASS.
2. The library run still shows 21 of 21 cases as expected.
3. The day 1 screen matches, apart from the intended change:

```sh
finding/finding check ../acceptance/cases/MRA-CMP-07 --today 2026-11-04 > ../acceptance/MRA-CMP-07-site.txt
diff ../acceptance/MRA-CMP-07.txt ../acceptance/MRA-CMP-07-site.txt
```

In a trial that added one plan template line and one record field, only the release on the Finding line differed. A change to what the tool prints also means editing the expected screens in `finding/selftest.py`, and the accepter reads that edit.

The tool keeps no log of site changes. Keep one page inside the bank with each site version, its date, the reason and the accepter. Add the hashes before and after, the release that signed each folder and the bank role that owns the kit.

## What stays open

The check ties each figure, date in digits and quotation to its own cited page, with no AI inside. It never compares documents, so two that disagree can both pass, and a wrong figure on the cited page ties. Whether a fix is right stays with people. Internal audit tests the fix, and only the issuer closes the finding. The tool has never run on a real finding.
