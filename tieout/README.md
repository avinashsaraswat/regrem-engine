# tieout: the engine underneath

The finding tool ties each claim in a closure memo to its cited page with this engine. The file `finding/finding.py` imports `record.py`, `verify.py` and `words.py` unchanged, and the document reader imports `docx_reader.py`, which brings in `claims.py`. Those five files are part of every finding's fingerprint, so a change to any of them asks for a fresh signature.

The engine started as a tool that checks every figure, date, quotation and citation in a draft expert report against the record the report cites. The rest of that tool is here because the engine's own self-test runs on it:

- The command line is `tieout.py`, and `gate.py` holds its write gate and sign-off.
- The measurement, `measure.py`, plants errors in the invented matter and counts what reaches the drop log.
- An optional model step lives in `providers.py`. It is off by default, and it is the only module here that can connect to another machine. The engine's self-test also starts a stand-in server on this machine's loopback address to test it. The finding tool imports neither.
- The folder `fixture/matter-1/` holds an invented contract damages case, and every company, person, figure, date and page in it is made up.
- Two stand-ins serve the self-test. `fixture/stub_model.py` is the stand-in model it runs on 127.0.0.1, and `fixture/make_docx.py` builds Word copies of the invented report.

Run the engine's self-test from the repository root:

```sh
python3 -I tieout/selftest.py
```

It prints `selftest: PASS (77 expectations)`. `python3 -I tieout/tieout.py --version` checks the engine's code against `tieout/RELEASE.json`, which keeps the engine's own version, 0.3.3. After a change to an engine file, `python3 -I tieout/gate.py release` refreshes that file. Until then the engine's self-test fails and prints a note that says to run it.

The engine's measurement records, its batch history and its other test matters are not in this repository, and neither are the pages `tieout/docs/measuring.md` and `tieout/docs/reference.md` that `measure.py` and matter 1's key name, or the script that built that key. So `python3 -I tieout/tieout.py measure --regress` has no batch to compare with here, and it stops with exit 2 and says so.
