# The finding owner

This page is for the person on the business side who owns a finding, such as the Head of Complaints in the invented case MRA-CMP-07. The tool asks two things of you. You rule on each row the check could not tie, and once nothing is left you sign.

The check is plain code with no AI model in it, so one folder checked as of one date always prints the same page. It looks for each figure, date and quotation in the closure memo on the evidence page its cite names. Whether the fix works is left to you, internal audit and the issuer.

## The page you read

From the root folder of the repository:

```sh
python3 -I finding/finding.py check finding/cases/MRA-CMP-07 --today 2026-11-04
```

The `--today` option fixes the date so your screen matches this one, trimmed where it shows `...`:

```text
Finding MRA-CMP-07, a supervisory finding from the Supervisor dated 2026-01-15. Owner: Head of Complaints. Checked as of 2026-11-04, kit release 0.7.0.
...
Memo check: 13 claims, 7 tie, 3 on the list, 1 cleared.
  Line 8: 1,248 is cited to EV-07 p2, and the page does not hold it; the nearest figures on the page are 1,284 and 2. To rule, name: 1,248 #972adb19
  Line 10: EV-12, which is a draft, holds 4 claims, on lines 10, 15 and 16, that match its pages and wait on a person's signature. To rule, name: EV-12 draft #81b3b231
  Line 16: the sample period for M2 starts 2026-01-05, before the fix took effect on 2026-03-17, so the sample mixes items from before and after the fix. To rule, name: sample period for M2 #106ddd50
  Cleared: line 8, March 2026, by the Head of Complaints on 2026-11-04: The page says January to March, and the plan year is 2026.
  7 ties rest on text a person typed: 7 in plain-text evidence, none on a page typed into a cover.
  Not checked: 1 figure written in words, line 6 (three).
Signature: none yet.
...
Needs a person:
  Head of Complaints: M2, the list (3 rows).
...
```

The Owner field names the role your rulings and signature must carry. The command exits 1 while anyone still has something to do.

## What each row means

Each row opens with the memo line it concerns, and a row you can rule on ends with the words a ruling uses to name it.

- Line 8 says 1,248 and the cited page says 1,284, which looks like two digits swapped in typing. The memo is wrong.
- Line 10 is one row for a draft. The quality review EV-12 supports four claims in the memo, and they wait until someone signs it.
- Line 16 says the tested sample starts before the fix took effect, so it mixes items from both sides of the fix.

Other rows name a missing cite, a cite to a file that is not there, or a page with no text that someone has to type. No ruling clears a row for a memo or plan that calls the finding closed before the closer has recorded it, so someone rewords the line.

Below the rows, each Cleared line gives the role, date and reason of a past ruling. The Not checked line names figures the check skipped, such as a number written in words.

## How to rule

A ruling is one line in closure/rulings.md. It gives the memo line, the name the row prints at its end, the ruling, your role, a date and a reason.

```text
Line 16 | sample period for M2 #106ddd50 | cleared | Head of Complaints | 2026-11-04 | Items from before 2026-03-17 were drawn on purpose as a baseline error rate.
```

A `cleared` ruling takes the row off the list and prints your reason on every later page. To send a row back, rule `fix the memo`, or `fix the evidence` when a document must change or be signed again. That row stays on the list until the fix lands, and your line stays as a record that the check caught it.

The check ignores a ruling from another role, one dated after the check or one with no reason, and says why under the rows. The mark after `#` stands for the claim, its cite and its sentence. Reword the sentence or move the cite and the row returns under a new mark, so you rule again.

The tool accepts `cleared` on any row that offers a name, a wrong figure included, so the restraint is yours. Use it only when you can see the memo is right and why the check missed it, such as a figure the page spells out in words. Send a wrong figure back every time. A colleague or an AI assistant may draft rulings for you to accept. The check cannot tell who typed a line, so every line naming your role counts as yours.

## The fingerprint and the signature

Sign refuses while a row is on the list, a milestone is unsigned or the board has not approved the plan, among other reasons. When no refusal is left, sign shows the full check page first and then asks two questions. Here it runs on a copy of the second invented case:

```sh
cp -R finding/cases/IA-CMP-02 walk-02
python3 -I finding/finding.py sign walk-02 --today 2026-11-04
```

```text
Ready to sign: the folder's fingerprint is a381fa0f. Internal audit records this as what it tests.

Type the finding owner's role to sign: Head of Complaints
Fingerprint a381fa0fb6127b44856ff31c8aec81ebd754e9dc6f80c8d6ba23aee16c39ec41
Type its first eight characters to confirm: a381fa0f
Signed by the Head of Complaints on 2026-11-04, a date typed with --today on a machine dated 2026-11-11, fingerprint a381fa0f. Written to closure/record.md.
```

The fingerprint is one SHA-256 hash over the memo, your rulings, the letter, the plan, every evidence file, the board's approval and the tool's own code. Sign writes your role, the date, the full hash and the release into closure/record.md. Change any of those files later and the page asks for a fresh signature. Entries that internal audit or the closer add afterwards leave it standing. On a real finding, sign refuses `--today` and uses the machine's date.

A signature records a role and proves no identity. The terminal prompt only stops a script from signing by accident, so the financial institution's access controls decide who may run sign.

## Before you sign

Read the whole screen sign prints, then go back over these:

- Every Cleared line, above all any made before you held the role.
- The Not checked line and the count of ties on typed text.
- The misses that `python3 -I finding/finding.py eval <folder>` lists. On MRA-CMP-07 it catches 24 of 27 planted errors, and all three misses are a figure swapped for another on the same page.
- The five points the [Check section](../finding/README.md#check) leaves to a reader, such as figures that disagree between two documents.

An empty list is a floor, because a wrong figure that happens to sit on its cited page still ties. Read each sentence against its page.

To refuse, delete a cleared line or change it from `cleared`, and the row comes back. Or answer the role prompt with anything other than your role, and sign records nothing.

Every case here is invented, and the tool has not yet run on a real finding.
