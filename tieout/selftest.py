"""Self-test for the tie-out, stages 1 and 3, run on the invented matter in fixture/matter-1.

Purpose: one probe per check code, I1 to I7, A1 to A4, V1 to V8, P1 to P9, W1 to W9, S1 to S9
  and N1 to N9 (55 in all), and 22 scenario probes: 77 expectations.
  A code probe copies the clean engagement into a temporary folder, plants the one fault the code
  names, and expects that code and no other:
    I   intake lists the hit and exits 2; run stops on it (and runs on past I3)
    A V run lists exactly the planted item in its drop log with the expected code
    P   the proposal checks refuse a planted reply to the rules proposer on that code alone
    W   the write gate refuses the planted write with that code
    S   sign refuses at that check, and writes nothing
    W1, N1  a syntax-tree walk, kept in this file, finds no write call outside gate.py and no
        network import outside providers.py, and does find each form planted alone in a copy
        of a module
    N2 to N9  the chat adapter runs against fixture/stub_model.py, a stub model on 127.0.0.1,
        and the probe plants the refused act: a lookup or connection outside counsel-terms, a
        redirect, plain http, a proxy from the environment, a failing or slow reply, a forced
        HTTP error with an invented key, a refused peer during a call
  Some probes plant their fault more than one way, or run a control beside it that must tie or
  must stay listed (a block quote that pairs with its own cite, a page's slash date read in the
  matter's order, a token whose proposal failed still checked), so that removing the check the
  probe names makes it fail.
  Scenario probes 1 to 15 run the clean, untagged and planted drafts against
  key/expected.json, the Word twins, status, the carry-forward and reopening of rulings,
  quarantine, a proposer that faults its first attempt (a RulesClient subclass kept in this
  file and handed to the run by patching providers.make_client), the fingerprint and the
  ledger. Scenario probes 17 to 22 run the chat format end to end with job 4's record snippets, the custom auth
  header and fixed query, an environment proxy trap, replay from a run and from the committed
  fixture with measure --proposer, a replay miss and the key/ refusals, and the words.py case
  table. Scenario 16 runs
  last, so it covers every probe before it.
  Sign walks the expert through each clearing ruling at a terminal (S8). The probes drive that
  walk through gate.sign's terminal parameter, a test seam the command line never sets, so a
  person signing always meets the real sys.stdin.isatty() check, and the signoff.json the
  seam produces records tty false. S9 needs code that differs from RELEASE.json: the probe runs
  a copy of the tool from a temporary folder and edits the copy.
Reads: fixture/matter-1 (the engagement files, replay/untagged-chat, and key/expected.json for
  what each draft must give: the runner never opens key/, the selftest does), the tool's own
  modules, fixture/make_docx.py, which builds the Word twins, and fixture/stub_model.py.
Writes: temporary engagement folders, a temporary copy of the tool and .docx files, all under
  one temporary folder that is removed at the end. Nothing in the repository.
Network: loopback only, inside the stage 3 probes. Before the first probe every socket entry
  point is patched to raise, and an audit hook records and refuses any socket event the patch
  misses; scenario 16 expects none. A stage 3 probe opens a loopback window: the real socket
  functions come back, the hook lets through a socket made and a lookup, bind or connection on
  127.0.0.1, ::1 or localhost and nothing else, and the stub serves on 127.0.0.1; on leaving, the
  stub stops and the patches return. Keys are invented, and main() first clears every TIEOUT_
  and proxy variable from this process's environment without reading them. The tool runs in this
  process (tieout.main), never as a subprocess, so the patch and the hook cover every call.
  Run as python3 -I tieout/selftest.py, with -v to list each expectation as it passes.
Exit codes: 0 when every expectation holds, 1 when an expectation fails.
"""
import ast
import base64
import contextlib
import csv
import importlib
import io
import json
import os
import re
import shutil
import socket
import stat
import sys
import tempfile
import time
import traceback
import zipfile

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(1, os.path.join(HERE, "fixture"))

# --- sockets: patched before any tool module loads, observed until the end ----------------------

SOCKET_EVENTS = []  # every socket call or audit event the guard refused while the selftest runs
_GUARD = {"canary": False, "patched": {}, "real": {}, "window": False}  # window: a loopback window is open
LOOPBACK = ("127.0.0.1", "::1", "localhost")
SOCKET_NAMES = ("socket", "create_connection", "create_server", "getaddrinfo", "socketpair", "fromfd",
                "gethostbyname", "gethostbyname_ex", "gethostbyaddr")


def _refusing(name):
    def refused(*args, **kwargs):
        SOCKET_EVENTS.append("call socket.%s" % name)
        raise OSError("the selftest patches socket.%s to raise: no network" % name)
    return refused


class _RefusedSocket(socket.socket):
    """socket.socket replaced by a subclass that refuses to be made, so a module that subclasses
    socket.socket (ssl does) still imports, and any attempt to open one is recorded."""

    def __init__(self, *args, **kwargs):
        SOCKET_EVENTS.append("call socket.socket")
        raise OSError("the selftest patches socket.socket to raise: no network")


def _loopback_event(event, args):
    """Inside a loopback window: a socket made, or a lookup, bind or connection on loopback only."""
    if event == "socket.__new__":
        return True
    if event in ("socket.getaddrinfo", "socket.gethostbyname", "socket.gethostbyaddr"):
        host = args[0].decode("ascii", "replace") if isinstance(args[0], bytes) else str(args[0])
        return host.lower() in LOOPBACK
    if event in ("socket.bind", "socket.connect"):
        return isinstance(args[1], tuple) and str(args[1][0]) in ("127.0.0.1", "::1")
    return False


def _audit(event, args):
    if event.startswith("socket."):
        if _GUARD["window"] and _loopback_event(event, args):
            return
        SOCKET_EVENTS.append("audit %s" % event)
        raise OSError("the selftest refuses %s: no network" % event)  # aborts a C-level socket too
    if event == "tieout.selftest.canary":
        _GUARD["canary"] = True


def guard_sockets():
    """Patch every socket entry point to raise and record, and add an audit hook that records and
    refuses any socket event the patch misses (a C-level socket, a name lookup)."""
    for name in SOCKET_NAMES:
        if hasattr(socket, name):
            stub = _RefusedSocket if name == "socket" else _refusing(name)
            _GUARD["real"][name] = getattr(socket, name)
            setattr(socket, name, stub)
            _GUARD["patched"][name] = stub
    sys.addaudithook(_audit)
    sys.audit("tieout.selftest.canary")  # proves the hook is live without opening a socket


def repatch():
    """Put the patches back: when a loopback window closes, and after a replay probe, since
    providers.watch wraps whatever socket.getaddrinfo it finds."""
    for name, stub in _GUARD["patched"].items():
        setattr(socket, name, stub)


guard_sockets()

import claims  # noqa: E402
import docx_reader  # noqa: E402
import gate  # noqa: E402
import make_docx  # noqa: E402
import providers  # noqa: E402
import record  # noqa: E402
import stub_model  # noqa: E402
import tieout  # noqa: E402
import verify  # noqa: E402
import words  # noqa: E402

MATTER = os.path.join(HERE, "fixture", "matter-1")
KEY = os.path.join(MATTER, "key", "expected.json")
TOOL_MODULES = ("tieout", "claims", "docx_reader", "gate", "providers", "record", "verify", "words")
PLANTED = "report/draft-planted.md"
UNTAGGED = "report/draft-untagged.md"
REVIEWER = "Riley Reviewer"  # an invented reviewer: a name in ruled_by that is not the expert
SYNTHETIC_KEY = "sk-synthetic-selftest-0123456789"  # an invented key value for W8

EXPECTATIONS = []  # (label, probe) in the order they run


def expectation(label):
    def register(probe):
        EXPECTATIONS.append((label, probe))
        return probe
    return register


class Miss(Exception):
    """An expectation that did not hold, with what was seen instead."""


def check(ok, detail):
    if not ok:
        raise Miss(detail)


# --- files --------------------------------------------------------------------------------------


def read_text(path):
    """A fixture file as text with its line endings kept, so an edit is newline-neutral."""
    with open(path, encoding="utf-8", newline="") as fh:
        return fh.read()


def write_text(path, text):
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)


def edit(path, old, new):
    """Replace text that occurs exactly once; a fixture that drifted fails loudly here."""
    text = read_text(path)
    n = text.count(old)
    if n != 1:
        raise Miss("fixture text %r occurs %d times in %s, not once" % (old[:60], n, os.path.basename(path)))
    write_text(path, text.replace(old, new))


def load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def dump_json(path, data):
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(data, indent=1, ensure_ascii=False) + "\n")


def rmtree(path):
    """Remove a temporary folder; a read-only file (Windows keeps the attribute on a copy) is
    made writable first."""
    for dirpath, _, names in os.walk(path):
        for n in names:
            p = os.path.join(dirpath, n)
            if not os.path.islink(p):
                os.chmod(p, stat.S_IREAD | stat.S_IWRITE)
    shutil.rmtree(path)


# --- the lab: one temporary folder, one clean engagement, cheap copies ---------------------------


class Lab:
    def __init__(self):
        self.tmp = tempfile.mkdtemp(prefix="tieout-selftest-")
        self.cache = {}
        self.base = os.path.join(self.tmp, "base")
        os.makedirs(self.base)
        for name in ("matter.json", "counsel-terms.json"):
            shutil.copyfile(os.path.join(MATTER, name), os.path.join(self.base, name))
        for name in ("report", "record"):  # key/ stays behind: the runner never opens it
            shutil.copytree(os.path.join(MATTER, name), os.path.join(self.base, name), copy_function=shutil.copyfile)
        rc, out = tie(self.base, "init", self.base)
        if rc != 0:
            raise RuntimeError("init of the clean engagement failed: %s" % out)
        self.key = load_json(KEY)
        self.expert = load_json(os.path.join(self.base, "matter.json"))["expert"]

    def copy(self, name, source=None):
        dest = os.path.join(self.tmp, name)
        shutil.copytree(source or self.base, dest, copy_function=shutil.copyfile)
        return dest

    def once(self, name, build):
        """A shared engagement built on first use, for the probes that start from one run."""
        if name not in self.cache:
            self.cache[name] = build()
        return self.cache[name]


LAB = None


# --- driving the tool in this process, so the socket patch covers every call ---------------------


def tie(eng, *args, env=None, tool=None):
    """Run one tieout command in this process: (exit code, stdout and stderr)."""
    tool = tool or tieout
    out = io.StringIO()
    saved = {k: os.environ.get(k) for k in (env or {})}
    os.environ.update(env or {})
    try:
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            try:
                rc = tool.main(["--engagement", eng] + list(args))
            except SystemExit as exc:  # an argparse usage error
                rc = exc.code if isinstance(exc.code, int) else 2
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
    return rc, out.getvalue()


def run(eng, *args, env=None, tool=None):
    """tieout run: (exit code, output, run id or None)."""
    rc, out = tie(eng, "run", *args, env=env, tool=tool)
    m = re.search(r"^run (\S+):", out, re.M)
    return rc, out, (m.group(1) if m else None)


def run_dir(eng, rid):
    return os.path.join(eng, "run", rid)


def drop_log(eng, rid):
    """drop-log.csv as a list of row dicts."""
    with open(os.path.join(run_dir(eng, rid), "drop-log.csv"), encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def verdicts(eng, rid):
    return load_json(os.path.join(run_dir(eng, rid), "verdicts.json"))


def drop_codes(eng, rid):
    return sorted(r["code"] for r in drop_log(eng, rid))


def fill_rulings(eng, rid, fill):
    """Edit rulings.csv the way a person does in a spreadsheet: fill(row) changes the list
    [key, item, ruling, note, location, minutes, ruled_by] in place."""
    path = os.path.join(run_dir(eng, rid), "rulings.csv")
    with open(path, encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.reader(fh))
    for r in rows[1:]:
        fill(r)
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:
        csv.writer(fh).writerows(rows)
    return rows


def expert_clears(expert):
    """The expert's rulings for every row: the first is record-supports at a page that
    resolves, the rest expert-opinion."""
    state = {"first": True}

    def fill(r):
        if state["first"]:
            r[2:7] = ["record-supports", "the figure is on the next page", "DX-104 at 3", "2", expert]
            state["first"] = False
        else:
            r[2:7] = ["expert-opinion", "my own computation", "", "1", expert]
    return fill


def ledger_lines(eng):
    return read_text(os.path.join(eng, "ledger.jsonl")).splitlines()


def write_ledger(eng, lines):
    write_text(os.path.join(eng, "ledger.jsonl"), "\n".join(lines) + "\n")


def _reply(value):
    """A scripted answer: text, or an exception class the prompt raises, as input() raises
    EOFError at end of input and KeyboardInterrupt on Ctrl-C."""
    if isinstance(value, type) and issubclass(value, BaseException):
        raise value()
    return value


def sign(eng, rid, answers=(), reading=None, terminal=True, tool=None):
    """Sign a run through gate.sign's terminal seam. answers are the y/n replies in order (y once
    they run out); the reading check types the first eight characters of the fingerprint the
    summary printed, or reading when given. An answer or reading may be EOFError or
    KeyboardInterrupt, which that prompt raises. Returns {rc, code, text, signed, ledger_grew};
    rc is "escaped" when such an exception came out of gate.sign instead of a refusal."""
    t = tool or tieout
    g = t.gate
    lines, replies = [], list(answers)

    def out(s=""):
        lines.append(str(s))

    def ask(prompt):
        lines.append(prompt)
        if prompt.startswith("Type the first eight"):
            if reading is not None:
                return _reply(reading)
            shown = [ln for ln in "\n".join(lines).splitlines() if ln.startswith("fingerprint ")]
            return shown[-1].split(" ", 1)[1].replace(" ", "")[:8] if shown else ""
        return _reply(replies.pop(0) if replies else "y")

    before = len(ledger_lines(eng))
    matter, _ = t.load_config(eng)
    g.configure(eng, matter["key_env"])
    g.lock()
    code = ""
    try:
        rc = g.sign(eng, rid, matter, out=out, ask=ask, terminal=lambda: terminal)
    except g.GateRefused as exc:
        rc, code = 3, exc.code
        lines.append("refused %s: %s" % (exc.code, exc.reason))
    except (EOFError, KeyboardInterrupt) as exc:
        rc = "escaped"
        lines.append("%s escaped gate.sign" % type(exc).__name__)
    finally:
        g.unlock()
    if rc == 1:
        codes = sorted(set(re.findall(r"^(S\d) refused", "\n".join(lines), re.M)))
        code = ",".join(codes)
    text = "\n".join(lines)
    return {"rc": rc, "code": code, "text": text,
            "signed": os.path.isfile(os.path.join(run_dir(eng, rid), "signoff.json")),
            "ledger_grew": len(ledger_lines(eng)) != before}


def signed_fingerprint(eng, rid):
    return load_json(os.path.join(run_dir(eng, rid), "signoff.json"))["fingerprint"]


# --- shared engagements --------------------------------------------------------------------------


def planted_ruled():
    """The planted draft run once, with every drop-log item cleared by the expert: the starting
    point of the sign probes. Returns (engagement, run id)."""
    def build():
        eng = LAB.copy("planted-ruled")
        rc, out, rid = run(eng, "--draft", PLANTED)
        if rc != 1 or not rid:
            raise Miss("planted run: exit %s: %s" % (rc, out[-300:]))
        fill_rulings(eng, rid, expert_clears(LAB.expert))
        return eng, rid
    return LAB.once("planted-ruled", build)


def signable(name):
    """A fresh copy of the ruled planted engagement for one sign probe."""
    eng, rid = planted_ruled()
    return LAB.copy(name, eng), rid


def docx_matter(eng, draft_bytes):
    """Point a copied engagement at a Word draft with comment tags."""
    m = load_json(os.path.join(eng, "matter.json"))
    m["draft"], m["tag_mode"] = "report/draft.docx", "comments"
    dump_json(os.path.join(eng, "matter.json"), m)
    with open(os.path.join(eng, "report", "draft.docx"), "wb") as fh:
        fh.write(draft_bytes)


def draft_md():
    return read_text(os.path.join(MATTER, "report", "draft.md"))


def docx_run():
    """The .docx twin of the clean draft, run once (scenarios 4 and 6), then signed through the
    seam for the served-file scenarios (8 and 9). Returns (engagement, run id)."""
    def build():
        eng = LAB.copy("docx")
        docx_matter(eng, make_docx.build(draft_md()))
        rc, out, rid = run(eng)
        if not rid:
            raise Miss("docx run: exit %s: %s" % (rc, out[-300:]))
        return eng, rid, rc
    return LAB.once("docx", build)


def docx_signed():
    def build():
        eng, rid, _ = docx_run()
        res = sign(eng, rid)
        if res["rc"] != 0:
            raise Miss("signing the .docx run: exit %d %s: %s" % (res["rc"], res["code"], res["text"][-300:]))
        return eng, rid, signed_fingerprint(eng, rid)
    return LAB.once("docx-signed", build)


def untagged_run():
    def build():
        eng = LAB.copy("untagged")
        rc, out, rid = run(eng, "--draft", UNTAGGED)
        return eng, rid, rc, out
    return LAB.once("untagged", build)


# =================================================================================================
# I: intake checks
# =================================================================================================


def intake_probe(name, code, plant):
    eng = LAB.copy(name)
    plant(eng)
    rc, out = tie(eng, "intake")
    failing = re.findall(r"^(I\d) FAIL$", out, re.M)
    check(rc == 2 and failing == [code], "intake: exit %s, failing %s, expected exit 2 and only %s"
          % (rc, failing, code))
    rc, out, rid = run(eng)
    if code == "I3":  # run continues past I3 with the flag recorded
        check(rc == 0 and rid is not None, "run on a thin page: exit %s, expected the run to continue" % rc)
        intake = load_json(os.path.join(run_dir(eng, rid), "intake.json"))
        flagged = [c["code"] for c in intake["intake"] if not c["pass"]]
        check(flagged == ["I3"], "intake.json flags %s, expected only I3" % flagged)
    else:
        check(rc == 2 and rid is None and "stopped on intake (%s)" % code in out,
              "run: exit %s, expected it to stop on %s with exit 2" % (rc, code))


OS_FILES = (("record", "pages", ".DS_Store"), ("record", ".DS_Store"), ("record", "documents", "Thumbs.db"),
            ("record", "data", "desktop.ini"))  # files Finder and Windows Explorer write into a folder


@expectation("I1: a page file not named by a Bates id; files the operating system writes are ignored")
def probe_i1():
    eng = LAB.copy("i1-os")
    for parts in OS_FILES:
        with open(os.path.join(eng, *parts), "wb") as fh:
            fh.write(b"\x00\x00\x00\x01Bud1\x00\x10\xff not a record file")
    rc, out = tie(eng, "intake")
    check(rc == 0 and "intake: clean" in out, "intake with %s present: exit %s: %s"
          % (", ".join(p[-1] for p in OS_FILES), rc, [ln for ln in out.splitlines() if "FAIL" in ln or "/" in ln][:4]))
    listed = [p for p in record.load(eng, "mdy").files if p.split("/")[-1] in [x[-1] for x in OS_FILES]]
    check(not listed, "the record manifest lists %s" % listed)

    def plant(eng):
        write_text(os.path.join(eng, "record", "pages", "notabates.txt"),
                   "SYNTHETIC: a page whose file name is not a Bates id.\nThe capacity plan was approved.\n")
    intake_probe("i1", "I1", plant)


@expectation("I2: one Bates id twice")
def probe_i2():
    def plant(eng):
        pages = os.path.join(eng, "record", "pages")
        shutil.copyfile(os.path.join(pages, "BVW0000101.txt"), os.path.join(pages, "BVW-0000101.txt"))
    intake_probe("i2", "I2", plant)


@expectation("I3: a thin page")
def probe_i3():
    def plant(eng):  # PX-7 at 5, which no claim cites
        write_text(os.path.join(eng, "record", "pages", "BVW0000124.txt"),
                   "SYNTHETIC: invented test matter.\nPlan approval.\n")
    intake_probe("i3", "I3", plant)


@expectation("I4: an exhibit whose last page is before its first")
def probe_i4():
    def plant(eng):
        edit(os.path.join(eng, "record", "exhibits.csv"), "PX-2,First Amendment to Master Supply Agreement,BVW0000107,BVW0000108",
             "PX-2,First Amendment to Master Supply Agreement,BVW0000108,BVW0000107")
    intake_probe("i4", "I4", plant)


@expectation("I5: a transcript line without a [page:line] marker")
def probe_i5():
    def plant(eng):
        edit(os.path.join(eng, "record", "transcripts", "prewett.txt"), "[12:3] A. I am the Chief", "A. I am the Chief")
    intake_probe("i5", "I5", plant)


@expectation("I6: a CSV row shorter than its header")
def probe_i6():
    def plant(eng):
        edit(os.path.join(eng, "record", "data", "shipments.csv"), "2022-05,5012,593420.80,118.40", "2022-05,5012,593420.80")
    intake_probe("i6", "I6", plant)


@expectation("I7: a cite that names no exhibit in exhibits.csv, a tag holding two values, and a calc "
             "that names no cell")
def probe_i7():
    def plant(eng):
        edit(os.path.join(eng, "report", "draft.md"), "{{$7.01 million | DX-104 at 3}}", "{{$7.01 million | DX-109 at 3}}")
    intake_probe("i7", "I7", plant)

    def two_values(eng):  # the second value would go unchecked
        edit(os.path.join(eng, "report", "draft.md"), "{{4,780 units | Prewett Dep. 12:16-17}}",
             "{{4,780 and 4,610 units | Prewett Dep. 12:16-17}}")
    intake_probe("i7-two", "I7", two_values)

    def numbers_only(eng):  # arithmetic on the draft's own numbers ties against nothing in the record
        edit(os.path.join(eng, "report", "draft.md"), "calc: (shipments.csv!B17 + shipments.csv!B18 + shipments.csv!B19) / 3",
             "calc: (4734 + 4734 + 4734) / 3")
    intake_probe("i7-calc", "I7", numbers_only)


# =================================================================================================
# A and V: one planted item in the clean draft, and exactly that item in the drop log
# =================================================================================================


def drop_probe(name, edits, codes, reason=None, extra="", plant=None):
    """Plant edits in the clean draft, append extra blocks to it, let plant(eng) change the record,
    run it, and expect exactly codes in the drop log."""
    eng = LAB.copy(name)
    path = os.path.join(eng, "report", "draft.md")
    for old, new in edits:
        edit(path, old, new)
    if extra:
        write_text(path, read_text(path).rstrip("\r\n") + "\n\n" + extra + "\n")
    if plant:
        plant(eng)
    rc, out, rid = run(eng)
    check(rid is not None, "run did not complete: exit %s: %s" % (rc, out[-300:]))
    got = drop_codes(eng, rid)
    check(rc == 1 and got == sorted(codes), "drop log %s with exit %s, expected %s with exit 1" % (got, rc, sorted(codes)))
    rows = drop_log(eng, rid)
    if reason:
        check(all(reason in r["reason"] for r in rows), "drop-log reasons %s, expected each to say %r"
              % ([r["reason"] for r in rows], reason))
    return eng, rid, rows


QUOTED = ("Buyer shall purchase not less than 4,800 Units in each calendar month of the Term. The Minimum "
          "Purchase Commitment is the essence of this Agreement, and Supplier has reserved dedicated production "
          "capacity in reliance on it.")  # two sentences of PX-1 at 3, word for word


def quote_row(eng, rid):
    rows = [r for r in verdicts(eng, rid)["claims"] if r["kind"] == "quotation" and r["span"].startswith(QUOTED[:30])]
    return rows[0] if len(rows) == 1 else {"code": "%d rows" % len(rows), "pairing": "", "cite_resolved": ""}


@expectation("A1: an untagged value with no cite in its sentence or footnotes, sentence ends inside a "
             "closing quote or parenthesis, and a block quote that pairs with its own cite")
def probe_a1():
    # the planted value drops; an untagged block quote with its cite on the last line pairs with
    # that cite (A1) and ties, so it adds nothing to the drop log
    eng, rid, rows = drop_probe("a1", [("The agreement set the price at {{$118.40 | PX-1 at 3}} per unit",
                                        "The agreement set the price at $118.40 per unit")], ["no_cite"],
                                extra="> " + QUOTED + "\n> (PX-1 at 3.)")
    row = [r for r in verdicts(eng, rid)["claims"] if r["key"] == rows[0]["key"]][0]
    check(row["span"] == "$118.40" and row["pairing"] == "none" and row["proposed_by"] == "rules",
          "the dropped claim reads %r, pairing %r, proposed by %r" % (row["span"], row["pairing"], row["proposed_by"]))
    bq = quote_row(eng, rid)
    check((bq["code"], bq["pairing"], bq["cite_resolved"]) == ("tie", "A1", "PX-1 at 3"),
          "the block quote got %s, pairing %r, cite %r" % (bq["code"], bq["pairing"], bq["cite_resolved"]))
    # a period inside a closing quote ends the sentence: the quotation has no cite of its own and
    # does not borrow the next sentence's
    _, _, rows = drop_probe("a1b", [], ["no_cite"],
                            extra='Ms. Prewett said "the price was fixed for the whole term and never moved." '
                                  'Brindlecote shipped 4,812 units in September (PX-4 at 1).')
    check(rows[0]["kind"] == "quotation", "the dropped claim is %s %r" % (rows[0]["kind"], rows[0]["span"]))
    # a period inside a citation parenthetical ends the sentence, after Id. too, and each citation
    # stays with the sentence before it
    _, _, rows = drop_probe("a1c", [], ["no_cite"],
                            extra="The agreement set the price at $118.40 per unit. (PX-1 at 3.) The price stayed "
                                  "at $118.40 through 2022. (Id.) Brindlecote shipped 4,812 units in September.")
    check(rows[0]["span"] == "4,812", "the dropped claim is %r" % rows[0]["span"])


@expectation("A2: two untagged values and two cites that do not alternate")
def probe_a2():
    drop_probe("a2", [("Ostmarren held {{6,150 units | OSTL0004026}} in its terminals on the effective date and expected "
                       "network demand of {{58,800 units | OSTL0004024}} for the following year.",
                       "Ostmarren held 6,150 units in its terminals on the effective date and expected network demand "
                       "of 58,800 units (OSTL0004026; OSTL0004024) for the following year.")],
               ["ambiguous_association", "ambiguous_association"], reason="do not alternate")


@expectation("A3: an untagged Id. with no earlier cite in its paragraph")
def probe_a3():
    drop_probe("a3", [("The agreement set the price at {{$118.40 | PX-1 at 3}} per unit",
                       "The agreement set the price at $118.40 (Id. at 3) per unit")], ["id_no_antecedent"])


@expectation("A4: a footnote with two cites on an untagged date, and a block quote with one footnote cite")
def probe_a4():
    eng, rid, _ = drop_probe("a4", [("Ostmarren's procurement committee met on {{July 11, 2023 | DX-104 at 1}}.",
                                     "Ostmarren's procurement committee met on July 11, 2023[^4].")],
                             ["ambiguous_association"], reason="footnote holds 2 cites",
                             extra="[^4]: DX-104 at 1; see also DX-104 at 8.\n\n> " + QUOTED + "[^5]\n\n[^5]: PX-1 at 3.")
    bq = quote_row(eng, rid)
    check((bq["code"], bq["pairing"], bq["cite_resolved"]) == ("tie", "A4", "PX-1 at 3"),
          "the block quote got %s, pairing %r, cite %r" % (bq["code"], bq["pairing"], bq["cite_resolved"]))


@expectation("V1: an Id. pin that its Bates antecedent cannot take")
def probe_v1():
    drop_probe("v1", [("{{0.31% | Id.}}", "{{0.31% | Id. at 4}}")], ["cite_unparsed"])


@expectation("V2: an exhibit pin past the exhibit's last page")
def probe_v2():
    drop_probe("v2", [("The agreement set the price at {{$118.40 | PX-1 at 3}}",
                       "The agreement set the price at {{$118.40 | PX-1 at 9}}")], ["location_missing"])


@expectation("V3: a figure the cited page does not hold")
def probe_v3():
    _, _, rows = drop_probe("v3", [("{{$5.87 million | PX-3 at 2}}", "{{$5.97 million | PX-3 at 2}}")], ["figure_not_found"])
    check("5,872,855" in rows[0]["hint"], "hint %r, expected the nearest values on the page" % rows[0]["hint"])


def add_line(eng, rel, line):
    path = os.path.join(eng, *rel.split("/"))
    write_text(path, read_text(path).rstrip("\r\n") + "\n" + line + "\n")


@expectation("V4: a date the cited page does not hold, and a page's slash date read in the matter's order")
def probe_v4():
    drop_probe("v4", [("{{December 9, 2022 | PX-2 at 1}}", "{{December 19, 2022 | PX-2 at 1}}")], ["date_not_found"])
    # page 1 of PX-2 gains 3/4/2023, which the matter's mdy order reads as March 4: a draft date
    # with day and month swapped drops, and March 4 ties
    _, _, rows = drop_probe("v4b", [], ["date_not_found"],
                            plant=lambda eng: add_line(eng, "record/pages/BVW0000107.txt",
                                                       "A price forecast was issued 3/4/2023."),
                            extra="The forecast is dated {{April 3, 2023 | PX-2 at 1}} in one copy and "
                                  "{{March 4, 2023 | PX-2 at 1}} in the other.")
    check(rows[0]["span"] == "April 3, 2023", "the dropped claim is %r" % rows[0]["span"])
    # a page's ordinal dates read as dates, in both orders: the day after one still drops
    _, _, rows = drop_probe("v4c", [], ["date_not_found"],
                            plant=lambda eng: add_line(eng, "record/pages/BVW0000107.txt",
                                                       "The paper closes on 21st February, 1988, and again on March 15th, 1990."),
                            extra="The paper is dated {{February 22, 1988 | PX-2 at 1}} in one copy, "
                                  "{{February 21, 1988 | PX-2 at 1}} in another, {{21st February, 1988 | PX-2 at 1}} "
                                  "in a third, and {{March 15, 1990 | PX-2 at 1}} in the last.")
    check(rows[0]["span"] == "February 22, 1988", "the dropped claim is %r" % rows[0]["span"])
    # the comma is for an ordinal day-first date only: a number before "May, 1990" is no day
    check(not [m for m in record.DATE.finditer("Table 12 May, 1990") if m.group("d2")],
          "a plain number before a month and a comma read as a day")


@expectation("V5: a quotation with one word changed, and a word after a bracketed change that is on "
             "the page only inside a longer word")
def probe_v5():
    drop_probe("v5", [('{{"I would not say late deliveries were the reason"',
                       '{{"I would never say late deliveries were the reason"')], ["misquote"])
    # PX-1 at 3 reads "Buyer shall purchase not less than"; "chase" is there only inside "purchase"
    drop_probe("v5-bracket", [], ["misquote"],
               extra='The agreement required that the {{"[Buyer] chase not less than" | PX-1 at 3}} the minimum.')
    # a hyphen at a real line end reads as a joined word or a kept hyphen, and that tie is weak; the
    # same spacing inside a line is no break, so that quotation still drops
    eng, rid, rows = drop_probe(
        "v5-hyphen", [], ["misquote"],
        plant=lambda e: add_line(e, "record/pages/BVW0000107.txt",
                                 "The state-\nments of the three-\nstage plan hold, though a sub- committee differs."),
        extra='The page says {{"The statements of the three-stage plan hold" | PX-2 at 1}}, and it adds '
              '{{"though a subcommittee differs" | PX-2 at 1}}.')
    check(rows[0]["span"].startswith('"though a subcommittee'), "the dropped claim is %r" % rows[0]["span"])
    weak = [r for r in verdicts(eng, rid)["claims"] if r["span"].startswith('"The statements of')]
    check(len(weak) == 1 and weak[0]["pass"] and "line_end_hyphen" in weak[0]["weak_flags"],
          "the claim across two line-end hyphens reads %r" % weak)


@expectation("V6: a figure that does not round to its cell, and a cell's slash date read in the matter's order")
def probe_v6():
    def data(eng):
        write_text(os.path.join(eng, "record", "data", "dates.csv"),
                   "# SYNTHETIC: invented test matter.\nevent,date\nprice forecast issued,3/4/2023\n")
    _, _, rows = drop_probe("v6", [("{{16 months | model.csv!B2}}", "{{17 months | model.csv!B2}}")],
                            ["cell_mismatch", "cell_mismatch"], plant=data,
                            extra="The model dates the forecast to {{April 3, 2023 | dates.csv!B2}}, and the "
                                  "minutes date it to {{March 4, 2023 | dates.csv!B2}}.")
    got = sorted(r["span"] for r in rows)
    check(got == ["17 months", "April 3, 2023"], "the dropped claims are %s" % got)


@expectation("V7: a figure that rounds to two distinct values on its page")
def probe_v7():
    # PX-4 at 1 holds 4,610 and 4,812 units; both round to 5 thousand
    drop_probe("v7", [("{{4,610 units | Id.}}", "{{5 thousand units | Id.}}")], ["ambiguous_tie"])


@expectation("V8: a Bates pin outside its exhibit's range")
def probe_v8():
    drop_probe("v8", [("{{97.6% | DX-104 at OSTL0004017}}", "{{97.6% | DX-104 at OSTL0004021}}")], ["exhibit_mismatch"])


# =================================================================================================
# P: proposal checks on the rules proposer's replies over the untagged twin
# =================================================================================================


def proposal_lab():
    """The untagged twin's analysis, its proposer chunks and the rules proposer's reply to each."""
    def build():
        index = record.load(LAB.base, "mdy")
        grammar = claims.Grammar(index.grammar_names(), "mdy")
        draft = claims.read_draft(os.path.join(LAB.base, "report", "draft-untagged.md"))
        analysis = claims.analyse(draft, grammar)
        chunks = claims.chunks(draft, analysis, 6)
        client = providers.RulesClient(grammar.names(), "mdy")
        replies = []
        for c in chunks:
            text, _ = client.complete(model="", system="", user=claims.chunk_message(c, analysis), max_tokens=0)
            replies.append(json.loads(text))
        return {"index": index, "grammar": grammar, "draft": draft, "analysis": analysis, "chunks": chunks,
                "replies": replies}
    return LAB.once("proposals", build)


def accept(pl, ci, proposals):
    return claims.accept(json.dumps(proposals), pl["analysis"], pl["chunks"][ci], {}, "rules")


def proposal_probe(code, plant):
    """plant(pl, chunk index, reply copy) returns the planted reply, or None when that chunk
    offers no place for the fault. The first chunk that does is used."""
    pl = proposal_lab()
    for ci, reply in enumerate(pl["replies"]):
        planted = plant(pl, ci, [dict(p) for p in reply])
        if planted is None:
            continue
        clean = accept(pl, ci, reply)
        check(not clean["codes"], "the rules reply for chunk %d fails %s" % (ci + 1, sorted(clean["codes"])))
        res = accept(pl, ci, planted)
        check(res["codes"] == {code}, "chunk %d: the planted reply fails %s, expected only %s"
              % (ci + 1, sorted(res["codes"]), code))
        return pl, ci, planted, res
    raise Miss("no chunk of the untagged twin offers a place to plant %s" % code)


def _kind_swap(kind):
    return {"figure": "date", "date": "figure", "quote": "figure"}[kind]


def _block(pl, para):
    return pl["analysis"]["blocks"][claims.parse_where(para)]


@expectation("P1: a reply with a verdict key, or with text outside its one code fence, two fences, a fence "
             "inside a fence or an unclosed fence; one fence round the whole reply, with or without a language "
             "tag, is stripped")
def probe_p1():
    def plant(pl, ci, props):
        props[0]["verdict"] = "tie"
        return props
    pl, ci, _, res = proposal_probe("P1", plant)
    check(res["whole"] and not res["accepted"], "P1 should reject the reply whole; accepted %d" % len(res["accepted"]))
    deep = claims.accept("[" * 100000 + "]" * 100000, pl["analysis"], pl["chunks"][ci], {}, "model")
    check(deep["codes"] == {"P1"} and deep["whole"], "a reply nested 100,000 deep fails %s" % sorted(deep["codes"]))
    body, want = json.dumps(pl["replies"][ci]), len(accept(pl, ci, pl["replies"][ci])["accepted"])
    for fenced in ("```json\n%s\n```" % body, "\n  ```\r\n%s\r\n```  \n" % body):
        res = claims.accept(fenced, pl["analysis"], pl["chunks"][ci], {}, "model")
        check(not res["codes"] and len(res["accepted"]) == want, "a reply in one code fence fails %s, accepts %d of %d"
              % (sorted(res["codes"]), len(res["accepted"]), want))
    for bad in ("Here it is:\n```json\n%s\n```" % body, "```json\n%s\n```\nThat is all." % body,
                "```json\n%s\n```\n```json\n%s\n```" % (body, body), "```\n```json\n%s\n```\n```" % body,
                "```json\n%s" % body, "```%s!\n%s\n```" % (" " * 100000, body)):
        res = claims.accept(bad, pl["analysis"], pl["chunks"][ci], {}, "model")
        check(res["codes"] == {"P1"} and res["whole"], "the fenced reply %r fails %s, expected P1 alone"
              % (bad[:24], sorted(res["codes"])))


@expectation("P2: a span that is not verbatim in its paragraph; its token, like any unproposed token, "
             "stays in checking (rule 1)")
def probe_p2():
    def plant(pl, ci, props):
        props[0]["span"] += " and then some"
        return props
    pl, ci, planted, _ = proposal_probe("P2", plant)
    # rule 1: one proposal fails P2 and another is left out of the reply; the coverage sweep keeps
    # both tokens in checking, as the rules proposer's, beside the accepted ones. The rules words
    # candidates stay out of this reply, since a model's words proposal would add a claim.
    reply = [dict(p) for p in planted[1:-1] if p["kind"] != "words"] + [dict(planted[0])]
    res = claims.accept(json.dumps(reply), pl["analysis"], pl["chunks"][ci], {}, "model")
    check(res["codes"] == {"P2"} and len(res["accepted"]) == len(reply) - 1,
          "the reply fails %s with %d accepted" % (sorted(res["codes"]), len(res["accepted"])))
    built = claims.build_claims(pl["draft"], pl["analysis"], pl["grammar"], res["accepted"])
    want = sorted((t["where"], t["start"]) for t in pl["analysis"]["values"])
    got = sorted((c["where"], c["start"]) for c in built)
    check(got == want, "%d claims for %d untagged tokens" % (len(got), len(want)))
    accepted = {(a["where"], a["start"]) for a in res["accepted"]}
    chunk = set(pl["chunks"][ci]["items"])
    swept = [c for c in built if c["where"] in chunk and (c["where"], c["start"]) not in accepted]
    check(len(swept) == 2 and all(c["proposed_by"] == "rules" for c in swept) and
          all(c["proposed_by"] == "model" for c in built if (c["where"], c["start"]) in accepted),
          "chunk %d: %d token(s) kept by the sweep, proposed by %s" % (ci + 1, len(swept), [c["proposed_by"] for c in swept]))


@expectation("P3: a cite taken from another paragraph")
def probe_p3():
    def plant(pl, ci, props):
        for p in props:
            if not p["cite"]:
                continue
            home = _block(pl, p["para"])
            near = home["text"] + " ".join(pl["analysis"]["blocks"].get(("foot", n), {}).get("text", "")
                                           for _, n in home["refs"])
            for q in props:  # a cite that resolves, written in another paragraph of the chunk only
                if q["cite"] and q["para"] != p["para"] and q["cite"] not in near and not q["cite"].startswith("Id."):
                    p["cite"] = q["cite"]
                    return props
        return None
    proposal_probe("P3", plant)


@expectation("P4: a span that overlaps an accepted proposal")
def probe_p4():
    def plant(pl, ci, props):
        return props + [dict(props[0])]
    proposal_probe("P4", plant)


@expectation("P5: a span whose kind is not the kind code reads in it, or a kind that is a list or an object; "
             "a quote span exact to a clean quotation's interior snaps to its token, and a shorter span fails P5")
def probe_p5():
    def plant(pl, ci, props):
        props[0]["kind"] = _kind_swap(props[0]["kind"])
        return props
    proposal_probe("P5", plant)
    for odd in (["figure"], {"kind": "figure"}):  # a reply must not crash the runner
        proposal_probe("P5", lambda pl, ci, props: [dict(props[0], kind=odd)] + props[1:])
    pl = proposal_lab()
    snapped = False
    for ci, reply in enumerate(pl["replies"]):
        quotes = [p for p in reply if p["kind"] == "quote" and len(p["span"]) > 4
                  and p["span"][0] in ('"', "\u201c") and p["span"][-1] in ('"', "\u201d")]
        if not quotes:
            continue
        q = quotes[0]
        interior = dict(q, span=q["span"][1:-1])
        res = claims.accept(json.dumps([interior]), pl["analysis"], pl["chunks"][ci], {}, "model")
        check(not res["codes"] and len(res["accepted"]) == 1 and res["accepted"][0]["span"] == q["span"],
              "exact quotation interior failed %s or did not restore marks: %s" % (res["codes"], res["accepted"]))
        dup = claims.accept(json.dumps([q, interior]), pl["analysis"], pl["chunks"][ci], {}, "model")
        check("P4" in dup["codes"], "full quotation plus its interior did not fail P4: %s" % dup["codes"])
        short = claims.accept(json.dumps([dict(q, span=q["span"][1:-2])]), pl["analysis"], pl["chunks"][ci], {}, "model")
        check(short["codes"] == {"P5"}, "truncated quotation interior failed %s, expected only P5" % short["codes"])
        snapped = True
        break
    check(snapped, "no clean quotation token found in the untagged chunks")


@expectation("P6: one span holding two values")
def probe_p6():
    def plant(pl, ci, props):
        an = pl["analysis"]
        for where in pl["chunks"][ci]["items"]:
            block = an["blocks"][where]
            vals = [t for t in an["values"] if t["where"] == where]
            for a, b in zip(vals, vals[1:]):
                if a["sentence"] != b["sentence"]:
                    continue
                span = block["text"][a["start"]:b["end"]]
                if block["text"].count(span) != 1:
                    continue
                label = claims.where_label(where)
                kept = [p for p in props if str(p["para"]) != label]
                kind = {"figure": "figure", "date": "date", "quotation": "quote"}[a["kind"]]
                cite = a["pair"]["cite_text"] if not a["pair"]["code"] else ""
                return kept + [{"para": props[[str(p["para"]) for p in props].index(label)]["para"],
                                "span": span, "cite": cite, "kind": kind}]
        return None
    proposal_probe("P6", plant)


@expectation("P7: a cite that differs from the pairing code makes")
def probe_p7():
    state = {}

    def plant(pl, ci, props):
        an = pl["analysis"]
        for where in pl["chunks"][ci]["items"]:
            block = an["blocks"][where]
            toks = an["tokens"][where]
            for v in [t for t in an["values"] if t["where"] == where]:
                if v["pair"]["code"] or not v["pair"]["resolved"]:
                    continue
                others = [t for t in toks if t["kind"] == "cite" and t["sentence"] == v["sentence"]
                          and t.get("resolved") and t["resolved"]["text"] != v["pair"]["resolved"]]
                if not others:
                    continue
                span = claims.unique_span(block["text"], v, toks, [(t["start"], t["end"]) for t in block["tags"]])
                label = claims.where_label(where)
                mine = [p for p in props if str(p["para"]) == label and p["span"] == span]
                if len(mine) != 1:
                    continue
                mine[0]["cite"] = others[0]["text"]
                state.update(where=where, start=v["start"], cite=others[0]["text"])
                return props
        return None
    pl, ci, planted, res = proposal_probe("P7", plant)
    # the token stays checked: it drops as ambiguous_association with the proposer's cite as a
    # hint, never used
    built = claims.build_claims(pl["draft"], pl["analysis"], pl["grammar"], res["accepted"])
    claim = [c for c in built if c["where"] == state["where"] and c["start"] == state["start"]][0]
    verdict = verify.verify_claim(claim, pl["index"])
    check(verdict["code"] == "ambiguous_association" and state["cite"] in claim["pre"]["hint"],
          "the P7 token got %s with hint %r" % (verdict["code"], claim["pre"]["hint"] if claim["pre"] else ""))


def words_chunk(pl, para):
    """(chunk index, rules reply) for the chunk holding paragraph para."""
    for ci, c in enumerate(pl["chunks"]):
        if ("para", para) in c["items"]:
            return ci, [dict(p) for p in pl["replies"][ci]]
    raise Miss("no chunk holds paragraph %d" % para)


@expectation("P8: a words proposal whose value is not words.py's reading; with the right value a model's "
             "words proposal is checked like a figure in digits, and the rules candidate is listed, never checked")
def probe_p8():
    def plant(pl, ci, props):
        mine = [p for p in props if p["kind"] == "words"]
        if not mine:
            return None
        mine[0]["value"] = mine[0]["value"] + "1"
        return props
    proposal_probe("P8", plant)
    pl = proposal_lab()
    ci, reply = words_chunk(pl, 28)  # paragraph 28: "short of the minimum by seventy-five units"
    mine = [p for p in reply if p["kind"] == "words" and p["para"] == 28]
    check(len(mine) == 1 and mine[0]["value"] == "75", "the rules words candidates in paragraph 28: %s" % mine)
    bad = [dict(mine[0], value="751")]
    bad_res = claims.accept(json.dumps(bad), pl["analysis"], pl["chunks"][ci], {}, "model")
    bad_why = " ".join(w for r in bad_res["rows"] for w in r["why"])
    bad_rwhy = json.dumps(claims.retry_reasons(bad_res))
    check("reads as 75" in bad_why and "751" in bad_rwhy and "reads as" not in bad_rwhy and " 75" not in bad_rwhy,
          "P8 leaked words.py reading into retry_reasons: why=%r retry=%r" % (bad_why, bad_rwhy))
    model = claims.accept(json.dumps(mine), pl["analysis"], pl["chunks"][ci], {}, "model")
    rules = claims.accept(json.dumps(mine), pl["analysis"], pl["chunks"][ci], {}, "rules")
    check(not model["codes"] and not rules["codes"], "codes %s and %s" % (model["codes"], rules["codes"]))
    built = claims.build_claims(pl["draft"], pl["analysis"], pl["grammar"], model["accepted"])
    said = [c for c in built if c["proposed_by"] == "model"]
    verdict = verify.verify_claim(said[0], pl["index"]) if len(said) == 1 else {}
    check(len(said) == 1 and said[0]["kind"] == "figure" and said[0]["cite_resolved"] == "PX-4 at 2" and
          verdict.get("code") == "tie", "the model's words claim: %s, verdict %s" %
          ([(c["span"], c["kind"], c["cite_resolved"]) for c in said], verdict.get("code")))
    plain = claims.build_claims(pl["draft"], pl["analysis"], pl["grammar"], rules["accepted"])
    check(len(plain) == len(pl["analysis"]["values"]), "rules words candidates added claims: %d for %d tokens"
          % (len(plain), len(pl["analysis"]["values"])))
    eng, rid, _, _ = untagged_run()
    md = read_text(os.path.join(run_dir(eng, rid), "drop-log.md"))
    check("- para 28 s3: seventy-five, reads 75 (PX-4 at 2)" in md, "the drop log does not list the candidate")


@expectation("P9: a flag on a span that is no token, or with a reason off the list; a flag never changes "
             "the claim set")
def probe_p9():
    pl = proposal_lab()
    ci, reply = words_chunk(pl, 6)  # paragraph 6: "I reviewed 41 documents produced by the parties"
    kept = [p for p in reply if p["kind"] != "words" and not (p["para"] == 6 and p["span"] == "41")]
    for flag in ({"para": 6, "span": "41", "cite": "", "kind": "flag", "reason": "unimportant"},
                 {"para": 6, "span": "documents produced", "cite": "", "kind": "flag", "reason": "count_in_prose"}):
        res = accept(pl, ci, kept + [flag])
        check(res["codes"] == {"P9"}, "flag %r fails %s, expected only P9" % (flag["span"], sorted(res["codes"])))
    good = {"para": 6, "span": "41", "cite": "", "kind": "flag", "reason": "count_in_prose"}
    res = claims.accept(json.dumps(kept + [good]), pl["analysis"], pl["chunks"][ci], {}, "model")
    check(not res["codes"], "a flag on 41 fails %s" % sorted(res["codes"]))
    base = claims.build_claims(pl["draft"], pl["analysis"], pl["grammar"], accept(pl, ci, reply)["accepted"])
    flagged = claims.build_claims(pl["draft"], pl["analysis"], pl["grammar"], res["accepted"])
    rows = [verify.claim_row(c, verify.verify_claim(c, pl["index"])) for c in flagged]
    check(sorted(c["key"] for c in flagged) == sorted(c["key"] for c in base),
          "the flag changed the claim set: %d claims, %d without it" % (len(flagged), len(base)))
    hit = [r for r in rows if r["para"] == 6 and r["span"] == "41"]
    check(len(hit) == 1 and hit[0]["hint_source"] == "model-flag" and "count_in_prose" in hit[0]["hint"]
          and hit[0]["code"] == "no_cite", "the flagged token's row: %s" % hit)
    claim = [c for c in flagged if c["where"] == ("para", 6) and c["span"] == "41"][0]
    coded = verify.claim_row(claim, dict(verify.verify_claim(claim, pl["index"]), hint="the record holds it at PX-1 at 3",
                                         hint_source="code"))
    check(coded["hint_source"] == "code, model-flag" and coded["hint"].startswith("the record holds it at PX-1 at 3; ")
          and coded["hint"].endswith("count_in_prose"), "a flag on a row with a code hint: %s, %r"
          % (coded["hint_source"], coded["hint"]))


# =================================================================================================
# W: the write gate
# =================================================================================================


def gate_lab():
    """A fresh engagement with the gate configured on it."""
    eng = LAB.copy("w-%d" % len(os.listdir(LAB.tmp)))
    gate.configure(eng, "TIEOUT_API_KEY")
    return eng


def refused(path, data=b"x", create=True):
    """The code the gate refuses a write with, or 'written'."""
    try:
        gate.write(path, data, create=create)
        return "written"
    except gate.GateRefused as exc:
        return exc.code


@contextlib.contextmanager
def measure_scope():
    """The gate's measure scope pointed at a temporary tieout/ folder, so a probe of it can never
    write into the repository: gate.HERE is the measure scope's root."""
    saved = gate.HERE
    gate.HERE = os.path.join(LAB.tmp, "m-%d" % len(os.listdir(LAB.tmp)))
    os.makedirs(gate.HERE)
    try:
        yield gate.HERE
    finally:
        gate.HERE = saved


def refused_measure(path, data=b"{}", create=True):
    """The code the gate's measure scope refuses a write with, or 'written'."""
    try:
        gate.write(path, data, create=create, scope="measure")
        return "written"
    except gate.GateRefused as exc:
        return exc.code


# W1 and N1 are readings of the source: syntax-tree walks that live here, outside the released code,
# and scan the nine code files gate.CODE_FILES names.

OS_WRITES = {"remove", "unlink", "rename", "renames", "replace", "rmdir", "removedirs", "makedirs", "mkdir",
             "open", "fdopen", "write", "truncate", "ftruncate", "link", "symlink", "chmod", "chown", "lchown",
             "utime", "mkfifo", "mknod", "system", "popen", "fork", "forkpty", "posix_spawn", "posix_spawnp"}
OS_PREFIXES = ("exec", "spawn")  # os.execv, os.spawnl and the rest start another program
PATH_WRITES = {"write_text", "write_bytes", "touch", "unlink", "mkdir", "rmdir", "symlink_to", "hardlink_to"}
MODE_CALLS = ("open", "FileIO", "ZipFile", "TarFile")  # calls that write when their mode says so
WRITE_MODULES = ("shutil", "tempfile", "subprocess", "importlib", "multiprocessing", "pty", "ctypes")
NET_MODULES = ("urllib", "http", "socket", "ssl", "select")


def _os_write(name):
    return name in OS_WRITES or name.startswith(OS_PREFIXES)


def _call_name(f):
    return f.id if isinstance(f, ast.Name) else (f.attr if isinstance(f, ast.Attribute) else "")


def write_calls(source):
    """W1: every write-capable call or import in a module's source, as 'line: what'. It finds a
    write mode on open, io.FileIO, ZipFile and TarFile; the os calls that write, remove, rename or
    start a program, also when imported by name (from os import remove); pathlib's write calls;
    an import of shutil, tempfile, subprocess, importlib, multiprocessing, pty or ctypes; and any
    __import__() call. It is a reading of the source, so a module that hides a write through
    getattr or a name built from a string would pass it. The controls for that are S5's
    re-performance from hashed inputs, the fingerprint in the certification (it covers the code
    hash), the ledger head kept outside the folder and the served-file check, as tieout/README.md
    says under what the tool cannot catch."""
    out = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name.split(".")[0] in WRITE_MODULES:
                    out.append("%d: imports %s" % (node.lineno, a.name))
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if mod.split(".")[0] in WRITE_MODULES:
                out.append("%d: imports from %s" % (node.lineno, mod))
            elif mod == "os":
                for a in node.names:
                    if a.name == "*" or _os_write(a.name):
                        out.append("%d: from os imports %s" % (node.lineno, a.name))
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        name = _call_name(f)
        if name == "__import__":
            out.append("%d: __import__()" % node.lineno)
        elif name in MODE_CALLS:
            mode = node.args[1] if len(node.args) > 1 else next((k.value for k in node.keywords if k.arg == "mode"), None)
            m = mode.value if isinstance(mode, ast.Constant) and isinstance(mode.value, str) else ("" if mode is None else "?")
            owner = f.value.id if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) else ""
            if owner == "os" or m == "?" or any(ch in m for ch in "wax+"):
                out.append("%d: %s with mode %r" % (node.lineno, name, m))
        elif isinstance(f, ast.Attribute):
            owner = f.value.id if isinstance(f.value, ast.Name) else ""
            if (owner == "os" and _os_write(name)) or owner in WRITE_MODULES or name in PATH_WRITES:
                out.append("%d: %s.%s()" % (node.lineno, owner or "<object>", name))
    return out


def network_imports(source):
    """N1: every import of urllib, http, socket, ssl or select in a module's source, including a
    dynamic one through __import__() or importlib.import_module() with that name or with a name
    the source does not spell out. Like write_calls, it reads the source, so an import reached
    through getattr passes it, and the same controls apply."""
    out = []
    for node in ast.walk(ast.parse(source)):
        names = []
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or ""]
        elif isinstance(node, ast.Call) and _call_name(node.func) in ("__import__", "import_module"):
            arg = node.args[0] if node.args else None
            target = arg.value if isinstance(arg, ast.Constant) and isinstance(arg.value, str) else "?"
            if target == "?" or target.split(".")[0] in NET_MODULES:
                out.append("%d: imports %s dynamically" % (node.lineno, target))
        for n in names:
            if n.split(".")[0] in NET_MODULES:
                out.append("%d: imports %s" % (node.lineno, n))
    return out


W1_PLANTS = (  # each one a way to write, planted alone in a copy of verify.py
    "def leak(p):\n    with open(p, 'w') as fh:\n        fh.write('x')\n",
    "import os\n\ndef leak(p):\n    os.remove(p)\n",
    "import os\n\ndef leak(p, q):\n    os.rename(p, q)\n",
    "import os\n\ndef leak(p, q):\n    os.replace(p, q)\n",
    "import shutil\n",
    "import pathlib\n\ndef leak(p):\n    pathlib.Path(p).write_text('x')\n",
    "import os\n\ndef leak(fd):\n    os.fdopen(fd, 'w').write('x')\n",
    "import subprocess\n",
    "from os import remove\n",
    "import zipfile\n\ndef leak(p):\n    zipfile.ZipFile(p, 'w').close()\n",
    "def leak():\n    return __import__('shutil')\n",
)


@expectation("W1: only gate.py writes, by a syntax-tree walk of every other module")
def probe_w1():
    hits = {}
    for name in gate.CODE_FILES:
        if name != "gate.py":
            found = write_calls(read_text(os.path.join(HERE, name)))
            if found:
                hits[name] = found
    check(not hits, "write calls outside gate.py: %s" % hits)
    base = read_text(os.path.join(HERE, "verify.py")) + "\n\n"
    missed = [plant.strip().splitlines()[-1].strip() for plant in W1_PLANTS if not write_calls(base + plant)]
    check(not missed, "the walk missed, each planted in a copy of verify.py: %s" % missed)


@expectation("W2: a target off the write allowlist, in the engagement and the measure scope")
def probe_w2():
    gate_lab()
    got = [refused("notes.txt"), refused("report-copy/draft.md")]
    with measure_scope():
        got += [refused_measure("notes.txt"), refused_measure("batches/sub/b.json")]
    check(got == ["W2"] * 4, "got %s, expected W2 for each" % got)


@expectation("W3: a protected target, and protected wins over allowed")
def probe_w3():
    gate_lab()
    got = [refused("report/draft.md", create=False), refused("record/pages/new.txt"), refused("matter.json", create=False),
           refused("key/expected.json"), refused("run/../counsel-terms.json", create=False)]
    with measure_scope():  # measure.py's records sit beside code, fixtures and keys it must not touch
        got += [refused_measure("measure.py"), refused_measure("fixture/matter-1/key/expected.json"),
                refused_measure("RELEASE.json")]
    check(got == ["W3"] * 8, "got %s, expected W3 for each" % got)


@expectation("W4: an unflagged create, a second write of a write-once file, a closed run")
def probe_w4():
    gate_lab()
    got = [refused("run/x1/note.txt", create=False)]
    gate.write("run/x1/verdicts.json", b"{}", create=True)
    got.append(refused("run/x1/verdicts.json", b"{}", create=False))
    gate.write("run/x2/signoff.json", b"{}", create=True)
    got.append(refused("run/x2/late.txt"))
    with measure_scope():  # an unflagged create of FROZEN.json, and a batch file written twice
        got.append(refused_measure("FROZEN.json", create=False))
        gate.write("batches/2026-01-01-b01.json", b"{}", create=True, scope="measure")
        got.append(refused_measure("batches/2026-01-01-b01.json", create=False))
    check(got == ["W4"] * 5, "got %s, expected W4 for each" % got)


@expectation("W5: one write over 16 MB, and a run folder over its cap")
def probe_w5():
    eng = gate_lab()
    got = [refused("run/x1/big.bin", b"0" * (16 * 1024 * 1024 + 1))]
    check(not os.path.exists(os.path.join(eng, "run", "x1", "big.bin")), "the oversize write touched the disk")
    saved = gate.MAX_RUN
    gate.MAX_RUN = 1000  # a small folder cap stands in for 512 MB, so the probe writes kilobytes
    try:
        gate.write("run/x2/a.bin", b"0" * 600, create=True)
        got.append(refused("run/x2/b.bin", b"0" * 600))
    finally:
        gate.MAX_RUN = saved
    check(got == ["W5", "W5"], "got %s, expected W5 for each" % got)


@expectation("W6: a target outside the engagement folder, or through a symlink")
def probe_w6():
    eng = gate_lab()
    got = [refused("../outside.txt"), refused(os.path.join(os.path.dirname(eng), "elsewhere", "x.txt"))]
    with measure_scope():
        got.append(refused_measure("../outside.json"))
    os.makedirs(os.path.join(eng, "run", "x1"))
    try:  # a link inside an allowed folder that leads to the record: every part of the target lies inside
        os.symlink(os.path.join(eng, "record"), os.path.join(eng, "run", "x1", "link"))
    except (OSError, NotImplementedError, AttributeError):
        pass  # Windows without the symlink privilege: the outside-path cases still run
    else:
        got.append(refused("run/x1/link/x.txt"))
    check(got and all(g == "W6" for g in got), "got %s, expected W6 for each" % got)


@expectation("W7: a ledger append whose prev is no longer the head")
def probe_w7():
    eng = gate_lab()
    stale = gate.ledger_entry("probe", "x1", b"first")
    gate.ledger_append(gate.ledger_entry("probe", "x1", b"second"))
    n = len(ledger_lines(eng))
    try:
        gate.ledger_append(stale)
        got = "appended"
    except gate.GateRefused as exc:
        got = exc.code
    check(got == "W7" and len(ledger_lines(eng)) == n, "got %s, expected W7 and no line appended" % got)


@expectation("W8: bytes holding the key value")
def probe_w8():
    eng = gate_lab()
    saved = os.environ.get("TIEOUT_API_KEY")
    os.environ["TIEOUT_API_KEY"] = SYNTHETIC_KEY
    try:
        gate.write("run/x1/k.txt", b"the key is " + SYNTHETIC_KEY.encode("utf-8"), create=True)
        got, msg = "written", ""
    except gate.GateRefused as exc:
        got, msg = exc.code, str(exc)
    finally:
        if saved is None:
            os.environ.pop("TIEOUT_API_KEY", None)
        else:
            os.environ["TIEOUT_API_KEY"] = saved
    check(got == "W8" and SYNTHETIC_KEY not in msg and not os.path.exists(os.path.join(eng, "run", "x1", "k.txt")),
          "got %s (%s), expected W8 with the value never printed" % (got, msg))


@expectation("W9: a malformed allowlist and a cap that is not a number fail closed")
def probe_w9():
    gate_lab()
    got = []
    for attr, broken in (("ALLOW", None), ("MAX_WRITE", "sixteen")):
        saved = getattr(gate, attr)
        setattr(gate, attr, broken)
        try:
            got.append(refused("run/x1/%s.txt" % attr.lower()))
        finally:
            setattr(gate, attr, saved)
    check(got == ["W9", "W9"], "got %s, expected W9 for each" % got)


# =================================================================================================
# S: sign, each check refusing before anything is written
# =================================================================================================


def sign_probe(res, rc, code):
    check(res["rc"] == rc and res["code"] == code, "sign: exit %s at %r, expected exit %d at %s: %s"
          % (res["rc"], res["code"], rc, code, res["text"].strip().splitlines()[-1:]))
    check(not res["signed"] and not res["ledger_grew"], "a refused sign wrote signoff.json or a ledger line")


@expectation("S1: the run's outputs line is missing from the ledger")
def probe_s1():
    eng, rid = signable("s1")
    lines = ledger_lines(eng)
    check(json.loads(lines[-1])["event"] == "outputs", "the ledger does not end on the run's outputs line")
    write_ledger(eng, lines[:-1])
    sign_probe(sign(eng, rid), 3, "S1")


@expectation("S2: the draft changed after the run")
def probe_s2():
    eng, rid = signable("s2")
    path = os.path.join(eng, PLANTED)
    write_text(path, read_text(path) + " ")
    sign_probe(sign(eng, rid), 3, "S2")


@expectation("S3: matter.json changed after the run, and counsel-terms.json changed after the run")
def probe_s3():
    eng, rid = signable("s3")
    m = load_json(os.path.join(eng, "matter.json"))
    m["max_tokens"] += 1
    dump_json(os.path.join(eng, "matter.json"), m)
    sign_probe(sign(eng, rid), 3, "S3")
    eng, rid = signable("s3-terms")  # the counsel-terms control: new terms need a new run
    update_json(os.path.join(eng, "counsel-terms.json"), {"timeout_seconds": 30})
    sign_probe(sign(eng, rid), 3, "S3")


@expectation("S4: a record file added after the run")
def probe_s4():
    eng, rid = signable("s4")
    write_text(os.path.join(eng, "record", "pages", "BVW0000135.txt"),
               "SYNTHETIC: invented test matter.\nA page produced after the run, holding enough words to index.\n")
    sign_probe(sign(eng, rid), 3, "S4")


@expectation("S5: verdicts.json edited and its ledger line recomputed")
def probe_s5():
    eng, rid = signable("s5")
    rdir = run_dir(eng, rid)
    doc = verdicts(eng, rid)
    row = [r for r in doc["claims"] if not r["pass"]][0]
    row.update(code="tie", reason="", hint="", hint_source="")
    row["pass"] = True
    doc["counts"] = {}
    for r in doc["claims"]:
        doc["counts"][r["code"]] = doc["counts"].get(r["code"], 0) + 1
    doc["counts"] = dict(sorted(doc["counts"].items()))
    with open(os.path.join(rdir, "verdicts.json"), "wb") as fh:
        fh.write((json.dumps(doc, indent=1, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8"))
    # the full rewrite S5 exists to catch: recompute the outputs line so S1 still verifies
    lines = ledger_lines(eng)
    last = json.loads(lines[-1])
    last["sha256"] = record.sha256_bytes(gate.outputs_payload(rdir))
    write_ledger(eng, lines[:-1] + [json.dumps(last, separators=(",", ":"))])
    sign_probe(sign(eng, rid), 3, "S5")


@expectation("S6: a reviewer's name in ruled_by, a blank ruled_by, and a location that does not resolve")
def probe_s6():
    eng, rid = signable("s6")
    fill_rulings(eng, rid, lambda r: r.__setitem__(6, REVIEWER) if r[2] == "expert-opinion" and REVIEWER not in r else None)
    res = sign(eng, rid)
    sign_probe(res, 1, "S6")
    check(REVIEWER in res["text"], "S6 did not name the reviewer in ruled_by")
    eng, rid = signable("s6b")
    fill_rulings(eng, rid, lambda r: r.__setitem__(4, "DX-104 at 99") if r[2] == "record-supports" else None)
    sign_probe(sign(eng, rid), 1, "S6")
    # a blank ruled_by is a proposed ruling, which clears nothing
    eng, rid = signable("s6c")
    fill_rulings(eng, rid, lambda r: r.__setitem__(6, "") if r[2] == "expert-opinion" else None)
    res = sign(eng, rid)
    sign_probe(res, 1, "S6")
    check("ruled_by is blank" in res["text"], "S6 did not name the blank ruled_by")


@expectation("S7: a rulings.csv row whose key is not in the drop log")
def probe_s7():
    eng, rid = signable("s7")
    path = os.path.join(run_dir(eng, rid), "rulings.csv")
    with open(path, "a", encoding="utf-8", newline="") as fh:
        csv.writer(fh).writerow(["c-000000", "a row from another run", "expert-opinion", "", "", "1", LAB.expert])
    res = sign(eng, rid)
    sign_probe(res, 1, "S7")
    check("c-000000" in res["text"], "the quarantined row was not named")


@expectation("S8: no terminal, an n, a failed reading check, and end of input or Ctrl-C at a prompt")
def probe_s8():
    for name, kwargs in (("s8a", {"terminal": False}), ("s8b", {"answers": ["y", "n"]}),
                         ("s8c", {"reading": "00000000"}), ("s8e", {"answers": ["y", EOFError]}),
                         ("s8f", {"reading": KeyboardInterrupt})):
        eng, rid = signable(name)
        res = sign(eng, rid, **kwargs)
        sign_probe(res, 1, "S8")
        if name in ("s8e", "s8f"):
            check("ended the session before confirming" in res["text"], "%s: %s" % (name, res["text"].splitlines()[-1:]))
    # the command line has no seam: with stdin a pipe, tieout sign meets the real check
    eng, rid = signable("s8d")
    saved = sys.stdin
    sys.stdin = io.StringIO("y\n" * 20)
    try:
        rc, out = tie(eng, "sign", "--run", rid)
    finally:
        sys.stdin = saved
    check(rc == 1 and "S8 refused: stdin is not a terminal" in out and
          not os.path.exists(os.path.join(run_dir(eng, rid), "signoff.json")),
          "tieout sign over a pipe: exit %s: %s" % (rc, out.strip().splitlines()[-1:]))


@contextlib.contextmanager
def tool_from(folder):
    """Load the tool's modules from a copy in folder for the length of the block, then put the
    real ones back."""
    saved = {n: sys.modules.pop(n) for n in TOOL_MODULES if n in sys.modules}
    path = list(sys.path)
    sys.path.insert(0, folder)
    try:
        yield importlib.import_module("tieout")
    finally:
        for n in TOOL_MODULES:
            sys.modules.pop(n, None)
        sys.modules.update(saved)
        sys.path[:] = path


@expectation("S9: the running code differs from RELEASE.json and intake.json")
def probe_s9():
    folder = os.path.join(LAB.tmp, "tool-copy")
    os.makedirs(folder)
    for name in gate.CODE_FILES + ("RELEASE.json", "matter.example.json", "counsel-terms.example.json"):
        shutil.copyfile(os.path.join(HERE, name), os.path.join(folder, name))
    shutil.copytree(os.path.join(HERE, "prompts"), os.path.join(folder, "prompts"), copy_function=shutil.copyfile)
    eng = LAB.copy("s9")
    with tool_from(folder) as copy:
        check(os.path.dirname(os.path.abspath(copy.__file__)) == os.path.abspath(folder), "the tool copy did not load")
        rc, out, rid = run(eng, "--draft", PLANTED, tool=copy)
        check(rc == 1 and rid, "run from the tool copy: exit %s" % rc)
        fill_rulings(eng, rid, expert_clears(LAB.expert))
        with open(os.path.join(folder, "verify.py"), "a", encoding="utf-8", newline="\n") as fh:
            fh.write("\n# a line added after the run\n")
        res = sign(eng, rid, tool=copy)
    sign_probe(res, 3, "S9")


# =================================================================================================
# N1: the network rule
# =================================================================================================


@expectation("N1: only providers.py may import urllib, http, socket, ssl or select")
def probe_n1():
    hits = {}
    for name in gate.CODE_FILES:
        if name != "providers.py":
            found = network_imports(read_text(os.path.join(HERE, name)))
            if found:
                hits[name] = found
    check(not hits, "network imports outside providers.py: %s" % hits)
    base = read_text(os.path.join(HERE, "claims.py")) + "\n\n"
    plants = ("from urllib import request\n", "import http.client\n", "import socket\n", "import ssl\n",
              "import select\n", "def fetch():\n    return __import__('socket')\n",
              "import importlib\n\ndef fetch(name):\n    return importlib.import_module(name)\n")
    missed = [p.strip().splitlines()[-1].strip() for p in plants if not network_imports(base + p)]
    check(not missed, "the walk missed, each planted in a copy of claims.py: %s" % missed)


# =================================================================================================
# N2 to N9: the chat adapter's egress checks, against a stub model on 127.0.0.1
# =================================================================================================

API_KEY = "sk-invented-selftest-key-0123456789"  # an invented key; the selftest never reads a real one
PROXY_AUTH = "synthetic-user:invented-proxy-pass"  # invented proxy credentials
PROXY_VARS = ("https_proxy", "HTTPS_PROXY", "http_proxy", "HTTP_PROXY", "all_proxy", "ALL_PROXY")
PARA_TEXT = "the deposition testimony of two witnesses"  # words of paragraph 6, in the first chunk sent


@contextlib.contextmanager
def loopback():
    """A loopback window (see the header). Yields serve(**options), which starts a stub model on
    127.0.0.1 with stub_model.serve's options. On leaving, every stub stops and the patches return,
    so a probe outside a window still meets them."""
    for name, real in _GUARD["real"].items():
        setattr(socket, name, real)
    _GUARD["window"] = True
    servers = []

    def serve(**options):
        servers.append(stub_model.serve(**options))
        return servers[-1]
    try:
        yield serve
    finally:
        for srv in servers:
            srv.shutdown()
            srv.server_close()
        _GUARD["window"] = False
        repatch()


def settle(done, seconds=2.0):
    """Wait until done() holds or the time runs out: a stub's thread counts a connection a moment
    after the connect returns."""
    end = time.time() + seconds
    while not done() and time.time() < end:
        time.sleep(0.01)


def proxy_url(srv):
    return "http://127.0.0.1:%d" % srv.server_address[1]


def update_json(path, change):
    data = load_json(path)
    data.update(change)
    dump_json(path, data)


def model_engagement(name, provider, matter=None, terms=None, source=None):
    """A copy of the clean engagement, or of source, set for a model proposer over the untagged
    twin with the invented model id; terms changes the synthetic counsel-terms block."""
    eng = LAB.copy(name, source)
    update_json(os.path.join(eng, "matter.json"), dict({"provider": provider, "model": stub_model.MODEL,
                                                        "draft": UNTAGGED}, **(matter or {})))
    update_json(os.path.join(eng, "counsel-terms.json"), terms or {})
    return eng


def chat_engagement(name, srv, matter=None, terms=None):
    """A copy set for provider chat, with counsel-terms naming the stub srv as the endpoint."""
    return model_engagement(name, "chat", matter, dict({"endpoint_base_url": srv.url}, **(terms or {})))


def with_replay(eng):
    """Copy the committed replay fixture into an engagement; the Lab leaves it out."""
    shutil.copytree(os.path.join(MATTER, "replay"), os.path.join(eng, "replay"), copy_function=shutil.copyfile)
    return eng


def last_run(eng):
    """The newest run folder, or None: a run stopped by egress prints no run id."""
    d = os.path.join(eng, "run")
    names = sorted(n for n in os.listdir(d) if not n.startswith(".")) if os.path.isdir(d) else []
    return os.path.join(d, names[-1]) if names else None


def run_files(eng):
    """(path under the engagement, bytes) for every file under run/."""
    out = []
    for dirpath, _, names in os.walk(os.path.join(eng, "run")):
        for n in names:
            p = os.path.join(dirpath, n)
            out.append((os.path.relpath(p, eng).replace(os.sep, "/"), read_bytes(p)))
    return out


def read_bytes(path):
    with open(path, "rb") as fh:
        return fh.read()


def receipts(rd):
    with open(os.path.join(rd, "receipts.jsonl"), encoding="utf-8") as fh:
        return [json.loads(ln) for ln in fh if ln.strip()]


def chat_run():
    """The untagged twin over the stub with provider chat, an invented key and a synthetic
    counsel-terms block that turns on candidate snippets, run once: (engagement, run id, what the
    stub received, exit code, output). Scenario 17 checks it; N9 and scenario 20 start from it."""
    def build():
        with loopback() as serve:
            stub = serve()
            eng = chat_engagement("chat", stub, terms={"candidate_snippets": True})
            rc, out, rid = run(eng, env={"TIEOUT_API_KEY": API_KEY})
        return eng, rid, list(stub.seen), rc, out
    return LAB.once("chat", build)


@expectation("N2: provider chat refuses when counsel-terms.json names no endpoint host, and a lookup of a host "
             "it does not name, by getaddrinfo, gethostbyname or gethostbyaddr, is refused before it resolves")
def probe_n2():
    eng = model_engagement("n2", "chat", terms={"endpoint_base_url": ""})
    rc, out, _ = run(eng, env={"TIEOUT_API_KEY": API_KEY})
    check(rc == 3 and "N2: counsel-terms.json names no endpoint host" in out and last_run(eng) is None,
          "with no endpoint host: exit %s: %s" % (rc, out.strip()[-200:]))
    got = []
    with loopback() as serve:
        stub = serve()
        providers.ChatClient({"provider": "chat", "key_env": "TIEOUT_API_KEY"}, {"endpoint_base_url": stub.url},
                             LAB.base, env={"TIEOUT_API_KEY": API_KEY})
        lookups = ((socket.getaddrinfo, ("127.0.0.1", stub.server_address[1], socket.AF_INET, socket.SOCK_STREAM)),
                   (socket.getaddrinfo, ("localhost", stub.server_address[1], socket.AF_INET, socket.SOCK_STREAM)),
                   (socket.gethostbyname, ("localhost",)), (socket.gethostbyname_ex, ("localhost",)),
                   (socket.gethostbyaddr, ("localhost",)))
        for lookup, args in lookups:  # the endpoint host, then a loopback name counsel did not write
            try:
                lookup(*args)
                got.append("resolved")
            except providers.EgressError as exc:
                got.append(exc.code)
    check(got == ["resolved", "N2", "N2", "N2", "N2"], "lookups of the endpoint host and of localhost gave %s" % got)


@expectation("N3: a connection to an address no allowed lookup returned is refused before it connects")
def probe_n3():
    got = []
    with loopback() as serve:
        trap = serve()
        port = trap.server_address[1]
        providers.watch({"127.0.0.1"})
        providers._WATCH["resolved"].clear()  # a port an earlier probe's stub resolved could come round again
        for lookup in (False, True):  # the control: once a lookup has returned the address, it connects
            if lookup:
                socket.getaddrinfo("127.0.0.1", port, socket.AF_INET, socket.SOCK_STREAM)
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                s.connect(("127.0.0.1", port))
                got.append("connected")
            except providers.EgressError as exc:
                got.append(exc.code)
            finally:
                s.close()
        settle(lambda: trap.connections >= 1)
        hits = trap.connections
    check(got == ["N3", "connected"] and hits == 1, "connects gave %s; the listener accepted %d" % (got, hits))


@expectation("N4: a redirect is refused with its status only and never followed")
def probe_n4():
    with loopback() as serve:
        stub = serve(fail=[302])
        eng = chat_engagement("n4", stub)
        rc, out, _ = run(eng, env={"TIEOUT_API_KEY": API_KEY})
        seen = len(stub.seen)
    check(rc == 3 and "N4: status http 302" in out and seen == 1 and "elsewhere" not in out and
          "localhost" not in out, "exit %s after %d request(s): %s" % (rc, seen, out.strip()[-200:]))


@expectation("N5: plain http to a host other than loopback is refused before any lookup")
def probe_n5():
    before = len(SOCKET_EVENTS)
    eng = model_engagement("n5", "chat", terms={"endpoint_base_url": "http://gateway.synthetic.example/v1"})
    try:
        rc, out, _ = run(eng, env={"TIEOUT_API_KEY": API_KEY})
    finally:
        repatch()
    check(rc == 3 and "N5: endpoint_base_url must use https" in out and last_run(eng) is None and
          len(SOCKET_EVENTS) == before, "exit %s, socket activity %s: %s" % (rc, SOCKET_EVENTS[before:][:2],
                                                                            out.strip()[-200:]))


@expectation("N6: a proxy comes only from counsel-terms.json, with Proxy-Authorization from TIEOUT_PROXY_AUTH, "
             "while the environment's proxy variables point at a trap and no_proxy names the endpoint")
def probe_n6():
    with loopback() as serve:
        stub, proxy, trap = serve(), serve(), serve()
        terms = {"proxy_host": "127.0.0.1:%d" % proxy.server_address[1]}
        eng = chat_engagement("n6", stub, terms=terms)
        env = dict({k: proxy_url(trap) for k in PROXY_VARS}, no_proxy="127.0.0.1", NO_PROXY="127.0.0.1",
                   TIEOUT_API_KEY=API_KEY, TIEOUT_PROXY_AUTH=PROXY_AUTH)
        rc, out, _ = run(eng, env=env)
        direct, via, trapped = len(stub.seen), list(proxy.seen), trap.connections
        # no proxy variable at all, where urllib's bypass test would read the system's own list
        rc2, _, _ = run(chat_engagement("n6-system", stub, terms=terms), env={"TIEOUT_API_KEY": API_KEY})
        direct2, via2 = len(stub.seen) - direct, len(proxy.seen) - len(via)
    want = "Basic " + base64.b64encode(PROXY_AUTH.encode("ascii")).decode("ascii")
    check(rc == 1 and via and not direct and not trapped and
          all(p["proxied"] and p["headers"].get("Proxy-Authorization") == want and
              p["headers"].get("Authorization") == "Bearer " + API_KEY for p in via),
          "exit %s; %d call(s) through counsel's proxy, %d direct, %d connection(s) to the trap"
          % (rc, len(via), direct, trapped))
    check(rc2 == 1 and via2 and not direct2, "with no proxy variable set: exit %s; %d call(s) through counsel's "
                                             "proxy, %d direct" % (rc2, via2, direct2))
    check(not [p for p, b in run_files(eng) if b"invented-proxy-pass" in b or API_KEY.encode() in b],
          "the proxy password or the key is in a run file")


@expectation("N7: one retry on a 5xx counts against max_calls, the run stops at the budget with the drop log "
             "marked proposer_budget, a reply slower than the timeout stops the run unretried, and a timeout of "
             "0 or less is refused")
def probe_n7():
    with loopback() as serve:
        once, budget, last, slow = serve(fail=[503]), serve(), serve(fail=[503]), serve(delay=0.5)
        a = chat_engagement("n7-retry", once)
        rc_a, out_a, rid_a = run(a, env={"TIEOUT_API_KEY": API_KEY})
        b = chat_engagement("n7-budget", budget, matter={"max_calls": 2})
        rc_b, out_b, rid_b = run(b, env={"TIEOUT_API_KEY": API_KEY})
        c = chat_engagement("n7-last", last, matter={"max_calls": 1})
        rc_c, out_c, _ = run(c, env={"TIEOUT_API_KEY": API_KEY})
        d = chat_engagement("n7-slow", slow, terms={"timeout_seconds": 0.1})
        rc_d, out_d, _ = run(d, env={"TIEOUT_API_KEY": API_KEY})
        seen = [len(s.seen) for s in (once, budget, last, slow)]
    rec = receipts(run_dir(a, rid_a)) if rid_a else []
    check(rc_a == 1 and len(rec) == seen[0] and rec[0]["status"] == "http 503" and rec[1]["status"] == "ok" and
          rec[1]["retry"] is True and rec[0]["request_sha256"] == rec[1]["request_sha256"] and
          tie(a, "status", "--run", rid_a)[0] == 0,
          "a 503 then a reply: exit %s, receipts %s, or status refuses the failed call's receipt"
          % (rc_a, [(r["status"], r["retry"]) for r in rec[:2]]))
    prop = load_json(os.path.join(run_dir(b, rid_b), "proposals.json")) if rid_b else {}
    md = read_text(os.path.join(run_dir(b, rid_b), "drop-log.md")) if rid_b else ""
    check(rc_b == 1 and seen[1] == 2 and len(receipts(run_dir(b, rid_b))) == 2 and prop.get("budget_hit") and
          "## proposer_budget" in md, "max_calls 2: exit %s after %d call(s)" % (rc_b, seen[1]))
    check(rc_c == 3 and seen[2] == 1, "max_calls 1 and a 503: exit %s after %d call(s); the retry would pass the "
                                      "budget" % (rc_c, seen[2]))
    check(rc_d == 3 and "N8: status " in out_d and seen[3] == 1, "a reply slower than timeout_seconds: exit %s after "
                                                                 "%d call(s): %s" % (rc_d, seen[3], out_d.strip()[-160:]))
    for t in (0, -1):
        e = model_engagement("n7-timeout%d" % t, "chat", terms={"endpoint_base_url": "http://127.0.0.1:9/v1",
                                                                 "timeout_seconds": t})
        rc_t, out_t, _ = run(e, env={"TIEOUT_API_KEY": API_KEY})
        check(rc_t == 2 and "timeout_seconds must be more than 0" in out_t and last_run(e) is None,
              "timeout_seconds %d: exit %s: %s" % (t, rc_t, out_t.strip()[-160:]))


@expectation("N8: a forced HTTP error prints its status, byte counts and receipt number only, with no key and no "
             "paragraph text in any run file or output; the key in TIEOUT_QUERY, another header or the endpoint "
             "address, percent-encoded or not, is refused; an empty key variable stops the run before it "
             "connects; each error reply is saved to sent/ with the key removed and never printed")
def probe_n8():
    refused = []
    with loopback() as serve:
        stub = serve(fail=[500, 500])  # each error body echoes the request and its Authorization header
        eng = chat_engagement("n8", stub)
        rc, out, _ = run(eng, env={"TIEOUT_API_KEY": API_KEY})
        calls = len(stub.seen)
        encoded = "".join("%%%02X" % b for b in API_KEY.encode("ascii"))
        for name, extra, terms in (("query", {"TIEOUT_QUERY": "key=" + API_KEY}, None),
                                   ("header", {"TIEOUT_EXTRA_HEADERS": "X-Other: " + API_KEY}, None),
                                   ("header-name", {"TIEOUT_EXTRA_HEADERS": API_KEY + ": 1"}, None),
                                   ("encoded-url", {}, {"endpoint_base_url": stub.url + "/" + encoded})):
            e = chat_engagement("n8-" + name, stub, terms=terms)
            n = len(stub.seen)
            r, o, _ = run(e, env=dict(extra, TIEOUT_API_KEY=API_KEY))
            refused.append((name, r, "N8: the key may travel only" in o, API_KEY in o, len(stub.seen) - n, last_run(e)))
        e = chat_engagement("n8-empty", stub)
        n = len(stub.seen)
        r, o, _ = run(e, env={"TIEOUT_API_KEY": ""})
        empty = (r, "N8: TIEOUT_API_KEY is empty, so nothing is sent" in o, len(stub.seen) - n, last_run(e))
    check(empty == (3, True, 0, None), "an empty key variable: exit, message, calls, run folder %s" % (empty,))
    check(rc == 3 and calls == 2 and re.search(r"N8: status http 500 \(receipt 2, \d+ bytes out, \d+ bytes in\)", out),
          "exit %s after %d call(s): %s" % (rc, calls, out.strip()[-200:]))
    files = run_files(eng)
    bodies = [p for p, _ in files if re.search(r"/sent/\d{4}-(request|error)\.json$", p)]
    errors = [b for p, b in files if re.search(r"/sent/\d{4}-error\.json$", p)]
    check(len(errors) == 2 and all(b"stub status 500" in b and b"Bearer [removed]" in b for b in errors) and
          re.search(r"the endpoint's reply is in run/[^/]+/sent/0002-error\.json", out) and "stub status" not in out,
          "each error reply saved to sent/ with the key removed, its place named and its text kept off the "
          "screen: %d saved; %s" % (len(errors), out.strip()[-200:]))
    first = [b for p, b in files if p.endswith("/sent/0001-request.json")]
    check(first and PARA_TEXT.encode("utf-8") in first[0], "the paragraph text is not in the first request body")
    check(API_KEY not in out and not [p for p, b in files if API_KEY.encode("utf-8") in b], "the key is in the output or "
          "in %s" % [p for p, b in files if API_KEY.encode("utf-8") in b])
    leaked = [p for p, b in files if PARA_TEXT.encode("utf-8") in b and p not in bodies]
    check(PARA_TEXT not in out and not leaked and "127.0.0.1" not in out and "chat/completions" not in out,
          "paragraph text or the URL outside the sent/ bodies: %s %s" % (leaked, out.strip()[-160:]))
    check(len(refused) == 4 and all(r[1:] == (3, True, False, 0, None) for r in refused),
          "the key in TIEOUT_QUERY, an extra header's value or name, or the endpoint percent-encoded: %s"
          % [r[:5] for r in refused])


@expectation("N9: status checks each receipt against its sent/ body and the observer's peer log, and a run "
             "whose call met a refused peer stops with exit 3")
def probe_n9():
    eng, rid, _, _, _ = chat_run()
    peer = LAB.copy("n9-peer", eng)
    path = os.path.join(run_dir(peer, rid), "receipts.jsonl")
    lines = read_text(path).splitlines()
    first = json.loads(lines[0])
    first["peers"][0]["host"] = "gateway.synthetic.example"
    write_text(path, "\n".join([json.dumps(first, sort_keys=True)] + lines[1:]) + "\n")
    rc1, out1 = tie(peer, "status", "--run", rid)
    body = LAB.copy("n9-body", eng)
    with open(os.path.join(run_dir(body, rid), "sent", "0002-request.json"), "ab") as fh:
        fh.write(b" ")
    rc2, out2 = tie(body, "status", "--run", rid)
    check(rc1 == 1 and "receipt 1: peer" in out1 and "outside the configured set" in out1,
          "a receipt peer outside the set: status exit %s" % rc1)
    check(rc2 == 1 and "sent/0002-request.json does not match receipt 2" in out2,
          "a changed sent/ body: status exit %s" % rc2)
    moved = LAB.copy("n9-terms", eng)
    update_json(os.path.join(moved, "counsel-terms.json"), {"endpoint_base_url": "https://gateway.synthetic.example/v1"})
    rc4, out4 = tie(moved, "status", "--run", rid)
    check(rc4 == 1 and "names host 127.0.0.1, which counsel-terms.json does not" in out4,
          "receipts whose host counsel-terms.json no longer names: status exit %s" % rc4)

    def reply(req):  # something in this process looks up a host counsel did not name, mid-call
        try:
            socket.getaddrinfo("localhost", 80)
        except providers.EgressError:
            pass
        return stub_model.rules_reply(req)
    with loopback() as serve:
        stub, plain = serve(reply=reply), serve()
        e = chat_engagement("n9-run", stub)
        rc3, out3, _ = run(e, env={"TIEOUT_API_KEY": API_KEY})
        calls = len(stub.seen)
        d = chat_engagement("n9-digest", plain, terms={"receipt_detail": "digest"})
        rc5, _, drid = run(d, env={"TIEOUT_API_KEY": API_KEY})
        dcalls = len(plain.seen)
    rd = last_run(e)
    rec = receipts(rd) if rd and os.path.isfile(os.path.join(rd, "receipts.jsonl")) else []
    check(rc3 == 3 and "N9: the observer refused a peer" in out3 and calls == 1 and len(rec) == 1 and
          any(not p["ok"] and p["host"] == "localhost" for p in rec[0]["peers"]),
          "a refused peer mid-call: exit %s after %d call(s): %s" % (rc3, calls, out3.strip()[-160:]))
    # digest receipts: one line per call and no bodies; status still passes, and replay is refused
    ddir = run_dir(d, drid) if drid else ""
    ok = rc5 == 1 and drid and not os.path.isdir(os.path.join(ddir, "sent")) and len(receipts(ddir)) == dcalls and \
        tie(d, "status", "--run", drid)[0] == 0
    update_json(os.path.join(d, "matter.json"), {"provider": "replay", "replay_from": "run/%s" % drid})
    rc6, out6, _ = run(d)
    check(ok and rc6 == 2 and "holds no sent/ folder" in out6, "digest receipts: exit %s, %d call(s); replay from "
                                                              "it: exit %s" % (rc5, dcalls, rc6))


# =================================================================================================
# Scenario probes 1 to 15
# =================================================================================================


@expectation("scenario 1: the clean tagged draft exits 0 with an empty drop log")
def scenario_1():
    eng = LAB.copy("sc1")
    rc, out, rid = run(eng)
    clean = LAB.key["drafts"]["clean"]
    doc = verdicts(eng, rid) if rid else {"claims": [], "not_checked": []}
    check(rc == 0 and rid and drop_log(eng, rid) == [], "exit %s, drop log %s" % (rc, drop_codes(eng, rid) if rid else "-"))
    got = sorted(r["key"] for r in doc["claims"])
    want = sorted(c["key"] for c in clean["claims"])
    check(got == want and all(r["code"] == "tie" for r in doc["claims"]),
          "%d claims, %d match the key's %d" % (len(got), len(set(got) & set(want)), len(want)))
    nc = sorted((n["para"], n["span"], n["reason"]) for n in doc["not_checked"])
    check(nc == sorted((n["para"], n["span"], n["reason"]) for n in clean["not_checked"]),
          "not checked %s" % nc)


FORMS = ("SYNTHETIC: invented test matter; number forms for scenario 2.\n\n"
         "## 9. Number forms\n\n"
         "Ostmarren took 4,610-4,812 units a month (PX-4 at 1). Over two months it took 4,812/4,610 units "
         "(PX-4 at 1). Its 2023 spend was $5.9m (PX-3 at 2). Release 2.1.3 of the planning tool held these "
         "figures (PX-4 at 1).\n\n"
         "1. The parties met at 10:30 a.m. and at 14:05 on 4/3/23 about Case No. 1:23-cv-04567, filed beside "
         "No. 23-cv-4567 and Docket No. 21-1234, and spoke again at 9 a.m. (PX-4 at 1).\n")
FORMS_CLAIMS = [("4,610-4,812", "tie"), ("4,812", "tie"), ("4,610", "tie"), ("$5.9m", "tie")]
FORMS_NOT_CHECKED = [("9.", "heading number"), ("2023", "bare year"), ("2.1.3", "unread number form"),
                     ("1.", "list number"), ("10:30 a.m.", "clock time"), ("14:05", "clock time"),
                     ("4/3/23", "two-digit-year date"), ("1:23-cv-04567", "docket number"),
                     ("23-cv-4567", "docket number"), ("21-1234", "docket number"), ("9 a.m.", "clock time")]
# a record page is read the same way: none of these forms gives a figure, and a ratio still gives two
SCAN_TEXT = ("At 10:30 a.m. on 4/3/23, in Case No. 1:23-cv-04567 and Docket No. 21-1234, the 9 a.m. call "
             "set a 3:1 ratio on 4,812 units.")
SCAN_FIGURES = ["3", "1", "4,812"]


@expectation("scenario 2: the untagged twin lists every untagged token with its pairing, exit 1, and no "
             "number form leaves checking unlisted")
def scenario_2():
    # a hyphen range is one claim, a slash pair two, $5.9m a scaled figure; a heading number, a
    # list number, a clock time, a two-digit-year date, a docket number and a digit run no token
    # reads are each listed as not checked with their own reason, and none is read as a figure
    feng = LAB.copy("sc2-forms")
    write_text(os.path.join(feng, "report", "draft-forms.md"), FORMS)
    rc, out, frid = run(feng, "--draft", "report/draft-forms.md")
    fdoc = verdicts(feng, frid) if frid else {"claims": [], "not_checked": []}
    got = [(r["span"], r["code"]) for r in fdoc["claims"]]
    nc = [(n["span"], n["reason"]) for n in fdoc["not_checked"]]
    check(rc == 1 and got == FORMS_CLAIMS and nc == FORMS_NOT_CHECKED,
          "number forms: exit %s, claims %s, not checked %s" % (rc, got, nc))
    figs = [f["raw"] for f in record.scan(SCAN_TEXT, "mdy")["figures"]]
    check(figs == SCAN_FIGURES, "a record page with the same forms reads figures %s" % figs)
    eng, rid, rc, out = untagged_run()
    key = LAB.key["drafts"]["untagged"]
    check(rc == 1 and rid, "exit %s" % rc)
    nc = sorted((n["para"], n["span"], n["reason"]) for n in verdicts(eng, rid)["not_checked"])
    want = sorted((n["para"], n["span"], n["reason"]) for n in key["not_checked"])
    check(nc == want, "the twin's not-checked rows differ from the key: tool only %s, key only %s"
          % (sorted(set(nc) - set(want))[:4], sorted(set(want) - set(nc))[:4]))
    rows = {r["key"]: r for r in verdicts(eng, rid)["claims"]}
    check(len(rows) == len(key["claims"]), "%d claims, the key has %d" % (len(rows), len(key["claims"])))
    report = read_text(os.path.join(run_dir(eng, rid), "tieout-report.md"))
    bad = []
    for c in key["claims"]:
        r = rows.get(c["key"])
        if r is None or (r["code"], r["pairing"], r["cite_resolved"]) != (c["code"], c["pairing"], c["cite_resolved"]):
            bad.append("%s %s: %s" % (c["key"], c["span"], "missing" if r is None else (r["code"], r["pairing"])))
        elif not re.search(r"^\| %s \|[^\n]*\| %s \|" % (re.escape(c["key"]), re.escape(c["pairing"])), report, re.M):
            bad.append("%s is not listed with pairing %s in tieout-report.md" % (c["key"], c["pairing"]))
    check(not bad, "%d token(s) differ from the key: %s" % (len(bad), "; ".join(bad[:4])))
    check("Untagged cite tokens in the draft: %d." % key["cite_tokens"] in report,
          "the report does not count %d cite tokens" % key["cite_tokens"])


@expectation("scenario 3: the planted variant lists each planted item with its code and nothing else")
def scenario_3():
    eng = LAB.copy("sc3")
    rc, out, rid = run(eng, "--draft", PLANTED)
    key = LAB.key["drafts"]["planted"]
    check(rc == 1 and rid, "exit %s" % rc)
    want = sorted((k, code) for item in key["items"] for k, code in zip(item["keys"], item["codes"]))
    got = sorted((r["key"], r["code"]) for r in drop_log(eng, rid))
    check(got == want and len(got) == key["drop_rows"] and len(key["items"]) == key["n_planted"],
          "drop log %s, expected %s" % (got, want))
    rows = {r["key"]: r for r in verdicts(eng, rid)["claims"]}
    blind = [k for item in key["blind"] for k in item["keys"]]
    check(all(rows.get(k, {}).get("code") == "tie" for k in blind), "a designed-blindness item did not tie: %s" % blind)


def patch_docx(data, old, new, count=1):
    """Replace old with new count times in word/document.xml inside .docx bytes."""
    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(data), "r") as zin, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
        for info in zin.infolist():
            raw = zin.read(info.filename)
            if info.filename == "word/document.xml":
                xml = raw.decode("utf-8")
                check(old in xml, "patch_docx: %r missing from word/document.xml" % (old,))
                raw = xml.replace(old, new, count).encode("utf-8")
            zout.writestr(info, raw)
    return out.getvalue()


@expectation("scenario 4: the .docx twin yields the same claim keys and footnote references as the .md draft")
def scenario_4():
    eng, rid, rc = docx_run()
    got = sorted(r["key"] for r in verdicts(eng, rid)["claims"])
    want = sorted(c["key"] for c in LAB.key["drafts"]["clean"]["claims"])
    check(rc == 0 and got == want, "exit %s; %d keys, %d match the .md draft's %d" % (rc, len(got), len(set(got) & set(want)), len(want)))
    draft = docx_reader.read(os.path.join(eng, "report", "draft.docx"))
    refs = [n for b in draft["blocks"] for _, n in b["refs"]]
    check(refs == [1, 2, 3], "docx footnote refs: %s" % refs)
    # a typed list marker in a paragraph that also references a footnote must keep both
    typed_path = os.path.join(LAB.tmp, "typed-list-footnote.docx")
    typed_bytes = patch_docx(make_docx.build("First item[^1].\n\n[^1]: Footnote body.\n", comments=False),
                             '<w:t xml:space="preserve">First item', '<w:t xml:space="preserve">1. First item')
    with open(typed_path, "wb") as fh:
        fh.write(typed_bytes)
    td = docx_reader.read(typed_path, served=True)
    tp = [b for b in td["blocks"] if b["kind"] == "para"]
    check(len(tp) == 1 and tp[0]["list_number"] == "1." and tp[0]["text"] == "First item."
          and tp[0]["refs"] == [(len("First item"), 1)], "typed marker with footnote: %s" % tp)


@expectation("scenario 5: tracked changes are refused, and with the flag the run records their counts")
def scenario_5():
    eng = LAB.copy("sc5")
    docx_matter(eng, make_docx.build(draft_md(), tracked=True))
    rc, out, rid = run(eng)
    check(rc == 2 and rid is None and "1 insertions, 1 deletions" in out, "without the flag: exit %s: %s" % (rc, out.strip()[-160:]))
    rc, out, rid = run(eng, "--accept-tracked-changes")
    check(rc == 0 and rid, "with the flag: exit %s" % rc)
    intake = load_json(os.path.join(run_dir(eng, rid), "intake.json"))
    got = (intake["tracked_changes"], intake["insertions"], intake["deletions"])
    check(got == ("accepted", 1, 1), "intake.json records %s" % (got,))


@expectation("scenario 6: a TIE: comment on a range reads as a tag with that span and cite")
def scenario_6():
    eng, rid, _ = docx_run()
    draft = docx_reader.read(os.path.join(eng, "report", "draft.docx"))
    tags = [(b, t) for b in draft["blocks"] for t in b["tags"] if t["text"] == "$7.01 million"]
    check(len(tags) == 1, "%d tags read on $7.01 million" % len(tags))
    block, tag = tags[0]
    check(tag["cite"] == "DX-104 at 3" and block["text"][tag["start"]:tag["end"]] == "$7.01 million"
          and tag["raw"] == "TIE: DX-104 at 3", "the tag reads %r over %r" % (tag["raw"], block["text"][tag["start"]:tag["end"]]))
    row = [r for r in verdicts(eng, rid)["claims"] if r["span"] == "$7.01 million"]
    check(len(row) == 1 and row[0]["proposed_by"] == "tag" and row[0]["cite_resolved"] == "DX-104 at 3"
          and row[0]["code"] == "tie", "the claim reads %s" % row)


@expectation("scenario 7: status reports void after one character of the draft changes")
def scenario_7():
    eng = LAB.copy("sc7")
    rc, out, rid = run(eng)
    rc1, out1 = tie(eng, "status")
    path = os.path.join(eng, "report", "draft.md")
    edit(path, "## 1. Assignment", "## 1. Assignmant")
    rc2, out2 = tie(eng, "status")
    void = [ln.strip() for ln in out2.splitlines() if "VOID" in ln]
    check(rc1 == 0 and rc2 == 1 and len(void) == 2 and void[0].startswith("draft report/draft.md"),
          "status before exit %s, after exit %s: %s" % (rc1, rc2, void))


def certification(fp):
    return "Tie-out certification. The signed draft carries tie-out fingerprint %s." % gate.grouped(fp)


@expectation("scenario 8: status --served reports a changed figure, prose edit, moved footnote or certification prose")
def scenario_8():
    eng, rid, fp = docx_signed()
    served = os.path.join(LAB.tmp, "served-changed.docx")
    with open(served, "wb") as fh:
        fh.write(make_docx.build(draft_md(), comments=False, certify=certification(fp),
                                 change=("{{$5.87 million | PX-3 at 2}}", "{{$5.97 million | PX-3 at 2}}")))
    rc, out = tie(eng, "status", "--served", served)
    diffs = [ln.strip() for ln in out.splitlines() if ln.strip().startswith("served") and
             ("MISSING" in ln or "NOT IN" in ln or "DIFFERS" in ln)]
    check(rc == 1 and len(diffs) == 2 and "$5.87 million" in diffs[0] + diffs[1] and "$5.97 million" in diffs[0] + diffs[1],
          "exit %s: %s" % (rc, diffs))
    prose = os.path.join(LAB.tmp, "served-prose-changed.docx")
    with open(prose, "wb") as fh:
        fh.write(make_docx.build(draft_md(), comments=False, certify=certification(fp),
                                 change=("I assume for this report that it did.",
                                         "I conclude for this report that it did.")))
    rc_p, out_p = tie(eng, "status", "--served", prose)
    pdiffs = [ln.strip() for ln in out_p.splitlines() if ln.strip().startswith("served") and "DIFFERS" in ln]
    check(rc_p == 1 and len(pdiffs) == 1 and "text differs from the signed text" in pdiffs[0],
          "prose edit exit %s: %s" % (rc_p, pdiffs))
    # prose smuggled into the added certification paragraph must fail
    cert_extra = os.path.join(LAB.tmp, "served-cert-prose.docx")
    with open(cert_extra, "wb") as fh:
        fh.write(make_docx.build(draft_md(), comments=False, certify=certification(fp) + " I withdraw Section 7."))
    rc_c, out_c = tie(eng, "status", "--served", cert_extra)
    cdiffs = [ln.strip() for ln in out_c.splitlines() if ln.strip().startswith("served") and "DIFFERS" in ln]
    check(rc_c == 1 and len(cdiffs) == 1 and "text differs from the signed text" in cdiffs[0],
          "certification prose exit %s: %s" % (rc_c, cdiffs))
    # moving a footnote reference between paragraphs without changing any text must fail
    fref1 = '<w:r><w:rPr><w:rStyle w:val="FootnoteReference"/></w:rPr><w:footnoteReference w:id="1"/></w:r>'
    moved_bytes = patch_docx(
        patch_docx(make_docx.build(draft_md(), comments=False, certify=certification(fp)), fref1, ""),
        "ending all purchases.</w:t></w:r>", "ending all purchases.</w:t></w:r>" + fref1)
    moved_fn = os.path.join(LAB.tmp, "served-moved-fn.docx")
    with open(moved_fn, "wb") as fh:
        fh.write(moved_bytes)
    rc_f, out_f = tie(eng, "status", "--served", moved_fn)
    fdiffs = [ln.strip() for ln in out_f.splitlines() if ln.strip().startswith("served") and "DIFFERS" in ln]
    check(rc_f == 1 and len(fdiffs) == 2 and all("text differs from the signed text" in d for d in fdiffs),
          "moved footnote reference exit %s: %s" % (rc_f, fdiffs))


@expectation("scenario 9: status --served matches the served file with comments deleted, changes accepted, "
             "inline certification or restyled heading")
def scenario_9():
    eng, rid, fp = docx_signed()
    served = os.path.join(LAB.tmp, "served-same.docx")
    with open(served, "wb") as fh:
        fh.write(make_docx.build(draft_md(), comments=False, tracked=True, certify=certification(fp), certify_tracked=True))
    rc, out = tie(eng, "status", "--served", served)
    check(rc == 0 and "carries the same figures" in out and "signed" in out,
          "exit %s: %s" % (rc, [ln.strip() for ln in out.splitlines() if "served" in ln or "status" in ln]))
    # the fingerprint typed into the report's existing closing paragraph must also match
    inline = os.path.join(LAB.tmp, "served-inline-cert.docx")
    with open(inline, "wb") as fh:
        fh.write(make_docx.build(draft_md(), comments=False,
                                 change=("I have relied on the documents as produced.",
                                         "I have relied on the documents as produced. Tie-out fingerprint: %s."
                                         % gate.grouped(fp))))
    rc_i, out_i = tie(eng, "status", "--served", inline)
    check(rc_i == 0 and "carries the same figures" in out_i,
          "inline certification exit %s: %s" % (rc_i, [ln.strip() for ln in out_i.splitlines() if "served" in ln]))
    # a pre-existing certification label in the signed draft with bare fingerprint typed in also matches
    g = claims.Grammar({}, "mdy")
    s_pre = {"blocks": [claims.finish_block("para", 1, "I certify tie-out fingerprint:", [], [], False, False)]}
    v_pre = {"blocks": [claims.finish_block("para", 1, "I certify tie-out fingerprint: %s." % gate.grouped(fp),
                                            [], [], False, False)]}
    check(gate.served_text_diffs(s_pre, v_pre, g, fp) == []
          and gate.served_keys(s_pre, g) == gate.served_keys(v_pre, g, fp, s_pre),
          "pre-existing certification label failed")
    # a numbered heading restyled in Word to a non-Heading style matches; changing its number fails
    restyled = os.path.join(LAB.tmp, "served-restyled-heading.docx")
    with open(restyled, "wb") as fh:
        fh.write(patch_docx(make_docx.build(draft_md(), comments=False, certify=certification(fp)),
                            '<w:pStyle w:val="Heading2"/>', '<w:pStyle w:val="Normal"/>'))
    rc_h, out_h = tie(eng, "status", "--served", restyled)
    check(rc_h == 0 and "carries the same figures" in out_h,
          "restyled heading exit %s: %s" % (rc_h, [ln.strip() for ln in out_h.splitlines() if "served" in ln]))
    renumbered = os.path.join(LAB.tmp, "served-renumbered-heading.docx")
    with open(renumbered, "wb") as fh:
        fh.write(patch_docx(
            patch_docx(make_docx.build(draft_md(), comments=False, certify=certification(fp)),
                       '<w:pStyle w:val="Heading2"/>', '<w:pStyle w:val="Normal"/>'),
            "1. Assignment", "2. Assignment"))
    rc_n, out_n = tie(eng, "status", "--served", renumbered)
    check(rc_n == 1 and "text differs from the signed text" in out_n,
          "renumbered restyled heading exit %s: %s" % (rc_n, out_n))
    # the match rests on the fingerprint too: the same file without the certification differs
    bare = os.path.join(LAB.tmp, "served-no-fingerprint.docx")
    with open(bare, "wb") as fh:
        fh.write(make_docx.build(draft_md(), comments=False, tracked=True))
    rc, out = tie(eng, "status", "--served", bare)
    check(rc == 1 and "does not quote the fingerprint" in out, "without the fingerprint: exit %s" % rc)


def carried_engagement():
    """Scenarios 10 and 11: the planted draft run, ruled by the expert, then run again."""
    def build():
        eng = LAB.copy("carry")
        _, _, first = run(eng, "--draft", PLANTED)
        fill_rulings(eng, first, expert_clears(LAB.expert))
        rc, out, second = run(eng, "--draft", PLANTED)
        return eng, first, second, rc
    return LAB.once("carry", build)


def rulings_rows(eng, rid):
    with open(os.path.join(run_dir(eng, rid), "rulings.csv"), encoding="utf-8-sig", newline="") as fh:
        return {r["key"]: r for r in csv.DictReader(fh)}


@expectation("scenario 10: a ruling carries forward when its claim is unchanged in a re-run")
def scenario_10():
    eng, first, second, rc = carried_engagement()
    before, after = rulings_rows(eng, first), rulings_rows(eng, second)
    same = [k for k in before if after.get(k, {}).get("ruling") == before[k]["ruling"] != ""
            and after[k]["ruled_by"] == before[k]["ruled_by"]]
    check(second != first and len(before) == 10 and len(same) == 10 and rc == 0,
          "run 2 exit %s, %d of %d rulings carried" % (rc, len(same), len(before)))


@expectation("scenario 11: a ruling reopens when the sentence holding its claim changes")
def scenario_11():
    eng, first, second, _ = carried_engagement()
    edit(os.path.join(eng, PLANTED), "The committee deck put Ostmarren's spend", "The committee deck then put Ostmarren's spend")
    rc, out, third = run(eng, "--draft", PLANTED)
    rows = rulings_rows(eng, third)
    reopened = [r["item"] for r in rows.values() if not r["ruling"]]
    check(rc == 1 and len(rows) == 10 and len(reopened) == 1 and "$7.01 million" in reopened[0],
          "run 3 exit %s, reopened %s" % (rc, reopened))


@expectation("scenario 12: a mangled rulings.csv key is quarantined and named, and sign refuses")
def scenario_12():
    eng, rid = signable("sc12")
    rows = fill_rulings(eng, rid, lambda r: None)
    target = rows[1][0]
    fill_rulings(eng, rid, lambda r: r.__setitem__(0, target + "x") if r[0] == target else None)
    res = sign(eng, rid)
    check(res["rc"] == 1 and not res["signed"] and "quarantined" in res["text"] and target + "x" in res["text"],
          "sign: exit %s: %s" % (res["rc"], res["text"].strip().splitlines()[:2]))
    rc, out = tie(eng, "status", "--run", rid)
    check("quarantined" in out and target + "x" in out, "status does not name the quarantined row")


class FaultyRules(providers.RulesClient):
    """The rules proposer with faults planted on attempt 0 of each chunk: a non-verbatim span
    (P2), a cite from another sentence (P3) and a verdict key (P1), so the one-retry path runs.
    Shaped after fsi's MockGenerator, which faults attempt 0 only. It lives here, outside the
    released code, and scenario 13 hands it to a run by patching providers.make_client."""

    def __init__(self, names, date_order):
        providers.RulesClient.__init__(self, names, date_order)
        self.seen_rejected = []

    def complete(self, *, model, system, user, max_tokens):
        text, usage = providers.RulesClient.complete(self, model=model, system=system, user=user,
                                                     max_tokens=max_tokens)
        req = json.loads(user)
        if "rejected" in req or req.get("job") == "candidates":
            if "rejected" in req:
                self.seen_rejected.append(req["rejected"])
                proposals = json.loads(text)
                if len(self.seen_rejected) == 1 and len(proposals) > 2:
                    # reply with only the fixed elements to prove attempt 0's accepted ones stay
                    return json.dumps([proposals[0], proposals[-1]], ensure_ascii=False), usage
            return text, usage
        proposals = json.loads(text)
        out = [dict(p) for p in proposals]
        if len(out) < 2:
            return json.dumps(out + [{"para": 0, "span": "", "cite": "", "kind": "figure", "verdict": "tie"}]), usage
        out[0]["span"] = out[0]["span"] + " and then some"
        items = {str(it["para"]): it for it in req.get("paragraphs", []) + req.get("context", [])}
        last = out[-1]
        para = items[str(last["para"])]["text"]
        here = ""
        for a, b in claims.sentences(para):
            if para.find(last["span"], a) != -1 and para.find(last["span"], a) < b:
                here = para[a:b]
                break
        feet = " ".join(items.get("fn%d" % n, {}).get("text", "") for _, n in items[str(last["para"])].get("refs", []))
        other = [p["cite"] for p in proposals if p["cite"] and p["cite"] not in here and p["cite"] not in feet]
        last["cite"] = other[0] if other else "PX-0 at 1"
        out.append(dict(proposals[0], verdict="tie"))
        return json.dumps(out, ensure_ascii=False), usage


@expectation("scenario 13: a proposer that faults attempt 0 fails P1, P2 and P3 there; attempt 1 merges "
             "with attempt 0's accepted proposals, clips and caps reasons, and matches a clean run")
def scenario_13():
    eng = LAB.copy("sc13")
    real = providers.make_client
    clients = []

    def make(matter, names, terms=None, root="."):
        c = FaultyRules(names, matter["date_order"])
        clients.append(c)
        return c

    providers.make_client = make
    try:
        rc, out, rid = run(eng, "--draft", UNTAGGED)
    finally:
        providers.make_client = real
    check(rid is not None, "the run with the faulty proposer: exit %s" % rc)
    attempts = load_json(os.path.join(run_dir(eng, rid), "proposals.json"))["chunks"][0]["attempts"]
    got = [a["codes"] for a in attempts]
    check(got == [["P1", "P2", "P3"], []], "chunk 1 attempts fail %s" % got)
    rej = clients[0].seen_rejected[0] if clients and clients[0].seen_rejected else []
    flat = " ".join(r for item in rej for r in item.get("reasons", []))
    check(len(rej) == 3 and all(isinstance(it.get("element"), int) and it.get("reasons") for it in rej) and
          "verbatim" in flat and "sentence" in flat and "expected exact keys" in flat and
          not any(code in flat for code in ("P1", "P2", "P3", "P7")),
          "retry rejected payload: %s" % rej)
    check(claims.retry_reasons({"rows": [{"proposal": {"para": 1, "span": "x"}, "codes": ["P7"],
                                          "why": ["cite 'a' differs from code's pairing 'b'"]}]}) == [],
          "retry_reasons leaked a P7 row")
    # clip every model-supplied value (para, span, cite, kind, keys) and cap retry_reasons at 40
    pl = proposal_lab()
    huge = "x" * 200
    many_keys = dict({"para": huge, "span": huge, "cite": huge, "kind": huge},
                     **{("k%02d_" % i) + huge: 1 for i in range(15)})
    flood = [many_keys] + [{"para": 9999, "span": "y" * 200, "cite": "z" * 200, "kind": "figure"} for _ in range(44)]
    capped = claims.retry_reasons(claims.accept(json.dumps(flood), pl["analysis"], pl["chunks"][0], {}, "model"))
    r0 = " ".join(capped[0]["reasons"]) + " " + str(capped[0].get("span", "")) + " " + str(capped[0].get("para", ""))
    check(len(capped) == claims.RETRY_CAP == 40 and huge not in r0 and "+7 more" in r0 and "..." in r0,
          "clipping/cap failed: len=%d, r0=%r" % (len(capped), r0[:200]))
    ueng, urid, _, _ = untagged_run()
    with open(os.path.join(run_dir(eng, rid), "verdicts.json"), "rb") as fh:
        hooked = fh.read()
    with open(os.path.join(run_dir(ueng, urid), "verdicts.json"), "rb") as fh:
        plain = fh.read()
    check(hooked == plain, "the retried run's verdicts differ from a run without the hook")
    reperf, _, _, _ = gate.reperform(eng, load_json(os.path.join(run_dir(eng, rid), "intake.json")),
                                     load_json(os.path.join(eng, "matter.json")), run_dir(eng, rid))
    check(reperf == plain, "S5 re-performance after merged retry differs from verdicts.json")


@expectation("scenario 14: two signs of one run print one fingerprint; an edited rulings.csv changes it")
def scenario_14():
    a, rid = signable("sc14a")
    b, _ = signable("sc14b")
    c, _ = signable("sc14c")
    fill_rulings(c, rid, lambda r: r.__setitem__(3, r[3] + " (edited)"))
    res = [sign(e, rid) for e in (a, b, c)]
    check(all(r["rc"] == 0 for r in res), "sign exits %s: %s" % ([r["rc"] for r in res], [r["code"] for r in res]))
    printed = [re.search(r"Fingerprint for the certification: ([0-9a-f ]+)", r["text"]).group(1) for r in res]
    fps = [signed_fingerprint(e, rid) for e in (a, b, c)]
    check(fps[0] == fps[1] and printed[0] == printed[1] == gate.grouped(fps[0]) and fps[2] != fps[0],
          "fingerprints %s" % [f[:8] for f in fps])
    so = load_json(os.path.join(run_dir(a, rid), "signoff.json"))
    check(so["confirmed_count"] == 10 and so["reading_check"] == "passed" and so["tty"] is False
          and so["terminal_check"] == "selftest seam" and "confirmation_minutes" not in so,
          "signoff.json records %s" %
          {k: so.get(k) for k in ("confirmed_count", "reading_check", "tty", "terminal_check", "confirmation_minutes")})
    rc, out = tie(a, "status", "--run", rid)
    check(rc == 0 and "signed" in out, "status of the signed run: exit %s" % rc)


@expectation("scenario 15: an edited middle line of the ledger is reported by status and refused by S1")
def scenario_15():
    eng, rid = signable("sc15")
    lines = ledger_lines(eng)
    middle = json.loads(lines[1])
    middle["time"] = "2026-01-01T00:00:00Z"
    lines[1] = json.dumps(middle, separators=(",", ":"))
    write_ledger(eng, lines)
    rc, out = tie(eng, "status", "--run", rid)
    check(rc == 1 and "BROKEN" in out and "line 3" in out, "status: exit %s: %s"
          % (rc, [ln.strip() for ln in out.splitlines() if "ledger" in ln]))
    sign_probe(sign(eng, rid), 3, "S1")


# =================================================================================================
# Scenario probes 17 to 22, then scenario 16, which runs last
# =================================================================================================


class StubModel(providers.ProviderClient):
    """A test double for a model in this process: answers each user message with reply(request),
    sent as JSON, or as it is when reply gives text."""

    name, host = "stub-model", "local"

    def __init__(self, reply):
        self.reply = reply

    def complete(self, *, model, system, user, max_tokens):
        out = self.reply(json.loads(user))
        return (out if isinstance(out, str) else json.dumps(out)), {"input_tokens": 0, "output_tokens": 0}


@expectation("scenario 17: a loopback stub accepts the chat format end to end with a synthetic counsel-terms "
             "block, job 4 sends record snippets only to a model and only when counsel turns them on, and "
             "malformed replies leave a complete run")
def scenario_17():
    eng, rid, seen, rc, out = chat_run()
    check(rc == 1 and rid, "the chat run: exit %s: %s" % (rc, out.strip()[-300:]))
    rd = run_dir(eng, rid)
    bodies = [json.loads(s["body"].decode("utf-8")) for s in seen]
    check(seen and all(s["path"] == "/v1/chat/completions" and not s["query"] and not s["proxied"] for s in seen) and
          all(sorted(b) == ["max_tokens", "messages", "model", "temperature"] and b["temperature"] == 0 and
              b["model"] == stub_model.MODEL and [m["role"] for m in b["messages"]] == ["system", "user"]
              for b in bodies), "the stub received %s" % [(s["path"], sorted(b)) for s, b in zip(seen, bodies)][:2])
    check(all(s["headers"].get("Authorization") == "Bearer " + API_KEY and API_KEY.encode("utf-8") not in s["body"]
              for s in seen), "the key did not travel in Authorization: Bearer alone")
    rec = receipts(rd)
    sent = [read_bytes(os.path.join(rd, "sent", "%04d-request.json" % r["n"])) for r in rec]
    check(len(rec) == len(seen) and sent == [s["body"] for s in seen] and
          all(r["status"] == "ok" and r["host"] == "127.0.0.1" and r["peers"] and all(p["ok"] for p in r["peers"])
              for r in rec), "%d receipts for %d calls, or sent/ differs from what the stub received" %
          (len(rec), len(seen)))
    src, sout = tie(eng, "status", "--run", rid)
    check(src == 0, "status of the chat run: exit %s: %s" % (src, sout.strip()[-300:]))
    said = [r for r in verdicts(eng, rid)["claims"] if r["proposed_by"] == "model" and r["span"] == "seventy-five"]
    check(len(said) == 1 and said[0]["code"] == "tie", "the model's words claim over the wire: %s" % said)
    job4 = [m for m in (json.loads(b["messages"][1]["content"]) for b in bodies) if m.get("job") == "candidates"]
    hinted = [r for r in drop_log(eng, rid) if "model-candidate" in r["hint_source"]]
    check(len(job4) == 1 and job4[0]["items"] and hinted and
          all(c["snippet"] for it in job4[0]["items"] for c in it["candidates"]) and
          all(r["hint_source"] == ("model-candidate" if r["hint"].startswith("candidate ") else "code, model-candidate")
              for r in hinted), "%d job 4 call(s), model-candidate hints %s" %
          (len(job4), [(r["hint_source"], r["hint"][:40]) for r in hinted]))
    fixture = read_bytes(os.path.join(MATTER, "replay", "untagged-chat", "verdicts.json"))
    check(read_bytes(os.path.join(rd, "verdicts.json")) == fixture,
          "verdicts.json differs from the replay fixture's, recorded with candidate snippets off")
    egress = load_json(os.path.join(rd, "intake.json"))["egress"]
    report = read_text(os.path.join(rd, "tieout-report.md"))
    check("record snippets" in egress and "127.0.0.1" in egress and "host 127.0.0.1" in report and
          "endpoint counsel-terms.json names" in report, "intake.json says %r, or the report's Egress section "
                                                       "does not name the host" % egress)
    check(not [p for p, b in run_files(eng) if API_KEY.encode("utf-8") in b], "the key is in a run file")
    # job 4 in this process: off, no job; under rules, no job even with snippets on; a model's invalid pick is dropped
    ueng, urid, _, _ = untagged_run()
    check("candidates" not in load_json(os.path.join(run_dir(ueng, urid), "proposals.json")),
          "job 4 ran with candidate_snippets off")
    jeng = LAB.copy("job4")
    update_json(os.path.join(jeng, "counsel-terms.json"), {"candidate_snippets": True})
    jrc, _, jrid = run(jeng, "--draft", UNTAGGED)
    jd = run_dir(jeng, jrid) if jrid else ""
    same = bool(jrid) and read_bytes(os.path.join(jd, "verdicts.json")) == \
        read_bytes(os.path.join(run_dir(ueng, urid), "verdicts.json"))
    # the rules proposer sends nothing, so neither rules run keeps a sent/ folder or a receipt
    kept = [p for p, _ in run_files(jeng) + run_files(ueng) if "/sent/" in p or p.endswith("/receipts.jsonl")]
    check(jrc == 1 and same and "candidates" not in load_json(os.path.join(jd, "proposals.json")) and not kept and
          "Record snippets" not in read_text(os.path.join(jd, "tieout-report.md")) and
          "Provider rules, run in this process: nothing left the machine." in read_text(os.path.join(jd, "tieout-report.md")),
          "rules with candidate snippets on: exit %s, verdicts.json %s, job 4 ran, or a rules run kept %s" %
          (jrc, "the same" if same else "changed", kept[:2]))
    pl = proposal_lab()
    built = claims.build_claims(pl["draft"], pl["analysis"], pl["grammar"], [])
    found = verify.verify_all(built, pl["index"])

    def reply(req):
        return [{"item": it["item"], "choice": 9 if len(it["candidates"]) == 1 else 2} for it in req["items"]]
    matter = load_json(os.path.join(LAB.base, "matter.json"))
    hints, doc, _ = tieout.candidate_hints(StubModel(reply), providers.Recorder(None), matter, built, found, pl["index"])
    two = [it["item"] for it in doc["items"] if len(it["locations"]) >= 2]
    check(two and sorted(hints) == sorted(two) and
          all(h["hint_source"] == "model-candidate" and "candidate 2 of" in h["hint"] for h in hints.values()),
          "picks %s for the items with two or more candidates %s" % (sorted(hints), two))
    fenced = tieout.candidate_hints(StubModel(lambda req: "```json\n%s\n```" % json.dumps(reply(req))),
                                    providers.Recorder(None), matter, built, found, pl["index"])
    check(fenced[0] == hints, "a job 4 reply in one code fence gave picks %s" % sorted(fenced[0]))
    deep = tieout.candidate_hints(StubModel(lambda req: "[" * 100000 + "]" * 100000), providers.Recorder(None), matter,
                                  built, found, pl["index"])
    check(not deep[0] and all(it["choice"] is None for it in deep[1]["items"]),
          "a job 4 reply nested past the parser's depth gave picks %s" % sorted(deep[0]))
    # malformed replies over the wire: a kind that is a list, a reply nested past the parser's depth, job 4
    # items that are a list or an object, and envelopes that do not parse; each is refused and the run completes

    def odd(req):
        msg = json.loads(req["messages"][-1]["content"])
        if msg.get("job") == "candidates":
            return json.dumps([{"item": [it["item"]], "choice": 1} for it in msg["items"]] +
                              [{"item": {"c": 1}, "choice": 1}])
        if "rejected" in msg:
            return "[" * 100000 + "]" * 100000
        return json.dumps([dict(p, kind=[p["kind"]]) for p in json.loads(stub_model.rules_reply(req))])
    with loopback() as serve:
        stub = serve(reply=odd)
        meng = chat_engagement("sc17-odd", stub, terms={"candidate_snippets": True})
        mrc, mout, mrid = run(meng, env={"TIEOUT_API_KEY": API_KEY})
        mcalls = len(stub.seen)
    mprop = load_json(os.path.join(run_dir(meng, mrid), "proposals.json")) if mrid else {}
    codes = [a["codes"] for c in mprop.get("chunks", []) for a in c["attempts"]]
    check(mrc == 1 and mrid and tie(meng, "status", "--run", mrid)[0] == 0 and ["P5"] in codes and ["P1"] in codes and
          mprop["candidates"]["asked"] and all(it["choice"] is None for it in mprop["candidates"]["items"]) and
          mcalls == mprop["calls"], "malformed replies: exit %s after %d call(s), attempt codes %s: %s"
          % (mrc, mcalls, codes[:4], mout.strip()[-200:]))
    zero = {"input_tokens": 0, "output_tokens": 0}
    for env_bytes in (b'{"choices":[{"message":{"content":"[]"}}],"usage":{"prompt_tokens":1e999}}',
                      b"[" * 100000 + b"]" * 100000, b'{"choices":[{"message":{"content":["x"]}}]}'):
        check(providers.reply_text(env_bytes) == ("", zero), "an envelope that does not parse gave %r"
              % (providers.reply_text(env_bytes)[0][:40],))


@expectation("scenario 18: the stub observes a custom auth header name and a fixed query parameter")
def scenario_18():
    env = {"TIEOUT_API_KEY": API_KEY, "TIEOUT_AUTH_HEADER": "X-Api-Key", "TIEOUT_AUTH_SCHEME": "",
           "TIEOUT_EXTRA_HEADERS": "X-Tenant: synthetic-tenant; X-Trace: on", "TIEOUT_QUERY": "api-version=2026-10-01"}
    with loopback() as serve:
        stub, bare = serve(), serve()
        rc, out, _ = run(chat_engagement("sc18", stub), env=env)
        brc, _, _ = run(chat_engagement("sc18-nokey", bare, matter={"key_env": ""}))  # a self-hosted server: no key
        seen, bseen = list(stub.seen), list(bare.seen)
    heads = [{k.lower(): v for k, v in s["headers"].items()} for s in seen]
    check(rc == 1 and seen and all(h.get("x-api-key") == API_KEY and "authorization" not in h and
                                   h.get("x-tenant") == "synthetic-tenant" and h.get("x-trace") == "on" for h in heads)
          and all(s["query"] == "api-version=2026-10-01" for s in seen),
          "exit %s; headers %s; query %s" % (rc, sorted(heads[0]) if heads else [], [s["query"] for s in seen][:1]))
    check(brc == 1 and bseen and not any("authorization" in {k.lower() for k in s["headers"]} for s in bseen),
          "with key_env set to \"\": exit %s, an auth header sent" % brc)


@expectation("scenario 19: https_proxy set to a loopback trap gets no connection")
def scenario_19():
    with loopback() as serve:
        stub, trap = serve(), serve()
        rc, out, _ = run(chat_engagement("sc19", stub), env=dict({k: proxy_url(trap) for k in PROXY_VARS},
                                                                 TIEOUT_API_KEY=API_KEY))
        settle(lambda: trap.connections > 0, 0.2)
        calls, trapped = len(stub.seen), trap.connections
    check(rc == 1 and calls and not trapped, "exit %s; %d call(s) to the endpoint, %d connection(s) to the trap"
          % (rc, calls, trapped))


@expectation("scenario 20: replay reproduces verdicts.json byte for byte with sockets patched, from a run and from "
             "the committed fixture, and measure --proposer scores the committed batch beside rules and judges it "
             "by the turn-on rule, which invented scores meet, and miss on each term alone, on a lost digit tie and "
             "on a covered quotation traded for a missed one")
def scenario_20():
    eng, rid, _, _, _ = chat_run()
    before = len(SOCKET_EVENTS)
    try:
        reng = model_engagement("sc20-run", "replay", {"replay_from": "run/" + rid}, source=eng)
        rc, out, rrid = run(reng)
        feng = with_replay(model_engagement("sc20-fixture", "replay", {"replay_from": "replay/untagged-chat"}))
        frc, fout, frid = run(feng)
        outs = [tie(LAB.base, "measure", "--proposer") for _ in range(2)]
    finally:
        repatch()
    check(len(SOCKET_EVENTS) == before, "socket activity during replay: %s" % SOCKET_EVENTS[before:][:3])
    check(rc == 1 and rrid and read_bytes(os.path.join(run_dir(reng, rrid), "verdicts.json")) ==
          read_bytes(os.path.join(run_dir(eng, rid), "verdicts.json")),
          "replay of the chat run: exit %s: %s" % (rc, out.strip()[-200:]))
    rec = receipts(run_dir(reng, rrid))
    check(rec and all(r["host"] == "replay" and not r["peers"] for r in rec) and tie(reng, "status", "--run", rrid)[0] == 0,
          "the replay run's receipts %s" % rec[:1])
    check(frc == 1 and frid and read_bytes(os.path.join(run_dir(feng, frid), "verdicts.json")) ==
          read_bytes(os.path.join(MATTER, "replay", "untagged-chat", "verdicts.json")),
          "replay of the committed fixture: exit %s: %s" % (frc, fout.strip()[-200:]))
    text = outs[0][1]
    check(outs[0][0] == 0 and outs[0] == outs[1], "measure --proposer: exit %s; two runs %s"
          % (outs[0][0], "agree" if outs[0] == outs[1] else "differ"))
    batch = text[text.find("replay untagged-chat, model %s" % stub_model.MODEL):]
    for part, line in ((text, "rules (the baseline)"), (text, "  quotations  recall 15 of 15"),
                       (text, "  words       recall 3 of 3"), (text, "  flags       none proposed"),
                       (text, "  hints       true location picked"), (batch, "replay untagged-chat"),
                       (batch, "  quotations  recall 15 of 15"), (batch, "  words       recall 3 of 3"),
                       (batch, "model %s: the rule is met on matter 1; matter 2 is not measured yet, so the model "
                               "stays off" % stub_model.MODEL),
                       (batch, "  figures and dates in digits, which rules covers: ties 92 of the 92 claims rules ties, "
                               "no worse"),
                       (batch, "    mis-association 0 of 15 against rules' 0 of 15, no worse"),
                       (batch, "numbers and dates in words, which rules misses: checks 1 of the 3 labelled")):
        check(line in part, "measure --proposer does not print %r%s" % (line, "" if part is text else
                                                                       " for the committed batch"))
    import measure  # as tieout measure imports it

    def sc(labels, proposed, hits, mis, checked):
        return {"labels": labels, "proposed": proposed, "hits": set(hits), "mis": set(mis), "checked": set(checked)}
    rules = {"quotations": sc(10, 9, "abcdefghi", "", "abcdefghi"), "words": sc(4, 6, "wxyz", "yz", ""),
             "digit_ties": {1, 2, 3}}
    same, ties = sc(10, 9, "abcdefghi", "", "abcdefghi"), {1, 2, 3}
    for quotes, words_, digits, want, line in (
            (same, sc(4, 2, "wx", "", "wx"), ties, True,
             "numbers and dates in words, which rules misses: checks 2 of the 4 labelled spans rules leaves unchecked, better"),
            (sc(10, 10, "abcdefghij", "", "abcdefghij"), sc(4, 0, "", "", ""), ties, True,
             "quote marks, which rules misses: checks 1 of the 1 labelled spans rules leaves unchecked, better"),
            (sc(10, 8, "abcdefgh", "", "abcdefgh"), sc(4, 4, "wxyz", "", "wxyz"), ties, False,
             "recall 8 of 9 against rules' 9 of 9, worse"),
            (sc(10, 10, "abcdefghi", "", "abcdefghi"), sc(4, 4, "wxyz", "", "wxyz"), ties, False,
             "precision over every quotation proposed 9 of 10 against rules' 9 of 9, worse"),
            (sc(10, 9, "abcdefghi", "i", "abcdefgh"), sc(4, 4, "wxyz", "", "wxyz"), ties, False,
             "mis-association 1 of 9 against rules' 0 of 9, worse"),
            (same, sc(4, 0, "", "", ""), ties, False,
             "words, which rules misses: checks 0 of the 4 labelled spans rules leaves unchecked, not better"),
            (same, sc(4, 2, "wx", "", "wx"), {1, 2}, False,
             "figures and dates in digits, which rules covers: ties 2 of the 3 claims rules ties, worse"),
            (sc(10, 9, "abcdefghj", "", "abcdefghj"), sc(4, 0, "", "", ""), ties, False,  # trades a covered for a missed
             "recall 8 of 9 against rules' 9 of 9, worse")):
        met, lines = measure.turn_on(rules, {"quotations": quotes, "words": words_, "digit_ties": digits})
        check(met is want and any(line in x for x in lines), "invented scores: the turn-on rule is %s, expected %s, "
              "and should print %r:\n%s" % ("met" if met else "not met", "met" if want else "not met", line,
                                             "\n".join(lines)))


@expectation("scenario 21: a replay miss exits 2 with no socket call and no receipt; a replay_from outside the "
             "engagement folder or in key/, a draft in key/ and a served file in key/, by any case of key/ or of "
             "the engagement folder, or through a link, exit 2 before anything is read")
def scenario_21():
    eng = with_replay(model_engagement("sc21", "replay", {"replay_from": "replay/untagged-chat",
                                                         "model": "synthetic-proposer-2"}))
    before = len(SOCKET_EVENTS)
    try:
        rc, out, _ = run(eng)
    finally:
        repatch()
    rd = last_run(eng)
    check(rc == 2 and "replay has no recorded response" in out and "nothing was sent" in out,
          "exit %s: %s" % (rc, out.strip()[-200:]))
    check(len(SOCKET_EVENTS) == before and rd and not os.path.exists(os.path.join(rd, "receipts.jsonl")) and
          not os.path.exists(os.path.join(rd, "sent")), "socket activity %s, or a receipt or body was written"
          % SOCKET_EVENTS[before:][:3])
    bad = []
    for i, where in enumerate(("key/x", "Key/x", "lab/x", "../elsewhere", "", os.path.abspath(LAB.tmp))):
        e = model_engagement("sc21-%d" % i, "replay", {"replay_from": where})
        if where in ("key/x", "Key/x", "lab/x"):  # a real recorded batch, so only the key/ refusal can stop it
            shutil.copytree(os.path.join(MATTER, "replay", "untagged-chat"), os.path.join(e, "key", "x"),
                            copy_function=shutil.copyfile)
        if where == "lab/x":
            try:
                os.symlink(os.path.join(e, "key"), os.path.join(e, "lab"), target_is_directory=True)
            except (OSError, NotImplementedError):  # Windows without the right to make links: nothing to test
                continue
        r, o, _ = run(e)
        said = "the runner never opens key/" if where in ("key/x", "Key/x", "lab/x") else \
            "replay_from must name a folder inside the engagement folder, outside key/"
        if r != 2 or said not in o or last_run(e):
            bad.append((where, r))
    # KEY/absent.md runs with no key/ folder at all, so only the name compare in any case can refuse it
    for i, where in enumerate(("key/draft.md", "Key/draft.md", "KEY/absent.md")):
        e = LAB.copy("sc21-draft-%d" % i)
        if where != "KEY/absent.md":
            os.makedirs(os.path.join(e, "key"), exist_ok=True)
            shutil.copyfile(os.path.join(e, "report", "draft.md"), os.path.join(e, "key", "draft.md"))
        r, o, _ = run(e, "--draft", where)
        if r != 2 or "the runner never opens key/" not in o or last_run(e):
            bad.append((where, r))
    # status --served takes a path from anywhere; one in key/, in any case or through a link, is refused
    # before the file is opened, so the served check cannot be used to read the answer key
    se = LAB.copy("sc21-served")
    os.makedirs(os.path.join(se, "key"))
    write_text(os.path.join(se, "key", "x.docx"), "SYNTHETIC: a file in key/ that status must never open\n")
    linked = True
    try:
        os.symlink(os.path.join(se, "key"), os.path.join(se, "lab"), target_is_directory=True)
    except (OSError, NotImplementedError):  # Windows without the right to make links: that leg is skipped
        linked = False
    for where in ("key/x.docx", "KEY/x.docx", "lab/x.docx")[:3 if linked else 2]:
        r, o = tie(se, "status", "--served", os.path.join(se, where))
        if r != 2 or "the runner never opens key/" not in o:
            bad.append(("--served " + where, r))
    # the engagement folder named in another case: on a disk that ignores case it is the same
    # folder, and key/ under it must still be refused; a disk that keeps case has no such folder
    other = os.path.join(os.path.dirname(se), os.path.basename(se).upper())
    if os.path.isdir(other) and os.path.samefile(other, se):
        r, o = tie(other, "status", "--served", os.path.join(se, "key", "x.docx"))
        if r != 2 or "the runner never opens key/" not in o:
            bad.append(("--engagement in another case, --served key/x.docx", r))
    check(not bad, "key/ and outside-folder refusals that failed: %s" % bad)


SPEC_WORDS = (("four thousand eight hundred and twelve", "4812"), ("the fourteenth of March 2019", "2019-03-14"),
              ("the first quarter of 2019", "2019-Q1"), ("two and a half percent", "2.5%"))  # one of each form


@expectation("scenario 22: the words.py case table reads as it says")
def scenario_22():
    bad = words.check_cases()
    check(not bad, "; ".join(bad[:3]))
    n = len(words.CASES) + len(words.FIND_CASES)
    check(n >= 38 and all(c in words.CASES and (words.read(c[0]) or {}).get("show") == c[1] for c in SPEC_WORDS),
          "the table holds %d cases, or misses or misreads one of the four phrases in SPEC_WORDS" % n)


@expectation("scenario 16: the whole selftest ran with sockets patched, and the stage 3 loopback windows let "
             "through nothing but loopback")
def scenario_16():
    still = all(getattr(socket, n, None) is stub for n, stub in _GUARD["patched"].items())
    check(_GUARD["canary"] and still and not _GUARD["window"] and "socket" in _GUARD["patched"],
          "the guard was not in place: audit hook live %s, patches in place %s, a window open %s"
          % (_GUARD["canary"], still, _GUARD["window"]))
    check(not SOCKET_EVENTS, "socket activity: %s" % SOCKET_EVENTS[:5])


# --- main ---------------------------------------------------------------------------------------


def main(argv=None):
    global LAB
    args = list(sys.argv[1:] if argv is None else argv)
    verbose = "-v" in args or "--verbose" in args
    started = time.time()
    for name in [n for n in os.environ if n.upper().startswith("TIEOUT_") or n.lower() in
                 ("http_proxy", "https_proxy", "all_proxy", "no_proxy")]:
        del os.environ[name]  # this process only: no key, header or proxy from the shell reaches a probe
    errors = []
    LAB = Lab()
    try:
        ok, version, rel_hash, running = gate.release_check()
        if not ok:
            print("note: RELEASE.json (%s) does not match the running code (%s); the probes that sign will "
                  "refuse on S9 until you run python3 -I tieout/gate.py release" % (rel_hash[:12], running[:12]))
        for label, probe in EXPECTATIONS:
            try:
                probe()
            except Miss as exc:
                errors.append("%s: %s" % (label, exc))
            except Exception as exc:  # noqa: BLE001 - a crash in a probe is a failed expectation
                errors.append("%s: crashed: %s: %s\n%s" % (label, type(exc).__name__, exc,
                                                          "".join(traceback.format_exc(limit=4))))
            else:
                if verbose:
                    print("ok   %s" % label)
    finally:
        rmtree(LAB.tmp)
    for e in errors:
        print("FAIL", e)
    total = len(EXPECTATIONS)
    if verbose:
        print("ran in %.1f s" % (time.time() - started))
    print("selftest: PASS (%d expectations)" % total if not errors else
          "selftest: %d of %d expectations failed" % (len(errors), total))
    return 0 if not errors else 1


if __name__ == "__main__":
    sys.exit(main())
