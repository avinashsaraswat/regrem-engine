"""Write gate, ledger, sign-off and status for the tie-out.

Purpose: every write the tool makes goes through write() or append() here, which check W2 to W9
  and fail closed. The engagement's ledger.jsonl is a hash chain, each line naming the hash of
  the line before it (W7 refuses an append whose prev is not the head). sign() runs S1 to S9 in
  order and writes signoff.json and its ledger line only when all pass; it prints the
  fingerprint, one sha256 over the draft, the record, the verdicts, the rulings, the ledger head
  and the code. status() compares what is on disk with what the run recorded, checks the
  receipts against sent/ and counsel-terms.json through providers.verify_receipts (N9), and
  with --served compares a served .docx with the signed text. W1 (only this module writes) and N1
  (only providers.py touches the network) are syntax-tree walks in selftest.py, outside the
  released code.
Reads: the engagement folder: matter.json, counsel-terms.json, report/, record/, run/<id>/,
  ledger.jsonl; tieout/RELEASE.json and the tool's own code files for the code hash.
Writes: only into the engagement folder's run/<id>/ and ledger.jsonl, and run/.lock while a
  run or sign holds the folder. With the measure scope, only measure.py's
  records in tieout/: FROZEN.json and batches/*.json, a batch file once. init_folder() writes
  the starting layout of a new engagement folder that holds no ledger. Run as a script,
  "release" writes tieout/RELEASE.json for the code as it stands.
Network: none.
Exit codes: as a library, a refusal raises GateRefused, which the CLI turns into exit 3. As a
  script: 0 written, 2 on a usage error. tieout.py --version checks RELEASE.json against the
  running code.
"""
import csv
import datetime
import getpass
import hashlib
import json
import os
import re
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import claims  # noqa: E402
import record  # noqa: E402
import verify  # noqa: E402

ALLOW = ("run/*/**", "ledger.jsonl")
PROTECT = ("report/**", "record/**", "matter.json", "counsel-terms.json", "key/**", "RELEASE.json", "tieout/**")
WRITE_ONCE = ("intake.json", "verdicts.json", "proposals.json")
# The measure scope: measure.py's records, written beside this module in tieout/. FROZEN.json is
# rewritten by each freeze; a batch file is written once and never overwritten.
MEASURE_ALLOW = ("FROZEN.json", "batches/*.json")
MEASURE_PROTECT = ("RELEASE.json", "*.py", "*.md", "*.example.json", "fixture/**", "prompts/**", "docs/**",
                   "key/**")
MEASURE_ONCE = ("batches/*.json",)
MAX_WRITE = 16 * 1024 * 1024
MAX_RUN = 512 * 1024 * 1024
CODE_FILES = ("tieout.py", "claims.py", "docx_reader.py", "record.py", "verify.py", "gate.py", "providers.py",
              "measure.py", "words.py")
LEDGER = "ledger.jsonl"
ZERO = "0" * 64
CLEARING = ("record-supports", "not-a-claim", "expert-opinion")
RULINGS = CLEARING + ("corrected", "remove")
RULING_COLUMNS = ["key", "item", "ruling", "note", "location", "minutes", "ruled_by"]
OUTPUT_FILES = ("verdicts.json", "tieout-report.md", "drop-log.md", "drop-log.csv", "proposals.json",
                "receipts.jsonl", "draft.txt")

_STATE = {"root": None, "key_env": "TIEOUT_API_KEY"}


class GateRefused(Exception):
    """A refusal: code (W2 to W9, S1 to S9) and the reason, with no secret in it."""

    def __init__(self, code, reason):
        Exception.__init__(self, "%s: %s" % (code, reason))
        self.code, self.reason = code, reason


def configure(root, key_env="TIEOUT_API_KEY"):
    _STATE["root"] = os.path.abspath(root)
    _STATE["key_env"] = key_env or "TIEOUT_API_KEY"


def now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --- W2 to W9 -----------------------------------------------------------------------------------


def _rx(template, optin, glob=True):
    """Ported from the author's earlier private code: {key} is filled from the opt-in values; * ? ** are globs."""
    out, globs = [], {"**": ".*", "*": "[^/]*", "?": "[^/]"} if glob else {}
    for part in re.split(r"(\{\w+\})", template):
        tail = "(?:/.*)?" if glob and part.endswith("/**") else ""
        if re.fullmatch(r"\{\w+\}", part):
            out.append(re.escape(str(optin[part[1:-1]])))
        else:
            for tok in re.findall(r"\*\*|\*|\?|[^*?]+", part[:-3] if tail else part):
                out.append(globs.get(tok) or re.escape(tok))
        out.append(tail)
    return re.compile("".join(out), re.S)


def _over_cap(texts, policy, kept=0):
    """Ported from the author's earlier private code: from sizes alone; a cap that is not a number raises,
    and the raise becomes W9."""
    cap = policy.get("max_write_bytes", 1000000)
    return any(len(t) > cap or kept + len(t) > cap for t in texts)


def _folder_bytes(path):
    total = 0
    for dirpath, _, names in os.walk(path):
        for n in names:
            try:
                total += os.lstat(os.path.join(dirpath, n)).st_size
            except OSError:
                pass
    return total


def _target(path, root=None):
    """W6: the engagement-relative POSIX path and the full path, inside the folder, with no
    symlink in any component. root is the engagement folder, or tieout/ for the measure scope."""
    root = root or _STATE["root"]
    if not root:
        raise GateRefused("W9", "the gate has no engagement folder configured")
    full = os.path.abspath(path if os.path.isabs(path) else os.path.join(root, path))
    try:
        rel = os.path.relpath(full, root)
    except ValueError:  # another drive on Windows
        raise GateRefused("W6", "%s lies outside the engagement folder" % path)
    if rel == os.curdir or rel == os.pardir or rel.startswith(os.pardir + os.sep) or os.path.isabs(rel):
        raise GateRefused("W6", "%s lies outside the engagement folder" % path)
    probe = root
    for part in rel.split(os.sep):
        probe = os.path.join(probe, part)
        if os.path.islink(probe):
            raise GateRefused("W6", "%s has a symlink in its path" % rel.replace(os.sep, "/"))
    real_root = os.path.realpath(root)
    real = os.path.realpath(full)
    if os.path.commonpath([real_root, real]) != real_root:
        raise GateRefused("W6", "%s resolves outside the engagement folder" % path)
    return rel.replace(os.sep, "/"), full


def _secrets():
    out = []
    for name in (_STATE["key_env"], "TIEOUT_PROXY_AUTH"):
        v = os.environ.get(name or "", "")
        if len(v) >= 8:  # a shorter value would refuse ordinary text; real keys are longer
            out.append((name, v.encode("utf-8")))
    return out


def _check_measure(path, data, create):
    """W2 to W9 for the measure scope: a path inside tieout/ on MEASURE_ALLOW and off
    MEASURE_PROTECT, a create flag for a new file, a batch file written once, the size cap and
    the key values."""
    rel, full = _target(path, HERE)
    if not isinstance(data, (bytes, bytearray)):
        raise GateRefused("W9", "%s: the gate writes bytes only" % rel)
    if any(_rx(g.casefold(), {}).fullmatch(rel.casefold()) for g in MEASURE_PROTECT):
        raise GateRefused("W3", "%s is protected" % rel)
    if not any(_rx(g, {}).fullmatch(rel) for g in MEASURE_ALLOW):
        raise GateRefused("W2", "%s is not on the measure allowlist" % rel)
    exists = os.path.lexists(full)
    if not exists and not create:
        raise GateRefused("W4", "%s does not exist and the write was not flagged create" % rel)
    if exists and create:
        raise GateRefused("W4", "%s exists; the gate does not overwrite a file it was asked to create" % rel)
    if exists and any(_rx(g, {}).fullmatch(rel) for g in MEASURE_ONCE):
        raise GateRefused("W4", "%s is written once" % rel)
    if _over_cap([bytes(data)], {"max_write_bytes": MAX_WRITE}):
        raise GateRefused("W5", "%s: one write is capped at 16 MB" % rel)
    for name, value in _secrets():
        if value in bytes(data):
            raise GateRefused("W8", "%s: the bytes hold the value of %s; nothing was written" % (rel, name))
    return rel, full


def _check(path, data, create, appending=False):
    rel, full = _target(path)
    if not isinstance(data, (bytes, bytearray)):
        raise GateRefused("W9", "%s: the gate writes bytes only" % rel)
    if any(_rx(g.casefold(), {}).fullmatch(rel.casefold()) for g in PROTECT):  # protected wins over allowed
        raise GateRefused("W3", "%s is protected" % rel)
    if not any(_rx(g, {}).fullmatch(rel) for g in ALLOW):
        raise GateRefused("W2", "%s is not on the write allowlist" % rel)
    exists = os.path.lexists(full)
    parts = rel.split("/")
    if parts[0] == "run" and len(parts) >= 3:
        run_dir = os.path.join(_STATE["root"], "run", parts[1])
        if os.path.exists(os.path.join(run_dir, "signoff.json")):
            raise GateRefused("W4", "run %s is closed: it holds signoff.json" % parts[1])
    if appending:
        if not exists and not create:
            raise GateRefused("W4", "%s does not exist and the append was not flagged create" % rel)
    elif not exists and not create:
        raise GateRefused("W4", "%s does not exist and the write was not flagged create" % rel)
    elif exists and create:
        raise GateRefused("W4", "%s exists; the gate does not overwrite a file it was asked to create" % rel)
    elif exists and parts[-1] in WRITE_ONCE:
        raise GateRefused("W4", "%s is written once per run" % rel)
    if _over_cap([bytes(data)], {"max_write_bytes": MAX_WRITE}):
        raise GateRefused("W5", "%s: one write is capped at 16 MB" % rel)
    if parts[0] == "run" and len(parts) >= 3:
        if _folder_bytes(os.path.join(_STATE["root"], "run", parts[1])) + len(data) > MAX_RUN:
            raise GateRefused("W5", "run folder %s would pass its 512 MB cap" % parts[1])
    for name, value in _secrets():
        if value in bytes(data):
            raise GateRefused("W8", "%s: the bytes hold the value of %s; nothing was written" % (rel, name))
    return rel, full


def write(path, data, create=False, scope="engagement"):
    """Write bytes to path inside the engagement folder, or raise GateRefused. With scope
    "measure" the path is relative to tieout/ and only measure.py's records may be written:
    FROZEN.json and batches/*.json."""
    try:
        if scope == "measure":
            rel, full = _check_measure(path, data, create)
        elif scope == "engagement":
            rel, full = _check(path, data, create)
        else:
            raise GateRefused("W9", "unknown write scope %r" % (scope,))
        if create:
            os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "xb" if create else "wb") as fh:
            fh.write(data)
        return rel
    except GateRefused:
        raise
    except Exception as exc:  # noqa: BLE001 - W9: any error inside the gate refuses the write
        raise GateRefused("W9", "gate error on %s: %s" % (path, type(exc).__name__))


def append(path, data, create=False):
    """Append bytes to path, or raise GateRefused."""
    try:
        rel, full = _check(path, data, create, appending=True)
        if create:
            os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "ab") as fh:
            fh.write(data)
        return rel
    except GateRefused:
        raise
    except Exception as exc:  # noqa: BLE001
        raise GateRefused("W9", "gate error on %s: %s" % (path, type(exc).__name__))


def lock():
    """Hold run/.lock for the length of a run or sign, so a second one refuses."""
    root = _STATE["root"]
    try:
        os.makedirs(os.path.join(root, "run"), exist_ok=True)
        fd = os.open(os.path.join(root, "run", ".lock"), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise GateRefused("W4", "another run or sign holds run/.lock; remove it only if none is in progress")
    except OSError as exc:
        raise GateRefused("W9", "cannot take run/.lock: %s" % exc.strerror)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write("%d %s\n" % (os.getpid(), now()))


def unlock():
    path = os.path.join(_STATE["root"], "run", ".lock")
    if os.path.exists(path):
        os.remove(path)


# --- hashes, release ----------------------------------------------------------------------------


def text_sha(path):
    """sha256 of a code or prompt file with line endings read as LF, so a Windows checkout that
    writes CRLF hashes the same."""
    with open(path, "rb") as fh:
        return record.sha256_bytes(fh.read().replace(b"\r\n", b"\n"))


def code_manifest(here=HERE):
    return {n: text_sha(os.path.join(here, n)) for n in CODE_FILES if os.path.isfile(os.path.join(here, n))}


def code_hash(here=HERE):
    return record.tree_hash(code_manifest(here))


def prompt_hashes(here=HERE):
    out = {}
    pdir = os.path.join(here, "prompts")
    if os.path.isdir(pdir):
        for n in sorted(os.listdir(pdir)):
            if os.path.isfile(os.path.join(pdir, n)):
                out["prompts/" + n] = text_sha(os.path.join(pdir, n))
    return out


def read_release(here=HERE):
    with open(os.path.join(here, "RELEASE.json"), encoding="utf-8") as fh:
        return json.load(fh)


def release_doc(version, here=HERE):
    return {"version": version, "stage": 3, "code_sha256": code_hash(here), "code_files": code_manifest(here),
            "regenerate": "python3 -I tieout/gate.py release"}


def release_check(here=HERE):
    """(matches, release version, release hash, running hash)."""
    rel = read_release(here)
    running = code_hash(here)
    return rel.get("code_sha256") == running, rel.get("version", ""), rel.get("code_sha256", ""), running


# --- the ledger ---------------------------------------------------------------------------------


def _lines(root):
    path = os.path.join(root, LEDGER)
    if not os.path.isfile(path):
        return []
    with open(path, "rb") as fh:
        raw = fh.read()
    return [ln.rstrip(b"\r") for ln in raw.split(b"\n") if ln.strip()]


def line_hash(line):
    return record.sha256_bytes(line.rstrip(b"\r\n"))


def ledger_head(root=None):
    lines = _lines(root or _STATE["root"])
    return line_hash(lines[-1]) if lines else ZERO


def ledger_entry(event, run, payload):
    """A ledger line for event over payload bytes, with prev read now (W7 checks it again)."""
    root = _STATE["root"]
    lines = _lines(root)
    return {"seq": len(lines), "prev": line_hash(lines[-1]) if lines else ZERO, "event": event, "run": run,
            "sha256": record.sha256_bytes(payload), "time": now()}


def ledger_append(entry):
    """W7: append when entry's prev equals the head read from the file at this moment."""
    head = ledger_head()
    if entry.get("prev") != head:
        raise GateRefused("W7", "the ledger head moved since this line was built; nothing was appended")
    line = json.dumps({k: entry[k] for k in ("seq", "prev", "event", "run", "sha256", "time")},
                      separators=(",", ":")) + "\n"
    append(LEDGER, line.encode("utf-8"))
    return line_hash(line.encode("utf-8"))


def verify_chain(root):
    """(problems, head, entries): the chain from the genesis line to the head."""
    problems, entries, prev = [], [], ZERO
    lines = _lines(root)
    if not lines:
        return ["ledger.jsonl is missing or empty"], ZERO, []
    for i, ln in enumerate(lines):
        try:
            obj = json.loads(ln.decode("utf-8"))
        except ValueError:
            problems.append("ledger line %d does not parse" % (i + 1))
            prev = line_hash(ln)
            continue
        if not isinstance(obj, dict) or set(obj) != {"seq", "prev", "event", "run", "sha256", "time"}:
            problems.append("ledger line %d does not have the six ledger fields" % (i + 1))
        elif obj["seq"] != i:
            problems.append("ledger line %d has seq %r" % (i + 1, obj["seq"]))
        elif obj["prev"] != prev:
            problems.append("ledger line %d: prev does not match line %d's hash; line %d was edited or a line "
                            "was removed" % (i + 1, i, i))
        if i == 0 and isinstance(obj, dict) and obj.get("event") != "genesis":
            problems.append("ledger line 1 is not the genesis line")
        entries.append(obj if isinstance(obj, dict) else {})
        prev = line_hash(ln)
    return problems, prev, entries


def init_folder(folder, matter_example, terms_example):
    """Create a new engagement folder's layout, the two configs and the genesis line. Refuses a
    folder that already holds a ledger, and never overwrites a file."""
    folder = os.path.abspath(folder)
    if os.path.exists(os.path.join(folder, LEDGER)):
        raise GateRefused("W4", "%s already holds a ledger" % folder)
    made = []
    for sub in ("report", os.path.join("record", "pages"), os.path.join("record", "documents"),
                os.path.join("record", "transcripts"), os.path.join("record", "data"), "run"):
        p = os.path.join(folder, sub)
        if not os.path.isdir(p):
            os.makedirs(p)
            made.append(sub.replace(os.sep, "/") + "/")
    for src, name in ((matter_example, "matter.json"), (terms_example, "counsel-terms.json")):
        dest = os.path.join(folder, name)
        if os.path.exists(dest):
            continue
        with open(src, "rb") as fh:
            data = fh.read()
        with open(dest, "xb") as fh:
            fh.write(data)
        made.append(name)
    genesis = {"seq": 0, "prev": ZERO, "event": "genesis", "run": "",
               "sha256": record.sha256_bytes(b"tieout engagement ledger"), "time": now()}
    with open(os.path.join(folder, LEDGER), "xb") as fh:
        fh.write((json.dumps(genesis, separators=(",", ":")) + "\n").encode("utf-8"))
    made.append(LEDGER)
    return made


# --- rulings ------------------------------------------------------------------------------------


def read_rulings(path, drop_keys=None):
    """rulings.csv as {key: row} plus quarantined rows, the one reader of the file: sign, status
    and a later run's carry-forward all read it here. A row is quarantined when it is malformed,
    when its key repeats (the first copy is kept), when its ruling or minutes do not read, or,
    when drop_keys is given, when its key is not a drop-log item of the run. Carry-forward passes
    no drop_keys and keeps the keys still in its own drop log."""
    rows, quarantined = {}, []
    if not os.path.isfile(path):
        return rows, ["rulings.csv is missing"]
    with open(path, encoding="utf-8-sig", newline="") as fh:
        reader = list(csv.reader(fh))
    if not reader or [h.strip().lower() for h in reader[0]] != RULING_COLUMNS:
        return rows, ["rulings.csv: the header is not %s" % ", ".join(RULING_COLUMNS)]
    seen = set()
    for i, r in enumerate(reader[1:], 2):
        if not any(c.strip() for c in r):
            continue
        if len(r) != len(RULING_COLUMNS):
            quarantined.append("row %d: %d fields where the header has %d" % (i, len(r), len(RULING_COLUMNS)))
            continue
        row = dict(zip(RULING_COLUMNS, [c.strip() for c in r]))
        key = row["key"]
        if key in seen:
            quarantined.append("row %d: key %s repeats" % (i, key))
            continue
        seen.add(key)
        if drop_keys is not None and key not in drop_keys:
            quarantined.append("row %d: key %r is not a drop-log item of this run" % (i, key))
            continue
        if row["ruling"] and row["ruling"] not in RULINGS:
            quarantined.append("row %d: ruling %r is not one of %s" % (i, row["ruling"], ", ".join(RULINGS)))
            continue
        if row["minutes"]:
            try:
                float(row["minutes"])
            except ValueError:
                quarantined.append("row %d: minutes %r is not a number" % (i, row["minutes"]))
                continue
        rows[key] = row
    return rows, quarantined


def state_of(row, expert):
    if not row or not row.get("ruling"):
        return "open"
    if row.get("ruled_by", "") != expert:
        return "proposed"
    return "cleared" if row["ruling"] in CLEARING else "removed"


# --- re-performance, fingerprint and sign -------------------------------------------------------


def _json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def reperform(root, intake, matter, run_dir):
    """S5: claims and verify again from the draft and record on disk, with the run's accepted
    proposals, as verdicts.json bytes."""
    index = record.load(root, matter["date_order"])
    grammar = claims.Grammar(index.grammar_names(), matter["date_order"])
    draft = claims.read_draft(os.path.join(root, intake["draft"]["path"]),
                              accept_tracked=intake.get("tracked_changes") == "accepted")
    analysis = claims.analyse(draft, grammar)
    props = _json(os.path.join(run_dir, "proposals.json"))
    accepted = []
    chunks = claims.chunks(draft, analysis, matter["chunk_paragraphs"])
    if len(chunks) != len(props.get("chunks", [])):
        return b"", [], index, grammar  # a different chunking cannot re-perform; S5 refuses
    for chunk, stored in zip(chunks, props["chunks"]):
        res = claims.accept(json.dumps(stored.get("accepted", [])), analysis, chunk, {}, props.get("proposed_by", "rules"))
        accepted += res["accepted"]
    built = claims.build_claims(draft, analysis, grammar, accepted)
    return verify.document(built, verify.verify_all(built, index), analysis["not_checked"]), built, index, grammar


def fingerprint(parts):
    """sha256 over the draft hash, the record manifest hash, the verdicts.json hash, the
    rulings.csv hash, the ledger head and the RELEASE code hash, in that order."""
    return record.sha256_bytes("\n".join(parts).encode("utf-8"))


def grouped(fp):
    return " ".join(fp[i:i + 4] for i in range(0, len(fp), 4))


def _run_lines(entries, run_id):
    return {e.get("event"): e for e in entries if e.get("run") == run_id}


def inside(packet, p):
    """Ported from the author's earlier private code: True when path p points inside the folder, after
    following symbolic links."""
    root = os.path.realpath(packet)
    full = os.path.realpath(os.path.join(packet, p))
    return not os.path.isabs(p) and os.path.commonpath([root, full]) == root


def packet_hash(packet, files):
    """Ported from the author's earlier private code: one sha256 over each listed file's path and bytes."""
    h = hashlib.sha256()
    for item in sorted(files, key=lambda f: f["path"]):
        if not inside(packet, item["path"]):
            raise ValueError(f"{item['path']}: path leaves the packet folder")
        h.update(item["path"].encode("utf-8") + b"\0")
        with open(os.path.join(packet, item["path"]), "rb") as fh:
            h.update(fh.read() + b"\0")
    return h.hexdigest()


def outputs_payload(run_dir):
    """The payload of a run's outputs ledger line: the packet hash over the output files present."""
    files = [{"path": n} for n in OUTPUT_FILES if os.path.isfile(os.path.join(run_dir, n))]
    return ("outputs " + packet_hash(run_dir, files)).encode("utf-8")


def sign(root, run_id, matter, out=print, ask=input, *, terminal=None):
    """S1 to S9 in order, the confirmation walk, the fingerprint, signoff.json and its ledger
    line. Returns the exit code: 0 signed, 1 refused by a ruling check, 3 a hash or gate refusal.

    terminal is a test seam: a callable that stands in for sys.stdin.isatty() in S8, so the
    selftest can drive the confirmation walk without a terminal. It is keyword-only and the
    command line never passes it, so a person signing always meets the real check, and
    signoff.json records tty false whenever the seam was used."""
    run_dir = os.path.join(root, "run", run_id)
    if not os.path.isfile(os.path.join(run_dir, "intake.json")):
        raise GateRefused("S1", "run %s has no intake.json" % run_id)
    if os.path.exists(os.path.join(run_dir, "signoff.json")):
        old = _json(os.path.join(run_dir, "signoff.json"))
        out("run %s is closed: it was signed at %s with fingerprint %s" % (run_id, old.get("time"),
                                                                           grouped(old.get("fingerprint", ""))))
        raise GateRefused("W4", "run %s is closed: it holds signoff.json" % run_id)
    intake = _json(os.path.join(run_dir, "intake.json"))
    verdicts_path = os.path.join(run_dir, "verdicts.json")
    with open(verdicts_path, "rb") as fh:
        verdicts_bytes = fh.read()
    vdoc = json.loads(verdicts_bytes.decode("utf-8"))
    drops = [r for r in vdoc["claims"] if not r["pass"]]
    drop_keys = {r["key"] for r in drops}
    rulings_path = os.path.join(run_dir, "rulings.csv")
    rulings, quarantined = read_rulings(rulings_path, drop_keys)
    for q in quarantined:
        out("quarantined: rulings.csv %s" % q)

    # S1: the chain, and this run's intake and output lines in it
    problems, head, entries = verify_chain(root)
    lines = _run_lines(entries, run_id)
    with open(os.path.join(run_dir, "intake.json"), "rb") as fh:
        intake_sha = record.sha256_bytes(fh.read())
    if "intake" not in lines or lines["intake"].get("sha256") != intake_sha:
        problems.append("the ledger has no intake line for run %s matching intake.json" % run_id)
    if "outputs" not in lines or lines["outputs"].get("sha256") != record.sha256_bytes(outputs_payload(run_dir)):
        problems.append("the ledger has no outputs line for run %s matching the run's output files" % run_id)
    if problems:
        raise GateRefused("S1", "; ".join(problems))
    # S2: the draft
    draft_path = os.path.join(root, intake["draft"]["path"])
    if not os.path.isfile(draft_path) or record.sha256_file(draft_path) != intake["draft"]["sha256"]:
        raise GateRefused("S2", "the draft on disk does not hash to intake.json's draft hash")
    # S3: the two configs
    for name, k in (("matter.json", "matter_sha256"), ("counsel-terms.json", "counsel_terms_sha256")):
        p = os.path.join(root, name)
        if not os.path.isfile(p) or record.sha256_file(p) != intake[k]:
            raise GateRefused("S3", "%s does not hash to intake.json's value" % name)
    # S4: the record manifest
    index_now = record.load(root, matter["date_order"])
    if index_now.files != intake["record"]["files"]:
        added = sorted(set(index_now.files) - set(intake["record"]["files"]))
        missing = sorted(set(intake["record"]["files"]) - set(index_now.files))
        changed = sorted(p for p in index_now.files if p in intake["record"]["files"]
                         and index_now.files[p] != intake["record"]["files"][p])
        raise GateRefused("S4", "record drift: added %s; missing %s; changed %s"
                          % (added or "none", missing or "none", changed or "none"))
    # S5: re-performance
    again, _, index, grammar = reperform(root, intake, matter, run_dir)
    if not again:
        raise GateRefused("S5", "proposals.json does not match the draft's proposer chunks")
    if again != verdicts_bytes:
        new = json.loads(again.decode("utf-8"))
        first = next((a["key"] for a, b in zip(new["claims"], vdoc["claims"]) if a != b),
                     "claim count %d against %d" % (len(new["claims"]), len(vdoc["claims"])))
        raise GateRefused("S5", "re-performance differs from verdicts.json at %s" % first)
    # S6: every drop-log item cleared by the expert's ruling
    expert = matter["expert"]
    refusals = []
    for r in drops:
        row = rulings.get(r["key"])
        if not row or not row["ruling"]:
            refusals.append("%s is open" % r["key"])
        elif not row["ruled_by"]:
            refusals.append("%s: ruled_by is blank; the expert writes the name matter.json gives" % r["key"])
        elif row["ruled_by"] != expert:
            refusals.append("%s: ruled_by %r is not the expert named in matter.json" % (r["key"], row["ruled_by"]))
        elif row["ruling"] in ("corrected", "remove"):
            refusals.append("%s is ruled %s and its key is still in the draft" % (r["key"], row["ruling"]))
        elif row["ruling"] == "record-supports":
            cite, why = claims.parse_cite(row["location"], grammar) if row["location"] else (None, "no location")
            if cite is None or cite["type"] in ("id", "calc"):
                refusals.append("%s: location %r does not parse: %s" % (r["key"], row["location"], why or "Id. is not a location"))
            else:
                try:
                    verify.locate(cite, index)
                except verify.Fail as f:
                    refusals.append("%s: location %r does not resolve: %s" % (r["key"], row["location"], f.reason))
    if refusals:
        for x in refusals:
            out("S6 refused: " + x)
        return _refused("S6", "%d drop-log item(s) not cleared by the expert" % len(refusals), out)
    # S7: rulings.csv keys a subset of the drop log, no duplicate, nothing quarantined
    if quarantined:
        return _refused("S7", "rulings.csv has %d quarantined row(s)" % len(quarantined), out)
    with open(rulings_path, "rb") as fh:
        rulings_sha = record.sha256_bytes(fh.read())
    # S8: the confirmation walk at a terminal
    release = read_release()
    fp = fingerprint([intake["draft"]["sha256"], intake["record"]["manifest_sha256"],
                      record.sha256_bytes(verdicts_bytes), rulings_sha, head, release.get("code_sha256", "")])
    at_terminal = sys.stdin.isatty() if terminal is None else bool(terminal())
    if not at_terminal:
        return _refused("S8", "stdin is not a terminal; the expert signs at a terminal", out)
    clearing = [(r, rulings[r["key"]]) for r in drops]
    confirmed = []
    out("Run %s: %d drop-log item(s) to confirm, each ruling in full." % (run_id, len(clearing)))
    try:  # end of input (Ctrl-D, Ctrl-Z) or Ctrl-C at a prompt ends the walk as a refusal
        for r, row in clearing:
            out("")
            out(_item_text(r, row))
            if ask("Confirm this ruling? [y/n] ").strip().lower() != "y":
                return _refused("S8", "the expert did not confirm %s" % r["key"], out)
            confirmed.append(r["key"])
        summary = _summary(run_id, intake, vdoc, clearing, fp)
        out("")
        out(summary)
        typed = ask("Type the first eight characters of the fingerprint: ").strip().replace(" ", "").lower()
    except (EOFError, KeyboardInterrupt):
        out("")
        return _refused("S8", "the expert ended the session before confirming", out)
    if typed != fp[:8]:
        return _refused("S8", "the reading check failed", out)
    # S9: the code
    running = code_hash()
    if release.get("code_sha256") != running or intake.get("code_sha256") != running:
        raise GateRefused("S9", "RELEASE.json, the running code and intake.json do not share one code hash")
    signoff = {"run": run_id, "fingerprint": fp,
               "inputs": {"draft_sha256": intake["draft"]["sha256"],
                          "record_manifest_sha256": intake["record"]["manifest_sha256"],
                          "verdicts_sha256": record.sha256_bytes(verdicts_bytes), "rulings_sha256": rulings_sha,
                          "ledger_head": head, "code_sha256": running},
               "expert": expert, "os_account": _account(), "host": _host(), "time": now(),
               "tty": terminal is None, "terminal_check": "sys.stdin.isatty" if terminal is None else "selftest seam",
               "signature": {"party": "expert", "role": "testifying expert", "signer": expert,
                             "signed": now()[:10]},
               "summary_sha256": record.sha256_bytes(summary.encode("utf-8")), "confirmed_keys": confirmed,
               "confirmed_count": len(confirmed), "reading_check": "passed"}
    data = (json.dumps(signoff, indent=1, sort_keys=True) + "\n").encode("utf-8")
    entry = ledger_entry("sign", run_id, data)
    write(os.path.join("run", run_id, "signoff.json"), data, create=True)
    ledger_append(entry)
    out("")
    out("Signed. Fingerprint for the certification: %s" % grouped(fp))
    return 0


def _refused(code, reason, out):
    out("%s refused: %s" % (code, reason))
    return 1


def _account():
    try:
        return getpass.getuser()
    except Exception:  # noqa: BLE001 - no account name on this system
        return ""


def _host():
    """The host name for signoff.json from os.uname(), or the COMPUTERNAME Windows sets. The
    platform module would reach the socket module on Windows, which N1 keeps out of gate.py."""
    try:
        return os.uname().nodename
    except AttributeError:
        return os.environ.get("COMPUTERNAME", "")


def _item_text(r, row):
    where = "paragraph %s" % r["para"] if r["para"] is not None else "footnote %s" % r["footnote"]
    return "\n".join([
        "item     %s, %s sentence %s: %s %s" % (r["key"], where, r["sentence"], r["kind"], r["span"]),
        "cite     %s%s" % (r["cite_text"] or "(none)", " -> " + r["cite_resolved"] if r["cite_resolved"]
                           and r["cite_resolved"] != r["cite_text"] else ""),
        "code     %s: %s" % (r["code"], r["reason"]),
        "ruling   %s" % row["ruling"],
        "note     %s" % (row["note"] or "(none)"),
        "location %s" % (row["location"] or "(none)"),
        "ruled_by %s" % row["ruled_by"],
        "hint     %s%s" % (r["hint"] or "(none)", " (source: %s)" % r["hint_source"] if r["hint"] else ""),
    ])


def _summary(run_id, intake, vdoc, clearing, fp):
    weak = [r for r in vdoc["claims"] if r["pass"] and r["weak_flags"]]
    lines = ["Sign-off summary for run %s" % run_id,
             "draft    %s  %s" % (intake["draft"]["path"], intake["draft"]["sha256"]),
             "record   %d files, manifest %s" % (len(intake["record"]["files"]), intake["record"]["manifest_sha256"]),
             "counts   " + ", ".join("%s %d" % kv for kv in sorted(vdoc["counts"].items())),
             "clearing rulings (%d):" % len(clearing)]
    for r, row in clearing:
        lines.append("  %s %s %s ruled %s by %s%s" % (r["key"], r["code"], r["span"], row["ruling"], row["ruled_by"],
                                                    " at " + row["location"] if row["location"] else ""))
    lines.append("weak-tie spot-check sample (%d):" % len(weak))
    for r in weak:
        lines.append("  %s %s (%s) %s" % (r["key"], r["span"], r["cite_resolved"] or "-", ", ".join(r["weak_flags"])))
    lines.append("egress   " + intake.get("egress", "none"))
    lines.append("fingerprint %s" % grouped(fp))
    return "\n".join(lines)


# --- status -------------------------------------------------------------------------------------


def run_order(root):
    """Run ids oldest first: in the ledger's intake order, then any folder the ledger lacks."""
    rdir = os.path.join(root, "run")
    folders = sorted(n for n in os.listdir(rdir) if os.path.isdir(os.path.join(rdir, n))) if os.path.isdir(rdir) else []
    order = []
    for ln in _lines(root):
        try:
            obj = json.loads(ln.decode("utf-8"))
        except ValueError:
            continue
        if isinstance(obj, dict) and obj.get("event") == "intake" and obj.get("run") in folders \
                and obj["run"] not in order:
            order.append(obj["run"])
    return order + [n for n in folders if n not in order]


def latest_run(root):
    runs = run_order(root)
    return runs[-1] if runs else None


def _fp_pattern(fp):
    return r"\s*".join(re.escape(ch) for ch in fp)


def _holds_fp(text, fp):
    return bool(fp) and re.search(_fp_pattern(fp), text, re.I) is not None


def _strip_fp(text, fp):
    if not fp:
        return text
    return re.sub(_fp_pattern(fp), "", text, flags=re.I)


def _strip_cert(text, fp):
    """Remove one certification phrase quoting fp (or bare fp), leaving any other prose intact."""
    if not fp:
        return text
    fpat = _fp_pattern(fp)
    paren = (r"\s*\(\s*(?:tie[-\s]?out\s+)?(?:fingerprint|certification)"
             r"(?:\s+for\s+the\s+certification)?[:\s]*" + fpat + r"\.?\s*\)")
    clause = (r"(?:tie[-\s]?out\s+certification[.:]?\s+)?"
              r"(?:the\s+signed\s+(?:draft|report)\s+carries\s+)?"
              r"(?:(?:tie[-\s]?out\s+)?(?:fingerprint|certification)"
              r"(?:\s+for\s+the\s+certification)?[:\s]+)?" + fpat + r"\.?")
    out, n = re.subn(paren, "", text, count=1, flags=re.I)
    return out if n else re.sub(clause, "", text, count=1, flags=re.I)


def _block_parts(b, text):
    """(body, list_number) with leading list markers stripped on headings and block quotes too,
    so a heading restyled to a non-Heading style in Word compares the same way."""
    if b["heading"] or b["block_quote"]:
        body, _, num = claims.strip_list_marker(text)
        return body, num
    return text, b.get("list_number", "")


def _served_block_text(b, fp, signed_paras=()):
    """Text of one served block with fp removed: bare fp strip when an aligned signed paragraph
    already holds the surrounding certification words, otherwise _strip_cert."""
    text = b["text"]
    if not fp or not _holds_fp(text, fp):
        return text
    candidates = (_strip_fp(text, fp), re.sub(_fp_pattern(fp) + r"\.?", "", text, count=1, flags=re.I))
    for cand in candidates:
        c_body, c_num = _block_parts(b, cand)
        for sa in signed_paras:
            s_body, s_num = _block_parts(sa, sa["text"])
            if record.norm_text(s_body) == record.norm_text(c_body) and s_num == c_num:
                return cand
    return _strip_cert(text, fp)


def _masked_norm(b, grammar, text):
    body, _ = _block_parts(b, text)
    toks = [t for t in claims.tokenise(body, grammar, (), b["heading"], b["block_quote"])
            if t["kind"] in ("figure", "date", "quotation", "cite")]
    masked = list(body)
    for t in toks:
        for i in range(t["start"], t["end"]):
            masked[i] = "#"
    return record.norm_text("".join(masked))


def served_keys(draft, grammar, fp="", signed=None):
    """The served-file claim set: every figure, date, quotation and cite the tokeniser alone
    finds in the reads-as text, keyed by kind, span and sentence. The fingerprint quoted in a
    certification is removed first."""
    out = {}
    signed_paras = [sb for sb in signed["blocks"] if sb["kind"] == "para"] if signed else ()
    for b in draft["blocks"]:
        raw = _served_block_text(b, fp, signed_paras if b["kind"] == "para" else ()) if fp else b["text"]
        text, _ = _block_parts(b, raw)
        block = claims.finish_block(b["kind"], b["n"], text, [], b["refs"], b["heading"], b["block_quote"])
        toks = [t for t in claims.tokenise(text, grammar, (), b["heading"], b["block_quote"])
                if t["kind"] in ("figure", "date", "quotation", "cite")]
        masked = list(text)
        for t in toks:  # the sentence is compared with its tokens masked, so one changed figure
            for i in range(t["start"], t["end"]):  # shows alone and its neighbours still match
                masked[i] = "#"
        masked = "".join(masked)
        for t in toks:
            i, _ = claims.sentence_of(block, t["start"])
            a, z = block["sentences"][i - 1]
            k = claims.claim_key(t["text"], t["kind"], masked[a:z])
            out.setdefault(k, []).append("%s %s, %s: %s" % ("paragraph" if b["kind"] == "para" else "footnote",
                                                             b["n"], t["kind"], t["text"]))
    return out


def served_text_diffs(signed, served_draft, grammar, fp="", flagged_signed=()):
    """Normalised whole-text comparison over paragraphs and footnotes. The fingerprint text is
    removed before comparing, whether it sits in one added certification paragraph (which may hold
    no other prose) or is typed into an existing certification paragraph."""
    out = []
    for kind, label in (("para", "paragraph"), ("foot", "footnote")):
        sb = [b for b in signed["blocks"] if b["kind"] == kind]
        vb = [b for b in served_draft["blocks"] if b["kind"] == kind]
        if kind == "para" and fp and len(vb) == len(sb) + 1:
            certs = [i for i, b in enumerate(vb) if _holds_fp(b["text"], fp)]
            if len(certs) == 1:
                cb = vb[certs[0]]
                c_body, c_num = _block_parts(cb, _strip_cert(cb["text"], fp))
                if record.norm_text(c_body) or c_num or cb["refs"]:
                    out.append("%s %d text differs from the signed text" % (label, cb["n"]))
                vb = vb[:certs[0]] + vb[certs[0] + 1:]
        if len(vb) != len(sb):
            out.append("the served file has %d %s(s); the signed text has %d" % (len(vb), label, len(sb)))
            continue
        for a, b in zip(sb, vb):
            s_body, s_num = _block_parts(a, a["text"])
            v_raw = _served_block_text(b, fp, (a,)) if (kind == "para" and fp) else _strip_fp(b["text"], fp)
            v_body, v_num = _block_parts(b, v_raw)
            s_refs = [n for _, n in a["refs"]]
            v_refs = [n for _, n in b["refs"]]
            if record.norm_text(s_body) == record.norm_text(v_body) and s_num == v_num and s_refs == v_refs:
                continue
            if (_masked_norm(a, grammar, a["text"]) != _masked_norm(b, grammar, v_raw)
                    or s_num != v_num
                    or s_refs != v_refs
                    or (a["kind"], a["n"]) not in flagged_signed):
                out.append("%s %d text differs from the signed text" % (label, a["n"]))
    return out


def status(root, run_id=None, served=None, out=print):
    """0 when everything on disk matches what the run recorded, 1 when void or different."""
    run_id = run_id or latest_run(root)
    if not run_id:
        out("status: no run yet")
        return 1
    run_dir = os.path.join(root, "run", run_id)
    if not os.path.isfile(os.path.join(run_dir, "intake.json")):
        out("status: run %s has no intake.json" % run_id)
        return 1
    intake = _json(os.path.join(run_dir, "intake.json"))
    matter = _json(os.path.join(root, "matter.json")) if os.path.isfile(os.path.join(root, "matter.json")) else {}
    bad = []
    out("run %s" % run_id)
    draft_path = os.path.join(root, intake["draft"]["path"])
    checks = [("draft %s" % intake["draft"]["path"], draft_path, intake["draft"]["sha256"]),
              ("matter.json", os.path.join(root, "matter.json"), intake["matter_sha256"]),
              ("counsel-terms.json", os.path.join(root, "counsel-terms.json"), intake["counsel_terms_sha256"])]
    for label, path, want in checks:
        ok = os.path.isfile(path) and record.sha256_file(path) == want
        out("  %-24s %s" % (label, "matches intake" if ok else "VOID: differs from intake"))
        if not ok:
            bad.append(label)
    index = record.load(root, matter.get("date_order") if matter.get("date_order") in ("mdy", "dmy") else "mdy")
    if index.files != intake["record"]["files"]:
        out("  %-24s VOID: differs from intake" % "record")
        bad.append("record")
    else:
        out("  %-24s %d files match intake" % ("record", len(index.files)))
    if prompt_hashes() != intake.get("prompts", {}):
        out("  %-24s VOID: differs from intake" % "prompts")
        bad.append("prompts")
    running = code_hash()
    if running != intake.get("code_sha256"):
        out("  %-24s VOID: the running code differs from intake" % "code")
        bad.append("code")
    problems, head, entries = verify_chain(root)
    lines = _run_lines(entries, run_id)
    with open(os.path.join(run_dir, "intake.json"), "rb") as fh:
        if "intake" not in lines or lines["intake"].get("sha256") != record.sha256_bytes(fh.read()):
            problems.append("no ledger intake line matches intake.json")
    if "outputs" not in lines or lines["outputs"].get("sha256") != record.sha256_bytes(outputs_payload(run_dir)):
        problems.append("no ledger outputs line matches the run's output files")
    for p in problems:
        out("  ledger                   BROKEN: %s" % p)
    if problems:
        bad.append("ledger")
    else:
        out("  %-24s chain verifies, head %s" % ("ledger", head))
    import providers  # here, not at the top: providers imports this module
    terms_path = os.path.join(root, "counsel-terms.json")
    rbad = providers.verify_receipts(run_dir, _json(terms_path) if os.path.isfile(terms_path) else {})
    for p in rbad:
        out("  receipts                 DIFFERS: %s" % p)
    bad += ["receipts"] if rbad else []
    if os.path.isfile(os.path.join(run_dir, "verdicts.json")):
        vdoc = _json(os.path.join(run_dir, "verdicts.json"))
        drops = [r for r in vdoc["claims"] if not r["pass"]]
        rulings, quarantined = read_rulings(os.path.join(run_dir, "rulings.csv"), {r["key"] for r in drops})
        states = {}
        for r in drops:
            s = state_of(rulings.get(r["key"]), matter.get("expert"))
            states[s] = states.get(s, 0) + 1
        out("  %-24s %d item(s): %s" % ("drop log", len(drops), ", ".join("%s %d" % kv for kv in sorted(states.items()))
                                         or "none"))
        for q in quarantined:
            out("  quarantined              %s" % q)
    fp = ""
    sp = os.path.join(run_dir, "signoff.json")
    if os.path.isfile(sp):
        so = _json(sp)
        fp = so.get("fingerprint", "")
        with open(sp, "rb") as fh:
            so_sha = record.sha256_bytes(fh.read())
        inputs = so.get("inputs", {})
        rp = os.path.join(run_dir, "rulings.csv")
        vp = os.path.join(run_dir, "verdicts.json")
        again = fingerprint([intake["draft"]["sha256"], intake["record"]["manifest_sha256"],
                             record.sha256_file(vp) if os.path.isfile(vp) else "",
                             record.sha256_file(rp) if os.path.isfile(rp) else "",
                             inputs.get("ledger_head", ""), inputs.get("code_sha256", "")])
        signed_line = any(e.get("event") == "sign" and e.get("run") == run_id and e.get("sha256") == so_sha
                          and e.get("prev") == inputs.get("ledger_head") for e in entries)
        if again == fp and signed_line:
            out("  %-24s signed %s, fingerprint %s" % ("signoff", so.get("time"), grouped(fp)))
        else:
            out("  signoff                  DIFFERS: the fingerprint or its ledger line no longer matches")
            bad.append("signoff")
    else:
        out("  %-24s not signed" % "signoff")
    if served:
        grammar = claims.Grammar(index.grammar_names(), matter.get("date_order", "mdy"))
        signed = claims.read_draft(draft_path, accept_tracked=intake.get("tracked_changes") == "accepted")
        try:
            served_draft = claims.read_draft(served, served=True)
        except ValueError as exc:
            out("  served                   cannot read %s: %s" % (served, exc))
            return 1
        a, b = served_keys(signed, grammar), served_keys(served_draft, grammar, fp, signed)
        diff = 0
        flagged_signed = set()
        for k in sorted(set(a) | set(b)):
            na, nb = len(a.get(k, [])), len(b.get(k, []))
            if na > nb:
                for d in a[k][nb:]:
                    out("  served                   MISSING from the served file: %s" % d)
                    head_parts = d.split(",", 1)[0].split()
                    flagged_signed.add(("para" if head_parts[0] == "paragraph" else "foot", int(head_parts[1])))
                    diff += 1
            elif nb > na:
                for d in b[k][na:]:
                    out("  served                   NOT IN the signed text: %s" % d)
                    diff += 1
        for td in served_text_diffs(signed, served_draft, grammar, fp, flagged_signed):
            out("  served                   DIFFERS: %s" % td)
            diff += 1
        if fp:
            text = " ".join(bl["text"] for bl in served_draft["blocks"])
            if not _holds_fp(text, fp):
                out("  served                   DIFFERS: the served file does not quote the fingerprint")
                diff += 1
        else:
            out("  served                   note: the run is not signed, so there is no fingerprint to look for")
        if diff:
            bad.append("served")
        else:
            out("  %-24s matches the signed text and carries the same figures, dates, quotations and cites" % "served")
    out("status: %s" % ("consistent" if not bad else "VOID or DIFFERS (%s)" % ", ".join(bad)))
    return 0 if not bad else 1


def main(argv=None):
    """Script entry: python3 -I tieout/gate.py release [--version V]. Any other argument is a
    usage error, so nothing is written by a mistyped command."""
    args = list(sys.argv[1:] if argv is None else argv)
    if args[:1] != ["release"] or len(args) not in (1, 3) or (len(args) == 3 and args[1] != "--version"):
        print("usage: python3 -I tieout/gate.py release [--version V]", file=sys.stderr)
        return 2
    path = os.path.join(HERE, "RELEASE.json")
    if len(args) == 3:
        version = args[2]
    else:
        version = read_release().get("version", "0.1.0") if os.path.isfile(path) else "0.1.0"
    doc = release_doc(version)
    with open(path, "wb") as fh:
        fh.write((json.dumps(doc, indent=1, sort_keys=True) + "\n").encode("utf-8"))
    print("wrote tieout/RELEASE.json: version %s, code %s" % (version, doc["code_sha256"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
