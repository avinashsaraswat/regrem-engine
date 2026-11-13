# Testing a closure package

This guide is for internal audit, model risk and anyone else the financial institution asks to test a closure package that RegRem Engine helped prepare. The check is deterministic code with no AI model inside, so a rerun on the same folder and date gives the page the team got. You can also make it fail on purpose before you rely on it. It looks for each figure and date written in digits, and each quotation, on the evidence page its cite names. Whether the fix works stays with you.

Run the commands from the kit root, the folder that holds finding/. They use the invented case IA-CMP-02, and on a real package you give the folder's own path. Windows users run `py -I finding\finding.py` in place of `finding/finding`.

## A half-day test plan

### 1. Copy the folder (15 minutes)

Work on a copy kept on a machine the institution approves. Copy the whole folder, so the hidden `.finding-state.json` that records which files were signed comes too. A copy made with `cp -R folder/* copy` leaves it behind.

```sh
cp -R finding/cases/IA-CMP-02 audit-02
```

### 2. Confirm the release (5 minutes)

```sh
finding/finding --version
```

On the published kit it reports that every file matches the release. A changed kit names each changed file or shows a site version such as 0.7.1+site.1. Then ask the team for the institution's log of each change.

### 3. Rerun the check and confirm the fingerprint (30 minutes)

```sh
finding/finding check audit-02
```

Your list should match the one the team showed you. The fingerprint is a hash of the letter, plan, evidence, memo, rulings and board approval, plus the tool's own code. This unsigned case prints it last, as `Ready to sign: the folder's fingerprint is e8196695.` A signed folder prints it on the signed line, and a `Changed since signing:` line names any covered file edited since. Compare the eight characters with the Fingerprint line in closure/record.md. For a second test, add `Internal audit tested fingerprint: e8196695` to the copy's record.md and check again. A match adds nothing to the page, and a mismatch names both values and asks internal audit for a fresh test.

### 4. Run the eval (20 minutes)

```sh
finding/finding eval audit-02
```

The eval plants one error at a time in a copy of the memo held in memory, and leaves the folder untouched. On this case it ends `Caught 30 of 38.` It caught every changed digit, swapped pair of digits and moved date. It caught none of the 6 figures replaced by another figure from the same page, and 11 of the 13 cites moved to another page. Each miss is listed by memo line for your workpaper.

### 5. Run the library (10 minutes)

```sh
finding/finding eval --library
```

It should report 21 cases, all as expected, 6 of them a known limit. Each known-limit case writes down something the check cannot see.

### 6. Plant your own errors (60 minutes)

The eval knows only six kinds of error and used five on this memo, so change the copy's memo yourself five to ten times. The command below plants six errors. They are two swapped digits, a moved date, a wrong month, a figure taken from elsewhere on the page, a changed quotation and a cite moved to another page.

```sh
sed -e 's/118 were/181 were/' \
    -e 's/on 2026-06-29/on 2026-06-19/' \
    -e 's/covers May 2026/covers June 2026/' \
    -e 's/402 of 410/410 of 410/' \
    -e 's/a deputy covers absence/the deputy "covers when the manager is on leave"/' \
    -e 's/2026-05-28 \[EV-21 p2\]/2026-05-28 [EV-21 p1]/' \
    audit-02/closure/memo.md > audit-02/memo.new
mv audit-02/memo.new audit-02/closure/memo.md
finding/finding check audit-02
```

The memo check now reads `14 claims, 9 tie, 5 on the list.` The quotation row shows the words the page holds. The second 410 still ties, because 410 appears on the cited page. The page also reports that the folder no longer matches the fingerprint you entered in step 3. Record 5 caught of 6 planted, with the release and the fingerprint from step 3.

### 7. Read for what the check cannot see (90 minutes)

An empty list means every claim was found on its cited page. A person still reads for five things:

- A version in force that is later than the version the institution approved.
- Figures that disagree between two documents, since each can tie to its own page.
- A scanned page whose typed text disagrees with the institution's own records.
- Work done before the control meant to precede it, such as staff handling complaints before their training.
- A status report claiming more than its evidence supports.

Read each sentence against its page too. A wrong figure the page also holds ties, as step 6 showed. So does a wrong month when the page lists that month too, as a monthly table does. The `Not checked:` line names figures written in words, bare years and dates with two-digit years. The page also counts ties that rest on text a person typed. In the invented cases every tie counts as typed, because the evidence is plain text and the check cannot tell an export from retyping. Put every typed tie in your sample. Compare the claim count with the memo's length, because a memo that makes no checkable claim still gets an empty list and a Ready to sign line.

### 8. Record the test (15 minutes)

In the live folder's closure/record.md, fill internal audit's reference, date and role, and put at least eight characters of the tested fingerprint on `Internal audit tested fingerprint:`. The owner's signature stands when you add them. If the folder changes later, every check asks internal audit to test again. When you send something back, someone on the team adds a `Sent back` line to closure/measures.md. A line ending `missed by the check` marks an item the check had passed, and the check page counts both.

## Limits

Every case here is invented, and the kit has not been run on a real finding. The counts above come from one small invented memo and predict nothing about your institution's papers. The check is a floor under a reviewer's reading. Whether the fix works, and whether the finding closes, stays with internal audit and the issuer.
