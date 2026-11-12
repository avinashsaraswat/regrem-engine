# Contributing

Issues and pull requests are welcome, with one rule that comes before everything else.

## Never post real material

Never put confidential supervisory information or a document from a real financial institution in an issue, a pull request, a test or a library case. The same goes for text from a real finding and for a real person's or institution's name. That includes screenshots and screens pasted from a real finding folder. Use invented names, figures and dates instead. Every case in this repository is invented and has to stay that way, and an invented example shows a problem just as well.

## Reporting a problem

Open an issue with the command you ran, what it printed on an invented case, what you expected, your Python version and your operating system. Report a security weakness privately, as [SECURITY.md](SECURITY.md) says.

## Proposing a change

- Keep to the Python standard library, version 3.9 and later. The finding self-test checks that the tool's files import only modules on a fixed list and start no process.
- Add a self-test expectation for each behaviour you change, and a [library case](library/README.md) for a new kind of miss.
- A change to `finding/finding.py`, `finding/documents.py` or the five engine files the tool imports changes every finding's fingerprint. Say so in the pull request.
- Refresh `RELEASE.json` at the version it already names, as in `python3 -I finding/release.py 0.7.0`. After a change to engine code, also run `python3 -I tieout/gate.py release`.
- Run `python3 -I finding/selftest.py`, `python3 -I tieout/selftest.py` and `python3 -I finding/finding.py --version` before you open the pull request. CI runs the self-tests on Linux, macOS and Windows with Python 3.9 and 3.13.
- When a page shows a screen, paste the tool's real output. The self-test compares several pasted screens with what the tool prints.
- Write pages in plain English, with dates as YYYY-MM-DD.

## Licence

By contributing, you agree that your contribution is licensed under the Apache License 2.0, as section 5 of [LICENSE](LICENSE) sets out.
