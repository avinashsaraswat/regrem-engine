"""Measurement for the tie-out: planted errors, baselines, intervals, freeze, declare and regress.

Purpose: measure the tie-out on matter 1, as tieout/docs/measuring.md describes. The corpus
  builder makes planted items from the tagged draft, one error per item, in every class in
  CLASSES below, plus the baselines: the clean draft, one respelled draft per normaliser and the
  untagged twin under rules. The mis_association class is planted in the untagged twin, where
  two figures in one sentence have their cites swapped in place and A2 does the pairing. Off
  the headline it plants one error per tying token of the twin (the coverage count). In the
  class layout, cites crossed inside two tags of the tagged draft are a cite-swap variant of
  wrong_cite, since a tag names its cite; exhibit_mismatch prints apart beside pin_missing; a
  dollar cell written in thousands with no scale word is a wrong_figure form, scale dropped.
  The scorer reads each draft with claims.text_draft_file, as a run does, and
  runs each item through the run's own checks (tieout.intake_checks and tieout.check_claims,
  the path tieout run takes, with nothing written). It compares the drop log with the item's
  label, which stays in this process and never reaches the runner. Each class prints as k of
  N with a Wilson 95 percent interval beside a cluster bootstrap over paragraphs (10,000
  resamples, fixed seed), escapes first with their upper bound. The builder routes a
  replacement value that still ties at its cite under the rounding rule to
  coincidental_figure and prints that count. Commands, each run as
  python3 -I tieout/tieout.py measure ...:
    measure                 build, score and print; writes nothing
    measure --class NAME    the same for one class
    measure --freeze        write tieout/FROZEN.json: hashes of the fixture, keys, code, corpus
    measure --declare       refuse unless FROZEN.json matches; write tieout/batches/<id>.json
                            before any item is scored, then score and write <id>-results.json
    measure --regress       score the whole offline corpus and compare it with the last
                            declared batch; exit 1 when the class layout differs, when
                            catches or expected codes fall, when escapes or false flags
                            rise, or when the untagged twin lists fewer of the rows the key
                            expects or gains claims the key lacks, naming the cause
    measure --proposer      the proposer eval: each proposer over the untagged twin
                            against key/proposer-labels.json, per class: span recall and
                            precision at exact boundaries, mis-association (an accepted span
                            whose code pairing differs from the label's cite), flag precision,
                            and for job 4 the share of items whose picked candidate is the
                            true location; rules is the baseline, and each recorded batch in
                            fixture/matter-1/replay/ is scored beside it through the replay
                            adapter, with the model id and max_tokens its requests carry,
                            and judged by the turn-on rule (turn_on below), each term
                            printed; writes nothing
Reads: tieout/fixture/matter-1/ (matter.json, report/draft.md, report/draft-untagged.md,
  record/, replay/, key/expected.json and key/proposer-labels.json), tieout/FROZEN.json,
  tieout/batches/*.json and the tool's code files for the code hash. The scorer is the only released
  code that opens key/, and the self-test, which is not released, reads it too; the runner never does.
Writes: through gate.write with scope "measure" only: tieout/FROZEN.json (--freeze) and
  tieout/batches/<id>.json and <id>-results.json (--declare). Plain measure and --regress write
  nothing.
Network: none.
Exit codes: 0 printed or written; 1 when --regress finds the class layout changed, catches,
  expected codes or the twin's listed rows fell, or escapes, false flags or the twin's claims
  the key lacks rose; 2 on a usage error, a fixture the builder cannot read, a missing or
  stale freeze for --declare, or no declared batch for --regress; 3 on a gate refusal.
"""
import datetime
import decimal
import hashlib
import json
import os
import random
import re
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import claims  # noqa: E402
import gate  # noqa: E402
import providers  # noqa: E402
import record  # noqa: E402
import verify  # noqa: E402
import words as words_py  # noqa: E402  (this module's own words() writes a number in words)

D = decimal.Decimal
MATTER_REL = "fixture/matter-1"
MATTER_DIR = os.path.join(HERE, "fixture", "matter-1")
FROZEN = "FROZEN.json"
BATCHES = "batches"

# Ported from fsi evals/detection.py: the target and floor on the Wilson lower bound, z, and the
# bootstrap's size. SIZE is the headline minimum, the fewest items a class needs to print a label
# on its Wilson lower bound: 63 of 70 at exactly 90 percent clears the 80 percent floor (the fsi
# rounded-count convention gives 54).
TARGET, FLOOR, Z = 0.90, 0.80, 1.96
SIZE = 70
BOOT_REPS, BOOT_SEED = 10000, 20261027

# The class layout. mis_association is planted in the untagged twin, where A2 pairs the crossed
# cites; the cites crossed inside two tags of the tagged draft report as a wrong_cite variant,
# since a tag names its cite and A1 to A4 never run on it.
HEADLINE = ("wrong_figure", "wrong_date", "wrong_cite", "mis_association", "misquote", "calc_error")
APART = ("pin_missing", "exhibit_mismatch", "rounding_mismatch")
BLIND = ("coincidental_figure", "sign_flip", "figure_in_words", "omission")
CLASSES = HEADLINE + APART + BLIND
LAYOUT = {"headline": list(HEADLINE), "apart": list(APART), "blind": list(BLIND)}
EXPECT = {
    "wrong_figure": ("figure_not_found", "cell_mismatch", "calc_error"),
    "wrong_date": ("date_not_found",),
    "wrong_cite": ("figure_not_found", "date_not_found", "misquote", "cell_mismatch"),
    "mis_association": ("figure_not_found", "cell_mismatch"),
    "misquote": ("misquote",),
    "calc_error": ("calc_error",),
    "exhibit_mismatch": ("exhibit_mismatch",),
    "pin_missing": ("pin_missing",),
    "rounding_mismatch": ("cell_mismatch",),
}
# The codes a planted error in the untagged twin should drop with, by token kind. A crossed
# pair of cites there is the mis_association class.
EXPECT_UNTAGGED = {"figure": ("figure_not_found", "cell_mismatch"), "date": ("date_not_found",),
                   "quotation": ("misquote",), "crossed cites": EXPECT["mis_association"]}
# The methods each item carries as its "how". A variant prints on its own how line with its
# forms; the class's forms and how lines count the rest.
CITE_SWAP = "cite swapped with another claim's cite in the same sentence"
TWIN_SWAP = "two cites swapped in place in the untagged twin"
VARIANTS = {"wrong_cite": (CITE_SWAP,)}
# A wrong_figure form of its own, scale dropped. Its items carry it as
# their form in place of the figure's written form, so wrong_figure's forms line counts it
# beside percent, plain, range and scaled; SCALE_HOW is their how.
SCALE_DROPPED = "scale dropped"
SCALE_HOW = "dollar cell written in thousands with no scale word"
# What a headline count does and does not show, printed under the class.
HEADLINE_NOTE = {
    "wrong_figure": "scale dropped writes a dollar cell in thousands with no scale word, a figure a thousand times "
                    "too small, and is planted as a wrong figure",
    "wrong_cite": "a cite swap crosses the cites inside two tags; a tag names its cite, so A1 to A4 never run on "
                  "it and mis_association measures pairing",
    "mis_association": "tests the A2 pairing rule on the untagged twin: the expected code counts an item only when "
                       "A2 paired each changed figure with the swapped cite",
}
APART_NOTE = {
    "pin_missing": "a test of the design: V2 refuses an exhibit cite with no pin by construction",
    "exhibit_mismatch": "a test of the design: holds by construction, since V8 compares the pin with the exhibit's "
                        "range and no record value enters; the expected-code count is the test of V8",
    "rounding_mismatch": "a rounding under another rule (truncated, rounded up); the draft's rounding may be "
                         "defensible, so each item goes to the expert",
}
BLIND_NOTE = {
    "coincidental_figure": "a replacement that still ties at the cite; routed here by the builder",
    "sign_flip": "figures compare without their sign",
    "figure_in_words": "under rules; measure --proposer measures it from stage 3",
    "omission": "the tool checks what the draft holds, never what it leaves out",
}

FULL_MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September",
               "October", "November", "December")
ABBR_MONTHS = ("Jan.", "Feb.", "Mar.", "Apr.", "May", "Jun.", "Jul.", "Aug.", "Sep.", "Oct.", "Nov.", "Dec.")
TAG = re.compile(r"\{\{(.*?)\}\}", re.S)
SEGMENT = re.compile(r"\{\{(.*?)\}\}|\[\^(\d+)\]", re.S)
FOOTDEF = re.compile(r"^\[\^(\d+)\]:\s*")
WORD_RX = re.compile(r"[A-Za-z][A-Za-z'\u2019\-]*")
ELLIPSIS = ("...", ". . .", "\u2026")

# One-word substitutions for misquote. A word not listed gains or loses a plural s.
SUBSTITUTE = {
    "the": "a", "a": "the", "an": "the", "is": "was", "was": "is", "are": "were", "were": "are",
    "will": "would", "would": "will", "not": "now", "no": "any", "and": "or", "or": "and", "of": "for",
    "for": "of", "in": "on", "on": "in", "at": "by", "to": "into", "we": "they", "our": "their",
    "its": "their", "it": "this", "this": "that", "that": "which", "so": "and", "say": "think",
    "lower": "better", "late": "slow", "lost": "net", "never": "not", "most": "much", "each": "every",
    "simply": "plainly", "move": "shift", "made": "final", "reason": "cause", "price": "cost",
}

ONES = ("zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven",
        "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen")
TENS = ("", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety")


class Refused(Exception):
    """A usage or input problem: exit 2."""


# --- statistics: ported from fsi evals/detection.py ---------------------------------------------


def wilson(k, n, z=Z):
    """Ported unchanged from fsi evals/detection.py: the Wilson score interval for k of n."""
    if n == 0:
        return (0.0, 1.0)
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def _below(rng, n):
    """A random int in [0, n): getrandbits with rejection, the draw random.Random uses for
    choice() in Python 3.9, written out so the sequence cannot change with the library."""
    k = n.bit_length()
    r = rng.getrandbits(k)
    while r >= n:
        r = rng.getrandbits(k)
    return r


def cluster_bootstrap(outcomes, reps=BOOT_REPS, seed=BOOT_SEED):
    """Ported from fsi evals/detection.py: a 95 percent percentile interval for a pooled
    proportion, resampling clusters (here the paragraph holding the planted claim) with
    replacement. outcomes is [(cluster, 0 or 1)]. Adapted to draw with _below and to sum each
    cluster once, which gives the same statistic faster."""
    by = {}
    for cid, hit in outcomes:
        by.setdefault(cid, []).append(hit)
    clusters = sorted(by)
    if not clusters:
        return (0.0, 1.0)
    sums = [(sum(by[c]), len(by[c])) for c in clusters]
    m = len(sums)
    rng = random.Random(seed)
    stats = []
    for _ in range(reps):
        hits = n = 0
        for _ in range(m):
            h, c = sums[_below(rng, m)]
            hits += h
            n += c
        stats.append(hits / n if n else 0.0)
    stats.sort()
    return (stats[int(0.025 * reps)], stats[int(0.975 * reps) - 1])


def label(k, n):
    """The fsi labels on the Wilson lower bound, with SIZE as the size: a class under SIZE items
    is underpowered unless even its upper bound is below the floor."""
    lo, hi = wilson(k, n)
    if n < SIZE:
        return "below floor" if hi < FLOOR else "underpowered"
    return "meets target" if lo >= TARGET else "meets floor" if lo >= FLOOR else "below floor"


def bar(n, level):
    """The smallest k whose Wilson lower bound at n clears level, or None."""
    for k in range(n + 1):
        if wilson(k, n)[0] >= level:
            return k
    return None


# --- the fixture --------------------------------------------------------------------------------


def _json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def parse_tag(body):
    """An inline tag's parts as the fixture writes them: (text, cite, calc, skip)."""
    parts = [p.strip() for p in body.split("|")]
    text, cite, calc, skip = parts[0], "", "", False
    for p in parts[1:]:
        if p == "skip":
            skip = True
        elif p.startswith("calc:"):
            calc = p[5:].strip()
        elif p:
            cite = p
    return text, cite, calc, skip


def tag(text, cite, calc=""):
    return "{{" + " | ".join([text] + ([cite] if cite else []) + (["calc: " + calc] if calc else [])) + "}}"


class Context:
    """Matter 1 as the builder and the scorer see it: the configs, the record index loaded once,
    the drafts, the answer key and the tagged draft's sites."""

    def __init__(self, tool):
        self.tool = tool
        self.root = MATTER_DIR
        self.matter = _json(os.path.join(MATTER_DIR, "matter.json"))
        if self.matter.get("tag_mode") != "inline":
            raise Refused("matter 1's matter.json must say tag_mode inline for its .md drafts")
        self.index = record.load(MATTER_DIR, self.matter["date_order"])
        bad = [c for c, rows in sorted(self.index.rows.items()) if rows and c in tool.BLOCKING]
        if bad:
            raise Refused("matter 1's record fails intake (%s); fix the fixture first" % ", ".join(bad))
        self.grammar = claims.Grammar(self.index.grammar_names(), self.matter["date_order"])
        try:  # read as tieout run reads a draft: raw bytes, utf-8-sig, line endings kept
            self.draft = claims.text_draft_file(os.path.join(MATTER_DIR, "report", "draft.md"))
            self.twin = claims.text_draft_file(os.path.join(MATTER_DIR, "report", "draft-untagged.md"))
        except ValueError as exc:
            raise Refused(str(exc))
        self.key = _json(os.path.join(MATTER_DIR, "key", "expected.json"))
        self.sites = sites_of(self.draft, self.key["drafts"]["clean"]["claims"])
        self.exhibits = sorted(self.index.exhibits.values(), key=lambda e: e["line"])


def sites_of(text, key_claims):
    """Each tag of the tagged draft that is not skip, in order, with its offsets in the draft
    text and the answer key's row for its claim."""
    out = []
    for m in TAG.finditer(text):
        t, cite, calc, skip = parse_tag(m.group(1))
        if not skip:
            out.append({"i": len(out), "start": m.start(), "end": m.end(), "text": t, "cite": cite, "calc": calc})
    if len(out) != len(key_claims):
        raise Refused("the tagged draft holds %d tags and the key %d claims" % (len(out), len(key_claims)))
    for s, k in zip(out, key_claims):
        if record.norm_text(s["text"]) != record.norm_text(k["span"]):
            raise Refused("tag %d reads %r and the key says %r" % (s["i"] + 1, s["text"], k["span"]))
        foot = k.get("para") is None
        s["where"] = ("foot", k["footnote"]) if foot else ("para", k["para"])
        s["cluster"] = "fn %d" % k["footnote"] if foot else "para %d" % k["para"]
        s["chain"] = ("foot",) if foot else s["where"]
        s["sentence"] = k["sentence"]
        s["kind"] = k["kind"]
        s["resolved"] = k["cite_resolved"].split(" | calc:")[0] if not k["cite_resolved"].startswith("calc:") else ""
        s["is_id"] = s["cite"][:3] in ("Id.", "id.")
    return out


def apply(text, edits):
    """The text with each (start, end, replacement) edit made; edits never overlap."""
    edits = sorted(edits)
    for (a, b, _), (c, _, _) in zip(edits, edits[1:]):
        if c < b:
            raise ValueError("overlapping edits")
    for a, b, new in reversed(edits):
        text = text[:a] + new + text[b:]
    return text


def protect(sites, changed, removed=()):
    """Edits that keep the planted change to one error: every later Id. tag in a changed or
    removed tag's chain is written as the cite it resolved to, up to the next cite written in
    full, so A3 gives it the cite it had before."""
    edits, active = [], set()
    for s in sites:
        if s["i"] in changed or s["i"] in removed:
            if s["cite"]:
                active.add(s["chain"])
            continue
        if s["chain"] not in active or not s["cite"]:
            continue
        if s["is_id"]:
            edits.append((s["start"], s["end"], tag(s["text"], s["resolved"], s["calc"])))
        else:
            active.discard(s["chain"])
    return edits


# --- the rules, as the builder applies them -----------------------------------------------------


def located(cite_text, ctx):
    if not cite_text:
        return None
    cite, _ = claims.parse_cite(cite_text, ctx.grammar)
    if cite is None or cite["type"] in ("id", "calc"):
        return None
    try:
        return verify.locate(cite, ctx.index)
    except verify.Fail:
        return None


def figure_at(fig, loc):
    """The rounding rule: the figure ties a value on the located text or the located cell."""
    if loc["cell"] is not None:
        num = record.cell_number(loc["cell"])
        return num is not None and record.cell_ties(num, fig)
    return any(s["pct"] == fig["pct"] and record.rounds_to(s["value"], fig)
               for _, sc, _ in loc["texts"] for s in sc["figures"])


def date_at(dv, loc):
    if loc["cell"] is not None:
        return any(record.date_ties(dv, v) for m in record.DATE.finditer(loc["cell"])
                   for v in record.date_values(m, loc.get("order")))
    return any(record.date_ties(dv, v) for _, sc, _ in loc["texts"] for d in sc["dates"] for v in d["values"])


def still_ties(text, cite, calc, ctx):
    """The builder's routing test: True when, under the rounding, date and quotation rules, the
    changed claim would still tie at its cite (and its calc). Such an item is no error the tool
    can see, so it goes to coincidental_figure, a designed blindness, and never to a headline."""
    val = claims.span_value(text, ctx.grammar)
    if cite:
        loc = located(cite, ctx)
        if loc is None:
            return False
        loc["order"] = ctx.matter["date_order"]
        if val["kind"] == "figure":
            if not all(figure_at(f, loc) for f in val["figures"]):
                return False
        elif val["kind"] == "date":
            if val["date"] is None or not date_at(val["date"], loc):
                return False
        else:
            try:
                verify.check_quote(text, loc, set(), val["kind"] == "quotation")
            except verify.Fail:
                return False
    if calc:
        if val["kind"] != "figure":
            return False
        try:
            value = verify.evaluate_calc(claims.parse_calc(calc), ctx.index)
        except verify.Fail:
            return False
        if not all(record.cell_ties((value, False), f) for f in val["figures"]):
            return False
    return bool(cite or calc)


# --- writing values -----------------------------------------------------------------------------


def fmt_number(value, places, commas):
    """A non-negative Decimal with places decimals, rounded half-up, with thousands separators
    when commas."""
    q = abs(value).quantize(D(1).scaleb(-places), rounding=decimal.ROUND_HALF_UP, context=record.CTX)
    s = format(q, "f")
    if commas:
        whole, _, frac = s.partition(".")
        s = "{:,}".format(int(whole)) + ("." + frac if frac else "")
    return s


def digit_swaps(num):
    """The first and the last adjacent-digit swap of a written number whose digits differ, with
    no swap that starts the number with a zero."""
    pos = [i for i, ch in enumerate(num) if ch.isdigit()]
    pairs = [(pos[j], pos[j + 1]) for j in range(len(pos) - 1) if num[pos[j]] != num[pos[j + 1]]]
    out = []
    for a, b in (pairs[:1] + pairs[-1:]):
        chars = list(num)
        chars[a], chars[b] = chars[b], chars[a]
        new = "".join(chars)
        if new[0] == "0" and len(new.split(".")[0].replace(",", "")) > 1:
            continue
        if new not in out:
            out.append(new)
    return out


def words(n):
    """A whole number in English words: 4812 is four thousand eight hundred and twelve."""
    if n < 20:
        return ONES[n]
    if n < 100:
        return TENS[n // 10] + ("-" + ONES[n % 10] if n % 10 else "")
    if n < 1000:
        return ONES[n // 100] + " hundred" + (" and " + words(n % 100) if n % 100 else "")
    for size, name in ((10 ** 9, "billion"), (10 ** 6, "million"), (1000, "thousand")):
        if n >= size:
            head, rest = words(n // size) + " " + name, n % size
            return head if not rest else head + (" and " if rest < 100 else " ") + words(rest)
    return str(n)


def figures_in(text):
    """The FIGURE matches in a tag's words, as the tool's pattern reads them."""
    return list(record.FIGURE.finditer(text))


def figure_form(text):
    ms = figures_in(text)
    if len(ms) >= 2:
        return "range"
    if not ms:
        return "none"
    m = ms[0]
    if m.group("pct"):
        return "percent"
    if m.group("scale") or m.group("abbr"):
        return "scaled"
    return "plain"


def with_num(text, m, new_num):
    return text[:m.start("num")] + new_num + text[m.end("num"):]


def in_form(value, m):
    """A record value written in the form of the draft's figure m: its scale, places and
    thousands separators."""
    f = record.parse_figure(m)
    return fmt_number(record.CTX.divide(abs(value), f["scale"]), f["places"], "," in m.group("num"))


def date_parts(text, order):
    m = record.DATE.search(text)
    if m is None:
        return None
    g = m.groupdict()
    p = {"pre": text[:m.start()], "post": text[m.end():], "y": None, "mo": None, "d": None, "q": None}
    if g["iy"]:
        p.update(form="iso", y=int(g["iy"]), mo=int(g["im"]), d=int(g["id"]))
    elif g["sy"]:
        a, b = int(g["sa"]), int(g["sb"])
        p.update(form="slash", y=int(g["sy"]), mo=a if order == "mdy" else b, d=b if order == "mdy" else a)
    elif g["y1"]:
        abbr = g["m1"].endswith(".") or len(g["m1"]) <= 3
        p.update(form="abbreviated month" if abbr else "month day year", y=int(g["y1"]),
                 mo=record.MONTHS[g["m1"][:3].lower()], d=int(g["d1"]))
    elif g["y2"]:
        p.update(form="day month year", y=int(g["y2"]), mo=record.MONTHS[g["m2"][:3].lower()], d=int(g["d2"]))
    elif g["y3"]:
        p.update(form="mid-month" if g["mid"] else "month year", y=int(g["y3"]), mo=record.MONTHS[g["m3"][:3].lower()])
    elif g["y4"]:
        p.update(form="quarter Qn", y=int(g["y4"]), q=int(g["q1"]))
    else:
        p.update(form="quarter nQ", y=int(g["y5"]), q=int(g["q2"]))
    return p


def fmt_date(p, y, mo=None, d=None, q=None, order="mdy", form=None):
    """A date written in a form of the date rule; None when the day does not exist."""
    form = form or p["form"]
    if d is not None:
        try:
            datetime.date(y, mo, d)
        except ValueError:
            return None
    if form == "iso":
        s = "%04d-%02d-%02d" % (y, mo, d)
    elif form == "slash":
        s = "%d/%d/%04d" % ((mo, d, y) if order == "mdy" else (d, mo, y))
    elif form == "abbreviated month":
        s = "%s %d, %04d" % (ABBR_MONTHS[mo - 1], d, y)
    elif form == "month day year":
        s = "%s %d, %04d" % (FULL_MONTHS[mo - 1], d, y)
    elif form == "day month year":
        s = "%d %s %04d" % (d, FULL_MONTHS[mo - 1], y)
    elif form == "mid-month":
        s = "mid-%s %04d" % (FULL_MONTHS[mo - 1], y)
    elif form == "month year":
        s = "%s %04d" % (FULL_MONTHS[mo - 1], y)
    elif form == "abbreviated month year":
        s = "%s %04d" % (ABBR_MONTHS[mo - 1], y)
    elif form == "quarter Qn":
        s = "Q%d %04d" % (q, y)
    else:
        s = "%dQ %04d" % (q, y)
    return p["pre"] + s + p["post"]


# --- the corpus builder -------------------------------------------------------------------------


class Corpus:
    """The planted items, each one error in a copy of the tagged draft, and the coincidental
    routing count. Ported in discipline from fsi src/harness/inject.py: one planted error per
    item, deterministic, ids from content hashes, the labels kept in this process."""

    def __init__(self, ctx):
        self.ctx = ctx
        self.items, self.texts, self.seen = [], {}, set()
        self.routed = {}
        self.unchanged = {}

    def add(self, cls, site_ids, how, form, edits, detail, removed=(), changed=(), routed_from=None, targets=None):
        """One item: the edits, plus the Id. protection a changed or removed cite needs, applied
        to the tagged draft. targets are the tags whose claims must drop (all of site_ids unless
        given); an item with none, a removal, is flagged by any row in the drop log."""
        sites = self.ctx.sites
        all_edits = list(edits)
        if changed or removed:
            all_edits += protect(sites, set(changed), set(removed))
        text = apply(self.ctx.draft, all_edits)
        h = sha(text)
        if (cls, h) in self.seen:
            return
        self.seen.add((cls, h))
        first = sites[site_ids[0]]
        item = {"cls": cls, "how": how, "form": form, "detail": detail, "draft_sha256": h,
                "targets": list(targets if targets is not None else site_ids), "removed": sorted(removed),
                "cluster": first["cluster"], "where": list(first["where"]), "untagged": False, "kind": first["kind"]}
        if routed_from:
            item["from"] = routed_from
            self.routed[routed_from] = self.routed.get(routed_from, 0) + 1
        item["id"] = "m-" + sha("|".join([cls, how, detail, h]))[:10]
        self.items.append(item)
        self.texts[item["id"]] = text

    def value_item(self, cls, s, how, form, new_text, detail, new_cite=None, new_calc=None):
        """A planted change to one tag: routed to coincidental_figure when it still ties."""
        cite = s["cite"] if new_cite is None else new_cite
        calc = s["calc"] if new_calc is None else new_calc
        if new_text == s["text"] and cite == s["cite"] and calc == s["calc"]:
            return
        check_cite = s["resolved"] if new_cite is None else new_cite
        edits = [(s["start"], s["end"], tag(new_text, cite, calc))]
        changed = [s["i"]] if new_cite is not None else []
        if still_ties(new_text, check_cite, calc, self.ctx):
            if s["kind"] == "quotation":
                self.unchanged[cls] = self.unchanged.get(cls, 0) + 1
                return
            self.add("coincidental_figure", [s["i"]], how, form, edits, detail, changed=changed, routed_from=cls)
            return
        self.add(cls, [s["i"]], how, form, edits, detail, changed=changed)


def gen_wrong_figure(c):
    ctx = c.ctx
    for s in ctx.sites:
        if s["kind"] != "figure":
            continue
        ms = figures_in(s["text"])
        form = figure_form(s["text"])
        for end, m in enumerate(ms):
            for new in digit_swaps(m.group("num")):
                c.value_item("wrong_figure", s, "adjacent-digit swap", form, with_num(s["text"], m, new),
                             "%s: %s to %s" % (s["text"], m.group("num"), new))
            for how, value in adjacent_values(s, m, ctx):
                new = in_form(value, m)
                if not new.strip("0.,"):
                    continue  # a value that writes as zero in the draft's form is no figure to plant
                c.value_item("wrong_figure", s, how, form, with_num(s["text"], m, new),
                             "%s: %s to %s (%s)" % (s["text"], m.group("num"), new, how))


def _cell_figure(s, ctx):
    """(the draft's one figure match, its parsed figure, the cited cell's number) for a figure
    tag whose resolved cite is one cell holding a number; else None."""
    if s["kind"] != "figure" or not s["resolved"]:
        return None
    parsed, _ = claims.parse_cite(s["resolved"], ctx.grammar)
    ms = figures_in(s["text"])
    if parsed is None or parsed["type"] != "cell" or len(ms) != 1:
        return None
    loc = located(s["resolved"], ctx)
    num = record.cell_number(loc["cell"]) if loc else None
    if num is None:
        return None
    return ms[0], record.parse_figure(ms[0]), num


def gen_scale_dropped(c):
    """wrong_figure, form scale dropped: a cited dollar cell of 10,000 or more written in
    thousands with no scale word, so the figure reads a thousand times too small."""
    for s in c.ctx.sites:
        got = _cell_figure(s, c.ctx)
        if got is None:
            continue
        m, f, num = got
        if f["money"] and not f["scaled"] and not f["pct"] and abs(num[0]) >= 10000:
            new_num = fmt_number(record.CTX.divide(abs(num[0]), D(1000)), 0, True)
            c.value_item("wrong_figure", s, SCALE_HOW, SCALE_DROPPED, with_num(s["text"], m, new_num),
                         "%s: %s to %s" % (s["text"], m.group("num"), new_num))


def _units(ctx, name, rows, r):
    """What a data cell measures: the model's unit column, or the column header elsewhere."""
    if name.lower() == "model.csv" and len(rows[r - 1]) > 2:
        return rows[r - 1][2].strip()
    return None


def adjacent_values(s, m, ctx):
    """Record values next to the cited one: for a cell, the nearest row above and below with the
    same unit and the next column on the same row; for a page or transcript, the first figure of
    the same kind on the page before and the page after, and the figures beside the cited value
    on its own page (which tie at the cite and so go to coincidental_figure)."""
    out = []
    fig = record.parse_figure(m)
    cite = s["resolved"]
    parsed = claims.parse_cite(cite, ctx.grammar)[0] if cite else None
    if parsed is None:
        return out
    if parsed["type"] == "cell":
        name, rows = ctx.index.data_file(parsed["file"])
        r, col = parsed["row"], record.column_index(parsed["col"])
        unit = _units(ctx, name, rows, r)
        for step in (-1, 1):
            rr = r + step
            while 2 <= rr <= len(rows):
                num = record.cell_number(rows[rr - 1][col]) if col < len(rows[rr - 1]) else None
                if num is not None and _units(ctx, name, rows, rr) == unit:
                    out.append(("adjacent row", num[0]))
                    break
                rr += step
        if unit is None:  # a column of the same measure beside it: net revenue and average price
            suffix = rows[0][col].split("_")[-1]
            for cc in (col - 1, col + 1):
                if 0 <= cc < len(rows[r - 1]) and rows[0][cc].split("_")[-1] == suffix:
                    num = record.cell_number(rows[r - 1][cc])
                    if num is not None:
                        out.append(("adjacent column", num[0]))
        return out
    loc = located(cite, ctx)
    if loc is None or loc["cell"] is not None:
        return out
    same = [f for _, sc, _ in loc["texts"] for f in sc["figures"]]
    for i, f in enumerate(same):
        if f["pct"] == fig["pct"] and record.rounds_to(f["value"], fig):
            for j in (i - 1, i + 1):
                if 0 <= j < len(same) and same[j]["pct"] == fig["pct"]:
                    out.append(("value beside it on the cited page", same[j]["value"]))
            break
    for page in neighbour_pages(parsed, loc, ctx):
        for f in page["figures"]:
            if f["pct"] == fig["pct"] and not record.is_bare_year(f):
                out.append(("adjacent page", f["value"]))
                break
    return out


def neighbour_pages(parsed, loc, ctx):
    """The scanned page before and after the located pages: Bates order for pages, page order
    for a transcript."""
    if parsed["type"] == "transcript":
        tr = ctx.index.transcript(parsed["witness"])
        p = parsed["start"][0]
        last = parsed["end"][0] if parsed.get("end") else p
        return [tr["page_scan"][q] for q in (p - 1, last + 1) if q in tr["page_scan"]]
    keys = [record.bates_key(label)[:2] for label, _, _ in loc["texts"] if record.bates_key(label)]
    if not keys:
        return []
    order = ctx.index.order
    out = []
    for k, step in ((keys[0], -1), (keys[-1], 1)):
        i = order.index(k) + step if k in order else -1
        if 0 <= i < len(order) and order[i][0] == k[0]:
            out.append(ctx.index.pages[order[i]])
    return out


def gen_wrong_date(c):
    """Day shifted either way, day and month swapped, year off either way; a month or a quarter
    shifted for a date written at that precision. Each in the form the draft wrote."""
    order = c.ctx.matter["date_order"]
    for s in c.ctx.sites:
        if s["kind"] != "date":
            continue
        p = date_parts(s["text"], order)
        if p is None:
            continue
        y, mo, d, q = p["y"], p["mo"], p["d"], p["q"]
        if d is not None:
            cands = [("day shifted", fmt_date(p, y, mo, d + 1, order=order)),
                     ("day shifted", fmt_date(p, y, mo, d - 1, order=order) if d > 1 else None),
                     ("day and month swapped", fmt_date(p, y, d, mo, order=order) if d <= 12 and d != mo else None),
                     ("year off", fmt_date(p, y + 1, mo, d, order=order)),
                     ("year off", fmt_date(p, y - 1, mo, d, order=order))]
        elif mo is not None:
            cands = [("month shifted", fmt_date(p, y, mo + 1) if mo < 12 else None),
                     ("month shifted", fmt_date(p, y, mo - 1) if mo > 1 else None),
                     ("year off", fmt_date(p, y + 1, mo)), ("year off", fmt_date(p, y - 1, mo))]
        else:
            cands = [("quarter shifted", fmt_date(p, y, q=q + 1) if q < 4 else None),
                     ("quarter shifted", fmt_date(p, y, q=q - 1) if q > 1 else None),
                     ("year off", fmt_date(p, y + 1, q=q)), ("year off", fmt_date(p, y - 1, q=q))]
        for how, new in cands:
            if new:
                c.value_item("wrong_date", s, how, p["form"], new, "%s to %s" % (s["text"], new))


def gen_wrong_cite(c):
    """The cite moved: page off by one, exhibit swapped, transcript page off by one, cell row off
    by one. A cite written as Id. is not moved."""
    ctx = c.ctx
    for s in ctx.sites:
        if not s["cite"] or s["is_id"]:
            continue
        parsed, _ = claims.parse_cite(s["cite"], ctx.grammar)
        if parsed is None:
            continue
        for how, form, new in cite_moves(parsed, s["cite"], ctx):
            detail = "%s: %s to %s" % (s["text"], s["cite"], new)
            c.value_item("wrong_cite", s, how, form, s["text"], detail, new_cite=new)


def _splice(text, spans):
    """text with each (start, end, replacement) span replaced, spans apart from one another."""
    for a, b, new in sorted(spans, reverse=True):
        text = text[:a] + new + text[b:]
    return text


def cite_moves(parsed, written, ctx):
    """Wrong cites for one cite as (how, form, cite): the page off by one either way, the exhibit
    swapped for the next one in exhibits.csv, a transcript page off by one, a cell row off by
    one. Every move stays inside the record, so the value check, not V2, is what it tests."""
    t = parsed["type"]
    if t == "exhibit":
        return _exhibit_moves(parsed, written, ctx)
    if t == "bates":
        return _bates_moves(parsed, written, ctx)
    if t == "transcript":
        return _transcript_moves(parsed, written, ctx)
    if t == "cell":
        rows = ctx.index.data_file(parsed["file"])[1]
        return [("cell row off by one", "cell", "%s!%s%d" % (parsed["file"], parsed["col"], parsed["row"] + step))
                for step in (-1, 1) if 2 <= parsed["row"] + step <= len(rows)]
    return []


def _exhibit_moves(parsed, written, ctx):
    out = []
    ex = ctx.index.exhibit(parsed["label"])
    if ex is None or not parsed["pin"]:
        return out
    pin, lab = parsed["pin"], parsed["written"]
    if "pages" in pin:
        a, b = pin["pages"]
        n = ex["last"] - ex["first"] + 1
        for step in (-1, 1):
            if 1 <= a + step and b + step <= n:
                p = str(a + step) if a == b else "%d-%d" % (a + step, b + step)
                out.append(("page off by one", "exhibit page pin", lab + " at " + p))
        nxt = _next_exhibit(ex, ctx)
        if nxt is not None and max(a, b) <= nxt["last"] - nxt["first"] + 1:
            new = _relabel(lab, nxt) + " at " + written.split(" at ", 1)[1]
            out.append(("exhibit swapped", "exhibit page pin", new))
        return out
    k = record.bates_key(pin["bates"])
    for step in (-1, 1):
        if ex["first"] <= k[1] + step <= ex["last"]:
            page = ctx.index.page_id(k[0], k[1] + step, len(k[2]))
            out.append(("page off by one", "exhibit Bates pin", lab + " at " + page))
    return out


def _bates_moves(parsed, written, ctx):
    """A Bates page or range moved one page either way, written as the cite wrote it."""
    out = []
    m = claims.BATES_ONLY.fullmatch(written)
    if m is None:
        return out
    s = record.bates_key(parsed["start"])
    e = record.bates_key(parsed["end"]) if parsed.get("end") else None
    width = len(m.group("bn"))
    for step in (-1, 1):
        if ctx.index.page(s[0], s[1] + step) is None or (e and ctx.index.page(e[0], e[1] + step) is None):
            continue
        spans = [(m.start("bn"), m.end("bn"), str(s[1] + step).zfill(width))]
        if m.group("bend"):
            full, short = str(e[1] + step).zfill(width), len(m.group("bend"))
            same_head = full[:width - short] == spans[0][2][:width - short]
            spans.append((m.start("bend"), m.end("bend"), full[-short:] if same_head else full))
        elif m.group("bn2"):
            spans.append((m.start("bn2"), m.end("bn2"), str(e[1] + step).zfill(len(m.group("bn2")))))
        out.append(("page off by one", "Bates range" if e else "Bates page", _splice(written, spans)))
    return out


def _transcript_moves(parsed, written, ctx):
    """A transcript cite moved one page either way, keeping its lines, where those lines exist."""
    out = []
    tr = ctx.index.transcript(parsed["witness"])
    m = claims.CITE.fullmatch(written)
    if tr is None or m is None or not m.group("tr"):
        return out
    p1, l1 = parsed["start"]
    end = parsed.get("end")
    for step in (-1, 1):
        spans = [(m.start("tp1"), m.end("tp1"), str(p1 + step))]
        ok = (p1 + step, l1) in tr["lines"] if l1 is not None else (p1 + step) in tr["pages"]
        if end and m.group("tp2"):
            spans.append((m.start("tp2"), m.end("tp2"), str(end[0] + step)))
            ok = ok and (end[0] + step, end[1]) in tr["lines"]
        elif end and end[1] is None:  # a page range, 45-46
            spans.append((m.start("tl2"), m.end("tl2"), str(end[0] + step)))
            ok = ok and (end[0] + step) in tr["pages"]
        elif end:
            ok = ok and (p1 + step, end[1]) in tr["lines"]
        if ok:
            out.append(("transcript page off by one", "transcript", _splice(written, spans)))
    return out


def _next_exhibit(ex, ctx):
    labels = [e["label"] for e in ctx.exhibits]
    i = labels.index(ex["label"])
    return ctx.exhibits[(i + 1) % len(labels)] if len(labels) > 1 else None


def _relabel(written, nxt):
    """The cite's label written for another exhibit, keeping an Ex. or Exhibit prefix; a label
    of digits alone takes Ex., since the grammar reads a bare number as no cite."""
    m = re.match(r"^((?:Exhibit|Exh\.|Ex\.)\s*)", written)
    prefix = m.group(1) if m else ("Ex. " if nxt["label"][:1].isdigit() else "")
    return prefix + nxt["label"]


def gen_cite_swap(c):
    """wrong_cite, the cite-swap variant: two figures with two different cites in one sentence
    of the tagged draft, their cites crossed inside the two tags. A tag names its cite, so the
    pairing rules never run; the value checks find each figure missing at the other cite, as
    for a moved cite. Each crossed claim that no longer ties is a target; when neither drops,
    the item is coincidental. Until 2026-10-28 these items were the mis_association class."""
    ctx = c.ctx
    groups = {}
    for s in ctx.sites:
        if s["kind"] == "figure" and s["cite"]:
            groups.setdefault((s["where"], s["sentence"]), []).append(s)
    for _, group in sorted(groups.items(), key=lambda kv: kv[1][0]["i"]):
        for x in range(len(group)):
            for y in range(x + 1, len(group)):
                a, b = group[x], group[y]
                if record.norm_text(a["resolved"]).casefold() == record.norm_text(b["resolved"]).casefold():
                    continue
                edits = [(a["start"], a["end"], tag(a["text"], b["resolved"], a["calc"])),
                         (b["start"], b["end"], tag(b["text"], a["resolved"], b["calc"]))]
                targets = [s["i"] for s, cite in ((a, b["resolved"]), (b, a["resolved"]))
                           if not still_ties(s["text"], cite, s["calc"], ctx)]
                form = "%s and %s" % (figure_form(a["text"]), figure_form(b["text"]))
                detail = "%s (%s) and %s (%s) crossed" % (a["text"], a["resolved"], b["text"], b["resolved"])
                if targets:
                    c.add("wrong_cite", [a["i"], b["i"]], CITE_SWAP, form, edits, detail,
                          changed=[a["i"], b["i"]], targets=targets)
                else:
                    c.add("coincidental_figure", [a["i"], b["i"]], CITE_SWAP, form, edits, detail,
                          changed=[a["i"], b["i"]], routed_from="wrong_cite", targets=[a["i"], b["i"]])


def quote_words(text):
    """The words of a quotation outside every bracket and away from every ellipsis, as
    (start, end): a word touching a bracket is part of an alteration and is left alone."""
    out = []
    for m in WORD_RX.finditer(text):
        a, b = m.start(), m.end()
        before, after = text[:a], text[b:]
        if before.count("[") > before.count("]") or before.endswith("]") or after.startswith("["):
            continue
        out.append((a, b))
    return out


def substitute(word):
    low = word.lower()
    if low in SUBSTITUTE:
        new = SUBSTITUTE[low]
    elif low.endswith(("'s", "\u2019s")):
        new = low[:-2]
    elif low.endswith("s") and len(low) > 3:
        new = low[:-1]
    else:
        new = low + "s"
    if word[:1].isupper():
        new = new[:1].upper() + new[1:]
    return new


def gen_misquote(c):
    """One word changed outside any bracket or ellipsis, at up to six word positions spread
    evenly through each quotation."""
    for s in c.ctx.sites:
        if s["kind"] != "quotation":
            continue
        ws = quote_words(s["text"])
        if not ws:
            continue
        picks = sorted({round(j * (len(ws) - 1) / 5.0) for j in range(6)}) if len(ws) > 6 else range(len(ws))
        if "[" in s["text"]:
            form = "with an alteration"
        elif any(e in s["text"] for e in ELLIPSIS):
            form = "with an ellipsis"
        else:
            form = "plain"
        for j in picks:
            a, b = ws[j]
            word, other = s["text"][a:b], substitute(s["text"][a:b])
            new = s["text"][:a] + other + s["text"][b:]
            c.value_item("misquote", s, "one word changed", form, new, "%r: %s to %s" % (s["text"][:40], word, other))


def calc_moves(cell, ctx):
    """Other numeric cells for one calc operand: the same column one, two and three rows away,
    then the same row in the next column on either side."""
    name, rows = ctx.index.data_file(cell["file"])
    col = record.column_index(cell["col"])
    out = []
    for dist in (1, 2, 3):
        for r in (cell["row"] - dist, cell["row"] + dist):
            if 2 <= r <= len(rows) and col < len(rows[r - 1]) and record.cell_number(rows[r - 1][col]) is not None:
                out.append(("operand row off by %d" % dist, "%s!%s%d" % (cell["file"], cell["col"], r)))
    for cc in (col - 1, col + 1):
        if 0 <= cc < len(rows[cell["row"] - 1]) and record.cell_number(rows[cell["row"] - 1][cc]) is not None:
            out.append(("operand column off by one", "%s!%s%d" % (cell["file"], record.col_letters(cc), cell["row"])))
    return out


def gen_calc_error(c):
    """A calc operand changed so the calc tag no longer ties: the operand moved to another
    numeric cell nearby (calc_moves)."""
    for s in c.ctx.sites:
        if not s["calc"]:
            continue
        form = "cell and calc" if s["cite"] else "calc only"
        for cell in claims.parse_calc(s["calc"])["cells"]:
            for how, new_cell in calc_moves(cell, c.ctx):
                expr = s["calc"][:cell["start"]] + new_cell + s["calc"][cell["end"]:]
                detail = "%s: %s to %s" % (s["text"], cell["text"], new_cell)
                c.value_item("calc_error", s, how, form, s["text"], detail, new_calc=expr)


def gen_exhibit_mismatch(c):
    """A Bates pin moved outside the exhibit's range: to the page before its first page and the
    page after its last, where the record holds them."""
    ctx = c.ctx
    for s in ctx.sites:
        if not s["cite"] or s["is_id"]:
            continue
        parsed, _ = claims.parse_cite(s["cite"], ctx.grammar)
        if parsed is None or parsed["type"] != "exhibit":
            continue
        ex = ctx.index.exhibit(parsed["label"])
        if ex is None:
            continue
        pin = parsed["pin"] or {}
        form = "Bates pin" if "bates" in pin else ("page pin" if pin else "no pin")
        for how, number in (("pin before the range", ex["first"] - 1), ("pin after the range", ex["last"] + 1)):
            if ctx.index.page(ex["prefix"], number) is None:
                continue
            new = parsed["written"] + " at " + ctx.index.page_id(ex["prefix"], number, ex["width"])
            c.add("exhibit_mismatch", [s["i"]], how, form, [(s["start"], s["end"], tag(s["text"], new, s["calc"]))],
                  "%s: %s to %s" % (s["text"], s["cite"], new), changed=[s["i"]])


def gen_pin_missing(c):
    """The pin dropped from an exhibit cite on an exhibit of more than one page."""
    ctx = c.ctx
    for s in ctx.sites:
        if not s["cite"] or s["is_id"]:
            continue
        parsed, _ = claims.parse_cite(s["cite"], ctx.grammar)
        if parsed is None or parsed["type"] != "exhibit" or not parsed["pin"]:
            continue
        ex = ctx.index.exhibit(parsed["label"])
        if ex is None or ex["last"] == ex["first"]:
            continue
        new = parsed["written"]
        form = "Bates pin" if "bates" in parsed["pin"] else "page pin"
        c.add("pin_missing", [s["i"]], "pin dropped", form, [(s["start"], s["end"], tag(s["text"], new, s["calc"]))],
              "%s: %s to %s" % (s["text"], s["cite"], new), changed=[s["i"]])


def gen_rounding_mismatch(c):
    """A cited cell that rounds to the draft figure only under another rule: the stored value
    truncated, or rounded up, where half-up gives another figure. The draft's rounding may be
    defensible. A dollar cell written in thousands with no scale word is a wrong figure since
    2026-10-28 (gen_scale_dropped)."""
    for s in c.ctx.sites:
        got = _cell_figure(s, c.ctx)
        if got is None:
            continue
        m, f, num = got
        exact = record.CTX.divide(abs(num[0]), f["scale"])
        if f["pct"] and not num[1] and abs(num[0]) < 1:
            exact = record.CTX.multiply(exact, D(100))
        q = D(1).scaleb(-f["places"])
        for how, mode in (("truncated", decimal.ROUND_DOWN), ("rounded up", decimal.ROUND_UP)):
            v = exact.quantize(q, rounding=mode, context=record.CTX)
            new_num = fmt_number(v, f["places"], "," in m.group("num"))
            if new_num != m.group("num"):
                c.value_item("rounding_mismatch", s, how, figure_form(s["text"]), with_num(s["text"], m, new_num),
                             "%s: %s to %s" % (s["text"], m.group("num"), new_num))


def gen_sign_flip(c):
    """Parentheses added to a figure, or removed from a negative one."""
    for s in c.ctx.sites:
        ms = figures_in(s["text"])
        if s["kind"] != "figure" or len(ms) != 1:
            continue
        m = ms[0]
        inner = m.group(0)[1:-1] if m.group("neg") else "(" + m.group(0) + ")"
        new = s["text"][:m.start()] + inner + s["text"][m.end():]
        how = "parentheses removed" if m.group("neg") else "parentheses added"
        edit = (s["start"], s["end"], tag(new, s["cite"], s["calc"]))
        c.add("sign_flip", [s["i"]], how, figure_form(s["text"]), [edit], "%s to %s" % (s["text"], new))


def gen_figure_in_words(c):
    """A whole-number figure replaced by a wrong value written in words, with its tag removed:
    rules read digits only, so nothing is checked and nothing is listed."""
    for s in c.ctx.sites:
        ms = figures_in(s["text"])
        if s["kind"] != "figure" or len(ms) != 1:
            continue
        m = ms[0]
        if any(m.group(g) for g in ("cur", "pct", "neg", "scale", "abbr")) or "." in m.group("num"):
            continue
        swaps = digit_swaps(m.group("num"))
        if not swaps:
            continue
        new = s["text"][:m.start()] + words(int(swaps[-1].replace(",", ""))) + s["text"][m.end():]
        c.add("figure_in_words", [s["i"]], "wrong value in words, untagged", figure_form(s["text"]),
              [(s["start"], s["end"], new)], "%s to %s" % (s["text"], new), removed=[s["i"]], targets=[])


def raw_lines(text):
    """(kind, n, start, end, prefix) for each block of the draft text, numbered as
    claims.read_text_draft numbers them; each block of matter 1's drafts is one line."""
    out, para, pos = [], 0, 0
    lines = text.split("\n")
    first = True
    for line in lines:
        start, pos = pos, pos + len(line) + 1
        if first:
            first = False
            if line.startswith(record.MARKERS):
                continue
        if not line.strip():
            continue
        m = FOOTDEF.match(line)
        if m:
            out.append(("foot", int(m.group(1)), start, start + len(line), m.end()))
            continue
        para += 1
        lm = re.match(r"^(?:#+\s*|\d+\.\s+|[-*]\s+|>\s?)", line)
        out.append(("para", para, start, start + len(line), lm.end() if lm else 0))
    return out


def gen_omission(c):
    """One sentence holding a tagged claim removed, with its tags; a paragraph of one sentence
    goes whole."""
    ctx = c.ctx
    for kind, n, a, z, prefix in raw_lines(ctx.draft):
        here = [s for s in ctx.sites if s["where"] == (kind, n)]
        if not here:
            continue
        body = ctx.draft[a + prefix:z]
        segs, cur = [], 0
        for m in SEGMENT.finditer(body):
            segs.append(("text", cur, m.start(), body[cur:m.start()]))
            t = parse_tag(m.group(1))[0] if m.group(1) is not None else ""
            segs.append(("tag" if m.group(1) is not None else "ref", m.start(), m.end(), t))
            cur = m.end()
        segs.append(("text", cur, len(body), body[cur:]))
        reads_as = "".join(x[3] for x in segs)
        spans = claims.block_sentences(reads_as)
        for si, (sa, sb) in enumerate(spans, 1):
            inside = [s for s in here if s["sentence"] == si]
            if not inside:
                continue
            if len(spans) == 1:
                edits = [(a, z + 2 if ctx.draft[z:z + 2] == "\n\n" else z, "")]
            else:  # the sentence and the space after it (before it, for the last sentence)
                lo, hi = (sa, sb + 1) if si < len(spans) else (sa - 1, sb)
                edits, off, base = [], 0, a + prefix
                for typ, ra, rb, t in segs:
                    if typ == "text":
                        da, db = max(lo, off), min(hi, off + len(t))
                        if da < db:
                            edits.append((base + ra + da - off, base + ra + db - off, ""))
                    elif lo <= off < hi:
                        edits.append((base + ra, base + rb, ""))
                    off += len(t)
            c.add("omission", [inside[0]["i"]], "sentence removed", "paragraph" if len(spans) == 1 else "sentence",
                  edits, "%s sentence %d" % (inside[0]["cluster"], si), removed=[s["i"] for s in inside], targets=[])


# The tagged draft's generators in a fixed order. mis_association comes from untagged_pairs.
GENERATORS = (("wrong_figure", gen_wrong_figure), ("wrong_figure", gen_scale_dropped), ("wrong_date", gen_wrong_date),
              ("wrong_cite", gen_wrong_cite), ("wrong_cite", gen_cite_swap), ("misquote", gen_misquote),
              ("calc_error", gen_calc_error), ("exhibit_mismatch", gen_exhibit_mismatch),
              ("pin_missing", gen_pin_missing), ("rounding_mismatch", gen_rounding_mismatch),
              ("sign_flip", gen_sign_flip), ("figure_in_words", gen_figure_in_words), ("omission", gen_omission))


# --- baselines ----------------------------------------------------------------------------------

DATE_RESPELLING = {"iso": "month day year", "slash": "iso", "month day year": "iso",
                   "abbreviated month": "day month year", "day month year": "abbreviated month",
                   "month year": "abbreviated month year", "mid-month": "month year", "quarter Qn": "quarter nQ",
                   "quarter nQ": "quarter Qn"}


def _ex_bates(parsed, ctx):
    """An exhibit cite with a one-page pin written with that page's Bates id instead."""
    ex = ctx.index.exhibit(parsed["label"])
    if ex is None or not parsed["pin"] or "pages" not in parsed["pin"]:
        return None
    a, b = parsed["pin"]["pages"]
    if a != b:
        return None
    return parsed["written"] + " at " + ctx.index.page_id(ex["prefix"], ex["first"] + a - 1, ex["width"])


def respell(name, s, ctx):
    """One normaliser's respelling of a tag as (text, cite), or None when it does not apply. Each
    respelling must tie wherever the original ties, by the rule the normaliser names."""
    t, cite, kind = s["text"], s["cite"], s["kind"]
    parsed = claims.parse_cite(cite, ctx.grammar)[0] if cite and not s["is_id"] else None
    ptype = parsed["type"] if parsed else ""
    if name == "quote marks" and kind == "quotation":
        if t[:1] == '"':
            return "“" + t[1:-1].replace("'", "’") + "”", cite
        if t[:1] == "“":
            return '"' + t[1:-1].replace("’", "'") + '"', cite
    elif name == "ellipsis" and kind == "quotation":
        for old, new in ((". . .", "..."), ("...", "…"), ("…", ". . .")):
            if old in t:
                return t.replace(old, new), cite
    elif name == "quotation whitespace" and kind == "quotation":
        return t.replace(" ", "  "), cite
    elif name == "currency sign" and kind == "figure":
        return t.replace("$", ""), cite
    elif name == "thousands separators" and kind == "figure":
        return re.sub(r"(?<=\d),(?=\d{3})", "", t), cite
    elif name == "scale abbreviation" and kind == "figure":
        return re.sub(r"(\d)K\b", r"\1 thousand", re.sub(r"(\d) million\b", r"\1M", t)), cite
    elif name == "range dash" and kind == "figure" and figure_form(t) == "range":
        return t.replace(" to ", "–", 1), cite
    elif name == "date form" and kind == "date":
        p = date_parts(t, ctx.matter["date_order"])
        if p is not None:
            other = DATE_RESPELLING[p["form"]]
            return fmt_date(p, p["y"], p["mo"], p["d"], p["q"], ctx.matter["date_order"], other), cite
    elif name == "exhibit label" and ptype == "exhibit":
        if parsed["written"].startswith("Ex. "):
            return t, "Exhibit " + cite[4:]
        if parsed["written"].startswith("Exhibit "):
            return t, "Ex. " + cite[8:]
        return t, "Ex. " + cite
    elif name == "Bates separator" and ptype == "bates" and not parsed.get("end"):
        k = record.bates_key(parsed["start"])
        return t, "%s-%s" % (k[0], k[2])
    elif name == "Bates pin" and ptype == "exhibit":
        new = _ex_bates(parsed, ctx)
        if new:
            return t, new
    elif name == "transcript form" and ptype == "transcript":
        return t, cite.replace(" Dep.", " Tr.", 1) if " Dep." in cite else cite.replace(" Tr.", " Dep.", 1)
    return None


NORMALISERS = ("quote marks", "ellipsis", "quotation whitespace", "currency sign", "thousands separators",
               "scale abbreviation", "range dash", "date form", "exhibit label", "Bates separator", "Bates pin",
               "transcript form")


def respelled_drafts(ctx):
    out = []
    for name in NORMALISERS:
        edits, n = [], 0
        for s in ctx.sites:
            r = respell(name, s, ctx)
            if r is None or (r[0] == s["text"] and r[1] == s["cite"]):
                continue
            edits.append((s["start"], s["end"], tag(r[0], r[1], s["calc"])))
            n += 1
        out.append((name, n, apply(ctx.draft, edits)))
    return out


def untagged_items(ctx):
    """Planted errors in the untagged twin: an adjacent-digit swap on a figure, a day or month
    shifted on a date, one word changed in a quotation, each at a token the key says ties."""
    out = []
    lines = {(k, n): (a + p, z) for k, n, a, z, p in raw_lines(ctx.twin)}
    for row in ctx.key["drafts"]["untagged"]["claims"]:
        if row["code"] != "tie":
            continue
        where = ("foot", row["footnote"]) if row.get("para") is None else ("para", row["para"])
        if where not in lines:
            continue
        a, z = lines[where]
        line = ctx.twin[a:z]
        span = row["span"]
        if line.count(span) != 1:
            continue
        new = None
        if row["kind"] == "figure":
            ms = figures_in(span)
            swaps = digit_swaps(ms[0].group("num")) if len(ms) == 1 else []
            new = with_num(span, ms[0], swaps[-1]) if swaps else None
        elif row["kind"] == "date":
            p = date_parts(span, ctx.matter["date_order"])
            if p and p["d"] is not None:
                new = fmt_date(p, p["y"], p["mo"], p["d"] + 1, order=ctx.matter["date_order"])
            elif p and p["mo"] is not None:
                new = fmt_date(p, p["y"], p["mo"] + 1 if p["mo"] < 12 else p["mo"] - 1)
        elif row["kind"] == "quotation":
            ws = quote_words(span)
            if ws:
                wa, wb = ws[len(ws) // 2]
                new = span[:wa] + substitute(span[wa:wb]) + span[wb:]
        if not new or new == span or (row["cite"] and still_ties(new, row["cite"], "", ctx)):
            continue
        off = a + line.index(span)
        out.append({"kind": row["kind"], "where": list(where), "span": new, "detail": "%s to %s" % (span, new),
                    "text": ctx.twin[:off] + new + ctx.twin[off + len(span):]})
    return out


PAREN_CITE = re.compile(r"\(([^()]+)\)")
PAIR_GAP = re.compile(r"[^()\d]{0,24}")


def _where_of(row):
    return ("foot", row["footnote"]) if row.get("para") is None else ("para", row["para"])


def twin_cites(line, ctx):
    """The parenthesised cites in one line of the untagged twin as (start, end, text, type),
    where start and end bound the text inside the parentheses. A group the grammar does not
    read whole as a cite is left out."""
    out = []
    for m in PAREN_CITE.finditer(line):
        parsed = claims.parse_cite(m.group(1), ctx.grammar)[0]
        if parsed is not None:
            out.append((m.start(1), m.end(1), m.group(1), parsed["type"]))
    return out


def value_slot(line, span, cites):
    """The index in cites of the cite written right after span, with only words between them
    (as in "48,237 units (PX-3 at 2)"), when the line writes span that way once; else None."""
    found = []
    for m in re.finditer(re.escape(span), line):
        if re.search(r"\d[,.]?$", line[:m.start()]) or re.match(r"[,.]?\d", line[m.end():]):
            continue  # part of a longer figure
        for gi, (ga, _, _, _) in enumerate(cites):
            if ga - 1 >= m.end():
                if PAIR_GAP.fullmatch(line[m.end():ga - 1]):
                    found.append(gi)
                break
    return found[0] if len(found) == 1 else None


def untagged_pairs(ctx):
    """The mis_association class, the association measure: in the untagged twin, two figures in
    one sentence, each written with its cite in parentheses right after it, have their cites
    swapped in place. The sentence then holds two or more figures and two or more cites, so A2
    pairs it: each figure with the cite now after it, and a pairing that read the draft any
    other way would show here. A1, A3 and A4 do not run on these items. Returns (items, still),
    still counting the swaps where both figures tie at the swapped cite. A pair is left out when
    either cite is an Id., when an Id. takes either cite as its antecedent (the next cite in the
    paragraph, or for the last cite of a footnote the next footnote), or when a figure is
    written twice in its block. The class is not padded to reach SIZE."""
    lines = {(k, n): (a + p, z) for k, n, a, z, p in raw_lines(ctx.twin)}
    rows = ctx.key["drafts"]["untagged"]["claims"]
    spans_in = {}
    for r in rows:
        spans_in.setdefault(_where_of(r), []).append(record.norm_text(r["span"]))
    groups = {}
    for r in rows:
        if r["code"] == "tie" and r["kind"] == "figure" and r["cite_resolved"]:
            groups.setdefault((_where_of(r), r["sentence"]), []).append(r)
    out, still = [], 0
    for (where, si) in sorted(groups, key=lambda k: (k[0][0], k[0][1], k[1])):
        if where not in lines:
            continue
        a, z = lines[where]
        line = ctx.twin[a:z]
        cites = twin_cites(line, ctx)
        slots = []
        for r in groups[(where, si)]:
            if spans_in[where].count(record.norm_text(r["span"])) != 1:
                continue
            gi = value_slot(line, r["span"], cites)
            if gi is None or cites[gi][3] == "id":
                continue
            if gi + 1 < len(cites) and cites[gi + 1][3] == "id":
                continue
            if where[0] == "foot" and gi == len(cites) - 1:
                continue
            if record.norm_text(cites[gi][2]).casefold() != record.norm_text(r["cite_resolved"]).casefold():
                continue
            slots.append((r, gi))
        for x in range(len(slots)):
            for y in range(x + 1, len(slots)):
                (ra, ia), (rb, ib) = slots[x], slots[y]
                ta, tb = cites[ia][2], cites[ib][2]
                if record.norm_text(ta).casefold() == record.norm_text(tb).casefold():
                    continue
                new_line = _splice(line, [(cites[ia][0], cites[ia][1], tb), (cites[ib][0], cites[ib][1], ta)])
                crossed = {ra["span"]: " ".join(tb.split()), rb["span"]: " ".join(ta.split())}
                targets = [r["span"] for r in (ra, rb) if not still_ties(r["span"], crossed[r["span"]], "", ctx)]
                if not targets:
                    still += 1
                    continue
                cluster = "fn %d" % where[1] if where[0] == "foot" else "para %d" % where[1]
                text = ctx.twin[:a] + new_line + ctx.twin[z:]
                detail = "%s (%s) and %s (%s) crossed" % (ra["span"], ta, rb["span"], tb)
                out.append({"cls": "mis_association", "how": TWIN_SWAP, "untagged": True,
                            "id": "u-" + sha("|".join(["mis_association", TWIN_SWAP, detail, sha(text)]))[:10],
                            "kind": "crossed cites", "where": list(where), "sentence": si,
                            "spans": [ra["span"], rb["span"]], "targets": targets, "crossed": crossed,
                            "cluster": cluster,
                            "form": "%s and %s" % (figure_form(ra["span"]), figure_form(rb["span"])),
                            "detail": detail, "text": text})
    return out, still


# --- scoring ------------------------------------------------------------------------------------


def run_text(text, ctx):
    """One draft through the run's own path: intake (I7 on the draft; the record's I1 to I6 are
    the context's), the proposer, claims and the verifier. Nothing is written."""
    draft = claims.read_text_draft(text)
    draft["type"] = "md"
    checks, _, draft, grammar, analysis = ctx.tool.intake_checks(ctx.root, ctx.matter, None, False,
                                                                 index=ctx.index, draft=draft)
    blocking = [c["code"] for c in checks if c["code"] in ctx.tool.BLOCKING and not c["pass"]]
    if blocking:
        return {"intake": blocking, "rows": []}
    client = providers.make_client(ctx.matter, grammar.names())
    built, verdicts = ctx.tool.check_claims(client, providers.Recorder(None), ctx.matter, draft, analysis,
                                            grammar, ctx.index)[:2]
    return {"intake": [], "rows": list(zip(built, verdicts))}


def score(item, res, n_sites):
    """The drop log against the item's label: caught when a planted claim drops, escaped when
    every planted claim ties; rows on other claims are counted apart."""
    out = {"caught": False, "escaped": False, "codes": [], "expected": False, "collateral": 0}
    if res["intake"]:
        out.update(caught=True, codes=["intake " + ", ".join(res["intake"])])
        return out
    rows = res["rows"]
    if item["untagged"]:
        hits = [(c, v) for c, v in rows if list(c["where"]) == item["where"] and
                record.norm_text(c["span"]) == record.norm_text(item["span"])]
        others = [(c, v) for c, v in rows if not v["pass"] and (c, v) not in hits]
        out["collateral"] = len(others)
        out["caught"] = any(not v["pass"] for _, v in hits)
        out["escaped"] = bool(hits) and all(v["pass"] for _, v in hits)
        out["codes"] = sorted({v["code"] for _, v in hits if not v["pass"]})
        want = EXPECT_UNTAGGED.get(item["kind"], ())
        out["expected"] = bool(hits) and all(not v["pass"] and v["code"] in want for _, v in hits)
        return out
    tags = [(c, v) for c, v in rows if c["proposed_by"] == "tag"]
    kept = [i for i in range(n_sites) if i not in item["removed"]]
    if len(tags) != len(kept):
        out["codes"] = ["tag count %d, expected %d" % (len(tags), len(kept))]
        return out
    by_site = dict(zip(kept, tags))
    if item["targets"]:
        mine = [by_site[i] for i in item["targets"]]
        out["caught"] = any(not v["pass"] for _, v in mine)
        out["escaped"] = all(v["pass"] for _, v in mine)
        out["codes"] = sorted({v["code"] for _, v in mine if not v["pass"]})
        want = EXPECT.get(item["cls"])
        out["expected"] = bool(want) and all(not v["pass"] and v["code"] in want for _, v in mine)
        others = [(c, v) for c, v in rows if not v["pass"] and all(c is not m[0] for m in mine)]
    else:  # a removal (omission, figure in words): any row in the drop log flags it
        here = [(c, v) for c, v in rows if not v["pass"]]
        out["caught"] = bool(here)
        out["escaped"] = not here
        out["codes"] = sorted({v["code"] for _, v in here})
        others = []
    out["collateral"] = len(others)
    return out


def score_pair(item, res, twin_drops):
    """A crossed pair in the untagged twin against its label: caught when a target figure drops;
    expected when every target drops with a code EXPECT_UNTAGGED names and A2, the rule the
    class tests, paired it with the cite now written after it. A pairing by any other rule is
    no expected code: in a "figure (cite)" sentence A1's nearest cite is often the same cite,
    so without the rule test the class could not see A2 switched off. twin_drops holds (where,
    span) for the rows the key expects the twin itself to drop, which are no false flag here."""
    out = {"caught": False, "escaped": False, "codes": [], "expected": False, "collateral": 0}
    if res["intake"]:
        out.update(caught=True, codes=["intake " + ", ".join(res["intake"])])
        return out
    rows = res["rows"]

    def here(span):
        return [(c, v) for c, v in rows if list(c["where"]) == item["where"] and c["sentence"] == item["sentence"]
                and record.norm_text(c["span"]) == record.norm_text(span)]

    mine = []
    for span in item["spans"]:
        hit = here(span)
        if len(hit) != 1:
            out["codes"] = ["%s read %d times" % (span, len(hit))]
            return out
        mine.append((span, hit[0]))
    targets = [(span, cv) for span, cv in mine if span in item["targets"]]
    out["caught"] = any(not v["pass"] for _, (_, v) in targets)
    out["escaped"] = all(v["pass"] for _, (_, v) in targets)
    out["codes"] = sorted({v["code"] for _, (_, v) in targets if not v["pass"]})
    want = EXPECT_UNTAGGED["crossed cites"]
    out["expected"] = all(not v["pass"] and v["code"] in want and c.get("pairing") == "A2" and
                          record.norm_text(c["cite_text"] or "") == record.norm_text(item["crossed"][span])
                          for span, (c, v) in targets)
    pair = [cv[0] for _, cv in mine]
    out["collateral"] = sum(1 for c, v in rows if not v["pass"] and all(c is not p for p in pair)
                            and (tuple(c["where"]), record.norm_text(c["span"])) not in twin_drops)
    return out


def build(ctx):
    """Every planted item, from every generator in a fixed order."""
    corpus = Corpus(ctx)
    for _, gen in GENERATORS:
        gen(corpus)
    return corpus


def corpus_hash(corpus, baselines, untagged, pairs):
    doc = {"items": [{k: i[k] for k in sorted(i)} for i in corpus.items],
           "baselines": [{"name": n, "respelled": r, "draft_sha256": sha(t)} for n, r, t in baselines],
           "untagged": [{"kind": u["kind"], "where": u["where"], "span": u["span"], "draft_sha256": sha(u["text"])}
                        for u in untagged],
           "mis_association": [{"where": p["where"], "sentence": p["sentence"], "spans": p["spans"],
                                "targets": p["targets"], "crossed": p["crossed"], "draft_sha256": sha(p["text"])}
                               for p in pairs[0]] + [{"still": pairs[1]}]}
    return hashlib.sha256(json.dumps(doc, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
                          .encode("utf-8")).hexdigest()


def whole_corpus(ctx):
    """(corpus, baselines, untagged, pairs, hash): every planted item and baseline, built once."""
    corpus = build(ctx)
    baselines = respelled_drafts(ctx)
    untagged = untagged_items(ctx)
    pairs = untagged_pairs(ctx)
    return corpus, baselines, untagged, pairs, corpus_hash(corpus, baselines, untagged, pairs)


def pair_row(p, scored=None):
    """A mis_association item as a results row: its label without the draft text, plus its
    score (or a blank one, for a declaration)."""
    row = {k: v for k, v in p.items() if k != "text"}
    row.update(scored or {"caught": False, "escaped": False, "codes": [], "expected": False, "collateral": 0})
    return row


def measure_all(ctx, only=None):
    """Build the whole corpus, then score every item and baseline, or with only the items of
    one class. Returns the results dict; the corpus hash is always the whole corpus's. The
    results hold the tagged draft's items, then the mis_association items from the twin."""
    corpus, baselines, untagged, (pairs, still), whole = whole_corpus(ctx)
    n_sites = len(ctx.sites)
    results = []
    for item in corpus.items:
        if only is None or item["cls"] == only:
            res = run_text(corpus.texts[item["id"]], ctx)
            results.append(dict(item, **score(item, res, n_sites)))
    twin_drops = {(_where_of(r), record.norm_text(r["span"])) for r in ctx.key["drafts"]["untagged"]["claims"]
                  if r["code"] != "tie"}
    if only is None or only == "mis_association":
        for p in pairs:
            results.append(pair_row(p, score_pair(p, run_text(p["text"], ctx), twin_drops)))
    else:
        still = 0
    base = {"respelled": [], "clean": None, "twin": None, "weak": None}
    if only is not None:
        return {"corpus": corpus, "results": results, "baselines": base, "untagged": [], "pairs_still": still,
                "only": only, "corpus_sha256": whole, "code_sha256": gate.code_hash()}
    clean = run_text(ctx.draft, ctx)
    ties = [v for _, v in clean["rows"] if v["pass"]]
    base["clean"] = {"n": len(clean["rows"]), "flagged": len(clean["rows"]) - len(ties) + len(clean["intake"])}
    base["weak"] = {"n": len(ties), "weak": sum(1 for v in ties if v["weak_flags"])}
    for name, n, text in baselines:
        res = run_text(text, ctx)
        codes = sorted({v["code"] for _, v in res["rows"] if not v["pass"]} | set(res["intake"]))
        flagged = sum(1 for _, v in res["rows"] if not v["pass"]) + len(res["intake"])
        base["respelled"].append({"name": name, "respelled": n, "n": len(res["rows"]), "flagged": flagged,
                                  "codes": codes})
    twin = run_text(ctx.twin, ctx)
    want = {r["key"]: r["code"] for r in ctx.key["drafts"]["untagged"]["claims"]}
    got = {c["key"]: v["code"] for c, v in twin["rows"]}
    tie_keys = [k for k, code in want.items() if code == "tie"]
    drop_keys = [k for k, code in want.items() if code != "tie"]
    base["twin"] = {"tie_n": len(tie_keys), "flagged": sum(1 for k in tie_keys if got.get(k) != "tie"),
                    "drop_n": len(drop_keys), "listed": sum(1 for k in drop_keys if got.get(k) == want[k]),
                    "extra": sorted(k for k in got if k not in want), "intake": twin["intake"]}
    for u in untagged:
        u.update(untagged=True, cls="untagged " + u["kind"], targets=[], removed=[])
        u.update(score(u, run_text(u["text"], ctx), n_sites))
    return {"corpus": corpus, "results": results, "baselines": base, "untagged": untagged,
            "pairs_still": still, "only": None, "corpus_sha256": whole, "code_sha256": gate.code_hash()}


# --- reporting ----------------------------------------------------------------------------------


def _kn(k, n):
    return "%d of %d" % (k, n)


def class_rows(results, cls):
    return [r for r in results if r["cls"] == cls]


def summary(results):
    out = {}
    for cls in CLASSES:
        rows = class_rows(results, cls)
        out[cls] = {"n": len(rows), "caught": sum(r["caught"] for r in rows),
                    "escaped": sum(r["escaped"] for r in rows), "expected": sum(r["expected"] for r in rows),
                    "collateral": sum(r["collateral"] for r in rows), "clusters": len({r["cluster"] for r in rows})}
    return out


def breakdown(rows, field):
    counts = {}
    for r in rows:
        k = r[field]
        a, b = counts.get(k, (0, 0))
        counts[k] = (a + r["caught"], b + 1)
    return ", ".join("%s %s" % (k, _kn(*counts[k])) for k in sorted(counts))


def report(m):
    """The printout. The first line carries the corpus and code hashes."""
    results, only = m["results"], m["only"]
    s = summary(results)
    twin = sum(1 for r in results if r.get("untagged"))
    if twin and len(results) > twin:
        where = "%d in copies of one tagged draft and %d in copies of its untagged twin" % (len(results) - twin, twin)
    else:
        where = "in copies of the tagged draft's untagged twin" if twin else "in copies of one tagged draft"
    lines = ["measure: corpus sha256 %s, code sha256 %s" % (m["corpus_sha256"], m["code_sha256"]),
             "matter 1: %d planted items%s, %s, against one record, in %d paragraphs; each item holds one error"
             % (len(results), " in class %s" % only if only else "", where,
                len({r["cluster"] for r in results})),
             "each class is k of N with a Wilson 95%% interval beside a cluster bootstrap over paragraphs "
             "(%d resamples, seed %d); labels read the Wilson lower bound: meets target at %.2f, meets floor at "
             "%.2f; under %d items a class is underpowered" % (BOOT_REPS, BOOT_SEED, TARGET, FLOOR, SIZE)]
    head = [c for c in HEADLINE if s[c]["n"]]
    if head:
        lines += ["", "Escapes, planted errors that tied (Wilson 95% upper bound)"]
        for cls in head:
            e, n = s[cls]["escaped"], s[cls]["n"]
            lines.append("  %-20s %-12s upper %.3f" % (cls, _kn(e, n), wilson(e, n)[1]))
        if only is None:
            e, n = sum(s[c]["escaped"] for c in head), sum(s[c]["n"] for c in head)
            lines.append("  %-20s %-12s upper %.3f" % ("all headline", _kn(e, n), wilson(e, n)[1]))
        lines += ["", "Headline classes (caught: the planted claim is in the drop log)"]
        for cls in head:
            lines += class_lines(cls, s[cls], class_rows(results, cls))
            if cls in HEADLINE_NOTE:
                lines.append("  %-20s %s" % ("", HEADLINE_NOTE[cls]))
            if cls == "mis_association" and m["pairs_still"]:
                lines.append("  %-20s left out: %d swaps where both figures still tie at the swapped cite"
                             % ("", m["pairs_still"]))
    apart = [c for c in APART if s[c]["n"]]
    if apart:
        lines += ["", "Apart"]
        for cls in apart:
            lines += class_lines(cls, s[cls], class_rows(results, cls))
            lines.append("  %-20s %s" % ("", APART_NOTE[cls]))
    blind = [c for c in BLIND if s[c]["n"]]
    if blind:
        lines += ["", "Designed blindness (each item is expected to tie; flagged is k of N)"]
        for cls in blind:
            lines.append("  %-20s flagged %s; %s" % (cls, _kn(s[cls]["caught"], s[cls]["n"]), BLIND_NOTE[cls]))
            if cls == "coincidental_figure":
                routed = m["corpus"].routed
                froms = ", ".join("%s %d" % (k, routed[k]) for k in sorted(routed))
                lines.append("  %-20s routed from %s" % ("", froms))
            lines.append("  %-20s how: %s" % ("", breakdown(class_rows(results, cls), "how")))
    if m["baselines"]["clean"] is not None:
        lines += baseline_lines(m)
    lines.append("coincidental_figure routing: %d planted changes still tied at the cite under the three rules and "
                 "went to coincidental_figure" % sum(m["corpus"].routed.values()))
    kept = m["corpus"].unchanged
    if kept:
        lines.append("left out: %s planted quotation changes that still match under the quotation rule, since no "
                     "error was made" % ", ".join("%s %d" % (k, kept[k]) for k in sorted(kept)))
    return "\n".join(lines) + "\n"


def baseline_lines(m):
    b, results, untagged = m["baselines"], m["results"], m["untagged"]
    out = ["", "Baselines (false flags per claim; every claim here should tie)",
           "  %-36s %s claims flagged" % ("clean tagged draft", _kn(b["clean"]["flagged"], b["clean"]["n"]))]
    for r in b["respelled"]:
        codes = (": " + ", ".join(r["codes"])) if r["codes"] else ""
        out.append("  %-36s %s claims flagged, %d respelled%s"
                   % ("respelled, " + r["name"], _kn(r["flagged"], r["n"]), r["respelled"], codes))
    t = b["twin"]
    out.append("  %-36s %s claims the key says tie flagged; %s rows the key expects listed with its code%s"
               % ("untagged twin under rules", _kn(t["flagged"], t["tie_n"]), _kn(t["listed"], t["drop_n"]),
                  "; %d claims the key lacks" % len(t["extra"]) if t["extra"] else ""))
    out.append("  %-36s %d" % ("rows on unplanted claims", sum(r["collateral"] for r in results)))
    w = b["weak"]
    lo, hi = wilson(w["weak"], w["n"])
    out += ["", "Weak-tie share on the clean draft: %s ties (Wilson %.3f to %.3f); the spot-check sample takes every "
                "weak tie, %d claims" % (_kn(w["weak"], w["n"]), lo, hi, w["weak"])]
    by = {}
    for x in untagged:
        a, n = by.get(x["kind"], (0, 0))
        by[x["kind"]] = (a + x["caught"], n + 1)
    out.append("Untagged items, a coverage count off the headline: %s planted errors in the untagged twin reached the "
               "drop log (%s); expected code %s" % (_kn(sum(x["caught"] for x in untagged), len(untagged)),
                                                   ", ".join("%ss %s" % (k, _kn(*by[k])) for k in sorted(by)),
                                                   _kn(sum(x["expected"] for x in untagged), len(untagged))))
    return out


def paragraphs(rows):
    """How the rows spread over paragraphs: the count and the largest one."""
    counts = {}
    for r in rows:
        counts[r["cluster"]] = counts.get(r["cluster"], 0) + 1
    if not counts:
        return "0 paragraphs"
    top, size = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0]
    return "%d paragraphs, the largest %s with %d of %d" % (len(counts), top, size, len(rows))


def class_lines(cls, st, rows):
    k, n = st["caught"], st["n"]
    lo, hi = wilson(k, n)
    blo, bhi = cluster_bootstrap([(r["cluster"], int(r["caught"])) for r in rows])
    out = ["  %-20s %-12s Wilson %.3f to %.3f  bootstrap %.3f to %.3f  %s"
           % (cls, _kn(k, n), lo, hi, blo, bhi, label(k, n))]
    out.append("  %-20s expected code %s; rows on unplanted claims %d; %s"
               % ("", _kn(st["expected"], n), st["collateral"], paragraphs(rows)))
    variants = VARIANTS.get(cls, ())
    main = [r for r in rows if r["how"] not in variants]
    if main:
        out.append("  %-20s forms: %s" % ("", breakdown(main, "form")))
        out.append("  %-20s how: %s" % ("", breakdown(main, "how")))
    for how in variants:
        vr = [r for r in rows if r["how"] == how]
        if vr:
            out.append("  %-20s how: %s %s, expected code %s, %s; forms: %s"
                       % ("", how, _kn(sum(r["caught"] for r in vr), len(vr)),
                          _kn(sum(r["expected"] for r in vr), len(vr)), paragraphs(vr), breakdown(vr, "form")))
    return out


# --- freeze, declare, regress -------------------------------------------------------------------


def _tree(folder, prefix, skip=()):
    out = {}
    for dirpath, dirs, names in os.walk(folder):
        dirs[:] = sorted(d for d in dirs if not record.ignored(d) and os.path.join(dirpath, d) not in skip)
        for name in sorted(names):
            if record.ignored(name):
                continue
            full = os.path.join(dirpath, name)
            out[prefix + os.path.relpath(full, folder).replace(os.sep, "/")] = gate.text_sha(full)
    return out


def hashes():
    """The hash groups FROZEN.json and a batch record: the fixture (matter 1 without key/), the
    keys and the code files, each file read with LF line endings."""
    key_dir = os.path.join(MATTER_DIR, "key")
    return {"fixture": _tree(MATTER_DIR, MATTER_REL + "/", skip=(key_dir,)),
            "keys": _tree(key_dir, MATTER_REL + "/key/"), "code": gate.code_manifest()}


def frozen_doc(corpus_sha):
    h = hashes()
    return {"schema": 1, "stage": 3, "matter": MATTER_REL, "hashes": h,
            "fixture_sha256": record.tree_hash(h["fixture"]), "keys_sha256": record.tree_hash(h["keys"]),
            "code_sha256": record.tree_hash(h["code"]), "corpus_sha256": corpus_sha,
            "regenerate": "python3 -I tieout/tieout.py measure --freeze"}


def changed(old, new):
    """Ported from the author's earlier private code: the hash groups, and the files inside them, that differ."""
    a, b = (old or {}).get("hashes", {}), new["hashes"]
    out = []
    for k in sorted(set(a) | set(b)):
        if a.get(k) == b.get(k):
            continue
        if isinstance(a.get(k), dict) and isinstance(b.get(k), dict):
            out += ["%s %s" % (k, f) for f in sorted(set(a[k]) | set(b[k])) if a[k].get(f) != b[k].get(f)]
        else:
            out.append(k)
    if (old or {}).get("corpus_sha256") != new["corpus_sha256"]:
        out.append("corpus")
    return out


def _dumps(doc):
    return (json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def _batch_ids():
    folder = os.path.join(HERE, BATCHES)
    if not os.path.isdir(folder):
        return []
    return sorted(n[:-5] for n in os.listdir(folder) if re.fullmatch(r"\d{4}-\d\d-\d\d-b\d\d\.json", n))


def next_batch_id(date):
    """Ported from the author's earlier private code: <date>-bNN, one more than the highest number that day."""
    nums = [int(b[-2:]) for b in _batch_ids() if b.startswith(date + "-b")]
    return "%s-b%02d" % (date, max(nums + [0]) + 1)


def results_doc(m, batch, decl_sha, printout):
    s = summary(m["results"])
    items = {}
    for cls in CLASSES:
        rows = class_rows(m["results"], cls)
        items[cls] = {"caught": sorted(r["id"] for r in rows if r["caught"]),
                      "escaped": sorted(r["id"] for r in rows if r["escaped"]),
                      "expected": sorted(r["id"] for r in rows if r["expected"])}
    b = m["baselines"]
    t = b["twin"]
    u = m["untagged"]
    return {"schema": 3, "batch": batch, "declaration_sha256": decl_sha, "corpus_sha256": m["corpus_sha256"],
            "code_sha256": m["code_sha256"], "layout": LAYOUT, "classes": s, "items": items,
            "false_flags": {"clean": b["clean"]["flagged"], "twin": t["flagged"],
                            "respelled": {r["name"]: r["flagged"] for r in b["respelled"]},
                            "unplanted rows": sum(r["collateral"] for r in m["results"])},
            "twin": {"tie claims": t["tie_n"], "flagged": t["flagged"], "drop rows": t["drop_n"],
                     "listed": t["listed"], "claims the key lacks": t["extra"]},
            "untagged": {"n": len(u), "caught": sum(x["caught"] for x in u),
                         "expected": sum(x["expected"] for x in u)},
            "mis_association left out": m["pairs_still"],
            "routed": dict(sorted(m["corpus"].routed.items())), "printout_sha256": sha(printout)}


def role_of(cls):
    return "headline" if cls in HEADLINE else "apart" if cls in APART else "blind"


def declaration(m, batch, date, frozen_bytes, off_headline=None):
    s = summary(m["results"])
    classes, bars = {}, {}
    for cls in CLASSES:
        n = s[cls]["n"]
        role = role_of(cls)
        classes[cls] = {"n": n, "role": role}
        if role != "blind":
            f, t = bar(n, FLOOR), bar(n, TARGET)
            bars[cls] = {"floor": [f, n] if f is not None else None, "target": [t, n] if t is not None else None}
    return {"schema": 2, "batch": batch, "date": date, "kind": "offline corpus, matter 1", "matter": MATTER_REL,
            "frozen_sha256": hashlib.sha256(frozen_bytes).hexdigest(), "hashes": hashes(),
            "corpus_sha256": m["corpus_sha256"], "code_sha256": m["code_sha256"], "layout": LAYOUT,
            "classes": classes, "bars": bars, "off_headline": off_headline or {}, "size": SIZE,
            "bootstrap": {"resamples": BOOT_REPS, "seed": BOOT_SEED},
            "replay": "none in this batch: measure --proposer scores recorded batches apart", "results": batch + "-results.json"}


def bar_lines(decl):
    """Each bar as k of N, never a percentage: the fewest catches whose Wilson lower bound clears
    the floor and the target."""
    out = []
    for cls in HEADLINE + APART:
        b, n = decl["bars"][cls], decl["classes"][cls]["n"]
        if n < SIZE:
            out.append("  %-20s %-8s N %d, underpowered: under %d items no bar is a headline"
                       % (cls, role_of(cls), n, SIZE))
            continue
        f = _kn(*b["floor"]) if b["floor"] else "none"
        t = _kn(*b["target"]) if b["target"] else "none"
        out.append("  %-20s %-8s meets floor at %s or more, meets target at %s or more" % (cls, role_of(cls), f, t))
    return out


def layout_changes(was, now):
    """Each class whose role differs between a batch's layout and this one, as text."""
    if not was:
        return ["the batch records no class layout, so it predates the layout of 2026-10-28"]
    role_was = {c: r for r, cs in was.items() for c in cs}
    role_now = {c: r for r, cs in now.items() for c in cs}
    def order(c):
        return (CLASSES.index(c) if c in CLASSES else len(CLASSES), c)

    return ["%s %s, batch %s" % (c, role_now.get(c, "absent"), role_was.get(c, "absent"))
            for c in sorted(set(role_was) | set(role_now), key=order) if role_was.get(c) != role_now.get(c)]


def regress(m, base):
    """(passed, lines): the class layout, then each headline and apart class's catches,
    expected codes, escapes and rows on unplanted claims, the baselines' false flags, the
    untagged twin's rows the key expects listed with its code and its claims the key lacks,
    the untagged coverage count, coincidental routing and the mis_association swaps left out,
    against the batch's results. A changed layout, fewer catches, expected codes or listed
    twin rows, or more escapes, false flags, claims the key lacks, routing or left-out swaps,
    fail it. A results file before schema 3 records no twin rows, and that line says so."""
    now = results_doc(m, "", "", "")
    lines, falls = [], []
    same = base["corpus_sha256"] == now["corpus_sha256"]
    lines.append("measure --regress: against batch %s (corpus sha256 %s, code sha256 %s)"
                 % (base["batch"], base["corpus_sha256"], base["code_sha256"]))
    lines.append("  corpus: %s" % ("the batch's items" if same else "differs from the batch's; counts compared by "
                                                                   "class, items by id where both hold them"))
    moved = layout_changes(base.get("layout"), now["layout"])
    if moved:
        falls.append("class layout differs from the batch's (%s)" % "; ".join(moved))
    lines.append("  layout: headline %s; apart %s%s" % (", ".join(HEADLINE), ", ".join(APART),
                                                       "; differs: " + "; ".join(moved) if moved else ""))
    ids = {r["id"] for r in m["results"]}
    for cls in HEADLINE + APART:
        a, b = base["classes"].get(cls, {}), now["classes"][cls]
        ka, kb, ea, eb = a.get("caught", 0), b["caught"], a.get("escaped", 0), b["escaped"]
        xa, xb = a.get("expected", 0), b["expected"]
        ca, cb = a.get("collateral", 0), b["collateral"]
        state = []
        if kb < ka:
            state.append("catches fell")
            falls.append("catches fell in %s (%d to %d)" % (cls, ka, kb))
        if xb < xa:  # a check bypassed or relabelled while the item still drops under another code
            state.append("expected code fell")
            falls.append("expected code fell in %s (%d to %d)" % (cls, xa, xb))
        if eb > ea:
            state.append("escapes rose")
            falls.append("escapes rose in %s (%d to %d)" % (cls, ea, eb))
        if cb > ca:
            state.append("false flags rose")
            falls.append("false flags rose in %s (%d to %d)" % (cls, ca, cb))
        for field, what in (("caught", "items that fell"), ("expected", "items that lost the expected code")):
            if field not in base["items"].get(cls, {}):
                continue
            was = set(base["items"][cls][field])
            lost = sorted(i for i in was - set(now["items"][cls][field]) if i in ids)
            if lost:
                more = " and %d more" % (len(lost) - 5) if len(lost) > 5 else ""
                state.append(what + ": " + ", ".join(lost[:5]) + more)
        lines.append("  %-20s %-8s caught %s, batch %s; expected code %d, batch %d; escaped %d, batch %d; rows on "
                     "unplanted claims %d, batch %d%s"
                     % (cls, role_of(cls), _kn(kb, b["n"]), _kn(ka, a.get("n", 0)), xb, xa, eb, ea, cb, ca,
                        "".join("; " + x for x in state)))
    fa, fb = base["false_flags"], now["false_flags"]
    for name in ("clean", "twin", "unplanted rows"):
        if fb[name] > fa.get(name, 0):
            falls.append("false flags rose on %s (%d to %d)" % (name, fa.get(name, 0), fb[name]))
    for name, v in sorted(fb["respelled"].items()):
        old = fa.get("respelled", {}).get(name, 0)
        if v > old:
            falls.append("false flags rose on respelled %s (%d to %d)" % (name, old, v))
    lines.append("  false flags: clean %d (batch %d), twin %d (batch %d), respelled %d (batch %d), unplanted rows %d "
                 "(batch %d)" % (fb["clean"], fa.get("clean", 0), fb["twin"], fa.get("twin", 0),
                                 sum(fb["respelled"].values()), sum(fa.get("respelled", {}).values()),
                                 fb["unplanted rows"], fa.get("unplanted rows", 0)))
    ta, tb = base.get("twin"), now["twin"]
    lacks = tb["claims the key lacks"]
    if ta is None:
        lines.append("  twin under rules: %s rows the key expects listed with its code; %d claims the key lacks; the "
                     "batch records neither" % (_kn(tb["listed"], tb["drop rows"]), len(lacks)))
    else:
        if tb["listed"] < ta["listed"]:  # the twin's expected drops no longer listed with the key's code
            falls.append("twin rows the key expects listed with its code fell (%d to %d)"
                         % (ta["listed"], tb["listed"]))
        new = sorted(set(lacks) - set(ta["claims the key lacks"]))
        if new:  # claims the key lacks: a changed Id. chain, token or pairing in the twin
            falls.append("the twin gained claims the key lacks (%d to %d: %s)"
                         % (len(ta["claims the key lacks"]), len(lacks), ", ".join(new)))
        lines.append("  twin under rules: %s rows the key expects listed with its code (batch %s); %d claims the key "
                     "lacks (batch %d)" % (_kn(tb["listed"], tb["drop rows"]), _kn(ta["listed"], ta["drop rows"]),
                                           len(lacks), len(ta["claims the key lacks"])))
    ua, ub = base.get("untagged", {}), now["untagged"]
    if ub["caught"] < ua.get("caught", 0):
        falls.append("untagged coverage fell (%d to %d)" % (ua.get("caught", 0), ub["caught"]))
    if ub["expected"] < ua.get("expected", 0):
        falls.append("untagged expected code fell (%d to %d)" % (ua.get("expected", 0), ub["expected"]))
    lines.append("  untagged coverage %s (batch %s); expected code %d (batch %d)"
                 % (_kn(ub["caught"], ub["n"]), _kn(ua.get("caught", 0), ua.get("n", 0)), ub["expected"],
                    ua.get("expected", 0)))
    ra, rb = sum(base.get("routed", {}).values()), sum(now["routed"].values())
    if rb > ra:  # more planted changes that tie at the cite: errors the tool can no longer see
        falls.append("coincidental_figure routing rose (%d to %d)" % (ra, rb))
    la, lb = base.get("mis_association left out", 0), now["mis_association left out"]
    if lb > la:  # the same, for swaps in the twin where both figures still tie
        falls.append("mis_association swaps left out rose (%d to %d)" % (la, lb))
    lines.append("  coincidental_figure routing %d (batch %d); mis_association swaps left out %d (batch %d)"
                 % (rb, ra, lb, la))
    lines.append("  replay batches: not replayed here; self-test scenario 20 replays the committed batch byte for byte")
    lines.append("regress: %s" % ("PASS" if not falls else "FAIL: " + "; ".join(falls)))
    return not falls, lines


# --- the proposer eval ----------------------------------------------------------------------------


def proposer_clients(grammar, date_order):
    """The proposers measure --proposer scores: rules first, the baseline, then each recorded
    batch in fixture/matter-1/replay/ through the replay adapter. Returns (name, client, the
    matter.json values the batch's requests were sent with)."""
    out = [("rules", providers.RulesClient(grammar.names(), date_order), {})]
    folder = os.path.join(MATTER_DIR, "replay")
    for name in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:
        first = os.path.join(folder, name, "sent", "0001-request.json")
        if os.path.isfile(first):
            body = _json(first)
            out.append(("replay %s, model %s" % (name, body["model"]),
                        providers.ReplayClient(os.path.join(folder, name)),
                        {"model": body["model"], "max_tokens": body["max_tokens"]}))
    return out


def _places(location, ctx):
    """What a location names, so a picked candidate can meet a hint label's true location: the
    Bates page ids it resolves to, (witness, page) for a transcript, (file, column, row) for a
    cell. A calc, or a location that does not resolve, names nothing."""
    cite, _ = claims.parse_cite(location, ctx.grammar)
    if cite is None:
        return set()
    if cite["type"] == "transcript":
        return {(cite["witness"].casefold(), cite["start"][0])}
    if cite["type"] == "cell":
        return {(cite["file"].casefold(), cite["col"], cite["row"])}
    try:
        return {label for label, _, _ in verify.locate(cite, ctx.index)["texts"]}
    except verify.Fail:
        return set()


def _score_spans(got, labels, claimed, by_value=False):
    """Spans at exact boundaries against the labels. Returns the label and proposal counts and
    three sets of label keys: hits; mis, the hits whose code pairing differs from the label's
    cite or whose claim a pre-check drops, as P7 drops one whose proposer gave another cite; and
    checked, the hits that are claims and not in mis, so they reach a record check with the
    label's cite. claimed maps each claim's (where, span) to whether a pre-check drops it; a
    rules words candidate is never a claim. A words span hits only at the label's value."""
    want = {(_where_of(lab), record.norm_text(lab["span"])): lab for lab in labels}
    hits = {k: t for k, t in got if k in want and (not by_value or words_py.same_value(want[k]["value"], t["reading"]))}
    mis = {k for k, t in hits.items() if claimed.get(k) or record.norm_text(t["pair"]["resolved"] if not
           t["pair"]["code"] else "").casefold() != record.norm_text(want[k]["cite"]).casefold()}
    return {"labels": len(want), "proposed": len(got), "hits": set(hits), "mis": mis,
            "checked": set(hits).intersection(claimed) - mis}


def proposer_eval(ctx):
    """Each proposer over the untagged twin, through the run's own proposer, claims, verifier and
    job 4, scored against the answer-key labels. Digits have no labels, so for them the scores keep
    digit_ties, the (where, start) of each figure or date claim from a digit token that ties.
    Returns (labels sha256, [(name, scores)])."""
    with open(os.path.join(MATTER_DIR, "key", "proposer-labels.json"), "rb") as fh:
        raw = fh.read()
    labels = json.loads(raw.decode("utf-8"))
    draft = claims.read_text_draft(ctx.twin)
    draft["type"] = "md"
    _, _, draft, grammar, analysis = ctx.tool.intake_checks(ctx.root, ctx.matter, None, False, index=ctx.index,
                                                            draft=draft)
    tokens = {(t["where"], t["start"]): t for t in analysis["values"] + analysis["words"]}
    digits = {(t["where"], t["start"], t["text"]) for t in analysis["values"] if t["kind"] in ("figure", "date")}
    out = []
    for name, client, sent_with in proposer_clients(grammar, ctx.matter["date_order"]):
        matter = dict(ctx.matter, **sent_with)
        try:
            accepted = ctx.tool.propose(client, providers.Recorder(None), matter, draft, analysis)[0]
        except providers.ReplayMiss:  # the batch was recorded from other inputs: re-record it
            out.append((name, None))
            continue
        built = claims.build_claims(draft, analysis, grammar, accepted)
        verdicts = verify.verify_all(built, ctx.index)
        claimed = {(c["where"], record.norm_text(c["span"])): bool(c["pre"]) for c in built}
        ties = {(c["where"], c["start"]) for c, v in zip(built, verdicts)
                if (c["where"], c["start"], c["span"]) in digits and v["code"] == "tie"}
        try:
            asked = ctx.tool.candidate_hints(client, providers.Recorder(None), matter, built, verdicts, ctx.index)[1]
        except providers.ReplayMiss:  # a batch recorded with candidate_snippets off holds no job 4 answer
            asked = None
        got = {}
        for a in accepted:
            t = tokens[(a["where"], a["start"])]
            got.setdefault(a["kind"], []).append(((a["where"], record.norm_text(t["text"])), t))
        flags = got.get("flag", [])
        not_claims = {(_where_of(lab), record.norm_text(lab["span"])) for lab in labels["not_a_claim"]}
        keys = {(c["where"], record.norm_text(c["span"])): c["key"] for c in built}
        items = {it["item"]: it for it in asked["items"]} if asked else {}
        hints = {"labels": len(labels["hints"]), "hits": 0, "among": 0, "recorded": asked is not None}
        for lab in labels["hints"]:
            it = items.get(keys.get((_where_of(lab), record.norm_text(lab["span"]))))
            true = _places(lab["true_location"], ctx)
            if it and true:
                hints["among"] += any(_places(loc, ctx) & true for loc in it["locations"])
                hints["hits"] += bool(it["choice"] and _places(it["locations"][it["choice"] - 1], ctx) & true)
        out.append((name, {"quotations": _score_spans(got.get("quote", []), labels["quotations"], claimed),
                           "words": _score_spans(got.get("words", []), labels["words"], claimed, by_value=True),
                           "digit_ties": ties,
                           "flags": {"labels": len(not_claims), "proposed": len(flags),
                                     "hits": sum(1 for k, _ in flags if k in not_claims)},
                           "hints": hints}))
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest(), out


def _ci(k, n):
    lo, hi = wilson(k, n)
    return "%s [%.2f, %.2f]" % (_kn(k, n), lo, hi) if n else _kn(k, n)


def turn_on(rules, model):
    """The turn-on rule set on 2026-10-28, for one model batch against rules on one matter. Rules
    covers figures and dates in digits and quotations in clean quote marks. Digits have no
    labels, so there the model must tie every claim rules ties. On the labelled quotations rules
    checks, the model's recall and mis-association are no worse than rules', and its precision
    over every quotation it proposes is no lower, since a false proposal belongs to no labelled
    class. On at least one class rules misses, it checks a labelled span rules leaves unchecked:
    the quotations rules misses are the labelled ones it leaves unchecked, and rules checks no
    number or date in words. Returns (met, the lines that print each term filled)."""
    m, r = model["quotations"], rules["quotations"]
    cover = r["checked"]
    hit, mis, rmis = m["hits"] & cover, m["mis"] & cover, r["mis"] & cover
    ties = len(model["digit_ties"] & rules["digit_ties"])
    rd = len(rules["digit_ties"])
    lines = ["  figures and dates in digits, which rules covers: ties %d of the %d claims rules ties, %s"
             % (ties, rd, "no worse" if ties == rd else "worse"),
             "  quotations in clean quote marks, which rules covers: the %d labelled quotations rules checks" % len(cover)]
    terms = [("recall", (len(hit), len(cover)), (len(cover), len(cover)), len(hit) == len(cover)),
             ("precision over every quotation proposed", (len(m["hits"]), m["proposed"]), (len(r["hits"]), r["proposed"]),
              len(m["hits"]) * r["proposed"] >= len(r["hits"]) * m["proposed"]),
             ("mis-association", (len(mis), len(hit)), (len(rmis), len(cover)),
              len(mis) * len(cover) <= len(rmis) * len(hit))]
    lines += ["    %s %s against rules' %s, %s" % (name, _kn(*a), _kn(*b), "no worse" if ok else "worse")
              for name, a, b, ok in terms]
    better = []
    for cls, what in (("quotations", "quotations without clean quote marks"), ("words", "numbers and dates in words")):
        more = len(model[cls]["checked"] - rules[cls]["checked"])
        left = rules[cls]["labels"] - len(rules[cls]["checked"])
        better.append(more > 0)
        lines.append("  %s, which rules misses: checks %d of the %d labelled spans rules leaves unchecked, %s"
                     % (what, more, left, "better" if more else "not better"))
    return ties == rd and all(ok for _, _, _, ok in terms) and any(better), lines


def proposer_report(labels_sha, scored):
    lines = ["measure --proposer: labels sha256 %s, code sha256 %s" % (labels_sha, gate.code_hash()),
             "matter 1's untagged twin against key/proposer-labels.json; each count is k of N with a Wilson 95% "
             "interval; a span counts at exact boundaries; rules is the baseline on every class it covers"]
    for name, s in scored:
        lines += ["", name + (" (the baseline)" if name == "rules" else "")]
        if s is None:
            lines.append("  replay miss: the batch's requests do not match this code's; record it again")
            continue
        for cls in ("quotations", "words"):
            c = s[cls]
            k = len(c["hits"])
            lines.append("  %-11s recall %s; precision %s; mis-association %s"
                         % (cls, _ci(k, c["labels"]), _ci(k, c["proposed"]), _kn(len(c["mis"]), k)))
        f, h = s["flags"], s["hints"]
        lines.append("  %-11s %s" % ("flags", "precision %s" % _ci(f["hits"], f["proposed"]) if f["proposed"] else
                                     "none proposed; %d tokens are labelled not a claim" % f["labels"]))
        lines.append("  %-11s true location picked %s; true location among code's candidates %s"
                     % ("hints", _ci(h["hits"], h["labels"]), _kn(h["among"], h["labels"])) if h["recorded"] else
                     "  %-11s not in this batch: it was recorded with candidate_snippets off" % "hints")
    lines += ["", "Rules lists every number or date in words that words.py reads as a candidate and checks none of them,",
              "so its words recall is what a model could add and its precision what listing them all costs.",
              "", "The turn-on rule, set 2026-10-28: a model turns on for a matter only when, on every class rules covers,",
              "it is no worse than rules on recall, precision and mis-association, and on at least one class rules",
              "misses it does better. Rules covers figures and dates in digits, and quotations in clean quote marks,",
              "whose marks code's tokeniser reads as one pair. Digits have no labels, so there a model must tie",
              "every claim rules ties. On quotations the terms are taken over the labelled ones rules checks, and",
              "precision over every quotation proposed. Rules misses quotations without clean quote marks, counted",
              "as the labelled quotations it leaves unchecked, and numbers and dates in words, which it lists and",
              "never checks. Doing better on one of those means checking a labelled span that rules leaves unchecked,",
              "as a claim that reaches a record check with the label's cite. The rule must hold on matter 1 and on",
              "matter 2, which arrives in stage 4."]
    base = dict(scored).get("rules")
    models = [(name, s) for name, s in scored if name != "rules"]
    for name, s in models:
        if s is None:
            lines += ["", "%s: not judged, since the batch is a replay miss" % name]
            continue
        met, terms = turn_on(base, s)
        lines += ["", "%s: the rule is %s" % (name, "met on matter 1; matter 2 is not measured yet, so the model stays off"
                                             if met else "not met on matter 1, so the model stays off")] + terms
    if not models:
        lines += ["", "No recorded batch is in fixture/matter-1/replay/, so no model is judged."]
    return "\n".join(lines) + "\n"


def run(args, tool):
    """tieout measure: returns the exit code. tool is the tieout module, which supplies the run's
    own intake and checks, so a planted item meets the path tieout run takes."""
    if getattr(args, "proposer", False):
        if args.cls or args.freeze or args.declare or args.regress:
            print("tieout measure: give --proposer alone", file=sys.stderr)
            return 2
        try:
            sys.stdout.write(proposer_report(*proposer_eval(Context(tool))))
            return 0
        except Refused as exc:
            print("tieout measure: %s" % exc, file=sys.stderr)
            return 2
    if args.cls and args.cls not in CLASSES:
        print("tieout measure: no class %r; the classes are %s" % (args.cls, ", ".join(CLASSES)), file=sys.stderr)
        return 2
    flags = [f for f in ("freeze", "declare", "regress") if getattr(args, f)]
    if len(flags) > 1 or (flags and args.cls):
        print("tieout measure: give at most one of --freeze, --declare, --regress, and --class alone", file=sys.stderr)
        return 2
    try:
        ctx = Context(tool)
        if args.freeze:
            return do_freeze(ctx)
        if args.declare:
            return do_declare(ctx, args.date)
        if args.regress:
            return do_regress(ctx)
        m = measure_all(ctx, args.cls)
        sys.stdout.write(report(m))
        return 0
    except Refused as exc:
        print("tieout measure: %s" % exc, file=sys.stderr)
        return 2
    except gate.GateRefused as exc:
        print("tieout measure: refused, %s" % exc, file=sys.stderr)
        return 3


def _frozen_now(ctx):
    """(FROZEN.json as it would be now, every planted item unscored in results order, the
    off-headline counts)."""
    corpus, _, untagged, (pairs, _), whole = whole_corpus(ctx)
    plan = [dict(i, caught=False, escaped=False, expected=False, collateral=0) for i in corpus.items]
    plan += [pair_row(p) for p in pairs]
    return frozen_doc(whole), plan, {"untagged coverage": len(untagged)}


def do_freeze(ctx):
    doc, _, _ = _frozen_now(ctx)
    path = os.path.join(HERE, FROZEN)
    old = _json(path) if os.path.isfile(path) else None
    diff = changed(old, doc) if old else ["no FROZEN.json yet"]
    gate.write(FROZEN, _dumps(doc), create=old is None, scope="measure")
    print("wrote tieout/FROZEN.json: corpus sha256 %s, code sha256 %s" % (doc["corpus_sha256"], doc["code_sha256"]))
    print("changed: %s" % ("; ".join(diff) if diff else "nothing"))
    print("review it and commit it before declaring a batch")
    return 0


def do_declare(ctx, date):
    date = date or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    try:
        datetime.date.fromisoformat(date)
    except ValueError:
        raise Refused("--date must be YYYY-MM-DD")
    path = os.path.join(HERE, FROZEN)
    if not os.path.isfile(path):
        raise Refused("no FROZEN.json; run measure --freeze and commit it first")
    with open(path, "rb") as fh:
        frozen_bytes = fh.read()
    now, items, off = _frozen_now(ctx)
    stale = changed(json.loads(frozen_bytes.decode("utf-8")), now)
    if stale:
        raise Refused("files changed since the freeze (%s); review, freeze again and commit" % "; ".join(stale))
    batch = next_batch_id(date)
    plan = {"results": items, "corpus_sha256": now["corpus_sha256"], "code_sha256": gate.code_hash()}
    decl = declaration(plan, batch, date, frozen_bytes, off)
    decl_bytes = _dumps(decl)
    gate.write("%s/%s.json" % (BATCHES, batch), decl_bytes, create=True, scope="measure")
    print("declared batch %s before any item was scored: %d items in %d classes"
          % (batch, len(items), len(CLASSES)))
    print("bars, each k of N on the Wilson lower bound:")
    print("\n".join(bar_lines(decl)))
    m = measure_all(ctx)
    printout = report(m)
    if m["corpus_sha256"] != decl["corpus_sha256"]:
        raise Refused("the scored corpus differs from the declared one; nothing more was written")
    res = results_doc(m, batch, hashlib.sha256(decl_bytes).hexdigest(), printout)
    gate.write("%s/%s-results.json" % (BATCHES, batch), _dumps(res), create=True, scope="measure")
    print("")
    sys.stdout.write(printout)
    print("wrote tieout/batches/%s.json and %s-results.json; commit both" % (batch, batch))
    return 0


def do_regress(ctx):
    ids = [b for b in _batch_ids() if os.path.isfile(os.path.join(HERE, BATCHES, b + "-results.json"))]
    if not ids:
        raise Refused("no declared batch with results in tieout/batches/; run measure --freeze, then measure --declare")
    base = _json(os.path.join(HERE, BATCHES, ids[-1] + "-results.json"))
    m = measure_all(ctx)
    ok, lines = regress(m, base)
    print("\n".join(lines))
    return 0 if ok else 1
