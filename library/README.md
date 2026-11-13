# The library

The library holds invented eval cases, one for each kind of miss a closure memo can hold. Each case says what the memo check must do about its miss, and every release has to pass all of them. Everything in this folder is invented.

```text
library/
  cases/      one eval case per kind of miss, run by `finding/finding eval --library`
```

## A case

A case is an invented example of a miss, small enough to read, with what the check must do about it:

```json
{
  "name": "figure-transposed",
  "kind": "figure",
  "why": "Two digits transposed when the figure was typed into the memo.",
  "evidence": [{"id": "EV-01", "pages": ["The team reclassified 1,284 complaints in the quarter."]}],
  "memo": "The team reclassified 1,248 complaints [EV-01 p1].",
  "expect": {"list": 1, "contains": ["the page does not hold it"]}
}
```

`finding/finding eval --library` builds each case in a temporary folder, runs the memo check and compares the result. It ends with the line `Library cases: 21, 21 as expected, 6 of them a known limit.`

The self-test runs the same cases, and RELEASE.json holds the hash of each one. So `finding/finding --version` and the self-test fail when a case is changed, added or removed without a refresh.

A case marked `known_limit` records what the check cannot see, such as a wrong figure that happens to sit on the cited page. Those cases keep the limit honest. If a later release catches one, its case changes in the same release.

## Adding a case

1. Write the miss in your own words, with invented names, figures and dates. A case never holds text from a real finding, a document from a real financial institution or confidential supervisory information.
2. Put it in `cases/` as one JSON file in the form above, and run `finding/finding eval --library`.
3. If the check gets it wrong, either fix the check in the same change or add `"known_limit": true` with a `why` that says what the check cannot see.
4. Refresh RELEASE.json at the version it already names, as in `python3 -I finding/release.py 0.7.1`, run both self-tests, and open a pull request as [CONTRIBUTING.md](../CONTRIBUTING.md) describes.
