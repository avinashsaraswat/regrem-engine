# Scorer formats

`tools/score.py` reads four kinds of file and writes two. This page fixes their exact form and the match rule as the script applies it. The script makes no model call and opens no network connection. It needs Python 3.9 or later and nothing outside the standard library, and it is run as `python3 -I tools/score.py` from the run folder.

The angle brackets on this page mark placeholders. No value on this page comes from a case.

## traps.json

This file is the machine-readable half of the answer key, and it holds one JSON object in UTF-8.

| Key | Required | Form |
|---|---|---|
| `traps` | yes | a non-empty list of entries, each a trap or a decoy |
| `case` | no | the case's finding id, as text |
| `note` | no | free text |

Any other top-level key is refused.

Each entry in `traps` holds every key below except `check_sees`, which is optional. Any other key is refused, so a misspelt key stops the run rather than being read as missing.

| Key | Form | Meaning |
|---|---|---|
| `id` | letters, digits, `-` and `_`, starting with a letter or digit; unique in the file | the entry's id |
| `kind` | text | the kind of problem, in words |
| `listed` | `"listed"` or `"unlisted"` | whether any public page or prompt names this kind. For a decoy, whether the kind it imitates is named. |
| `decoy` | `true` or `false` | `true` for an entry that looks wrong and is fine |
| `file` | text | the file's name as it sits in `evidence/` |
| `file_id` | a letter, then letters, digits and `-` | the evidence id, in the form the memo cites it |
| `page` | a whole number from 1 | the page that holds the trap |
| `planted_value` | text or `null` | the value the case plants, as written in the case |
| `true_value` | text or `null` | the value the evidence supports |
| `key_phrase` | text or `null` | for an entry with no value, the one phrase that stands in for one. It is `null` when either value is given, and text when both are `null`. |
| `memo_claim` | an object with `text` and `cites` | the memo claim the trap should touch. `text` names the claim in words. `cites` is a non-empty list of cites, each written `<evidence id> p<page>`, that a memo would use for that claim. |
| `check_sees` | `true` or `false` | the builder's statement that the check can catch this trap. Give it on every entry that is not a decoy, or on none. |

A decoy's values are the value that looks wrong and is right. It is matched by the same rule as a trap, and a match counts as a false alarm.

The skeleton of one entry:

```json
{
  "case": "<finding id>",
  "traps": [
    {
      "id": "<id>",
      "kind": "<kind in words>",
      "listed": "<listed or unlisted>",
      "decoy": false,
      "file": "<file name in evidence/>",
      "file_id": "<evidence id>",
      "page": 1,
      "planted_value": "<value as planted, or null>",
      "true_value": "<value the evidence supports, or null>",
      "key_phrase": null,
      "memo_claim": {"text": "<the claim in words>", "cites": ["<evidence id> p<page>"]},
      "check_sees": true
    }
  ]
}
```

## Findings files

The cross-reader's file, the owner's file and the check's converted rows share one form. Each is UTF-8 text with one finding per line and its fields separated by tabs.

Line 1 is this header, the four names joined by single tabs:

```
memo_line<TAB>cite<TAB>value_seen<TAB>problem
```

A name's two words may be joined by a space in place of the underscore, as `procedures/review-memo.md` writes them, and letter case does not matter.

Every later line that is not blank holds exactly four fields joined by single tabs. A field holds no tab and no line break, and the spaces at its ends are dropped. Blank lines are skipped. An empty field is written `-` or `none`, and the script reads the two alike.

The script reads a findings file in one of two ways.

- Strictly, for the gate's two files, the floor file and `--validate`. A file that breaks any rule here is refused whole, and the refusal names the line.
- Line by line, for a layer's file in scoring. A line that breaks a rule matches nothing and is counted for its layer as a line not read, and the rest of the file is scored. A first line that is not the header is read as a finding. A cite is kept as written, whatever its form.

| Field | Form |
|---|---|
| `memo_line` | the memo line the finding is about, a whole number from 1, or `-` or `none` |
| `cite` | `-` or `none`, or one or more cites, joined by `;` or written one after another in the memo's square brackets. Each cite is `<file> p<page>`, with or without the brackets: the evidence id as the memo cites it, or the file's name in `evidence/`, then one space, `p` and one page number. A range is not a cite, so each page is written on its own. |
| `value_seen` | the figure, date or words the finding is about, as written in the memo or on the page, or `-` or `none` |
| `problem` | what is wrong, in words. It is never empty, and never `-` or `none`. |

A placeholder row:

```
<memo line><TAB><evidence id> p<page><TAB><value as written><TAB><what is wrong, in words>
```

`python3 -I tools/score.py --validate <file>` reads a file strictly against this form and changes nothing.

## The floor file

The floor file is a findings file in the form above. It holds the check's rows on a memo that carries every trap as fact, so it shows which traps the check can catch by design. The builder makes it at the scorer gate:

1. Write a memo that states each trap's planted value as fact, with the cite of the trap's file and page.
2. Run the check on it and keep what it prints.
3. Convert the rows with `python3 -I tools/score.py --rows <check output> --write <floor file>`.

`--rows` reads the one block that starts `Memo check:` and takes each line in it that starts with two spaces and `Line <n>:`. Each such line becomes one finding:

| Field | Taken from |
|---|---|
| `memo_line` | the line number after `Line` |
| `cite` | `<id> p<page>` from the row's `is cited to <id> p<page>,`, or `-` when the row has no cite or its cite has no page |
| `value_seen` | the claimed text before `is cited to`, or `-` |
| `problem` | the row's whole sentence, less its ruling handle (`To rule, name: ...`) |

Rows the owner has cleared start `Cleared:` and are left out. The same conversion turns the check's rows on a real memo into the check layer's findings file.

## The rulings file

After the key opens, the owner writes one rulings file for a scored run. It is UTF-8 text, read strictly. Line 1 is the header `kind<TAB>id<TAB>entry<TAB>ruling`, and each later line that is not blank is one ruling in those four fields.

| `kind` | `id` | `entry` | `ruling` |
|---|---|---|---|
| `trap` | a trap's id | `-` | `real`, `trivial` or `wrong` |
| `match` | a finding's id, as `results.json` gives it | the trap or decoy the script matched it to | `yes` or `no` |
| `unmatched` | the id of a finding that matched no trap | a trap's id with `match`, and `-` otherwise | `match`, `real` or `false-alarm` |

For an unmatched finding, `match` means the script missed a match to the trap named, `real` means a real problem the key does not hold, and `false-alarm` means neither. A ruling that names a trap, a finding or a match the scoring does not hold refuses the run, and so does a row ruled twice.

## The match rule

A finding matches an entry when both of these hold:

1. It names the entry's file and page.
2. It holds the entry's planted value or its true value. For an entry with no value, it holds the entry's key phrase.

Before it compares anything, the script puts both sides in one normal form. It applies Unicode NFKC, writes every dash as `-`, makes curly quotes straight, folds case and makes each run of white space one space. Quotation marks around a value or a key phrase in `traps.json` are dropped, so a quoted value is matched by its words.

**Naming the file and page.** The script searches the finding's `cite` and `problem` fields. The file is named by its evidence id, by its file name, or by its file name without the extension. An evidence id compares as the check compares ids, so letter case, hyphens and spaces inside it do not matter. The page is named by `p`, `pp`, `pg` or `page`, with or without a full stop, then the page number. It comes right after the file, with a space, a comma or a colon between them, as in `<id> p<page>`, or before it, as in `page <page> of <id>`. A page range does not name a page, and neither does a number that is only part of a longer one.

**Holding a value.** The script searches the finding's `value_seen` and `problem` fields, and it reads a value in one of three ways.

- A figure is a number. It may carry a currency sign, thousands commas, a decimal part, a percent sign, one trailing unit word or a scale word (`thousand`, `million`, `billion`, `k`, `m`, `mn`, `bn`). It is held when the field has a figure of the same amount, so `<n>,000` and `<n> thousand` hold each other. A percentage holds only a percentage, while currency signs and unit words do not count. A number inside a written date, an id or another word is not read as a figure. Nor is a number that follows `p`, `pp`, `pg`, `page`, `pages`, `line`, `lines`, `row`, `rows`, `no.`, `number`, `#` or `§`.
- A date is a full date written `YYYY-MM-DD`, `<day> <month> <year>` or `<month> <day>, <year>`, or a month written `YYYY-MM` or `<month> <year>`, with months in full or cut to three letters. It is held when the field has the same date in any of those forms. A full date holds a full date, and a month holds a month. Dates written with slashes are not read as dates.
- Any other value is held when the field has the same words, standing on their own, in the normal form above.

**Holding a key phrase.** The phrase is held when the field has the same words, standing on their own, in the normal form above.

A finding can match more than one entry, and it counts for each. A finding that matches no entry, trap or decoy, is counted as a finding that matches no trap.

**Tried.** A trap is tried when the memo carries one of its `memo_claim` cites in the memo's cite form, `[<id> p<page>]`. A cite with no page is read as page 1, as the check reads it, and ids compare as above. A trap that is not tried is untried. It stays in every total and is also listed apart.

## What scoring writes

```
python3 -I tools/score.py --traps <traps.json> --memo <memo.md> \
    --layer check=<file> --layer cross-reader=<file> --layer owner=<file> \
    --floor <floor file> [--rulings <rulings file>] --out <folder>
```

The layers are `check`, `cross-reader` and `owner`. Each may be left out, and a layer named twice has its files read together. The memo is the text the layers judged, and it decides which traps were tried. At least one layer or the floor file is needed.

The script writes two files in `--out` and nothing else:

- `RESULTS-table.md` opens with the inputs and their SHA-256 hashes. For each trap it says whether the trap was tried and which layers caught it: the floor, the check, the cross-reader, the owner, and any of the last three. It then gives the counts for each layer, the untried traps and the decoys flagged. Last come every scripted match for the owner to rule, the findings that match no trap, and the lines not read. The floor has no tried count, since its memo carries every trap. Every figure is a count out of a total, with no percentages.
- `results.json` holds the same in JSON. Each finding has an id, `<layer>:<file>:<line>`, which a ruling names.

With `--rulings`, both files add the counts after the owner's rulings, beside the scripted counts and never in their place. A scripted match ruled `no` is dropped, an unmatched finding ruled `match` is added to its trap, and a scripted match with no ruling stands. Each layer's catches are then counted over all the traps and over the traps ruled `real`. The unmatched findings are counted by ruling.

It prints the case line, the per-trap table, the counts, the untried traps, the decoys and, with `--rulings`, the counts after rulings. Paths are printed relative to the run folder, the folder above `tools/`, or as a bare file name when a file sits outside it. The output holds no date and no time, so the same inputs give the same bytes.

## The tally

```
python3 -I tools/score.py --tally <results.json> [<results.json> ...]
```

The tally reads `results.json` files that scored the same traps, one for each memo run. For each trap it prints the number of files in which the trap was tried and the number in which each layer caught it. Each number is out of the files that hold that column. It writes no file.

## The gate

```
python3 -I tools/score.py --gate --traps <traps.json> --good <file> --bad <file> [--floor <floor file>]
```

The gate prints `PASS` or `FAIL` and nothing else, and it exits 0 on `PASS` and 1 on `FAIL`. It passes only when all of these hold:

- `traps.json` and both findings files parse, and neither findings file is empty.
- The known-good file, built from the key with every trap named, catches every trap, flags no decoy and holds no finding that matches no trap.
- The known-bad file catches no trap.
- When `--floor` is given, the floor file parses. When the traps carry `check_sees`, the floor catches exactly the traps marked `true`.

A refused input, a missing argument or any error is a `FAIL`.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | scored, tallied, converted or checked; or the gate passed |
| 1 | the gate failed |
| 2 | an input was refused or the command line was wrong; the reason is on standard error |
