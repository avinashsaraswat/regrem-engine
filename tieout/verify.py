"""Pure verifier for the tie-out: one claim against the record index, checks V1 to V8.

Purpose: decide in code whether a figure, date or quotation in the draft ties to the record at
  its cite. The checks run in a fixed order: V1 (the cite parsed and any Id. resolved), V2 (the
  cite resolves to text in the index), V8 (a Bates pin lies inside its exhibit; a range runs
  forward and ends inside the file), then by kind V3 (figure, rounding rule), V4 (date, date
  rule), V5 (quotation, quotation rule), V6 (cell and calc) and V7 (two or more distinct source
  values match). A tie carries weak-tie flags, which put it in the spot-check sample.
Reads: nothing. It takes a claim dict (claims.py) and a record.Index; it opens no file, makes
  no network call and asks no model.
Writes: nothing.
Network: none.
Exit codes: none; a library module. Each verdict is {key, code, pass, reason, weak_flags, hint,
  hint_source}; code is "tie" or the failing code.
"""
import ast
import decimal
import json
import re

import record

D = decimal.Decimal
CTX = record.CTX

ORDER = ("V1", "V2", "V8", "V3", "V4", "V5", "V6", "V7")
CODES = {  # every code a verdict can carry, with the check that returns it
    "cite_unparsed": "V1", "id_no_antecedent": "V1", "location_missing": "V2", "pin_missing": "V2",
    "figure_not_found": "V3", "date_not_found": "V4", "misquote": "V5", "cell_mismatch": "V6",
    "calc_error": "V6", "calc_invalid": "V6", "ambiguous_tie": "V7",
    "exhibit_mismatch": "V8", "range_invalid": "V8",
    "no_cite": "A1", "ambiguous_association": "A2",
}


class Fail(Exception):
    """A check found the claim does not tie: code, reason and an optional code-search hint."""

    def __init__(self, code, reason, hint=""):
        Exception.__init__(self, reason)
        self.code, self.reason, self.hint = code, reason, hint


def guarded(f, *args):
    """Ported in shape from the author's earlier private code: a check that crashes fails closed, with
    the error as its reason, so a bug can never turn into a tie."""
    try:
        return f(*args)
    except Fail:
        raise
    except Exception as exc:  # noqa: BLE001 - any crash is the same failed verdict
        raise Fail("check_error", "the check could not run: %s: %s" % (type(exc).__name__, exc))


# --- locating the cited text: V2 and V8 ---------------------------------------------------------


def _pages_text(index, keys):
    out = []
    for prefix, number in keys:
        p = index.page(prefix, number)
        out.append((p["id"], p, p["thin"]))
    return out


def locate(cite, index):
    """The located text for a resolved cite, or raise Fail with a V2 or V8 code.

    Returns {"label", "texts": [(label, scan, thin)], "pins": set of ints, "cell": raw or None}."""
    t = cite["type"]
    if t == "exhibit":
        ex = index.exhibit(cite["label"])
        if ex is None:
            raise Fail("location_missing", "exhibit %s is not in exhibits.csv" % cite["label"])
        pin = cite.get("pin")
        if pin is None:
            if ex["last"] > ex["first"]:
                raise Fail("pin_missing", "%s runs %d pages and the cite gives no page"
                           % (ex["label"], ex["last"] - ex["first"] + 1),
                           "exhibit pages %s to %s" % (index.page_id(ex["prefix"], ex["first"], ex["width"]),
                                                      index.page_id(ex["prefix"], ex["last"], ex["width"])))
            keys = [(ex["prefix"], ex["first"])]
            return {"label": cite["text"], "texts": _pages_text(index, keys), "pins": set(), "cell": None}
        if "bates" in pin:
            k = record.bates_key(pin["bates"])
            if k is None or index.page(k[0], k[1]) is None:
                raise Fail("location_missing", "page %s is not in the record" % pin["bates"])
            if k[0] != ex["prefix"] or not ex["first"] <= k[1] <= ex["last"]:
                raise Fail("exhibit_mismatch", "page %s lies outside %s (%s to %s)"
                           % (pin["bates"], ex["label"], index.page_id(ex["prefix"], ex["first"], ex["width"]),
                              index.page_id(ex["prefix"], ex["last"], ex["width"])))
            return {"label": cite["text"], "texts": _pages_text(index, [(k[0], k[1])]), "pins": set(), "cell": None}
        a, b = pin["pages"]
        n = ex["last"] - ex["first"] + 1
        for page in (a, b):
            if page < 1 or page > n:
                raise Fail("location_missing", "%s has %d pages; the cite asks for page %d" % (ex["label"], n, page))
        keys = [(ex["prefix"], ex["first"] + p - 1) for p in range(min(a, b), max(a, b) + 1)]
        for k in keys:
            if index.page(*k) is None:
                raise Fail("location_missing", "page %s of %s is not in the record"
                           % (index.page_id(k[0], k[1], ex["width"]), ex["label"]))
        if b < a:
            raise Fail("range_invalid", "page range %d-%d runs backward" % (a, b))
        texts = _pages_text(index, keys)
        label = "%s (%s)" % (cite["text"], ", ".join(x[0] for x in texts))
        return {"label": label, "texts": texts, "pins": set(range(a, b + 1)), "cell": None}

    if t == "bates":
        s = record.bates_key(cite["start"])
        if s is None or index.page(s[0], s[1]) is None:
            raise Fail("location_missing", "page %s is not in the record" % cite["start"])
        if not cite.get("end"):
            return {"label": cite["text"], "texts": _pages_text(index, [(s[0], s[1])]), "pins": set(), "cell": None}
        e = record.bates_key(cite["end"])
        if e is None or index.page(e[0], e[1]) is None:
            raise Fail("location_missing", "page %s is not in the record" % cite["end"])
        if e[0] != s[0] or e[1] < s[1]:
            raise Fail("range_invalid", "Bates range %s runs backward" % cite["text"])
        keys = [(s[0], n) for n in range(s[1], e[1] + 1)]
        for k in keys:
            if index.page(*k) is None:
                raise Fail("location_missing", "page %s%s in the range is not in the record"
                           % (k[0], str(k[1]).zfill(len(s[2]))))
        return {"label": cite["text"], "texts": _pages_text(index, keys), "pins": set(), "cell": None}

    if t == "transcript":
        tr = index.transcript(cite["witness"])
        if tr is None:
            raise Fail("location_missing", "no transcript for %s" % cite["witness"])
        p1, l1 = cite["start"]
        if l1 is None:
            if p1 not in tr["pages"]:
                raise Fail("location_missing", "%s has no page %d" % (cite["witness"], p1))
        elif (p1, l1) not in tr["lines"]:
            raise Fail("location_missing", "%s has no line %d:%d" % (cite["witness"], p1, l1))
        lo = (p1, l1 if l1 is not None else 0)
        hi = (p1, l1 if l1 is not None else 10 ** 9)
        if cite.get("end"):
            p2, l2 = cite["end"]
            hi = (p2, l2 if l2 is not None else 10 ** 9)
            ends_inside = (p2, l2) in tr["lines"] if l2 is not None else p2 in tr["pages"]
            if hi < lo:
                raise Fail("range_invalid", "transcript range %s runs backward" % cite["text"])
            if not ends_inside:
                raise Fail("range_invalid", "transcript range %s ends outside %s" % (cite["text"], tr["file"]))
        keys = [k for k in tr["order"] if lo <= k <= hi]
        text = "\n".join(tr["lines"][k] for k in keys)
        pins = set()
        for p, ln in keys:
            pins.update((p, ln))
        return {"label": cite["text"], "texts": [(cite["text"], record.scan(text, index.date_order), False)], "pins": pins,
                "cell": None}

    if t == "cell":
        name, rows = index.data_file(cite["file"])
        if rows is None:
            raise Fail("location_missing", "data file %s is not in record/data/" % cite["file"])
        if cite.get("sheet"):
            raise Fail("location_missing", "sheet names apply to .xlsx files, which are read from stage 4")
        r, c = cite["row"], record.column_index(cite["col"])
        if r < 1 or r > len(rows) or c >= len(rows[r - 1]):
            raise Fail("location_missing", "%s has no cell %s%d" % (name, cite["col"], r))
        return {"label": cite["text"], "texts": [], "pins": set(), "cell": rows[r - 1][c]}

    raise Fail("cite_unparsed", "cite form %r cannot be located" % t)


# --- the three rules ----------------------------------------------------------------------------


def _fig_text(fig):
    return fig["raw"].strip()


def _nearest(fig, figures, n=3):
    target = CTX.multiply(fig["mantissa"], fig["scale"])
    seen, out = set(), []
    for s in sorted(figures, key=lambda s: (abs(abs(s["value"]) - target), s["start"])):
        raw = s["raw"].strip()
        same = (record.norm_figure(raw.strip("()").split()[0]), s["pct"])
        if same not in seen:
            seen.add(same)
            out.append(raw)
        if len(out) == n:
            break
    return out


def check_figure(fig, located, flags):
    """V3 and V7 for one figure against the located pages or lines."""
    matches, everything = [], []
    for label, scanned, thin in located["texts"]:
        for s in scanned["figures"]:
            everything.append(s)
            if s["pct"] == fig["pct"] and record.rounds_to(s["value"], fig):
                matches.append((label, s, thin))
    if not matches:
        near = _nearest(fig, everything)
        raise Fail("figure_not_found", "%s is not on %s under the rounding rule" % (_fig_text(fig), located["label"]),
                   ("nearest values on the page: " + "; ".join(near)) if near else "no figure on the page")
    distinct = sorted({abs(s["value"]) for _, s, _ in matches})
    if len(distinct) >= 2:
        raise Fail("ambiguous_tie", "%s matches %d distinct values on %s: %s"
                   % (_fig_text(fig), len(distinct), located["label"],
                      "; ".join(s["raw"].strip() for _, s, _ in matches)))
    _figure_flags(fig, [s for _, s, _ in matches], located, flags)
    if any(thin for _, _, thin in matches):
        flags.add("thin_page")


def _figure_flags(fig, matches, located, flags):
    if len(matches) >= 2:
        flags.add("repeated")
    if record.significant_digits(fig) <= 2:
        flags.add("low_precision")
    if fig["places"] == 0 and not fig["scaled"] and int(fig["mantissa"]) in located["pins"]:
        flags.add("equals_page_or_line")
    exact = CTX.multiply(fig["mantissa"], fig["scale"])
    if any(abs(s["value"]) != exact for s in matches) or fig["scaled"] and any(not s["scaled"] for s in matches):
        flags.add("rounded")


def check_date(claimed, raw, located, flags):
    """V4 and V7 for one date."""
    hits, everything = [], []
    for label, scanned, thin in located["texts"]:
        for d in scanned["dates"]:
            everything.append(d["raw"])
            tying = frozenset(v for v in d["values"] if record.date_ties(claimed, v))
            if tying:
                hits.append((tying, thin))
    if not hits:
        raise Fail("date_not_found", "%s is not on %s at the precision written" % (raw, located["label"]),
                   ("dates on the page: " + "; ".join(dict.fromkeys(everything))) if everything else "no date on the page")
    distinct = sorted({h for h, _ in hits}, key=lambda s: sorted(record.show_date(v) for v in s))
    if len(distinct) >= 2:
        raise Fail("ambiguous_tie", "%s matches %d distinct dates on %s: %s"
                   % (raw, len(distinct), located["label"],
                      "; ".join("/".join(sorted(record.show_date(v) for v in s)) for s in distinct)))
    if len(hits) >= 2:
        flags.add("repeated")
    if any(thin for _, thin in hits):
        flags.add("thin_page")


BRACKET_OR_ELLIPSIS = re.compile(r"(\[[^\]]*\]|\.(?:\s?\.){2})")


def quote_segments(quote, marks=True):
    """Quotation rule: normalise, drop the outer quote marks, split at every bracketed alteration
    and every ellipsis, drop the bracket contents. Returns [(segment, after_bracket,
    before_bracket)] with empty segments removed."""
    t = record.norm_text(quote)
    if marks and len(t) >= 2 and t[0] == '"' and t[-1] == '"':
        t = t[1:-1]
    t = t.strip()
    if t.endswith((",", ".")) and not t.endswith("..."):
        t = t[:-1]  # punctuation set inside the closing mark by style, not quoted
    parts = BRACKET_OR_ELLIPSIS.split(t)
    out = []
    for i in range(0, len(parts), 2):
        seg = parts[i].strip()
        before = parts[i - 1] if i > 0 else ""
        after = parts[i + 1] if i + 1 < len(parts) else ""
        if seg:
            # a bracket lifts the word boundary only where it touches the segment: "[T]he" but not
            # "the [Company] agreed", whose "agreed" must not match inside "disagreed"
            out.append((seg, before.startswith("[") and not parts[i][:1].isspace(),
                        after.startswith("[") and not parts[i][-1:].isspace()))
    return out


def _broken_word(word):
    """A quoted word's pattern on a page with marked line-end hyphens: the mark may sit between any
    two of its characters, and a hyphen in the word may be the one the line ended on."""
    mark = record.HYPHEN_BREAK
    return (mark + "?").join("[-" + mark + "]" if ch == "-" else re.escape(ch) for ch in word)


def _segment_rx(seg, after_bracket, before_bracket, breaks=False):
    words = seg.split(" ")
    spell = _broken_word if breaks else re.escape
    first = spell(words[0])
    if after_bracket:
        first = "(?i:" + first + ")"  # case-insensitive for the first word after a bracket
    body = first + "".join(r"\s+" + spell(w) for w in words[1:])
    mark = record.HYPHEN_BREAK if breaks else ""
    left = "" if after_bracket else r"(?<![\w" + mark + "])"
    right = "" if before_bracket or not seg[-1:].isalnum() else r"(?![\w" + mark + "])"
    return re.compile(left + body + right)


def _first_missing(segments, text, breaks=False):
    """The first segment not on text after the segment before it, or None when all are there."""
    pos = 0
    for seg, after_b, before_b in segments:
        m = _segment_rx(seg, after_b, before_b, breaks).search(text, pos)
        if m is None:
            return seg
        pos = m.end()
    return None


def check_quote(span, located, flags, marks=True):
    """V5: every segment in order on the located text."""
    if located["cell"] is not None:
        text = record.norm_text(located["cell"])
    else:
        text = record.norm_text("\n".join(s["norm"] for _, s, _ in located["texts"]))
    segments = quote_segments(span, marks)
    if not segments:
        raise Fail("misquote", "the quotation holds no words to find")
    missing = _first_missing(segments, text)
    if missing is not None and located["cell"] is None:
        marked = record.norm_text("\n".join(record.mark_hyphen_breaks(s["text"]) for _, s, _ in located["texts"]))
        if record.HYPHEN_BREAK in marked and _first_missing(segments, marked, breaks=True) is None:
            missing = None
            flags.add("line_end_hyphen")
    if missing is not None:
        raise Fail("misquote", 'segment "%s" is not on %s after the segment before it' % (missing, located["label"]),
                   _closest(missing, text))
    if any(len(seg.split()) < 3 for seg, _, _ in segments):
        flags.add("short_segment")
    if any(thin for _, _, thin in located["texts"]):
        flags.add("thin_page")


def _closest(seg, text):
    words = seg.split(" ")
    for k in range(len(words) - 1, 2, -1):
        rx = re.compile(r"\s+".join(re.escape(w) for w in words[:k]), re.I)
        m = rx.search(text)
        if m:
            return 'the page reads: "%s"' % text[m.start():m.start() + len(seg) + 20].strip()
    return ""


# --- cells and calcs: V6 ------------------------------------------------------------------------


def _safe_eval(expr, env):
    """Ported from fsi verify.py: evaluate + - * / and parens over named values. Nothing else.
    The tie-out passes Decimal values so the rounding rule sees exact arithmetic."""
    node = ast.parse(expr, mode="eval")

    def walk(n):
        if isinstance(n, ast.Expression):
            return walk(n.body)
        if isinstance(n, ast.BinOp) and isinstance(n.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
            left, right = walk(n.left), walk(n.right)
            return {ast.Add: CTX.add, ast.Sub: CTX.subtract,
                    ast.Mult: CTX.multiply, ast.Div: CTX.divide}[type(n.op)](left, right)
        if isinstance(n, ast.UnaryOp) and isinstance(n.op, ast.USub):
            return -walk(n.operand)
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
            return D(str(n.value))
        if isinstance(n, ast.Name):
            if n.id not in env:
                raise KeyError("unknown name %r" % n.id)
            return env[n.id]
        raise ValueError("disallowed node %s" % type(n).__name__)

    return walk(node)


def evaluate_calc(calc, index):
    """The value of a calc tag over cells, or raise Fail (location_missing or calc_invalid)."""
    expr, env = calc["expr"], {}
    for i, cell in sorted(enumerate(calc["cells"]), key=lambda x: -x[1]["start"]):
        located = locate(cell, index)
        num = record.cell_number(located["cell"])
        if num is None:
            raise Fail("calc_invalid", "cell %s holds %r, not a number" % (cell["text"], located["cell"]))
        name = "c%d" % i
        env[name] = num[0]
        expr = expr[:cell["start"]] + name + expr[cell["end"]:]
    try:
        return _safe_eval(expr, env)
    except (SyntaxError, ValueError, KeyError, ArithmeticError, TypeError) as exc:
        raise Fail("calc_invalid", "calc %r does not evaluate: %s" % (calc["expr"], exc))


def check_cell(claim, located, flags, order):
    """V6 for a cited cell: a figure under the rounding rule, a date read in the matter's date
    order, a quotation under the quotation rule."""
    raw = located["cell"]
    if claim["kind"] == "figure":
        num = record.cell_number(raw)
        for fig in claim["figures"]:
            if num is None:
                raise Fail("cell_mismatch", "cell %s holds %r, not a number" % (claim["cite"]["text"], raw))
            if not record.cell_ties(num, fig):
                raise Fail("cell_mismatch", "%s does not round to the stored value of %s"
                           % (_fig_text(fig), claim["cite"]["text"]), "stored value %s" % raw.strip())
            _cell_flags(fig, num[0], flags)
    elif claim["kind"] == "date":
        found = [v for m in record.DATE.finditer(raw) for v in record.date_values(m, order)]
        if not any(record.date_ties(claim["date"], v) for v in found):
            raise Fail("cell_mismatch", "%s does not match cell %s" % (claim["span"], claim["cite"]["text"]),
                       "stored value %s" % raw.strip())
    else:
        check_quote(claim["span"], located, flags, claim["kind"] == "quotation")


def _show(value):
    """A calc result for a hint: at most six decimal places, trailing zeros dropped."""
    q = value.quantize(D("0.000001"), rounding=decimal.ROUND_HALF_UP, context=CTX)
    return format(q.normalize(), "f")


def _cell_flags(fig, value, flags):
    if record.significant_digits(fig) <= 2:
        flags.add("low_precision")
    exact = CTX.multiply(fig["mantissa"], fig["scale"])
    if abs(value) != exact and abs(CTX.multiply(value, D(100))) != exact:
        flags.add("rounded")


def check_calc(claim, index, flags):
    value = evaluate_calc(claim["calc"], index)
    for fig in claim["figures"]:
        if not record.cell_ties((value, False), fig):
            raise Fail("calc_error", "%s does not round to the calc result" % _fig_text(fig),
                       "calc %s gives %s" % (claim["calc"]["expr"], _show(value)))
        _cell_flags(fig, value, flags)


# --- one claim ----------------------------------------------------------------------------------


def _verify(claim, index, flags):
    pre = claim.get("pre")
    if pre:
        raise Fail(pre["code"], pre["reason"], pre.get("hint", ""))
    cite = claim.get("cite")
    if cite is None and not claim.get("calc"):
        raise Fail("cite_unparsed", "the claim has no cite")
    if claim["kind"] == "figure" and not claim.get("figures"):
        raise Fail("figure_not_found", "no figure in %r" % claim["span"])
    if cite is not None:
        located = guarded(locate, cite, index)
        if located["cell"] is not None:
            guarded(check_cell, claim, located, flags, index.date_order)
        elif claim["kind"] == "figure":
            for fig in claim["figures"]:
                guarded(check_figure, fig, located, flags)
        elif claim["kind"] == "date":
            guarded(check_date, claim["date"], claim["span"], located, flags)
        else:
            guarded(check_quote, claim["span"], located, flags, claim["kind"] == "quotation")
    if claim.get("calc"):
        if claim["kind"] != "figure":
            raise Fail("calc_invalid", "a calc tag applies to a figure only")
        guarded(check_calc, claim, index, flags)


def verify_claim(claim, index):
    """The verdict for one claim."""
    flags = set()
    try:
        _verify(claim, index, flags)
    except Fail as f:
        return {"key": claim["key"], "code": f.code, "pass": False, "reason": f.reason, "weak_flags": [],
                "hint": f.hint, "hint_source": "code" if f.hint else ""}
    if claim.get("proposed_by") in ("rules", "model"):
        flags.add("proposed")
    return {"key": claim["key"], "code": "tie", "pass": True, "reason": "", "weak_flags": sorted(flags),
            "hint": "", "hint_source": ""}


def search(claim, index, limit=3):
    """Up to limit places the record holds the claim's value: a code search for the figure, the
    date or the longest segment of the quotation. The hints use it, and job 4's candidates."""
    if claim["kind"] == "figure" and claim.get("figures"):
        return index.find_figure(claim["figures"][0], limit)
    if claim["kind"] == "date" and claim.get("date"):
        return index.find_date(claim["date"], limit)
    if claim["kind"] in ("quotation", "text"):
        segs = quote_segments(claim["span"], claim["kind"] == "quotation")
        if segs:
            return index.find_text(max(segs, key=lambda s: len(s[0]))[0], limit)
    return []


def hint_for(claim, verdict, index):
    """A code-search hint for an item with no usable cite: where the value or date appears in the
    record. It never changes the verdict."""
    if verdict["code"] == "misquote":
        found = index.find_text(claim["span"])
        if found:
            verdict = dict(verdict)
            verdict["hint"] = ((verdict["hint"] + "; ") if verdict["hint"] else "") + \
                "its words appear at " + "; ".join(found)
            verdict["hint_source"] = "code"
        return verdict
    if verdict["hint"] or verdict["code"] not in ("no_cite", "ambiguous_association", "id_no_antecedent"):
        return verdict
    found = search(claim, index)
    extra = verdict["hint"]
    if found:
        verdict = dict(verdict)
        verdict["hint"] = ((extra + "; ") if extra else "") + "the record holds it at " + "; ".join(found)
        verdict["hint_source"] = "code"
    return verdict


def verify_all(claims, index):
    """Verdicts for every claim, in claim order, each with its code-search hint."""
    return [hint_for(c, verify_claim(c, index), index) for c in claims]


# --- the verdicts document ----------------------------------------------------------------------


def claim_row(claim, verdict):
    """One claim and its verdict as the run's files show them."""
    kind, n = claim["where"]
    row = {"key": claim["key"], "para": n if kind == "para" else None, "footnote": n if kind == "foot" else None,
           "sentence": claim["sentence"], "kind": claim["kind"], "span": claim["span"],
           "cite_text": claim["cite_text"], "cite_resolved": claim["cite_resolved"],
           "proposed_by": claim["proposed_by"], "pairing": claim["pairing"], "code": verdict["code"],
           "pass": verdict["pass"], "reason": verdict["reason"], "weak_flags": verdict["weak_flags"],
           "hint": verdict["hint"], "hint_source": claim.get("hint_source") if verdict["hint"] and
           claim.get("hint_source") else verdict["hint_source"]}
    if claim.get("flag"):  # a model's not-a-claim flag (P9): a hint only; the verdict stands
        note = "the proposer flags it as not a claim: " + claim["flag"]
        row["hint_source"] = (row["hint_source"] + ", " if row["hint"] else "") + "model-flag"
        row["hint"] = (row["hint"] + "; " if row["hint"] else "") + note
    return row


def document(claims, verdicts, not_checked):
    """verdicts.json as bytes: deterministic, with no time or run id, so sign can re-perform the
    run and compare byte for byte (S5)."""
    rows = [claim_row(c, v) for c, v in zip(claims, verdicts)]
    counts = {}
    for r in rows:
        counts[r["code"]] = counts.get(r["code"], 0) + 1
    nc = [{"para": n["where"][1] if n["where"][0] == "para" else None,
           "footnote": n["where"][1] if n["where"][0] == "foot" else None,
           "sentence": n["sentence"], "span": n["span"], "reason": n["reason"]} for n in not_checked]
    doc = {"schema": 1, "counts": dict(sorted(counts.items())), "claims": rows, "not_checked": nc}
    return (json.dumps(doc, indent=1, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
