#!/usr/bin/env python3
"""Score findings files against traps.json. No model call, no network, standard library only.

Usage, from the run folder:
  python3 -I tools/score.py --traps <traps.json> --memo <memo.md> --layer check=<file>
      [--layer cross-reader=<file>] [--layer owner=<file>] [--floor <file>] [--rulings <file>] --out <folder>
  python3 -I tools/score.py --tally <results.json> [<results.json> ...]
  python3 -I tools/score.py --gate --traps <traps.json> --good <file> --bad <file> [--floor <file>]
  python3 -I tools/score.py --rows <check output> [--write <file>]
  python3 -I tools/score.py --validate <file> [<file> ...]

The formats and the match rule are fixed in tools/SCHEMA.md; this file applies them and nothing more.
Scoring writes RESULTS-table.md and results.json in --out and nothing else. The gate prints PASS or FAIL
and nothing else. Paths are printed relative to the run folder (the folder above tools/, or --run-dir),
or as a bare file name when a file sits outside it. Every count is printed as a count out of a total.
"""

import argparse
import datetime
import hashlib
import json
import re
import sys
import unicodedata
from decimal import Decimal, InvalidOperation
from pathlib import Path

HEADER = ("memo_line", "cite", "value_seen", "problem")
LAYERS = ("check", "cross-reader", "owner")
LAYER_NAMES = {"floor": "Check by design", "check": "Check", "cross-reader": "Cross-reader", "owner": "Owner",
               "any": "Any of the three"}
RUN_DIR = Path(__file__).resolve().parent.parent
RESULTS_MD = "RESULTS-table.md"
RESULTS_JSON = "results.json"
RESULTS_FORMAT = "agent-run-results/1"
NONE_WORDS = ("-", "none")  # either marks an empty field in a findings file
RULINGS_HEADER = ("kind", "id", "entry", "ruling")
TRAP_RULINGS = ("real", "trivial", "wrong")
MATCH_RULINGS = ("yes", "no")
UNMATCHED_RULINGS = ("match", "real", "false-alarm")

TOP_KEYS = {"traps"}
TOP_OPTIONAL = {"case", "note"}
ENTRY_KEYS = {"id", "kind", "listed", "decoy", "file", "file_id", "page", "planted_value", "true_value",
              "key_phrase", "memo_claim"}
ENTRY_OPTIONAL = {"check_sees"}

ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")
EVIDENCE_ID_RE = re.compile(r"[A-Za-z][A-Za-z0-9-]*")
CLAIM_CITE_RE = re.compile(r"(?P<id>[A-Za-z][A-Za-z0-9-]*) p(?P<page>[1-9][0-9]*)")
FINDING_CITE_RE = re.compile(r"(?P<file>\S(?:[^;\t]*\S)?) p(?P<page>[1-9][0-9]*)")
MEMO_LINE_RE = re.compile(r"[1-9][0-9]*")
MEMO_CITE_RE = re.compile(r"\[(?P<id>[A-Za-z][A-Za-z0-9-]*)(?: p(?P<page>\d+))?\]")  # the memo's cite form

# ------------------------------------------------------------------------------------------- refusals


class Refused(Exception):
    """An input the script will not score, with the reason in words."""


class UsageError(Exception):
    """A command line the script cannot run."""


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise UsageError(message)


def shown(path, run_dir):
    """A path as printed: relative to the run folder, or the bare file name when outside it."""
    p = Path(path).resolve()
    try:
        return p.relative_to(run_dir).as_posix()
    except ValueError:
        return p.name


def read_bytes(path, run_dir):
    try:
        return Path(path).read_bytes()
    except OSError as err:
        raise Refused("cannot read {}: {}".format(shown(path, run_dir), err.strerror or "read error"))


def read_text(path, run_dir):
    raw = read_bytes(path, run_dir)
    try:
        return raw.decode("utf-8-sig"), raw
    except UnicodeDecodeError:
        raise Refused("{} is not UTF-8 text".format(shown(path, run_dir)))


def sha256(raw):
    return hashlib.sha256(raw).hexdigest()


# --------------------------------------------------------------------------------------- normal form

DASHES = dict.fromkeys(map(ord, "\u2010\u2011\u2012\u2013\u2014\u2015\u2212\ufe58\ufe63\uff0d"), "-")
QUOTES = {ord(c): "'" for c in "\u2018\u2019\u201a\u201b\u2032"}
QUOTES.update({ord(c): '"' for c in "\u201c\u201d\u201e\u201f\u2033"})


def norm(text):
    """The form both sides are compared in: NFKC, dashes and curly quotes made plain, case folded,
    runs of white space made one space."""
    text = unicodedata.normalize("NFKC", text).translate(DASHES).translate(QUOTES)
    return re.sub(r"\s+", " ", text.casefold()).strip()


def bare(value):
    """A key value or phrase in normal form, less any quotation marks around it."""
    return norm(norm(value).strip("\"'"))


def label_norm(label):
    """An evidence id as the check looks it up: Ex., Exh. and Exhibit stripped, case folded, hyphens and
    spaces ignored."""
    s = re.sub(r"^\s*(?:Exhibit|Exh\.|Ex\.)\s*", "", label, flags=re.I)
    return re.sub(r"[\s\-]", "", s).casefold()


def phrase_pattern(phrase):
    """A normalised phrase found on its own: not inside a longer word or a longer number."""
    head = r"(?<!\w)" if re.match(r"\w", phrase) else ""
    if phrase[:1].isdigit():
        head += r"(?<!\d[.,])"
    tail = r"(?!\w)" if re.search(r"\w$", phrase) else ""
    if phrase[-1:].isdigit():
        tail += r"(?![.,]\d)"
    return re.compile(head + re.escape(phrase) + tail)


# ------------------------------------------------------------------------------------ figures, dates

SCALES = {"thousand": 10 ** 3, "k": 10 ** 3, "million": 10 ** 6, "mn": 10 ** 6, "m": 10 ** 6,
          "billion": 10 ** 9, "bn": 10 ** 9}
_NUM = r"(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?"
_FIGURE = (r"(?P<cur>[$\u00a3\u20ac]\s?)?(?P<num>" + _NUM + r")"
           r"(?:\s?(?P<scale>thousand|million|billion|mn|bn|k|m)(?!\w))?"
           r"(?:\s?(?P<pct>%|percent|per cent)(?!\w))?")
FIGURE_VALUE_RE = re.compile(r"(?:(?:usd|gbp|eur)\s?)?" + _FIGURE + r"(?: [a-z][a-z-]*)?")
FIGURE_TEXT_RE = re.compile(r"(?<![\w.,\-])" + _FIGURE + r"(?!\w)(?![.,]\d)(?!-\d)")
REFERENCE_BEFORE_RE = re.compile(
    r"(?:(?<!\w)(?:p|pp|pg|page|pages|line|lines|row|rows|no\.|number)|[#\u00a7])\s?$")

MONTHS = {"january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3, "april": 4, "apr": 4,
          "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7, "august": 8, "aug": 8, "september": 9,
          "sept": 9, "sep": 9, "october": 10, "oct": 10, "november": 11, "nov": 11, "december": 12, "dec": 12}
_MON = r"(?P<mon>(?:" + "|".join(sorted(MONTHS, key=len, reverse=True)) + r")\.?)"
DATE_RES = (
    re.compile(r"(?<![\w-])(?P<y>\d{4})-(?P<m>\d{1,2})-(?P<d>\d{1,2})(?![\w-])"),
    re.compile(r"(?<![\w-])(?P<d>\d{1,2})(?:st|nd|rd|th)? (?:of )?" + _MON + r" ?,? (?P<y>\d{4})(?![\w-])"),
    re.compile(r"(?<![\w-])" + _MON + r" (?P<d>\d{1,2})(?:st|nd|rd|th)? ?,? (?P<y>\d{4})(?![\w-])"),
    re.compile(r"(?<![\w-])(?P<y>\d{4})-(?P<m>\d{1,2})(?!\w)(?!-\d)"),
    re.compile(r"(?<![\w-])" + _MON + r" ?,? (?P<y>\d{4})(?![\w-])"),
)


def figure_of(m):
    try:
        value = Decimal(m.group("num").replace(",", ""))
    except InvalidOperation:
        return None
    if m.group("scale"):
        value *= SCALES[m.group("scale")]
    return value, bool(m.group("pct"))


def date_of(m):
    """(year, month, day) or (year, month, None), or None when it is not a real date."""
    groups = m.groupdict()
    year = int(groups["y"])
    month = MONTHS[groups["mon"].rstrip(".")] if groups.get("mon") else int(groups["m"])
    day = int(groups["d"]) if groups.get("d") else None
    try:
        datetime.date(year, month, day or 1)
    except ValueError:
        return None
    return year, month, day


def value_kind(value):
    """('figure', (amount, percent)), ('date', tuple) or ('text', pattern) for a normalised value."""
    m = FIGURE_VALUE_RE.fullmatch(value)
    if m and figure_of(m) is not None:
        return "figure", figure_of(m)
    for pattern in DATE_RES:
        m = pattern.fullmatch(value)
        if m and date_of(m) is not None:
            return "date", date_of(m)
    return "text", phrase_pattern(value)


def dates_in(text):
    """Every date written in the text, and the text with those dates blanked out."""
    found, masked = [], list(text)
    for pattern in DATE_RES:
        for m in pattern.finditer(text):
            d = date_of(m)
            if d is not None:
                found.append(d)
                masked[m.start():m.end()] = "\x00" * (m.end() - m.start())
    return found, "".join(masked)


def figures_in(text):
    """Every figure in the text, leaving out the parts of a written date and a number that follows a page,
    line or row word."""
    _, masked = dates_in(text)
    found = []
    for m in FIGURE_TEXT_RE.finditer(masked):
        if REFERENCE_BEFORE_RE.search(masked, max(0, m.start() - 12), m.start()):
            continue
        fig = figure_of(m)
        if fig is not None:
            found.append(fig)
    return found


def holds(kind, target, text):
    """True when a normalised text holds the value."""
    if kind == "figure":
        return any(fig == target for fig in figures_in(text))
    if kind == "date":
        return target in dates_in(text)[0]
    return target.search(text) is not None


# ----------------------------------------------------------------------------------------- traps.json


def fail_entry(n, entry, why):
    ident = entry.get("id") if isinstance(entry, dict) else None
    return Refused("traps.json entry {}{}: {}".format(n, " ({})".format(ident) if isinstance(ident, str) else "", why))


def text_or_null(value):
    return value is None or (isinstance(value, str) and value.strip() != "")


def load_traps(path, run_dir):
    text, raw = read_text(path, run_dir)
    try:
        data = json.loads(text)
    except ValueError as err:
        raise Refused("{} is not valid JSON: line {}".format(shown(path, run_dir), getattr(err, "lineno", "?")))
    if not isinstance(data, dict):
        raise Refused("traps.json must hold one JSON object")
    extra = set(data) - TOP_KEYS - TOP_OPTIONAL
    if extra or not TOP_KEYS <= set(data):
        raise Refused("traps.json top level must hold traps, and may hold case and note; found {}".format(
            ", ".join(sorted(data)) or "nothing"))
    for key in TOP_OPTIONAL:
        if key in data and not isinstance(data[key], str):
            raise Refused("traps.json {} must be text".format(key))
    entries = data["traps"]
    if not isinstance(entries, list) or not entries:
        raise Refused("traps.json traps must be a non-empty list")
    seen = set()
    for n, e in enumerate(entries, 1):
        if not isinstance(e, dict):
            raise fail_entry(n, e, "an entry must be a JSON object")
        missing, extra = ENTRY_KEYS - set(e), set(e) - ENTRY_KEYS - ENTRY_OPTIONAL
        if missing:
            raise fail_entry(n, e, "missing " + ", ".join(sorted(missing)))
        if extra:
            raise fail_entry(n, e, "unknown key " + ", ".join(sorted(extra)))
        if not isinstance(e["id"], str) or not ID_RE.fullmatch(e["id"]):
            raise fail_entry(n, e, "id must be letters, digits, - or _")
        if e["id"] in seen:
            raise fail_entry(n, e, "id is used twice")
        seen.add(e["id"])
        if not isinstance(e["kind"], str) or not e["kind"].strip():
            raise fail_entry(n, e, "kind must be text")
        if e["listed"] not in ("listed", "unlisted"):
            raise fail_entry(n, e, "listed must be \"listed\" or \"unlisted\"")
        if not isinstance(e["decoy"], bool):
            raise fail_entry(n, e, "decoy must be true or false")
        if not isinstance(e["file"], str) or not e["file"].strip() or "\t" in e["file"]:
            raise fail_entry(n, e, "file must be the file's name in evidence/")
        if not isinstance(e["file_id"], str) or not EVIDENCE_ID_RE.fullmatch(e["file_id"]):
            raise fail_entry(n, e, "file_id must be an evidence id in the form the memo cites it")
        if not isinstance(e["page"], int) or isinstance(e["page"], bool) or e["page"] < 1:
            raise fail_entry(n, e, "page must be a whole number from 1")
        for key in ("planted_value", "true_value", "key_phrase"):
            if not text_or_null(e[key]):
                raise fail_entry(n, e, key + " must be text or null")
        has_value = e["planted_value"] is not None or e["true_value"] is not None
        if has_value and e["key_phrase"] is not None:
            raise fail_entry(n, e, "key_phrase must be null when a value is given")
        if not has_value and e["key_phrase"] is None:
            raise fail_entry(n, e, "an entry with no value needs a key_phrase")
        claim = e["memo_claim"]
        if (not isinstance(claim, dict) or set(claim) != {"text", "cites"} or not isinstance(claim["text"], str)
                or not claim["text"].strip() or not isinstance(claim["cites"], list) or not claim["cites"]):
            raise fail_entry(n, e, "memo_claim must hold text and a non-empty list of cites")
        for cite in claim["cites"]:
            if not isinstance(cite, str) or not CLAIM_CITE_RE.fullmatch(cite):
                raise fail_entry(n, e, "each memo_claim cite must read <evidence id> p<page>")
        if "check_sees" in e and not isinstance(e["check_sees"], bool):
            raise fail_entry(n, e, "check_sees must be true or false")
    real = [e for e in entries if not e["decoy"]]
    if not real:
        raise Refused("traps.json holds only decoys")
    marked = [e for e in real if "check_sees" in e]
    if marked and len(marked) != len(real):
        raise Refused("check_sees must be on every trap that is not a decoy, or on none")
    for e in entries:
        e["_match"] = compile_entry(e)
    return {"case": data.get("case"), "entries": entries, "sha256": sha256(raw)}


def compile_entry(e):
    """The patterns one entry is matched with: where it is named, and what value or phrase it holds."""
    runs = re.findall(r"[A-Za-z0-9]+", e["file_id"])
    names = {r"[\s\-]*".join(re.escape(r.casefold()) for r in runs), re.escape(norm(e["file"]))}
    stem = e["file"].rsplit(".", 1)[0] if "." in e["file"].strip(".") else ""
    if stem.strip():
        names.add(re.escape(norm(stem)))
    name = "(?:" + "|".join(sorted(names, key=lambda s: (-len(s), s))) + ")"
    page = r"(?:pp|pg|page|p)\.? ?0*" + str(e["page"]) + r"(?!\d)(?! ?- ?\d)"
    naming = re.compile(r"(?<![a-z0-9])" + name + r"(?: ?[,:] ?| )" + page
                        + r"|(?<![a-z0-9])" + page + r" (?:of|in|on) (?:the )?" + name + r"(?![a-z0-9])")
    values = [value_kind(bare(v)) for v in (e["planted_value"], e["true_value"]) if v is not None]
    if not values:
        values = [("text", phrase_pattern(bare(e["key_phrase"])))]
    return naming, values


def matches(entry, finding):
    """The match rule: the finding names the entry's file and page, and holds its planted or true value,
    or its key phrase when it has no value."""
    naming, values = entry["_match"]
    if not any(naming.search(text) for text in finding.naming_texts):
        return False
    return any(holds(kind, target, text) for kind, target in values for text in finding.value_texts)


def memo_tried(entries, memo_text):
    cited = {(label_norm(m.group("id")), int(m.group("page") or 1)) for m in MEMO_CITE_RE.finditer(memo_text)}
    tried = {}
    for e in entries:
        wanted = [CLAIM_CITE_RE.fullmatch(c) for c in e["memo_claim"]["cites"]]
        tried[e["id"]] = any((label_norm(m.group("id")), int(m.group("page"))) in cited for m in wanted)
    return tried


# -------------------------------------------------------------------------------------- findings files


class Finding(object):
    def __init__(self, layer, source, line, memo_line, cite, value_seen, problem):
        self.layer, self.source, self.line = layer, source, line
        self.memo_line, self.cite, self.value_seen, self.problem = memo_line, cite, value_seen, problem
        self.uid = "{}:{}:{}".format(layer, source, line)
        self.naming_texts = [norm(t) for t in (cite, problem) if t != "-"]
        self.value_texts = [norm(t) for t in (value_seen, problem) if t != "-"]

    def as_dict(self):
        return {"id": self.uid, "layer": self.layer, "source": "{}:{}".format(self.source, self.line),
                "memo_line": self.memo_line, "cite": self.cite, "value_seen": self.value_seen,
                "problem": self.problem}


def is_header(line):
    """True for the header line. Its four names may be joined by a space or an underscore, in any case."""
    return tuple(p.strip().casefold().replace(" ", "_") for p in line.split("\t")) == HEADER


def cite_pieces(cite):
    """The cites in a cite field: joined by ; or written one after another, each with or without [ ]."""
    return [c.strip().strip("[]").strip() for c in re.split(r";|\]\s*\[", cite)]


def parse_row(layer, name, n, line, cite_form):
    """(Finding, None) for a line that can be read, or (None, the reason it cannot)."""
    parts = line.split("\t")
    if len(parts) != 4:
        return None, "has {} fields, not 4".format(len(parts))
    memo_line, cite, value_seen, problem = (p.strip() for p in parts)
    memo_line, cite, value_seen = ("-" if f.casefold() in NONE_WORDS else f for f in (memo_line, cite, value_seen))
    if memo_line != "-" and not MEMO_LINE_RE.fullmatch(memo_line):
        return None, "memo_line must be a whole number from 1, or - or none"
    if not cite or (cite_form and cite != "-" and not all(FINDING_CITE_RE.fullmatch(c) for c in cite_pieces(cite))):
        return None, "cite must be - or none, or cites each written <file> p<page>"
    if not value_seen:
        return None, "value_seen is empty; write - or none"
    if not problem or problem.casefold() in NONE_WORDS:
        return None, "problem must say what is wrong"
    return Finding(layer, name, n, memo_line, cite, value_seen, problem), None


def file_lines(text):
    return [line[:-1] if line.endswith("\r") else line for line in text.split("\n")]


def read_findings(path, layer, run_dir):
    """The strict reading, for the gate's files, the floor file and --validate: any line that breaks the form
    refuses the whole file."""
    name = shown(path, run_dir)
    text, raw = read_text(path, run_dir)
    lines = file_lines(text)
    if not lines or not is_header(lines[0]):
        raise Refused("{} line 1 must be the header: {}".format(name, " <TAB> ".join(HEADER)))
    rows = []
    for n, line in enumerate(lines[1:], 2):
        if not line.strip():
            continue
        row, why = parse_row(layer, name, n, line, True)
        if row is None:
            raise Refused("{} line {}: {}".format(name, n, why))
        rows.append(row)
    return rows, sha256(raw)


def read_layer(path, layer, run_dir):
    """The reading used to score a layer: (findings, the file's hash, lines not read). A line that cannot be read
    matches nothing and is counted, and it never refuses the file. A first line that is not the header is read
    as a finding."""
    name = shown(path, run_dir)
    text, raw = read_text(path, run_dir)
    lines = file_lines(text)
    rows, unread = [], []
    for n, line in enumerate(lines, 1):
        if not line.strip() or (n == 1 and is_header(line)):
            continue
        row, why = parse_row(layer, name, n, line, False)
        if row is None:
            unread.append({"layer": layer, "source": "{}:{}".format(name, n), "reason": why})
        else:
            rows.append(row)
    return rows, sha256(raw), unread


# ---------------------------------------------------------------------------------------------- rulings


def read_rulings(path, run_dir):
    """The owner's rulings file, read strictly: {"trap": {id: ruling}, "match": {(finding, entry): ruling},
    "unmatched": {finding: (ruling, trap id or None)}} and the file's hash."""
    name = shown(path, run_dir)
    text, raw = read_text(path, run_dir)
    lines = file_lines(text)
    if not lines or tuple(p.strip() for p in lines[0].split("\t")) != RULINGS_HEADER:
        raise Refused("{} line 1 must be the header: {}".format(name, " <TAB> ".join(RULINGS_HEADER)))
    out = {"trap": {}, "match": {}, "unmatched": {}}
    for n, line in enumerate(lines[1:], 2):
        if not line.strip():
            continue
        parts = [p.strip() for p in line.split("\t")]
        if len(parts) != 4:
            raise Refused("{} line {} has {} fields, not 4".format(name, n, len(parts)))
        kind, ident, entry, ruling = parts
        entry = None if entry in ("", "-") else entry
        if kind == "trap" and ruling in TRAP_RULINGS and entry is None:
            key, value = ident, ruling
        elif kind == "match" and ruling in MATCH_RULINGS and entry is not None:
            key, value = (ident, entry), ruling
        elif kind == "unmatched" and ruling in UNMATCHED_RULINGS and (entry is not None) == (ruling == "match"):
            key, value = ident, (ruling, entry)
        else:
            raise Refused("{} line {}: not a ruling in the form tools/SCHEMA.md gives".format(name, n))
        if not ident or key in out[kind]:
            raise Refused("{} line {}: {} is ruled twice or not named".format(name, n, ident or "the row"))
        out[kind][key] = value
    return out, sha256(raw)


def apply_rulings(result, traps, rulings):
    """The counts after the owner's rulings. A scripted match ruled no is dropped, an unmatched finding ruled a
    match is added, and a scripted match with no ruling stands. Raises Refused for a ruling that names a trap,
    a finding or a match the scoring does not hold."""
    entries = {e["id"]: e for e in traps["entries"]}
    real_ids = [e["id"] for e in traps["entries"] if not e["decoy"]]
    decoy_ids = [e["id"] for e in traps["entries"] if e["decoy"]]
    by_uid = {f.uid: f for f in result["findings"]}
    matched = result["matched"]
    for ident in rulings["trap"]:
        if ident not in real_ids:
            raise Refused("the rulings name {}, which is not a trap in traps.json".format(ident))
    for uid, ident in rulings["match"]:
        if uid not in by_uid or ident not in matched[uid]:
            raise Refused("the rulings name a match of {} to {}, which the script did not make".format(uid, ident))
    for uid, (ruling, ident) in rulings["unmatched"].items():
        if uid not in by_uid or matched[uid]:
            raise Refused("the rulings name {}, which is not a finding that matches no trap".format(uid))
        if ruling == "match" and ident not in real_ids:
            raise Refused("the rulings match {} to {}, which is not a trap in traps.json".format(uid, ident))
    kept = {}
    for f in result["findings"]:
        ids = [i for i in matched[f.uid] if rulings["match"].get((f.uid, i)) != "no"]
        ruled = rulings["unmatched"].get(f.uid)
        if ruled and ruled[0] == "match":
            ids.append(ruled[1])
        kept[f.uid] = ids
    ruled_real = [i for i in real_ids if rulings["trap"].get(i) == "real"]
    cols = [c for c in result["columns"] if c != "any"]
    named = [c for c in cols if c in LAYERS]
    caught = {c: {i for f in result["findings"] if f.layer == c for i in kept[f.uid]} for c in cols}
    if named:
        caught["any"] = set().union(*(caught[c] for c in named))
    counts = {}
    for c in result["columns"]:
        row = {"caught": sum(i in caught[c] for i in real_ids),
               "caught_of_ruled_real": sum(i in caught[c] for i in ruled_real),
               "decoys_flagged": sum(i in caught[c] for i in decoy_ids)}
        if c != "any":
            loose = [f.uid for f in result["findings"] if f.layer == c and not matched[f.uid]]
            how = [rulings["unmatched"].get(u, ("not ruled", None))[0] for u in loose]
            row["unmatched"] = {k: how.count(k) for k in UNMATCHED_RULINGS + ("not ruled",)}
            row["matches_ruled_no"] = sum(1 for (u, _), r in rulings["match"].items()
                                          if r == "no" and by_uid[u].layer == c)
        counts[c] = row
    return {"traps": {i: rulings["trap"].get(i, "not ruled") for i in real_ids},
            "totals": dict({k: sum(rulings["trap"].get(i) == k for i in real_ids) for k in TRAP_RULINGS},
                           not_ruled=sum(i not in rulings["trap"] for i in real_ids)),
            "caught": {c: sorted(caught[c], key=list(entries).index) for c in result["columns"]},
            "counts": counts}


# ------------------------------------------------------------------------------- check rows to findings

CHECK_ROW_RE = re.compile(r"^  Line (?P<line>[1-9][0-9]*): (?P<text>.*)$")
CITED_RE = re.compile(r"^(?P<claimed>.+?) is cited to (?P<id>[A-Za-z][A-Za-z0-9-]*)(?: p(?P<page>[1-9][0-9]*))?, ")
RULE_TAIL_RE = re.compile(r" To rule, name: .*$")


def check_rows(text):
    """Findings rows from the check's printed output: the lines under Memo check: that start Line <n>:."""
    lines = [line.rstrip("\r") for line in text.split("\n")]
    starts = [i for i, line in enumerate(lines) if line.startswith("Memo check: ")]
    if len(starts) != 1:
        raise Refused("the check output must hold one Memo check: block; it holds {}".format(len(starts)))
    if lines[starts[0]].startswith("Memo check: no memo"):
        raise Refused("the check output says there is no memo")
    rows = []
    for line in lines[starts[0] + 1:]:
        if not line.startswith("  "):
            break
        m = CHECK_ROW_RE.match(line)
        if m is None:
            continue
        sentence = RULE_TAIL_RE.sub("", m.group("text")).replace("\t", " ").strip()
        cited = CITED_RE.match(sentence)
        cite = "{} p{}".format(cited.group("id"), cited.group("page")) if cited and cited.group("page") else "-"
        value = cited.group("claimed").strip() if cited else "-"
        rows.append((m.group("line"), cite, value, sentence))
    return rows


# --------------------------------------------------------------------------------------------- scoring


def score(traps, layers, floor, tried, unread=()):
    """layers: {label: [Finding]} for the labels given; floor: [Finding] or None; tried: {id: bool};
    unread: the lines of the layers' files that could not be read."""
    entries = traps["entries"]
    columns = ([("floor", floor)] if floor is not None else []) + [(k, layers[k]) for k in LAYERS if k in layers]
    hits, matched = {}, {}
    for col, findings in columns:
        for f in findings:
            ids = [e["id"] for e in entries if matches(e, f)]
            matched[f.uid] = ids
            for i in ids:
                hits.setdefault((i, col), []).append(f.uid)
    present = [col for col, _ in columns]
    named_layers = [k for k in LAYERS if k in layers]

    def caught(i, col):
        if col == "any":
            return any((i, k) in hits for k in named_layers) if named_layers else None
        return ((i, col) in hits) if col in present else None

    shown_cols = present + (["any"] if named_layers else [])
    real = [e for e in entries if not e["decoy"]]
    decoys = [e for e in entries if e["decoy"]]
    trap_rows = [{"id": e["id"], "kind": e["kind"], "listed": e["listed"], "file": e["file"],
                  "file_id": e["file_id"], "page": e["page"], "tried": tried[e["id"]],
                  "caught": {col: caught(e["id"], col) for col in shown_cols},
                  "matches": {col: hits.get((e["id"], col), []) for col in present}} for e in real]
    decoy_rows = [{"id": e["id"], "kind": e["kind"], "file": e["file"], "file_id": e["file_id"], "page": e["page"],
                   "flagged": {col: caught(e["id"], col) for col in shown_cols},
                   "matches": {col: hits.get((e["id"], col), []) for col in present}} for e in decoys]
    totals = {"traps": len(real), "listed": sum(e["listed"] == "listed" for e in real),
              "unlisted": sum(e["listed"] == "unlisted" for e in real), "decoys": len(decoys),
              "tried": sum(tried[e["id"]] for e in real)}
    counts = {}
    for col in shown_cols:
        row = {"caught": sum(bool(t["caught"][col]) for t in trap_rows),
               "listed_caught": sum(bool(t["caught"][col]) for t in trap_rows if t["listed"] == "listed"),
               "unlisted_caught": sum(bool(t["caught"][col]) for t in trap_rows if t["listed"] == "unlisted"),
               "tried_caught": None if col == "floor" else sum(bool(t["caught"][col]) for t in trap_rows if t["tried"]),
               "decoys_flagged": sum(bool(d["flagged"][col]) for d in decoy_rows)}
        if col != "any":
            findings = dict(columns)[col]
            row["findings"] = len(findings)
            row["matching_no_trap"] = sum(not matched[f.uid] for f in findings)
            row["lines_not_read"] = sum(u["layer"] == col for u in unread)
        counts[col] = row
    all_findings = [f for _, findings in columns for f in findings]
    return {"columns": shown_cols, "totals": totals, "traps": trap_rows, "decoys": decoy_rows, "counts": counts,
            "findings": all_findings, "matched": matched, "unread": list(unread)}


def cell(text):
    return str(text).replace("|", "\\|").strip()


def yes_no(value):
    return "-" if value is None else ("yes" if value else "no")


def render(result, inputs, case, ruled=None):
    """The Markdown table as (heading, lines) sections, in print order."""
    t, cols = result["totals"], result["columns"]
    head = ["# Results table", "",
            "Scored by `tools/score.py` with the match rule in `tools/SCHEMA.md`. No model call.",
            "Case: {}. Traps: {} ({} listed, {} unlisted). Decoys: {}. Traps whose claim the memo cites: {} of {}.".format(
                case or "not named", t["traps"], t["listed"], t["unlisted"], t["decoys"], t["tried"], t["traps"])]
    inp = ["## Inputs", "", "| Input | File | SHA-256 |", "|---|---|---|"]
    inp += ["| {} | {} | {} |".format(cell(role), cell(name), digest) for role, name, digest in inputs]
    per = ["## Each trap", "",
           "yes: at least one finding in that layer matches the trap. -: no file was given for that layer. "
           "Tried: the memo cites a page listed for the trap's claim. "
           "Check by design is the floor file, the check's rows on a memo that carries every trap as fact, "
           "so it has no tried count. Any is the check, the cross-reader or the owner.", "",
           "| Trap | Kind | List | Tried | " + " | ".join(LAYER_NAMES[c] for c in cols) + " |",
           "|---|---|---|---|" + "---|" * len(cols)]
    per += ["| {} | {} | {} | {} | {} |".format(cell(r["id"]), cell(r["kind"]), r["listed"], yes_no(r["tried"]),
                                               " | ".join(yes_no(r["caught"][c]) for c in cols)) for r in result["traps"]]
    cnt = ["## Counts", "",
           "Each count is out of the total in its column heading.", "",
           "| Layer | Traps caught, of {} | Listed caught, of {} | Unlisted caught, of {} | Tried caught, of {} "
           "| Decoys flagged, of {} | Findings | Matching no trap | Lines not read |".format(
               t["traps"], t["listed"], t["unlisted"], t["tried"], t["decoys"]),
           "|---|---|---|---|---|---|---|---|---|"]
    for c in cols:
        r = result["counts"][c]
        cnt.append("| {} | {} | {} | {} | {} | {} | {} | {} | {} |".format(
            LAYER_NAMES[c], r["caught"], r["listed_caught"], r["unlisted_caught"],
            "-" if r["tried_caught"] is None else r["tried_caught"],
            r["decoys_flagged"], r.get("findings", "-"), r.get("matching_no_trap", "-"),
            r.get("lines_not_read", "-")))
    untried = [r for r in result["traps"] if not r["tried"]]
    unt = ["## Untried traps", ""]
    if untried:
        unt.append("The memo cites none of the pages listed for these traps' claims. They stay in every total "
                   "above and are listed here apart.")
        unt.append("")
        unt.append("Untried: {} of {}: {}.".format(len(untried), t["traps"], ", ".join(
            "{} ({})".format(r["id"], r["kind"]) for r in untried)))
    else:
        unt.append("Untried: 0 of {}. The memo cites a listed page for every trap's claim.".format(t["traps"]))
    dec = ["## Decoys flagged", "", "A decoy looks wrong and is fine, so a finding that matches one is a false alarm.", ""]
    if result["decoys"]:
        dec += ["| Decoy | Kind | " + " | ".join(LAYER_NAMES[c] for c in cols) + " |", "|---|---|" + "---|" * len(cols)]
        dec += ["| {} | {} | {} |".format(cell(d["id"]), cell(d["kind"]), " | ".join(yes_no(d["flagged"][c]) for c in cols))
                for d in result["decoys"]]
    else:
        dec.append("traps.json holds no decoys.")
    by_uid = {f.uid: f for f in result["findings"]}
    mat = ["## Scripted matches", "", "Each finding the script matched to a trap or a decoy, for the owner to rule.", ""]
    match_rows = [(e["id"], col, uid) for e in result["traps"] + result["decoys"]
                  for col in cols if col != "any" for uid in e["matches"].get(col, [])]
    if match_rows:
        mat += ["| Entry | Layer | Finding | Memo line | Cite | Value seen | Problem |", "|---|---|---|---|---|---|---|"]
        for ident, col, uid in match_rows:
            f = by_uid[uid]
            mat.append("| {} | {} | {}:{} | {} | {} | {} | {} |".format(
                cell(ident), LAYER_NAMES[col], cell(f.source), f.line, f.memo_line, cell(f.cite),
                cell(f.value_seen), cell(f.problem)))
    else:
        mat.append("None.")
    loose = [f for f in result["findings"] if not result["matched"][f.uid]]
    unm = ["## Findings that match no trap", "", "No trap or decoy matches these by the match rule. "
           "The owner rules each one from the first run.", ""]
    if loose:
        unm += ["| Layer | Finding | Memo line | Cite | Value seen | Problem |", "|---|---|---|---|---|---|"]
        unm += ["| {} | {}:{} | {} | {} | {} | {} |".format(LAYER_NAMES[f.layer], cell(f.source), f.line, f.memo_line,
                                                         cell(f.cite), cell(f.value_seen), cell(f.problem))
                for f in loose]
    else:
        unm.append("None.")
    bad = ["## Lines not read", "", "A line of a layer's file that is not in the findings form. It matches nothing "
           "and is counted here.", ""]
    if result["unread"]:
        bad += ["| Layer | Line | Why |", "|---|---|---|"]
        bad += ["| {} | {} | {} |".format(LAYER_NAMES[u["layer"]], cell(u["source"]), cell(u["reason"]))
                for u in result["unread"]]
    else:
        bad.append("None.")
    sections = [("head", head), ("inputs", inp), ("each", per), ("counts", cnt), ("untried", unt), ("decoys", dec),
                ("matches", mat), ("unmatched", unm), ("unread", bad)]
    if ruled is not None:
        rt, n = ruled["totals"], t["traps"]
        rul = ["## After the owner's rulings", "",
               "Traps ruled real: {} of {}. Ruled trivial: {} of {}. Ruled wrong: {} of {}. Not ruled: {} of {}.".format(
                   rt["real"], n, rt["trivial"], n, rt["wrong"], n, rt["not_ruled"], n),
               "A scripted match the owner ruled no is dropped. A finding that matched no trap and that the owner "
               "ruled a match is added. A scripted match with no ruling stands.", "",
               "| Layer | Traps caught, of {} | Caught among traps ruled real, of {} | Decoys flagged, of {} "
               "| Scripted matches ruled no | Unmatched ruled a match | Unmatched ruled a real problem "
               "| Unmatched ruled a false alarm | Unmatched not ruled |".format(n, rt["real"], t["decoys"]),
               "|---|---|---|---|---|---|---|---|---|"]
        for c in cols:
            r = ruled["counts"][c]
            u = r.get("unmatched")
            rul.append("| {} | {} | {} | {} | {} | {} | {} | {} | {} |".format(
                LAYER_NAMES[c], r["caught"], r["caught_of_ruled_real"], r["decoys_flagged"],
                r.get("matches_ruled_no", "-"), u["match"] if u else "-", u["real"] if u else "-",
                u["false-alarm"] if u else "-", u["not ruled"] if u else "-"))
        rul += ["", "| Trap | Ruling | " + " | ".join(LAYER_NAMES[c] for c in cols) + " |",
                "|---|---|" + "---|" * len(cols)]
        rul += ["| {} | {} | {} |".format(cell(i), ruling, " | ".join(
            yes_no(i in ruled["caught"][c]) for c in cols)) for i, ruling in ruled["traps"].items()]
        sections.append(("ruled", rul))
    return sections


def to_json(result, inputs, case, ruled=None):
    data = {
        "format": RESULTS_FORMAT,
        "case": case,
        "match_rule": "tools/SCHEMA.md",
        "inputs": [{"role": role, "file": name, "sha256": digest} for role, name, digest in inputs],
        "totals": result["totals"],
        "columns": result["columns"],
        "counts": result["counts"],
        "traps": result["traps"],
        "decoys": result["decoys"],
        "findings": [dict(f.as_dict(), matches=result["matched"][f.uid]) for f in result["findings"]],
        "lines_not_read": result["unread"],
    }
    if ruled is not None:
        data["after_rulings"] = ruled
    return data


# ------------------------------------------------------------------------------------------------ modes


def parse_layers(specs):
    pairs = []
    for spec in specs:
        label, sep, path = spec.partition("=")
        if not sep or label not in LAYERS or not path:
            raise UsageError("--layer takes LAYER=FILE with LAYER one of {}".format(", ".join(LAYERS)))
        pairs.append((label, path))
    return pairs


def run_score(args, run_dir):
    if not args.traps or not args.memo or not args.out:
        raise UsageError("scoring needs --traps, --memo and --out")
    pairs = parse_layers(args.layer)
    if not pairs and not args.floor:
        raise UsageError("scoring needs at least one --layer or --floor")
    traps = load_traps(args.traps, run_dir)
    memo, memo_raw = read_text(args.memo, run_dir)
    inputs = [("traps", shown(args.traps, run_dir), traps["sha256"]),
              ("memo", shown(args.memo, run_dir), sha256(memo_raw))]
    floor = None
    if args.floor:
        floor, digest = read_findings(args.floor, "floor", run_dir)
        inputs.append(("floor", shown(args.floor, run_dir), digest))
    layers, unread = {}, []
    for label in LAYERS:
        for lab, path in pairs:
            if lab == label:
                rows, digest, bad = read_layer(path, label, run_dir)
                layers.setdefault(label, []).extend(rows)
                unread.extend(bad)
                inputs.append((label, shown(path, run_dir), digest))
    result = score(traps, layers, floor, memo_tried(traps["entries"], memo), unread)
    ruled = None
    if args.rulings:
        rulings, digest = read_rulings(args.rulings, run_dir)
        inputs.append(("rulings", shown(args.rulings, run_dir), digest))
        ruled = apply_rulings(result, traps, rulings)
    sections = render(result, inputs, traps["case"], ruled)
    md = "\n\n".join("\n".join(lines) for _, lines in sections) + "\n"
    data = json.dumps(to_json(result, inputs, traps["case"], ruled), indent=2, ensure_ascii=False) + "\n"
    out = Path(args.out)
    try:
        out.mkdir(parents=True, exist_ok=True)
        (out / RESULTS_MD).write_text(md, encoding="utf-8")
        (out / RESULTS_JSON).write_text(data, encoding="utf-8")
    except OSError as err:
        raise Refused("cannot write to {}: {}".format(shown(out, run_dir), err.strerror or "write error"))
    printed = [lines for name, lines in sections if name in ("head", "each", "counts", "untried", "decoys", "ruled")]
    print("\n\n".join("\n".join(lines) for lines in printed))
    print("\nWrote {} and {} in {}.".format(RESULTS_MD, RESULTS_JSON, shown(out, run_dir) or "."))
    return 0


def gate_passes(args, run_dir):
    if not args.traps or not args.good or not args.bad:
        return False
    entries = load_traps(args.traps, run_dir)["entries"]
    good, _ = read_findings(args.good, "good", run_dir)
    bad, _ = read_findings(args.bad, "bad", run_dir)
    real = [e for e in entries if not e["decoy"]]
    decoys = [e for e in entries if e["decoy"]]
    if not good or not bad:
        return False
    if not all(any(matches(e, f) for f in good) for e in real):
        return False  # the known-good file must catch every trap
    if any(matches(e, f) for e in decoys for f in good):
        return False  # and flag no decoy
    if not all(any(matches(e, f) for e in real) for f in good):
        return False  # and hold no finding that matches no trap
    if any(matches(e, f) for e in real for f in bad):
        return False  # the known-bad file must catch none
    if args.floor:
        floor, _ = read_findings(args.floor, "floor", run_dir)
        for e in real:
            if "check_sees" in e and any(matches(e, f) for f in floor) != e["check_sees"]:
                return False  # the floor must catch exactly the traps the key says the check sees
    return True


def run_gate(args, run_dir):
    try:
        ok = gate_passes(args, run_dir)
    except Exception:
        ok = False
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


def run_rows(args, run_dir):
    text, _ = read_text(args.rows, run_dir)
    rows = check_rows(text)
    body = "\t".join(HEADER) + "\n" + "".join("\t".join(r) + "\n" for r in rows)
    if args.write:
        try:
            Path(args.write).write_text(body, encoding="utf-8")
        except OSError as err:
            raise Refused("cannot write {}: {}".format(shown(args.write, run_dir), err.strerror or "write error"))
        print("Wrote {} rows to {}.".format(len(rows), shown(args.write, run_dir)))
    else:
        sys.stdout.write(body)
    return 0


def run_tally(args, run_dir):
    """Adds up results.json files that scored the same traps: for each trap, the number of files in which it was
    tried and in which each layer caught it."""
    runs = []
    for path in args.tally:
        text, _ = read_text(path, run_dir)
        try:
            data = json.loads(text)
        except ValueError:
            data = None
        if not isinstance(data, dict) or data.get("format") != RESULTS_FORMAT:
            raise Refused("{} is not a results.json this script wrote".format(shown(path, run_dir)))
        runs.append((shown(path, run_dir), data))
    ids = [t["id"] for t in runs[0][1]["traps"]]
    for name, data in runs:
        if [t["id"] for t in data["traps"]] != ids:
            raise Refused("{} scored other traps than {}".format(name, runs[0][0]))
    cols = [c for c in ("floor",) + LAYERS + ("any",) if any(c in d["columns"] for _, d in runs)]
    have = {c: sum(c in d["columns"] for _, d in runs) for c in cols}
    lines = ["# Tally over {} results file{}".format(len(runs), "" if len(runs) == 1 else "s"), "",
             "Each cell counts the files in which the trap was tried, or in which that layer caught it, out of the "
             "files that hold that column.", "",
             "| Trap | Tried | " + " | ".join(LAYER_NAMES[c] for c in cols) + " |", "|---|---|" + "---|" * len(cols)]
    for n, ident in enumerate(ids):
        cells = ["{} of {}".format(sum(bool(d["traps"][n]["caught"].get(c)) for _, d in runs), have[c]) for c in cols]
        lines.append("| {} | {} of {} | {} |".format(cell(ident), sum(bool(d["traps"][n]["tried"]) for _, d in runs),
                                                    len(runs), " | ".join(cells)))
    lines += ["", "Files, in the order given: {}.".format(", ".join(name for name, _ in runs))]
    print("\n".join(lines))
    return 0


def run_validate(args, run_dir):
    for path in args.validate:
        rows, _ = read_findings(path, "file", run_dir)
        print("OK: {}, {} finding{}.".format(shown(path, run_dir), len(rows), "" if len(rows) == 1 else "s"))
    return 0


def build_parser():
    p = Parser(prog="score.py", description="Score findings files against traps.json. See tools/SCHEMA.md.")
    p.add_argument("--traps", help="the answer key's traps.json")
    p.add_argument("--memo", help="the memo the layers judged, for which traps were tried")
    p.add_argument("--layer", action="append", default=[], metavar="LAYER=FILE",
                   help="a findings file for check, cross-reader or owner; repeat a layer to add files")
    p.add_argument("--floor", help="the floor file: the check's rows on a memo that carries every trap as fact")
    p.add_argument("--out", help="the folder RESULTS-table.md and results.json are written to")
    p.add_argument("--gate", action="store_true", help="the scorer gate; prints PASS or FAIL only")
    p.add_argument("--good", help="gate: the known-good findings file built from the key")
    p.add_argument("--bad", help="gate: the known-bad findings file")
    p.add_argument("--rows", metavar="CHECK_OUTPUT", help="convert the check's printed rows to a findings file")
    p.add_argument("--write", help="rows: the findings file to write; standard output when left out")
    p.add_argument("--validate", nargs="+", metavar="FILE", help="check findings files against the format")
    p.add_argument("--rulings", help="scoring: the owner's rulings file, for the counts after rulings")
    p.add_argument("--tally", nargs="+", metavar="RESULTS_JSON", help="add up results.json files over memo runs")
    p.add_argument("--run-dir", help="the folder printed paths are relative to; the folder above tools/ by default")
    return p


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    gate_mode = "--gate" in argv
    try:
        args = build_parser().parse_args(argv)
        run_dir = Path(args.run_dir).resolve() if args.run_dir else RUN_DIR
        if sum((args.gate, args.rows is not None, args.validate is not None, args.tally is not None)) > 1:
            raise UsageError("give one of --gate, --rows, --validate and --tally")
        if args.gate:
            return run_gate(args, run_dir)
        if args.rows is not None:
            return run_rows(args, run_dir)
        if args.validate is not None:
            return run_validate(args, run_dir)
        if args.tally is not None:
            return run_tally(args, run_dir)
        return run_score(args, run_dir)
    except (UsageError, Refused) as err:
        if gate_mode:
            print("FAIL")
            return 1
        print("score.py: {}".format(err), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
