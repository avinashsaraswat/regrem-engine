"""Claims for the tie-out: draft readers, tags, the reads-as text, tokens, pairing and proposals.

Purpose: turn a draft into the list of claims the verifier checks. It reads a .md or .txt draft
  (a .docx goes through docx_reader.py into the same block form), parses inline tags
  {{text | cite}}, builds the reads-as text (the draft with each tag replaced by its words),
  splits sentences, and lists every untagged figure, date, quotation and cite token, and as not
  checked every bare year, cross-reference, heading number, list number, docket number, clock
  time, two-digit-year slash date and digit run no token reads, each with its reason. It pairs
  each untagged value with a cite by the fixed rules A1 to A4, resolves Id. chains (A3), checks
  every proposal against P1 to P9, and gives each claim its key, c- plus six hex characters of
  sha256 over the normalised span, cite and sentence. Every number or date written in words that
  words.py reads is a words phrase with code's pairing (stage 3). The rules proposer lists each
  one as a candidate, which the drop log shows and nothing checks; a model's words proposal that
  passes P1 to P9 becomes a claim, checked like a figure or date in digits. A model's flag (P9)
  puts a hint on the token it names and never changes the claim set.
Reads: the draft file it is given. Nothing else; the record arrives as names only (the cite
  grammar's labels, prefixes, witnesses and data files).
Writes: nothing.
Network: none.
Exit codes: none; a library module. Reader problems are returned as intake rows (I7).
"""
import hashlib
import json
import os
import re

import record
import words

VALUE_KINDS = ("figure", "date", "quotation")
NOT_CHECKED = {"year": "bare year", "xref": "cross-reference", "heading_number": "heading number",
               "unread": "unread number form"}
NOT_CHECKED.update(record.NOT_FIGURE_REASONS)  # docket number, clock time, two-digit-year date
LIST_NUMBER = "list number"  # the reason on a numbered list item's marker, kept apart from the text
PROPOSAL_KINDS = {"figure": "figure", "date": "date", "quote": "quotation"}  # a proposal kind: the token kind it names
FLAG_REASONS = ("cross_reference", "page_or_section_number", "count_in_prose", "date_of_report", "scare_quote",
                "label")  # P9: the reasons a flag may give
P1_KEYS = {"para", "span", "cite", "kind"}
FENCE = re.compile(r"```[ \t]*(?:[\w.+-]+[ \t]*)?\r?\n(.*)\r?\n```", re.S)  # P1: one code fence round a whole reply
ABBREV = ("Dep.", "Tr.", "Ex.", "Exh.", "Id.", "No.", "Nos.", "Inc.", "Corp.", "Ltd.", "Co.", "v.",
          "e.g.", "i.e.", "Mr.", "Ms.", "Dr.", "Jan.", "Feb.", "Mar.", "Apr.", "Jun.", "Jul.", "Aug.",
          "Sep.", "Sept.", "Oct.", "Nov.", "Dec.", "Fig.", "Tbl.", "Sec.", "approx.")

TAG = re.compile(r"\{\{(.*?)\}\}", re.S)
FOOTDEF = re.compile(r"^\[\^(\d+)\]:\s*")
FOOTREF = re.compile(r"\[\^(\d+)\]")
LIST_MARK = re.compile(r"^(?:\d+\.|[-*])\s+")
HEADING_NUMBER = re.compile(r"^\s*\d+(?:\.\d+)*\.?(?=\s)")
XREF = re.compile(r"(?<![\w.])(?:(?i:sections?|sec\.|paragraphs?|tables?|tbl\.|figures?|fig\.|pages?|footnotes?)"
                  r"|\u00b6\u00b6?|n\.)\s*\d+(?:\.\d+)*[a-z]?(?:\s*(?:-|\u2013|to|and)\s*\d+(?:\.\d+)*[a-z]?)?(?![\w%])")
RANGE_JOIN = re.compile(r"\s+to\s+|\s*[-\u2013]\s*")  # between the two ends of a range: to, a hyphen or an en dash
DIGIT_RUN = re.compile(r"\d+(?:[.,]\d+)*")  # any run of digits, for the catch-all in tokenise()


def norm(s):
    """Key normalisation: NFKC, curly quotes to straight, dashes to hyphens, whitespace runs to
    one space, stripped."""
    return record.norm_text(s)


def claim_key(span, cite, sentence):
    raw = norm(span) + "\n" + norm(cite).casefold() + "\n" + norm(sentence)
    return "c-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:6]


def where_label(where):
    kind, n = where
    return str(n) if kind == "para" else "fn%d" % n


def parse_where(label):
    """A proposal's para value: an integer paragraph or "fnN" for footnote N; None if neither."""
    if isinstance(label, bool):
        return None
    if isinstance(label, int):
        return ("para", label)
    if isinstance(label, str):
        m = re.fullmatch(r"\s*(?:fn|\^)(\d+)\s*", label)
        if m:
            return ("foot", int(m.group(1)))
        if label.strip().isdigit():
            return ("para", int(label.strip()))
    return None


# --- sentences ----------------------------------------------------------------------------------


CLOSERS = "\"\u201d\u2019')]"  # closing quote marks, parenthesis and bracket that may follow the mark
SENTENCE_END = re.compile(r"[.?!][\"\u201d\u2019')\]]*(?= [A-Z\"\u201c\u2018'])")


def sentences(text):
    """Split on . ? ! followed by a space and a capital letter or an opening quote mark, except
    after an abbreviation the splitter lists or a single capital initial. Closing quote marks and
    a closing parenthesis may sit between the mark and the space, so 'the reason." The next' and
    '(PX-1 at 3.) The next' each end a sentence; a run ending '.)' ends one even after Id., the
    one abbreviation that often closes a citation parenthetical. An opening parenthesis does not
    start a sentence, so a citation sentence, '... per unit. (PX-1 at 3.)', stays with the
    sentence it supports. Returns [(start, end)] with the end after the mark and its closers."""
    out, start = [], 0
    for m in SENTENCE_END.finditer(text):
        head = text[start:m.end()].split()
        tail = head[-1] if head else ""
        core = tail.rstrip(CLOSERS)
        last = core.lstrip("(\"'\u201c\u2018[")
        if ")" not in tail[len(core):] and (last in ABBREV or re.search(r"(?:^|\.)[A-Z]\.$", last)):
            continue
        out.append((start, m.end()))
        start = m.end() + 1
    if start < len(text) or not out:
        out.append((start, len(text)))
    return out


def block_sentences(text, block_quote=False):
    """The sentences of one block. A block quote is one quotation token, so it is one sentence:
    the quotation and the cite on its last line, or in a footnote it carries, pair within it."""
    return [(0, len(text))] if block_quote else sentences(text)


def sentence_of(block, offset):
    for i, (a, b) in enumerate(block["sentences"], 1):
        if a <= offset <= b:
            return i, block["text"][a:b]
    a, b = block["sentences"][-1]
    return len(block["sentences"]), block["text"][a:b]


# --- readers ------------------------------------------------------------------------------------


def _parse_tag(body):
    """Parts of one inline tag: (text, cite, calc, skip, problem)."""
    parts = [p.strip() for p in body.split("|")]
    text = body.split("|")[0].strip()
    cite, calc, skip, problem = "", "", False, ""
    for p in parts[1:]:
        if p == "skip":
            skip = True
        elif p.startswith("calc:"):
            calc = p[5:].strip()
        elif p:
            if cite:
                problem = "tag holds two cites"
            cite = p
    if not text:
        problem = "tag holds no text"
    elif not (cite or calc or skip):
        problem = "tag holds no cite"
    return text, cite, calc, skip, problem


def make_block(kind, n, raw, heading=False, block_quote=False, errors=None, list_number=""):
    """One paragraph or footnote: reads-as text, tags with offsets, footnote reference offsets.
    list_number is the number a list marker the reader removed held ("3." for "3. "), or empty."""
    text, tags, refs, pos = [], [], [], 0
    rx = re.compile(r"\{\{(.*?)\}\}|\[\^(\d+)\]", re.S)
    for m in rx.finditer(raw):
        text.append(raw[pos:m.start()])
        start = sum(len(t) for t in text)
        if m.group(2) is not None:
            refs.append((start, int(m.group(2))))
        else:
            body = m.group(1)
            t, cite, calc, skip, problem = _parse_tag(body)
            text.append(t)
            tags.append({"start": start, "end": start + len(t), "text": t, "cite": cite, "calc": calc,
                         "skip": skip, "raw": m.group(0), "problem": problem})
        pos = m.end()
    text.append(raw[pos:])
    text = "".join(text)
    if errors is not None and ("{{" in text or "}}" in text):
        errors.append(("I7", (kind, n), "unclosed or stray tag braces"))
    block = {"kind": kind, "n": n, "where": (kind, n), "text": text, "heading": heading,
             "block_quote": block_quote, "tags": tags, "refs": refs, "list_number": list_number}
    block["sentences"] = block_sentences(text, block_quote)
    return block


def finish_block(kind, n, text, tags, refs, heading=False, block_quote=False, list_number=""):
    """A block built by another reader (docx_reader.py): the same shape make_block gives."""
    block = {"kind": kind, "n": n, "where": (kind, n), "text": text, "heading": heading,
             "block_quote": block_quote, "tags": tags, "refs": refs, "list_number": list_number}
    block["sentences"] = block_sentences(text, block_quote)
    return block


def strip_list_marker(text):
    """A list marker at the start of a paragraph is structure: (text without it, characters cut,
    the number it held). A bullet holds no number, so its number is empty."""
    m = LIST_MARK.match(text)
    if not m:
        return text, 0, ""
    marker = m.group(0).strip()
    return text[m.end():], m.end(), marker if marker[:1].isdigit() else ""


def read_text_draft(text):
    """Blocks of a .md or .txt draft. A paragraph is a block of non-blank lines; a block starting
    [^n]: is footnote n. Heading hashes, a list marker and footnote reference markers are
    structure, not text, since a .docx holds them as structure. A numbered list marker's number
    is kept on the block, so analyse() lists it as not checked."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text, _ = record.drop_marker(text)
    blocks, errors, cur, para = [], [], [], 0
    for line in text.split("\n") + [""]:
        if line.strip():
            cur.append(line)
            continue
        if not cur:
            continue
        raw = " ".join(cur)
        m = FOOTDEF.match(raw)
        if m:
            blocks.append(make_block("foot", int(m.group(1)), raw[m.end():], errors=errors))
        else:
            para += 1
            heading = raw.startswith("#")
            quote = raw.startswith(">")
            number = ""
            if heading:
                raw = raw.lstrip("#").strip()
            elif quote:
                raw = " ".join(re.sub(r"^>\s?", "", ln) for ln in cur)
            else:
                raw, _, number = strip_list_marker(raw)
            blocks.append(make_block("para", para, raw, heading, quote, errors=errors, list_number=number))
        cur = []
    return {"blocks": blocks, "errors": errors, "tracked": None}


def text_draft_file(path):
    """A .md or .txt draft's text as a run reads it: the raw bytes decoded as UTF-8 with a
    byte-order mark stripped and every line ending kept. measure.py reads matter 1's drafts
    through this function too, so its scorer sees the text tieout run sees."""
    with open(path, "rb") as fh:
        raw = fh.read()
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("%s: not UTF-8 text (%s at byte %d)" % (path, exc.reason, exc.start))


def read_draft(path, accept_tracked=False, served=False):
    """The draft at path as blocks. .md and .txt here; .docx through docx_reader.py."""
    ext = os.path.splitext(path)[1].lower()
    if ext in (".md", ".txt"):
        draft = read_text_draft(text_draft_file(path))
        draft["type"] = ext[1:]
        return draft
    if ext == ".docx":
        import docx_reader
        draft = docx_reader.read(path, accept_tracked=accept_tracked, served=served)
        draft["type"] = "docx"
        return draft
    raise ValueError("%s: the tool reads .md, .txt and .docx drafts" % path)


def reads_as_text(draft):
    """The numbered reads-as text, written to run/<id>/draft.txt."""
    lines = []
    for b in draft["blocks"]:
        lines.append(("[%d] " % b["n"] if b["kind"] == "para" else "[^%d] " % b["n"]) + b["text"])
    return "\n\n".join(lines) + "\n"


# --- cite grammar -------------------------------------------------------------------------------

BATES_ID = r"[A-Z]{1,8}[-_ ]?\d{4,10}"
CELL_RX = (r"(?<![\w.\-])(?P<cfile>[A-Za-z0-9_][A-Za-z0-9_.\-]*\.(?:csv|xlsx))!(?:(?P<csheet>[^!\s|()]+)!)?"
           r"(?P<ccol>[A-Z]{1,3})(?P<crow>\d+)(?!\w)")
CITE = re.compile(
    r"(?P<cell>" + CELL_RX + r")"
    r"|(?P<tr>(?<![\w.])(?P<wit>[A-Z][A-Za-z'\u2019\-]+)\s+(?P<tform>Dep\.|Tr\.|Depo\.)(?:\s+at)?\s+"
    r"(?P<tp1>\d+)(?::(?P<tl1>\d+))?(?:\s*-\s*(?:(?P<tp2>\d+):)?(?P<tl2>\d+))?(?![\w:]))"
    r"|(?P<id>(?<![\w.])[Ii]d\.(?:\s+at\s+(?P<idpin>" + BATES_ID + r"|\d+(?::\d+)?(?:\s*-\s*\d+(?::\d+)?)?))?)"
    r"|(?P<ex>(?<![\w.])(?:(?P<expre>Exhibit|Exh\.|Ex\.)\s*(?P<elab>[A-Z]{0,4}-?\d+[A-Z]?)|(?P<blab>[A-Z]{1,4}-\d{1,5}[A-Z]?))(?!\d)"
    r"(?:\s+at\s+(?P<epin>" + BATES_ID + r"|\d+(?:\s*-\s*\d+)?))?(?![\w:]))"
    r"|(?P<bates>(?<![\w.])(?P<bp>[A-Z]{1,8})(?P<bsep>[-_ ]?)(?P<bn>\d{4,10})"
    r"(?:-(?P<bend>\d{1,10})|\s+to\s+(?P<bp2>[A-Z]{1,8})[-_ ]?(?P<bn2>\d{4,10}))?(?!\w))"
)
BATES_ONLY = re.compile(
    r"(?P<bp>[A-Z]{1,8})(?P<bsep>[-_ ]?)(?P<bn>\d{4,10})"
    r"(?:-(?P<bend>\d{1,10})|\s+to\s+(?P<bp2>[A-Z]{1,8})[-_ ]?(?P<bn2>\d{4,10}))?(?!\w)")
CALC_CELL = re.compile(CELL_RX)


class Grammar:
    """The names the cite grammar needs: exhibit labels and their letter prefixes, Bates
    prefixes, witnesses and data files. Built from the record index, or from the plain dict the
    index gives (grammar_names), which is all the rules proposer receives."""

    def __init__(self, names, date_order="mdy"):
        self.labels = set(names.get("labels", ()))
        self.label_prefixes = set(names.get("label_prefixes", ()))
        self.bates_prefixes = set(names.get("bates_prefixes", ()))
        self.witnesses = set(names.get("witnesses", ()))
        self.data_files = set(names.get("data_files", ()))
        self.date_order = date_order

    def names(self):
        return {"labels": sorted(self.labels), "label_prefixes": sorted(self.label_prefixes),
                "bates_prefixes": sorted(self.bates_prefixes), "witnesses": sorted(self.witnesses),
                "data_files": sorted(self.data_files)}


def _bates_end(start_digits, end):
    if len(end) < len(start_digits):
        return start_digits[:len(start_digits) - len(end)] + end
    return end.zfill(len(start_digits))


def _bates_from(m, text):
    start = m.group("bp") + m.group("bn")
    end = None
    if m.group("bend"):
        end = m.group("bp") + _bates_end(m.group("bn"), m.group("bend"))
    elif m.group("bn2"):
        end = m.group("bp2") + m.group("bn2")
    return {"type": "bates", "text": text, "start": start, "end": end}


def _pin(pin):
    if pin is None:
        return None
    pin = pin.strip()
    k = record.bates_key(pin)
    if k is not None and not pin.isdigit():
        return {"bates": k[0] + k[2]}
    a, _, b = pin.partition("-")
    a = int(a.strip())
    return {"pages": [a, int(b.strip()) if b else a]}


def _from_match(m, text, grammar, strict):
    """A cite dict from one CITE match, or None when the match is not a cite under the grammar.
    strict (untagged text) requires a known exhibit prefix or Bates prefix."""
    if m.group("cell"):
        return {"type": "cell", "text": text, "file": m.group("cfile"), "sheet": m.group("csheet"),
                "col": m.group("ccol"), "row": int(m.group("crow"))}
    if m.group("tr"):
        p1 = int(m.group("tp1"))
        l1 = int(m.group("tl1")) if m.group("tl1") else None
        end = None
        if m.group("tl2"):
            if l1 is None:
                end = [int(m.group("tl2")), None]  # a page range, 45-46
            else:
                end = [int(m.group("tp2")) if m.group("tp2") else p1, int(m.group("tl2"))]
        return {"type": "transcript", "text": text, "witness": m.group("wit"), "form": m.group("tform"),
                "start": [p1, l1], "end": end}
    if m.group("id"):
        return {"type": "id", "text": text, "pin": m.group("idpin")}
    if m.group("ex"):
        label = m.group("elab") if m.group("expre") else m.group("blab")
        written = text[:m.end("elab") - m.start()] if m.group("expre") else m.group("blab")
        known = record.label_norm(label) in grammar.labels
        if not m.group("expre") and not known:
            lp = re.match(r"[A-Z]+", label).group(0)
            if lp not in grammar.label_prefixes and strict:
                return None
        return {"type": "exhibit", "text": text, "label": label, "written": written, "pin": _pin(m.group("epin"))}
    if m.group("bates"):
        if strict and m.group("bp") not in grammar.bates_prefixes:
            return None
        return _bates_from(m, text)
    return None


def parse_cite(text, grammar):
    """A tag's cite (or a record-supports location) parsed under the grammar: (cite, problem)."""
    t = " ".join(text.split())
    m = CITE.fullmatch(t)
    if m:
        c = _from_match(m, t, grammar, strict=False)
        if c is not None:
            if c["type"] == "exhibit" and c["pin"] is None and record.label_norm(c["label"]) not in grammar.labels:
                b = BATES_ONLY.fullmatch(t)
                if b and b.group("bp") in grammar.bates_prefixes:
                    return _bates_from(b, t), ""
            return c, ""
    b = BATES_ONLY.fullmatch(t)
    if b:
        return _bates_from(b, t), ""
    return None, "cite %r does not parse under the grammar" % text


def parse_calc(expr):
    cells = []
    for m in CALC_CELL.finditer(expr):
        cells.append({"type": "cell", "text": m.group(0), "file": m.group("cfile"), "sheet": m.group("csheet"),
                      "col": m.group("ccol"), "row": int(m.group("crow")), "start": m.start(), "end": m.end()})
    return {"type": "calc", "text": "calc: " + expr, "expr": expr, "cells": cells}


def find_cites(text, grammar):
    """Every untagged cite token in text, as (start, end, cite)."""
    out, pos = [], 0
    while True:
        m = CITE.search(text, pos)
        if not m:
            return out
        c = _from_match(m, m.group(0), grammar, strict=True)
        end = m.end()
        if c is None and m.group("ex"):
            b = BATES_ONLY.match(text, m.start())
            if b and b.group("bp") in grammar.bates_prefixes:
                c, end = _bates_from(b, b.group(0)), b.end()
        if c is None:
            pos = m.start() + 1
            continue
        out.append((m.start(), end, c))
        pos = end


def resolve_id(idcite, antecedent, grammar):
    """A3: Id. takes the antecedent; Id. at N replaces its pin. Returns (resolved text, problem)."""
    if antecedent is None:
        return None, "Id. has no earlier resolved cite in its paragraph or footnote chain"
    pin = idcite.get("pin")
    if not pin:
        return antecedent["text"], ""
    t = antecedent["type"]
    if t == "exhibit":
        return antecedent["written"] + " at " + pin, ""
    if t == "transcript":
        return "%s %s %s" % (antecedent["witness"], antecedent["form"], pin), ""
    if t == "bates" and record.bates_key(pin):
        return pin, ""
    return None, "Id. at %s cannot take a pin on the cite %s" % (pin, antecedent["text"])


def cite_names_problem(cite, grammar):
    """I7: the cite names an exhibit, witness or data file that exists."""
    t = cite["type"]
    if t == "exhibit" and record.label_norm(cite["label"]) not in grammar.labels:
        return "exhibit %s is not in exhibits.csv" % cite["label"]
    if t == "transcript" and cite["witness"].casefold() not in grammar.witnesses:
        return "no transcript for %s" % cite["witness"]
    if t == "cell" and cite["file"] not in grammar.data_files and \
            cite["file"].casefold() not in {f.casefold() for f in grammar.data_files}:
        return "data file %s is not in record/data/" % cite["file"]
    return ""


# --- tokens -------------------------------------------------------------------------------------


def _quotations(masked):
    """(start, end) of each pair of double quote marks holding four or more words."""
    out, start = [], None
    for i, ch in enumerate(masked):
        if ch == "\u201c" or (ch == '"' and start is None):
            start = i
        elif start is not None and ch in ('"', "\u201d"):
            inner = masked[start + 1:i]
            if len(re.findall(r"[\w'\u2019\-]+", inner)) >= 4 and "\x00" not in inner:
                out.append((start, i + 1))
            start = None
    return out


BQ_OPEN_TRIM = " \t)]};,.:\u2014\u2013-"   # dropped before a block quote's words, after a cite
BQ_CLOSE_TRIM = " \t([{;,:\u2014\u2013-"   # dropped after its words, before a cite


def _block_quote(text, cites):
    """(start, end) of the quotation in an untagged block quote: the longest stretch of words
    between its cite tokens, without the brackets and punctuation that open or close a cite. A
    block quote with its cite on the last line, "... the whole term. (PX-1 at 3.)", gives the
    words up to "term." and leaves the cite to pair with them."""
    edges = [0] + [x for a, b, _ in cites for x in (a, b)] + [len(text)]
    best = None
    for i in range(0, len(edges), 2):
        a, b = edges[i], edges[i + 1]
        seg = text[a:b]
        a += len(seg) - len(seg.lstrip(BQ_OPEN_TRIM))
        b -= len(seg) - len(seg.rstrip(BQ_CLOSE_TRIM))
        if a < b and (best is None or len(text[a:b].split()) > len(text[best[0]:best[1]].split())):
            best = (a, b)
    return best


def tokenise(text, grammar, masked=(), heading=False, block_quote=False):
    """Every untagged token in one block's reads-as text, outside the masked ranges (tags).

    Kinds: figure, date, quotation, cite; and, not checked, year (bare years), xref (the draft's
    own cross-references), heading_number, docket, clock, short_date (record.not_figures) and
    unread (a digit run no other kind took, listed so that no number leaves checking unseen). A
    range "X to Y", "X-Y", or the same with an en dash, is one figure token. An untagged block
    quote is one quotation token, found after its cites so that a cite on its last line pairs
    with it instead of being read as quoted words. Docket numbers are found before cites, since
    no cite holds one; clock times and two-digit-year dates after them, so the page:line pin of
    a transcript cite, "Esterby Dep. 12:16", stays with its cite."""
    chars = list(text)
    for a, b in masked:
        for i in range(a, b):
            chars[i] = "\x00"

    def hide(a, b):
        for i in range(a, b):
            chars[i] = "\x00"

    tokens = []
    s = "".join(chars)
    if block_quote and "\x00" not in s:
        found = find_cites(s, grammar)
        for a, b, c in found:
            tokens.append({"kind": "cite", "start": a, "end": b, "text": text[a:b], "cite": c})
            hide(a, b)
        span = _block_quote(text, found)
        if span and len(re.findall(r"[\w'\u2019\-]+", text[span[0]:span[1]])) >= 4:
            tokens.append({"kind": "quotation", "start": span[0], "end": span[1], "text": text[span[0]:span[1]],
                           "marks": False})
            hide(*span)
        s = "".join(chars)
    for a, b in _quotations(s):
        tokens.append({"kind": "quotation", "start": a, "end": b, "text": text[a:b], "marks": True})
        hide(a, b)

    def list_not_figures(kinds):
        for a, b, kind in record.not_figures("".join(chars), kinds):
            tokens.append({"kind": kind, "start": a, "end": b, "text": text[a:b]})
            hide(a, b)

    list_not_figures(("docket",))
    s = "".join(chars)
    for a, b, c in find_cites(s, grammar):
        tokens.append({"kind": "cite", "start": a, "end": b, "text": text[a:b], "cite": c})
        hide(a, b)
    list_not_figures(("clock", "short_date"))
    s = "".join(chars)
    for m in record.DATE.finditer(s):
        vals = record.date_values(m, grammar.date_order)
        tokens.append({"kind": "date", "start": m.start(), "end": m.end(), "text": m.group(0),
                       "date": sorted(vals, key=record.show_date)[0] if vals else None})
        hide(m.start(), m.end())
    s = "".join(chars)
    for m in XREF.finditer(s):
        tokens.append({"kind": "xref", "start": m.start(), "end": m.end(), "text": m.group(0)})
        hide(m.start(), m.end())
    if heading:
        m = HEADING_NUMBER.match("".join(chars))
        if m:
            tokens.append({"kind": "heading_number", "start": m.start(), "end": m.end(), "text": m.group(0).strip()})
            hide(m.start(), m.end())
    s = "".join(chars)
    figs = []
    for m in record.FIGURE.finditer(s):
        f = record.parse_figure(m)
        kind = "year" if record.is_bare_year(f) else "figure"
        figs.append({"kind": kind, "start": m.start(), "end": m.end(), "text": text[m.start():m.end()], "figures": [f]})
    # the catch-all: a digit run that no token covers and no tag masks is listed as not checked
    covered = set()
    for t in figs:
        covered.update(range(t["start"], t["end"]))
    for m in DIGIT_RUN.finditer(s):
        if any(i not in covered for i in range(m.start(), m.end()) if s[i].isdigit()):
            tokens.append({"kind": "unread", "start": m.start(), "end": m.end(), "text": text[m.start():m.end()]})
    i = 0
    while i < len(figs):
        t = figs[i]
        join = s[t["end"]:figs[i + 1]["start"]] if i + 1 < len(figs) else ""
        if t["kind"] == "year" and figs[i + 1:i + 2] and re.fullmatch(r"[-\u2013]", join) and \
                re.fullmatch(r"\d\d", figs[i + 1]["text"]):
            tokens.append(t)  # a span of years written short, 2022-23: both ends are years
            tokens.append(dict(figs[i + 1], kind="year"))
            i += 2
            continue
        if t["kind"] == "figure" and i + 1 < len(figs) and figs[i + 1]["kind"] == "figure" and \
                RANGE_JOIN.fullmatch(join):
            nxt = figs[i + 1]
            a, b = dict(t["figures"][0]), nxt["figures"][0]
            if not a["scaled"] and b["scaled"]:
                a["scale"], a["scaled"] = b["scale"], True
            if not a["pct"] and b["pct"]:
                a["pct"] = True
            tokens.append({"kind": "figure", "start": t["start"], "end": nxt["end"],
                           "text": text[t["start"]:nxt["end"]], "figures": [a, b], "range": True})
            i += 2
            continue
        tokens.append(t)
        i += 1
    tokens.sort(key=lambda t: t["start"])
    return tokens


def span_value(span, grammar):
    """Kind and value of a tagged span: quotation, date, figure (or range) or text."""
    if span[:1] in "\"\u201c'\u2018":
        return {"kind": "quotation"}
    toks = [t for t in tokenise(span, grammar) if t["kind"] in ("figure", "date")]
    if toks:
        t = toks[0]
        if t["kind"] == "date":
            return {"kind": "date", "date": t["date"]}
        return {"kind": "figure", "figures": t["figures"], "range": bool(t.get("range"))}
    return {"kind": "text"}


def word_phrases(text, tokens, mask=()):
    """Every phrase words.py reads in one block, outside the masked ranges (tags), that cuts no
    figure, date, quotation or cite token in two. holds lists the figure and date tokens a
    phrase takes in whole, as "the fourteenth of March 2019" takes "March 2019"."""
    out = []
    for a, b, reading in words.find(text):
        if any(x < b and a < y for x, y in mask):
            continue
        near = [t for t in tokens if t["kind"] in VALUE_KINDS + ("cite",) and t["start"] < b and a < t["end"]]
        holds = [t for t in near if t["kind"] in ("figure", "date") and a <= t["start"] and t["end"] <= b]
        if len(holds) == len(near):
            out.append({"kind": "words", "start": a, "end": b, "text": text[a:b], "reading": reading, "holds": holds})
    return out


# --- pairing: A1 to A4 --------------------------------------------------------------------------


def pair_sentence(values, cites, foot_cites):
    """Pair untagged values with cites in one sentence. Returns {value index: (rule, cite index
    or None, code or None, foot)}; foot says the cite came from a footnote (A4)."""
    out = {}
    if len(cites) >= 2 and len(values) >= 2:
        seq = sorted([("v", i, v["start"]) for i, v in enumerate(values)] +
                     [("c", j, c["start"]) for j, c in enumerate(cites)], key=lambda x: x[2])
        alternate = len(seq) % 2 == 0 and all(seq[k][0] == "v" and seq[k + 1][0] == "c" for k in range(0, len(seq), 2))
        for k in range(0, len(seq), 2) if alternate else ():
            out[seq[k][1]] = ("A2", seq[k + 1][1], None, False)
        if not alternate:
            for i in range(len(values)):
                out[i] = ("A2", None, "ambiguous_association", False)
        return out
    if cites:
        for i, v in enumerate(values):
            best = None
            for j, c in enumerate(cites):
                if c["start"] >= v["end"]:
                    dist, follows = c["start"] - v["end"], 0
                else:
                    dist, follows = v["start"] - c["end"], 1
                cand = (dist, follows, j)
                if best is None or cand < best:
                    best = cand
            out[i] = ("A1", best[2], None, False)
        return out
    for i in range(len(values)):
        if len(foot_cites) == 1:
            out[i] = ("A4", 0, None, True)
        elif len(foot_cites) >= 2:
            out[i] = ("A4", None, "ambiguous_association", True)
        else:
            out[i] = ("A1", None, "no_cite", False)
    return out


def pair_phrase(phrase, values, cites, foot_cites):
    """Code's pairing for a words phrase: A1 to A4 over its sentence's values with the phrase in
    place of the tokens it holds. Every other token keeps the pairing it had without the phrase."""
    seq = sorted([v for v in values if all(v is not h for h in phrase["holds"])] + [phrase], key=lambda t: t["start"])
    return pair_sentence(seq, cites, foot_cites)[seq.index(phrase)]


def _in_sentence(block, tok):
    for i, (a, b) in enumerate(block["sentences"], 1):
        if a <= tok["start"] <= b:
            return i
    return len(block["sentences"])


def analyse(draft, grammar):
    """Tokens, the Id. chain and code's pairing for every untagged token in the draft.

    Returns {"blocks": {where: block}, "tokens": {where: [token]}, "values": [value token],
    "words": [words phrase], "not_checked": [row], "cite_count": n}. Each value token and words
    phrase carries "pair": {rule, cite_text, resolved, cite, code, reason, candidates}."""
    blocks = {b["where"]: b for b in draft["blocks"]}
    tokens = {}
    for b in draft["blocks"]:
        mask = [(t["start"], t["end"]) for t in b["tags"]]
        tokens[b["where"]] = tokenise(b["text"], grammar, mask, b["heading"], b["block_quote"])
        for t in tokens[b["where"]]:
            t["where"] = b["where"]
            t["sentence"] = _in_sentence(b, t)

    # A3: the Id. chain, over tag cites and untagged cite tokens in reading order. A paragraph
    # starts a fresh chain; a footnote starts from the last resolved cite of the footnote before.
    feet = sorted((b for b in draft["blocks"] if b["kind"] == "foot"), key=lambda b: b["n"])
    order = [b for b in draft["blocks"] if b["kind"] == "para"] + feet
    prev_foot = None
    for b in order:
        prev = prev_foot if b["kind"] == "foot" else None
        items = [("tag", t["start"], t) for t in b["tags"] if t["cite"] and not t["skip"]]
        items += [("tok", t["start"], t) for t in tokens[b["where"]] if t["kind"] == "cite"]
        for kind, _, it in sorted(items, key=lambda x: x[1]):
            if kind == "tag":
                cite, problem = parse_cite(it["cite"], grammar)
                it["parsed"], it["parse_problem"] = cite, problem
            else:
                cite, problem = it["cite"], ""
            if cite is None:
                it["resolved"], it["resolve_code"], it["resolve_reason"] = None, "cite_unparsed", problem
                continue
            if cite["type"] == "id":
                text, why = resolve_id(cite, prev, grammar)
                if text is None:
                    code = "id_no_antecedent" if prev is None else "cite_unparsed"
                    it["resolved"], it["resolve_code"], it["resolve_reason"] = None, code, why
                    continue
                cite, problem = parse_cite(text, grammar)
                if cite is None:
                    it["resolved"], it["resolve_code"], it["resolve_reason"] = None, "cite_unparsed", problem
                    continue
            it["resolved"], it["resolve_code"], it["resolve_reason"] = cite, "", ""
            prev = cite
        if b["kind"] == "foot":
            prev_foot = prev

    values, phrases, not_checked, cite_count = [], [], [], 0
    for b in draft["blocks"]:
        w = b["where"]
        toks = tokens[w]
        found = word_phrases(b["text"], toks, [(t["start"], t["end"]) for t in b["tags"]])
        for p in found:
            p["where"], p["sentence"] = w, _in_sentence(b, p)
        cite_count += sum(1 for t in toks if t["kind"] == "cite")
        if b.get("list_number"):
            not_checked.append({"where": w, "sentence": 1, "span": b["list_number"], "reason": LIST_NUMBER})
        for t in b["tags"]:
            if t["skip"]:
                s, _ = sentence_of(b, t["start"])
                not_checked.append({"where": w, "sentence": s, "span": t["text"], "reason": "tagged skip"})
        for t in toks:
            if t["kind"] in NOT_CHECKED:
                not_checked.append({"where": w, "sentence": t["sentence"], "span": t["text"],
                                    "reason": NOT_CHECKED[t["kind"]]})
        for si in range(1, len(b["sentences"]) + 1):
            vals = [t for t in toks if t["sentence"] == si and t["kind"] in VALUE_KINDS]
            said = [p for p in found if p["sentence"] == si]
            if not vals and not said:
                continue
            cites = [t for t in toks if t["sentence"] == si and t["kind"] == "cite"]
            a, z = b["sentences"][si - 1]
            fns = [n for off, n in b["refs"] if a <= off <= z]
            fcites = [t for n in fns for t in tokens.get(("foot", n), []) if t["kind"] == "cite"]
            pairs = pair_sentence(vals, cites, fcites)
            for i, v in enumerate(vals):
                v["pair"] = _pair_of(pairs[i], cites, fcites)
                values.append(v)
            for p in said:
                p["pair"] = _pair_of(pair_phrase(p, vals, cites, fcites), cites, fcites)
                phrases.append(p)
    return {"blocks": blocks, "tokens": tokens, "values": values, "words": phrases, "not_checked": not_checked,
            "cite_count": cite_count}


def _pair_of(pairing, cites, fcites):
    rule, j, code, foot = pairing
    ct = None if j is None else (fcites[j] if foot else cites[j])
    return _pairing(rule, ct, code, fcites if foot or not cites else cites)


def _pairing(rule, ct, code, pool):
    p = {"rule": rule if code is None else "none", "cite_text": "", "resolved": "", "cite": None,
         "code": code or "", "reason": "", "candidates": [c["text"] for c in pool]}
    if code == "no_cite":
        p["reason"] = "no cite in the sentence or in a footnote it carries"
    elif code == "ambiguous_association":
        p["reason"] = ("the sentence's footnote holds %d cites" % len(pool) if rule == "A4"
                       else "values and cites in the sentence do not alternate")
    if ct is not None:
        p["cite_text"] = ct["text"]
        if ct.get("resolved") is None:
            p["code"], p["reason"] = ct.get("resolve_code") or "cite_unparsed", ct.get("resolve_reason", "")
        else:
            p["cite"] = ct["resolved"]
            p["resolved"] = ct["resolved"]["text"]
    return p


# --- claims -------------------------------------------------------------------------------------


def _where_fields(where):
    kind, n = where
    return {"para": n} if kind == "para" else {"footnote": n}


def tag_claims(draft, analysis, grammar):
    """One claim per inline tag or Word comment tag that is not skip."""
    out = []
    for b in draft["blocks"]:
        for t in b["tags"]:
            if t["skip"]:
                continue
            si, sent = sentence_of(b, t["start"])
            val = span_value(t["text"], grammar)
            claim = {"where": b["where"], "sentence": si, "sentence_text": sent, "span": t["text"],
                     "start": t["start"], "end": t["end"], "proposed_by": "tag", "pairing": "tag",
                     "cite_text": t["cite"] or ("calc: " + t["calc"] if t["calc"] else ""), "cite": None,
                     "calc": parse_calc(t["calc"]) if t["calc"] else None, "pre": None}
            claim.update(val)
            resolved = ""
            if t["cite"]:
                if t.get("resolved") is None:
                    claim["pre"] = {"code": t.get("resolve_code") or "cite_unparsed",
                                    "reason": t.get("resolve_reason") or t.get("problem") or "cite does not parse"}
                    resolved = t["cite"]
                else:
                    claim["cite"] = t["resolved"]
                    resolved = t["resolved"]["text"]
            keycite = resolved + (" | calc: " + t["calc"] if t["calc"] and resolved else "")
            keycite = keycite or ("calc: " + t["calc"] if t["calc"] else "")
            claim["cite_resolved"] = keycite
            claim["key"] = claim_key(t["text"], keycite, sent)
            out.append(claim)
    return out


def value_claim(tok, analysis, proposed_by, p7=None):
    """The claim for one untagged value token, with code's pairing; p7 is a model cite that
    differed from code's (P7), which drops the token as ambiguous_association."""
    b = analysis["blocks"][tok["where"]]
    si, sent = sentence_of(b, tok["start"])
    pair = tok["pair"]
    claim = {"where": tok["where"], "sentence": si, "sentence_text": sent, "span": tok["text"],
             "start": tok["start"], "end": tok["end"], "proposed_by": proposed_by, "pairing": pair["rule"],
             "cite_text": pair["cite_text"], "cite": pair["cite"], "calc": None, "pre": None,
             "cite_resolved": pair["resolved"]}
    kind = tok["kind"]
    if kind == "words":  # a model's words proposal: checked as the figure or date words.py reads
        kind = tok["reading"]["kind"]
        tok = dict(tok, figures=[tok["reading"].get("figure")], date=tok["reading"].get("date"))
    claim["kind"] = kind
    if kind == "figure":
        claim["figures"], claim["range"] = tok["figures"], bool(tok.get("range"))
    elif kind == "date":
        claim["date"] = tok["date"]
    if pair["code"]:
        hint = ""
        if pair["code"] == "ambiguous_association" and pair["candidates"]:
            hint = "cites in reach: " + "; ".join(pair["candidates"])
        claim["pre"] = {"code": pair["code"], "reason": pair["reason"], "hint": hint}
    if p7 is not None:
        claim["pre"] = {"code": "ambiguous_association",
                        "reason": "the proposer's cite differs from the pairing code makes (P7)",
                        "hint": "proposer's cite, never used: %s" % (p7 or "(none)")}
        claim["hint_source"] = "model-flag" if proposed_by == "model" else "code"
    if claim["pre"] and claim["pre"]["code"] in ("no_cite", "ambiguous_association"):
        claim["cite_resolved"] = ""
    keycite = claim["cite_resolved"] or ("" if not claim["pre"] or claim["pre"]["code"] in
                                         ("no_cite", "ambiguous_association") else claim["cite_text"])
    claim["key"] = claim_key(tok["text"], keycite, sent)
    return claim


def coverage_sweep(analysis, covered):
    """Ported in shape from fsi narrative_coverage_audit: every untagged value token is either
    covered by an accepted proposal or listed. Returns (pct, uncovered tokens, matched tokens).
    The skip rules are the not-checked kinds tokenise() sets apart and analyse() lists with their
    reasons: bare years, cross-references, heading and list numbers, docket numbers, clock times,
    two-digit-year dates and unread digit runs."""
    tokens, uncovered, matched = analysis["values"], [], []
    for t in tokens:
        (matched if (t["where"], t["start"]) in covered else uncovered).append(t)
    pct = 100.0 if not tokens else 100.0 * len(matched) / len(tokens)
    return round(pct, 2), uncovered, matched


def build_claims(draft, analysis, grammar, accepted):
    """Every claim in draft order: tags, then accepted proposals, then the coverage sweep.

    accepted: list of {"where", "start", "proposed_by", "p7", "kind", ...} from accept(). A
    model's words proposal adds a claim; the rules proposer's words proposals are candidates
    only, listed in the drop log and never checked, so under rules a number in words stays the
    designed blindness measure.py counts (figure_in_words). A flag adds its
    reason to the claim of the token it names, which build_claims makes either way."""
    claims = tag_claims(draft, analysis, grammar)
    covered, flags, said = {}, {}, {}
    phrases = {(p["where"], p["start"]): p for p in analysis.get("words", [])}
    for a in accepted:
        at = (a["where"], a["start"])
        if a.get("kind") == "flag":
            flags[at] = a["reason"]
        elif a.get("kind") == "words":
            if a["proposed_by"] == "model":
                said[at] = a
        else:
            covered[at] = a
    _, uncovered, matched = coverage_sweep(analysis, covered)
    for t in matched:
        a = covered[(t["where"], t["start"])]
        claims.append(value_claim(t, analysis, a["proposed_by"], a.get("p7")))
    for t in uncovered:
        claims.append(value_claim(t, analysis, "rules"))
    for at, a in said.items():
        claims.append(value_claim(phrases[at], analysis, "model", a.get("p7")))
    for c in claims:
        if (c["where"], c["start"]) in flags and c["proposed_by"] != "tag":
            c["flag"] = flags[(c["where"], c["start"])]
    order = {b["where"]: i for i, b in enumerate(draft["blocks"])}
    claims.sort(key=lambda c: (order[c["where"]], c["start"]))
    return claims


# --- proposals: chunks, the rules proposer and P1 to P7 -----------------------------------------


def chunks(draft, analysis, size):
    """Groups of up to size paragraphs that hold untagged value tokens or words phrases, each with
    the footnotes those paragraphs reference. A footnote holding either joins as an item itself."""
    with_values = {t["where"] for t in analysis["values"] + analysis.get("words", [])}
    units = [b for b in draft["blocks"] if b["where"] in with_values]
    out = []
    for i in range(0, len(units), max(1, size)):
        group = units[i:i + size]
        items = [b["where"] for b in group]
        refs = sorted({n for b in group for _, n in b["refs"]})
        context = [("foot", n) for n in refs if ("foot", n) in analysis["blocks"] and ("foot", n) not in items]
        out.append({"items": items, "context": context})
    return out


def chunk_message(chunk, analysis, rejected=None):
    """The user message for one chunk: JSON with the reads-as text of each paragraph, the spans
    already tagged, and the footnotes the paragraphs reference. Nothing from the record."""

    def item(w, propose):
        b = analysis["blocks"][w]
        return {"para": b["n"] if b["kind"] == "para" else "fn%d" % b["n"], "text": b["text"],
                "propose": propose, "tagged": [[t["start"], t["end"]] for t in b["tags"]],
                "refs": [[off, n] for off, n in b["refs"]], "heading": b["heading"],
                "block_quote": b["block_quote"]}

    body = {"kinds": sorted(list(PROPOSAL_KINDS) + ["flag", "words"]),
            "paragraphs": [item(w, True) for w in chunk["items"]], "context": [item(w, False) for w in chunk["context"]]}
    if rejected:
        body["rejected"] = list(rejected)
    return json.dumps(body, ensure_ascii=False, sort_keys=True, indent=1)


def rules_propose(user, names, date_order):
    """The rules proposer: every figure and date in digits, every quotation in quote marks, each
    with the cite A1, A2 and A4 pair it with in this chunk, then every words phrase as a words
    candidate with its reading and code's pairing. A phrase that holds a figure or date token is
    left out, since that token is proposed and checked already. It reads only the user message."""
    req = json.loads(user)
    grammar = Grammar(names, date_order)
    toks = {}
    for it in req.get("paragraphs", []) + req.get("context", []):
        b = {"text": it["text"], "sentences": block_sentences(it["text"], it.get("block_quote", False))}
        mask = [tuple(x) for x in it.get("tagged", [])]
        ts = tokenise(it["text"], grammar, mask, it.get("heading", False), it.get("block_quote", False))
        for t in ts:
            t["sentence"] = _in_sentence(b, t)
        toks[str(it["para"])] = (b, ts, mask)
    out = []
    for it in req.get("paragraphs", []):
        if not it.get("propose", True):
            continue
        b, ts, mask = toks[str(it["para"])]
        for si in range(1, len(b["sentences"]) + 1):
            vals = [t for t in ts if t["sentence"] == si and t["kind"] in VALUE_KINDS]
            if not vals:
                continue
            cites = [t for t in ts if t["sentence"] == si and t["kind"] == "cite"]
            a, z = b["sentences"][si - 1]
            fcites = []
            for off, n in it.get("refs", []):
                if a <= off <= z:
                    fcites += [t for t in toks.get("fn%d" % n, (None, [], None))[1] if t["kind"] == "cite"]
            pairs = pair_sentence(vals, cites, fcites)
            for i, v in enumerate(vals):
                _, j, _, foot = pairs[i]
                cite = "" if j is None else (fcites[j] if foot else cites[j])["text"]
                kind = {"figure": "figure", "date": "date", "quotation": "quote"}[v["kind"]]
                out.append({"para": it["para"], "span": unique_span(it["text"], v, ts, mask), "cite": cite,
                            "kind": kind})
        phrases = [p for p in word_phrases(it["text"], ts, mask) if not p["holds"]]
        for p in phrases:
            si = _in_sentence(b, p)
            vals = [t for t in ts if t["sentence"] == si and t["kind"] in VALUE_KINDS]
            cites = [t for t in ts if t["sentence"] == si and t["kind"] == "cite"]
            a, z = b["sentences"][si - 1]
            fcites = [t for off, n in it.get("refs", []) if a <= off <= z
                      for t in toks.get("fn%d" % n, (None, [], None))[1] if t["kind"] == "cite"]
            _, j, _, foot = pair_phrase(p, vals, cites, fcites)
            cite = "" if j is None else (fcites[j] if foot else cites[j])["text"]
            out.append({"para": it["para"], "span": unique_span(it["text"], p, ts + phrases, mask), "cite": cite,
                        "kind": "words", "value": p["reading"]["show"]})
    return out


def unique_span(text, tok, tokens, mask, reach=8):
    """The token's text, grown by whole words to the left and then the right until it occurs
    once in the paragraph (P2), without taking in another value or a tagged range (P4 to P6)."""
    ntext = _norm_map(text)[0]

    def ok(a, b):
        if any(x < b and a < y for x, y in mask):
            return False
        if any(t is not tok and t["kind"] in VALUE_KINDS + ("words",) and t["start"] < b and a < t["end"]
               for t in tokens):
            return False
        span = _norm_map(text[a:b])[0].strip()
        return bool(span) and ntext.count(span) == 1

    a, b = tok["start"], tok["end"]
    if ok(a, b):
        return text[a:b]
    for side in ("left", "right"):
        a, b = tok["start"], tok["end"]
        for _ in range(reach):
            if side == "left":
                m = re.search(r"\S+\s*$", text[:a])
                if not m:
                    break
                a = m.start()
            else:
                m = re.match(r"\s*\S+", text[b:])
                if not m:
                    break
                b += m.end()
            if ok(a, b):
                return text[a:b]
    return text[tok["start"]:tok["end"]]


def _norm_map(text):
    """norm_text with a map from each normalised character to its offset in text."""
    out, idx, prev_space = [], [], True
    for i, ch in enumerate(text):
        c = record.QUOTES.get(ch, record.DASHES.get(ch, ch))
        if c.isspace():
            if prev_space:
                continue
            c, prev_space = " ", True
        else:
            prev_space = False
        out.append(c)
        idx.append(i)
    while out and out[-1] == " ":
        out.pop()
        idx.pop()
    return "".join(out), idx


def unfence(reply):
    """The reply with one Markdown code fence taken off, when the trimmed reply is a line of three
    backticks with an optional language tag such as json, the body, and a closing line of three
    backticks. Text outside the fence or an unclosed fence leaves the reply as it was, and two
    fences or a fence inside a fence leave a fence line in the body; P1 refuses each as not JSON."""
    m = FENCE.fullmatch(reply.strip())
    return m.group(1) if m else reply


RETRY_CAP = 40


def _clip(val, limit=80):
    s = repr(val)
    return s if len(s) <= limit else s[:limit - 3] + "..."


def _clip_field(val, limit=120):
    if isinstance(val, str):
        return val if len(val) <= limit else val[:limit - 3] + "..."
    if isinstance(val, int) and not isinstance(val, bool):
        s = str(val)
        return val if len(s) <= limit else s[:limit - 3] + "..."
    return _clip(val, limit)


def _clip_keys(keys, max_keys=12, limit=40):
    items = sorted(str(k) for k in keys)
    shown = [k if len(k) <= limit else k[:limit - 3] + "..." for k in items[:max_keys]]
    if len(items) > max_keys:
        shown.append("+%d more" % (len(items) - max_keys))
    return shown


def accept(reply, analysis, chunk, accepted_spans, proposed_by):
    """P1 to P9 over one reply, after unfence. Returns {"codes": set, "whole": bool, "rows": [...],
    "accepted": [...]}: whole is True when P1 rejects the reply whole; rows give each
    proposal's codes and plain-English reasons; accepted lists the proposals that pass P2 to P6,
    P8 and P9 (P7 failures are accepted and drop as ambiguous_association). A quote span that is
    exact to a clean quotation token's interior snaps to that token; any other partial or
    non-token quote span fails P5. A words span holds one phrase words.py reads, to the value the
    proposal states (P8); a flag's span is an untagged token's own text and its reason one of
    FLAG_REASONS (P9). A flag takes no pairing, so P7 skips it."""
    codes, rows, accepted = set(), [], []
    try:
        data = json.loads(unfence(reply))
    except (ValueError, RecursionError):  # RecursionError: nested deeper than the parser goes
        msg = "the reply is not valid JSON"
        return {"codes": {"P1"}, "whole": True, "rows": [{"codes": ["P1"], "why": [msg], "rwhy": [msg]}],
                "accepted": []}
    whole = False
    if not isinstance(data, list) or not all(isinstance(p, dict) for p in data):
        msg = "the reply must be a JSON array of objects"
        return {"codes": {"P1"}, "whole": True,
                "rows": [{"codes": ["P1"], "why": [msg], "rwhy": [msg]}],
                "accepted": []}
    allowed_where = set(chunk["items"])
    taken = {w: list(v) for w, v in accepted_spans.items()}
    said = {}
    for ph in analysis.get("words", []):
        said.setdefault(ph["where"], []).append(ph)
    for p in data:
        pc, why, rwhy = [], [], []

        def fail(code, msg, retry_msg=None):
            pc.append(code)
            why.append(msg)
            rwhy.append(msg if retry_msg is None else retry_msg)

        keys = set(p)
        need = set(P1_KEYS)
        if p.get("kind") == "words":
            need.add("value")
        if p.get("kind") == "flag":
            need.add("reason")
        if keys != need:
            fail("P1", "element has keys %s; expected exact keys %s" % (_clip_keys(keys), sorted(need)))
            whole = True
        where = parse_where(p.get("para"))
        span, cite, kind = p.get("span"), p.get("cite"), p.get("kind")
        block = analysis["blocks"].get(where) if where in allowed_where else None
        if block is None or not isinstance(span, str) or not span.strip():
            fail("P2", "paragraph %s is not a paragraph to propose in this message" % _clip(p.get("para"), 40)
                 if block is None else "span must be non-empty text copied from the paragraph")
            rows.append({"proposal": p, "codes": pc, "why": why, "rwhy": rwhy})
            codes.update(pc)
            continue
        para_disp = _clip_field(str(p.get("para")).strip(), 40)
        ntext, idx = _norm_map(block["text"])
        nspan = _norm_map(span)[0].strip()
        hits = [m.start() for m in re.finditer(re.escape(nspan), ntext)] if nspan else []
        if len(hits) != 1:
            fail("P2", "span was not found verbatim in paragraph %s" % para_disp if not hits else
                 "span appears %d times in paragraph %s; include nearby words so it appears once"
                 % (len(hits), para_disp))
            rows.append({"proposal": p, "codes": pc, "why": why, "rwhy": rwhy})
            codes.update(pc)
            continue
        s = idx[hits[0]]
        e = idx[hits[0] + len(nspan) - 1] + 1
        toks = analysis["tokens"][where]
        if kind == "quote":
            snap = [t for t in toks if t["kind"] == "quotation" and t.get("marks")
                    and (s, e) == (t["start"] + 1, t["end"] - 1)]
            if len(snap) == 1:
                s, e = snap[0]["start"], snap[0]["end"]
        si, _ = sentence_of(block, s)
        a, z = block["sentences"][si - 1]
        cite_tok = None
        if not isinstance(cite, str):
            fail("P3", "cite must be text (or \"\" when there is no cite)")
        elif cite.strip():
            fns = [n for off, n in block["refs"] if a <= off <= z]
            pool = [t for t in toks if t["kind"] == "cite" and t["sentence"] == si]
            pool += [t for n in fns for t in analysis["tokens"].get(("foot", n), []) if t["kind"] == "cite"]
            match = [t for t in pool if record.norm_text(t["text"]) == record.norm_text(cite)]
            if not match:
                fail("P3", "cite %s is not in the span's sentence or a footnote that sentence references"
                     % _clip(cite))
            elif match[0].get("resolved") is None:
                fail("P3", "cite %s does not resolve (for example Id. with no earlier cite)" % _clip(cite))
            else:
                cite_tok = match[0]
        if any(x < e and s < y for x, y in [(t["start"], t["end"]) for t in block["tags"]] + taken.get(where, [])):
            fail("P4", "span overlaps an already-tagged range or an earlier element in this reply")
        inside = [t for t in toks if t["kind"] in VALUE_KINDS and s <= t["start"] and t["end"] <= e]
        tok = inside[0] if len(inside) == 1 else None
        if kind == "flag":
            tok = ([t for t in toks if t["kind"] in VALUE_KINDS and (t["start"], t["end"]) == (s, e)] or [None])[0]
            if tok is None or p.get("reason") not in FLAG_REASONS:
                fail("P9", "kind \"flag\" must copy the exact figure, date or quotation and use a reason from: %s"
                     % ", ".join(FLAG_REASONS))
        elif kind == "words":
            phrases = [ph for ph in said.get(where, []) if s <= ph["start"] and ph["end"] <= e]
            held = [h for ph in phrases for h in ph["holds"]]
            tok = phrases[0] if phrases else None
            if not phrases:
                fail("P5", "span holds no number or date written in words")
            elif len(phrases) >= 2 or any(all(t is not h for h in held) for t in inside):
                fail("P6", "span holds %d values; put one value in each element"
                     % (len(phrases) + len(inside) - len(held)))
            elif not words.same_value(p.get("value"), tok["reading"]):
                fail("P8",
                     "phrase %r reads as %s, whereas \"value\" gave %s"
                     % (tok["text"], tok["reading"]["show"], _clip(p.get("value"))),
                     "\"value\" %s does not match the number or date written in words"
                     % _clip(p.get("value")))
        elif not isinstance(kind, str) or kind not in PROPOSAL_KINDS:
            fail("P5", "kind %s is unknown; expected figure, date, quote, words or flag" % _clip(kind, 40))
        elif not inside:
            fail("P5", "span holds no quotation of four or more words; include the opening and closing quote marks"
                 if kind == "quote" else "span holds no figure, date or quotation of four or more words")
        elif len(inside) >= 2:
            fail("P6", "span holds %d values; put one value in each element" % len(inside))
        elif inside[0]["kind"] != PROPOSAL_KINDS[kind]:
            fail("P5", "span holds a %s, whereas kind was %s" % (inside[0]["kind"], _clip(kind, 40)))
        p7 = None
        if not pc:
            code_cite = tok["pair"]["resolved"] if not tok["pair"]["code"] else ""
            mine = cite_tok["resolved"]["text"] if cite_tok is not None else ""
            if kind != "flag" and record.norm_text(mine) != record.norm_text(code_cite):
                pc.append("P7")
                why.append("cite %s differs from code's pairing %r" % (_clip(cite), code_cite))
                p7 = cite if isinstance(cite, str) else ""
            taken.setdefault(where, []).append((s, e))
            got = {"where": where, "start": tok["start"], "span_range": (s, e), "proposed_by": proposed_by,
                   "p7": p7, "span": block["text"][s:e], "cite": cite, "kind": kind}
            got.update({k: p[k] for k in ("value", "reason") if k in p})
            accepted.append(got)
        rows.append({"proposal": p, "codes": pc, "why": why, "rwhy": rwhy})
        codes.update(pc)
    return {"codes": codes, "whole": whole, "rows": rows, "accepted": [] if whole else accepted}


def merge_accepted(prev, curr):
    """Keep earlier accepted proposals whose span overlaps none in curr, then add curr, in document
    order. S5 re-runs accept() on the merged list, so non-overlap preserves P4."""
    if not prev:
        return list(curr)
    if not curr:
        return list(prev)
    by_where = {}
    for c in curr:
        by_where.setdefault(c["where"], []).append(c.get("span_range", (c["start"], c["start"] + len(c["span"]))))
    kept = []
    for a in prev:
        s0, e0 = a.get("span_range", (a["start"], a["start"] + len(a["span"])))
        if not any(x < e0 and s0 < y for x, y in by_where.get(a["where"], ())):
            kept.append(a)
    merged = kept + list(curr)
    merged.sort(key=lambda a: (0 if a["where"][0] == "para" else 1, a["where"][1],
                               a.get("span_range", (a["start"], 0))[0]))
    return merged


def retry_reasons(res):
    """Plain-English failure reasons per rejected element for one retry, leaving out P7 and
    words.py's reading, with model-supplied values clipped and at most RETRY_CAP elements."""
    out = []
    for i, r in enumerate(res["rows"]):
        if not [c for c in r["codes"] if c != "P7"]:
            continue
        if len(out) >= RETRY_CAP:
            break
        if "rwhy" in r:
            reasons = list(r["rwhy"])
        elif len(r["codes"]) == len(r["why"]):
            reasons = [w for c, w in zip(r["codes"], r["why"]) if c != "P7"]
        else:
            reasons = list(r["why"])
        if "proposal" not in r:
            out.append({"element": None, "reasons": reasons})
            continue
        p = r["proposal"]
        item = {"element": i, "reasons": reasons}
        if "para" in p and p.get("para") is not None:
            item["para"] = _clip_field(p["para"], 40)
        if "span" in p and p.get("span") is not None:
            item["span"] = _clip_field(p["span"], 120)
        if "cite" in p and p.get("cite") not in (None, ""):
            item["cite"] = _clip_field(p["cite"], 80)
        if "kind" in p and p.get("kind") is not None:
            item["kind"] = _clip_field(p["kind"], 40)
        out.append(item)
    return out


# --- intake: I7 ---------------------------------------------------------------------------------


def intake_rows(draft, analysis, grammar):
    """I7: every cite token, tagged or untagged, parses and names an exhibit, witness or data file
    that exists; a .docx holds no inline tag."""
    rows = []

    def at(where, offset):
        b = analysis["blocks"][where]
        si, _ = sentence_of(b, offset)
        return "%s %s sentence %d" % ("paragraph" if where[0] == "para" else "footnote", where[1], si)

    for code, where, why in draft.get("errors", []):
        rows.append("%s: %s" % ("%s %s" % ("paragraph" if where[0] == "para" else "footnote", where[1]), why))
    for b in draft["blocks"]:
        for t in b["tags"]:
            if t["problem"]:
                rows.append("%s: %s %s" % (at(b["where"], t["start"]), t["problem"], t["raw"]))
                continue
            if t["skip"]:
                continue
            if t["text"][:1] not in "\"\u201c'\u2018":  # a tag checks one value, so a second would go unchecked
                vals = [v["text"] for v in tokenise(t["text"], grammar) if v["kind"] in ("figure", "date")]
                if len(vals) > 1:
                    rows.append("%s: tag %r holds %d values (%s); give each its own tag"
                                % (at(b["where"], t["start"]), t["text"], len(vals), "; ".join(vals)))
            if t["cite"]:
                cite, problem = t.get("parsed"), t.get("parse_problem", "")
                if cite is None and "parsed" not in t:
                    cite, problem = parse_cite(t["cite"], grammar)
                if cite is None:
                    rows.append("%s: %s" % (at(b["where"], t["start"]), problem))
                elif cite["type"] != "id":
                    why = cite_names_problem(cite, grammar)
                    if why:
                        rows.append("%s: cite %r: %s" % (at(b["where"], t["start"]), t["cite"], why))
            if t["calc"]:
                calc = parse_calc(t["calc"])
                if not calc["cells"]:  # arithmetic on numbers alone would tie against nothing in the record
                    rows.append("%s: calc %r names no cell" % (at(b["where"], t["start"]), t["calc"]))
                for c in calc["cells"]:
                    why = cite_names_problem(c, grammar)
                    if why:
                        rows.append("%s: calc %r: %s" % (at(b["where"], t["start"]), t["calc"], why))
        for t in analysis["tokens"][b["where"]]:
            if t["kind"] == "cite" and t["cite"]["type"] != "id":
                why = cite_names_problem(t["cite"], grammar)
                if why:
                    rows.append("%s: cite %r: %s" % (at(b["where"], t["start"]), t["text"], why))
    return rows
