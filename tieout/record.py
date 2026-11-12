"""Record index for the tie-out: Bates pages, exhibits, transcripts and spreadsheet cells.

Purpose: read everything under <engagement>/record/ into one index the verifier searches. A page
  is held by its Bates id (the page id a production stamps on each page) with its normalised
  text, every figure and date on it, and a thin flag for pages with fewer than 40 letters and
  digits. Exhibits map a cited label to a Bates range. Transcripts map page:line markers to
  text. CSV files map a cell address to its stored value. While it reads, the index collects the
  record problems that intake checks I1 to I6 report.
Reads: <engagement>/record/pages/*.txt, documents/*.txt, exhibits.csv, transcripts/*.txt,
  transcripts.csv and data/*.csv. A first line starting "SYNTHETIC:" (or "# SYNTHETIC:" in a
  CSV) marks a fixture file and is dropped before anything else reads the file. Files the
  operating system writes into a folder someone opens (names starting with a dot, Thumbs.db,
  desktop.ini) are skipped and stay out of the record manifest.
Writes: nothing.
Network: none.
Exit codes: none; a library module. Problems become intake rows, never exceptions, so one
  intake run lists every problem at once.
"""
import csv
import datetime
import decimal
import hashlib
import io
import os
import re
import unicodedata

D = decimal.Decimal
CTX = decimal.Context(prec=50, rounding=decimal.ROUND_HALF_UP)

THIN = 40  # a page with fewer letters and digits than this is thin (I3)
EXHIBIT_COLUMNS = ["exhibit", "title", "first_page", "last_page", "file"]
TRANSCRIPT_COLUMNS = ["witness", "file", "date"]
MARKERS = ("SYNTHETIC:", "# SYNTHETIC:")
IGNORED_NAMES = ("thumbs.db", "desktop.ini")  # with names starting with a dot, see ignored()

# --- text normalisation -------------------------------------------------------------------------

COMMENT = re.compile(r"<!--.*?-->", re.S)
QUOTES = {"\u201c": '"', "\u201d": '"', "\u201e": '"', "\u2018": "'", "\u2019": "'"}
DASHES = {"\u2010": "-", "\u2011": "-", "\u2012": "-", "\u2013": "-", "\u2014": "-", "\u2212": "-"}


def _read(path):
    """Return the text of a UTF-8 file, ready for the checks.

    Ported from the author's earlier private code. The text is normalised so look-alike forms of a
    character compare equal (NFKC). Invisible format characters (zero-width spaces, soft hyphens,
    byte-order marks) and HTML comments are removed, so no one can hide a term from the checks by
    splitting it."""
    with open(path, encoding="utf-8") as fh:
        try:
            text = fh.read()
        except UnicodeDecodeError as exc:
            raise ValueError(f"{path}: not UTF-8 text ({exc.reason} at byte {exc.start})") from None
    text = unicodedata.normalize("NFKC", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Cf")
    return COMMENT.sub(" ", text)


def norm_text(s):
    """NFKC, curly quotes to straight, dashes to hyphens, runs of whitespace to one space."""
    s = unicodedata.normalize("NFKC", s)
    for a, b in list(QUOTES.items()) + list(DASHES.items()):
        s = s.replace(a, b)
    return " ".join(s.split())


# A hyphen that ends a line of a page, between a letter and a lower-case letter. The word may run on
# across the line ("sub-" then "jects"), or the hyphen may belong to it ("three-" then "stage"). The
# mark stands in for both, and the verifier reads it only after the plain reading fails.
LINE_END_HYPHEN = re.compile(r"(?<=[A-Za-z])[-\u2010\u2011][ \t]*\n[ \t]*(?=[a-z])")
HYPHEN_BREAK = "\x01"


def mark_hyphen_breaks(text):
    """The text with each line-end hyphen and its line break replaced by HYPHEN_BREAK."""
    return LINE_END_HYPHEN.sub(HYPHEN_BREAK, text.replace(HYPHEN_BREAK, "\x02"))  # \x02: no word, no space


def drop_marker(text):
    """Drop a SYNTHETIC marker line; return (text, lines dropped)."""
    first, _, rest = text.partition("\n")
    if first.lstrip("\ufeff").startswith(MARKERS):
        return rest, 1
    return text, 0


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def tree_hash(manifest):
    """sha256 over sorted '<file sha256>  <relpath>' lines."""
    lines = "".join("%s  %s\n" % (manifest[p], p) for p in sorted(manifest))
    return sha256_bytes(lines.encode("utf-8"))


# --- figures ------------------------------------------------------------------------------------
# FIGURE starts from the earlier code's FIGURE alternatives and widens them for the rounding rule:
# one and two digit numbers, a parenthesised negative, a scale word or abbreviation in either
# case, and a percent sign or the word percent. The same pattern reads the draft and the record.
# A figure may start right after a hyphen, slash or colon that follows a digit, so a range
# (4,800-4,900), a pair (4,812/4,610) and a ratio (3:1) read as two figures. After a letter and a
# hyphen (PX-7, COVID-19) it may not: that digit run is a label. claims.tokenise() lists any digit
# run this pattern leaves unread, so a form it misses is listed rather than silent. Docket numbers,
# clock times and two-digit-year slash dates are masked before FIGURE runs (not_figures, below).

NUM = r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?"
FIGURE = re.compile(
    r"(?<![\w.,$\x00])(?<![^\W\d][-/:])"
    r"(?P<neg>\()?(?P<cur>\$)?(?P<num>" + NUM + r")"
    r"(?:\s?(?P<scale>(?i:thousand|million|billion|trillion|bn|mn))\b|(?P<abbr>(?i:k|m|b))\b)?"
    r"(?P<pct>\s?%|\s(?:percent|per cent)\b)?"
    r"(?(neg)\))"
    r"(?![\w%]|[.,]\d)"
)
SCALES = {"thousand": D(1000), "million": D(10) ** 6, "billion": D(10) ** 9, "trillion": D(10) ** 12,
          "bn": D(10) ** 9, "mn": D(10) ** 6, "k": D(1000), "m": D(10) ** 6, "b": D(10) ** 9}
YEAR = re.compile(r"(?:19|20)\d\d")
WORD = re.compile(r"[a-z0-9]+")
SPAN = 8  # ported from the author's earlier private code: this many words in a row is a shared passage


def norm_figure(s):
    """Ported from the author's earlier private code: a figure as a plain decimal string."""
    s = s.replace("$", "").replace(",", "").rstrip("%")
    try:
        return format(decimal.Decimal(s).normalize(), "f")
    except ArithmeticError:
        return s


def shingles(text):
    """Ported from the author's earlier private code: every run of SPAN words in a row, lower-cased."""
    words = WORD.findall(text.lower())
    return {" ".join(words[i:i + SPAN]) for i in range(len(words) - SPAN + 1)}


def parse_figure(m):
    """A FIGURE match as a dict: mantissa (absolute), places, scale, negative, pct, value."""
    num = m.group("num").replace(",", "")
    mantissa = D(num)
    places = len(num.split(".")[1]) if "." in num else 0
    word = m.group("scale") or m.group("abbr")
    scale = SCALES[word.lower()] if word else D(1)
    negative = bool(m.group("neg"))
    value = CTX.multiply(mantissa, scale)
    return {"raw": m.group(0), "mantissa": mantissa, "places": places, "scale": scale,
            "scaled": bool(word), "negative": negative, "pct": bool(m.group("pct")),
            "value": -value if negative else value, "start": m.start(), "end": m.end(),
            "money": bool(m.group("cur"))}


def is_bare_year(fig):
    return (not fig["scaled"] and not fig["pct"] and not fig["negative"] and not fig["money"]
            and "," not in fig["raw"] and YEAR.fullmatch(fig["raw"]) is not None)


def rounds_to(source, fig):
    """Rounding rule: |source| divided by the scale, rounded half-up to the written places,
    equals the written mantissa."""
    v = CTX.divide(abs(source), fig["scale"])
    q = D(1).scaleb(-fig["places"])
    return v.quantize(q, rounding=decimal.ROUND_HALF_UP, context=CTX) == fig["mantissa"]


def significant_digits(fig):
    digits = fig["raw"]
    num = re.sub(r"[^\d.]", "", re.search(r"\d[\d,]*(?:\.\d+)?", digits).group(0).replace(",", ""))
    if "." in num:
        return len(num.replace(".", "").lstrip("0"))
    return len(num.lstrip("0").rstrip("0")) or 1


# --- dates --------------------------------------------------------------------------------------
# MONTHS and the numeric alternatives are ported from the earlier code; the month, quarter and
# mid-month forms are the tie-out's date rule.

MONTHS = {m: i for i, m in enumerate(("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"), 1)}
MON = (r"(?:January|February|March|April|May|June|July|August|September|October|November|December"
       r"|Jan\.?|Feb\.?|Mar\.?|Apr\.?|Jun\.?|Jul\.?|Aug\.?|Sept\.?|Sep\.?|Oct\.?|Nov\.?|Dec\.?)")
DATE = re.compile(
    r"(?<![\w/.\-\x00])(?P<iy>\d{4})[-/.](?P<im>\d{1,2})[-/.](?P<id>\d{1,2})(?![\w/\-]|\.\d)"
    r"|(?<![\w/.\-\x00])(?P<sa>\d{1,2})[-/.](?P<sb>\d{1,2})[-/.](?P<sy>\d{4})(?![\w/\-]|\.\d)"
    r"|\b(?P<m1>" + MON + r") (?P<d1>\d{1,2})(?:st|nd|rd|th)?,? (?P<y1>\d{4})\b"
    r"|\b(?P<d2>\d{1,2})(?P<ord>st|nd|rd|th)? (?P<m2>" + MON + r")(?(ord),?) (?P<y2>\d{4})\b"
    r"|(?:\b(?P<mid>mid)-)?\b(?P<m3>" + MON + r") (?P<y3>\d{4})\b"
    r"|\bQ(?P<q1>[1-4]) (?P<y4>\d{4})\b"
    r"|\b(?P<q2>[1-4])Q (?P<y5>\d{4})\b"
)


def _month(name):
    return MONTHS.get(name[:3].lower())


def date_values(m, order=None):
    """Every reading of one DATE match as (precision, value) pairs.

    precision is 'd' (value a datetime.date), 'm' (value (year, month)) or 'q' (value (year,
    quarter)). A slash date is read in the matter's date_order, on the draft and the record
    alike; with no order it gives both readings, as the earlier code's norm_dates does."""
    g = m.groupdict()
    out = set()

    def day(y, mo, d):
        try:
            out.add(("d", datetime.date(int(y), int(mo), int(d))))
        except (TypeError, ValueError):
            pass

    if g["iy"]:
        day(g["iy"], g["im"], g["id"])
    elif g["sy"]:
        if order in (None, "mdy"):
            day(g["sy"], g["sa"], g["sb"])
        if order in (None, "dmy"):
            day(g["sy"], g["sb"], g["sa"])
    elif g["y1"]:
        day(g["y1"], _month(g["m1"]), g["d1"])
    elif g["y2"]:
        day(g["y2"], _month(g["m2"]), g["d2"])
    elif g["y3"]:
        out.add(("m", (int(g["y3"]), _month(g["m3"]))))
    elif g["y4"]:
        out.add(("q", (int(g["y4"]), int(g["q1"]))))
    elif g["y5"]:
        out.add(("q", (int(g["y5"]), int(g["q2"]))))
    return out


def date_ties(claimed, source):
    """Date rule: a date ties at the precision written."""
    cp, cv = claimed
    sp, sv = source
    if cp == "d":
        return sp == "d" and sv == cv
    if cp == "m":
        if sp == "d":
            return (sv.year, sv.month) == cv
        return sp == "m" and sv == cv
    if sp == "d":
        return sv.year == cv[0] and (sv.month - 1) // 3 + 1 == cv[1]
    if sp == "m":
        return sv[0] == cv[0] and (sv[1] - 1) // 3 + 1 == cv[1]
    return sp == "q" and sv == cv


def show_date(dv):
    p, v = dv
    if p == "d":
        return v.isoformat()
    if p == "m":
        return "%04d-%02d" % v
    return "%04d-Q%d" % v


# --- forms that are not figures -----------------------------------------------------------------
# A court docket number, a clock time and a slash date with a two-digit year each hold digit runs
# that FIGURE would read as figures, since a figure may start after a hyphen, slash or colon that
# follows a digit. not_figures() finds them first. On the draft, claims.tokenise() lists each one
# as not checked with its own reason; on the record, scan() masks them, so a page's figures never
# include them. A two-digit year is never read as a date, because its century would be a guess.
# A ratio whose second term has two digits and fits a clock, such as 1:10, reads as a clock time.

CASE_TYPES = r"(?i:cv|civ|cr|crim|mc|md|mj|ml|po|bk|ap|ad)"  # the case types a federal docket writes
AMPM = r"(?:[AaPp]\.[Mm]\.|[AaPp][Mm](?![A-Za-z]))"
NOT_FIGURES = (
    # a docket number with its case type, 1:23-cv-04567 or 23-cv-4567, and any judges' initials
    ("docket", re.compile(r"(?<![\w.:/\-\x00])(?P<t>(?:\d{1,2}:)?\d{2}-" + CASE_TYPES +
                          r"-\d{1,6}(?:-[A-Za-z]{1,5})*)(?![\w\-])")),
    # a docket number without one, after Case No., Docket No. or Appeal No.: Case No. 21-1234
    ("docket", re.compile(r"\b(?i:case|docket|appeal)\s+No\.\s*(?P<t>\d{2}-\d{1,7})(?![\w\-]|[.,]\d)")),
    # a clock time, 10:30, 14:05, 10:30 a.m. or 9:15:30, or an hour with a.m. or p.m., 9 a.m.
    ("clock", re.compile(r"(?<![\w.,:/$\x00])(?<![^\W\d]-)"
                         r"(?P<t>(?:[01]?\d|2[0-3]):[0-5]\d(?::[0-5]\d)?(?:\s?" + AMPM + r")?"
                         r"|(?:1[0-2]|0?[1-9])\s?" + AMPM + r")(?![\w:%]|[.,]\d)")),
    # a slash date with a two-digit year, 4/3/23; the numbers are checked in not_figures()
    ("short_date", re.compile(r"(?<![\w/.\x00])(?<![^\W\d]-)"
                              r"(?P<t>(?P<sa>\d{1,2})/(?P<sb>\d{1,2})/\d{2})(?![\w/]|[.,]\d)")),
)
NOT_FIGURE_REASONS = {"docket": "docket number", "clock": "clock time", "short_date": "two-digit-year date"}


def not_figures(text, kinds=None):
    """Every docket number, clock time and two-digit-year slash date in text, as (start, end,
    kind) in text order, limited to the kinds named. A slash form counts as a date when both of
    its first two numbers are 1 to 31 and one of them is 12 or under. A later pattern never takes
    a character an earlier one took."""
    out, taken = [], set()
    for kind, rx in NOT_FIGURES:
        if kinds is not None and kind not in kinds:
            continue
        for m in rx.finditer(text):
            a, b = m.span("t")
            if kind == "short_date":
                x, y = int(m.group("sa")), int(m.group("sb"))
                if not (1 <= x <= 31 and 1 <= y <= 31 and min(x, y) <= 12):
                    continue
            if taken.intersection(range(a, b)):
                continue
            taken.update(range(a, b))
            out.append((a, b, kind))
    return sorted(out)


# --- Bates ids ----------------------------------------------------------------------------------

BATES = re.compile(r"(?P<prefix>[A-Z]{1,8})[-_ ]?(?P<digits>\d{4,10})")


def bates_key(text):
    """(prefix, number, digits) for a Bates id, or None."""
    m = BATES.fullmatch(text.strip())
    if not m:
        return None
    return (m.group("prefix"), int(m.group("digits")), m.group("digits"))


def label_norm(label):
    """Exhibit label as looked up: Ex., Exh. and Exhibit stripped, case folded, hyphens and
    spaces inside the label ignored."""
    s = re.sub(r"^\s*(?:Exhibit|Exh\.|Ex\.)\s*", "", label, flags=re.I)
    return re.sub(r"[\s\-]", "", s).casefold()


def column_index(letters):
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def cell_number(raw):
    """A stored cell value as (Decimal, is_percent), or None when it is not a number."""
    s = raw.strip().replace(",", "").replace("$", "")
    neg = s.startswith("(") and s.endswith(")")
    s = s.strip("()")
    pct = s.endswith("%")
    s = s.rstrip("%").strip()
    try:
        v = D(s)
    except (decimal.InvalidOperation, ValueError):
        return None
    if not v.is_finite():
        return None
    return (-v if neg else v, pct)


# --- the index ----------------------------------------------------------------------------------


class Index:
    """The record as the verifier sees it. Built by load(); never written to."""

    def __init__(self, root, date_order=None):
        self.root = root
        self.date_order = date_order  # the matter's order for slash dates, mdy or dmy
        self.files = {}         # record relpath -> sha256 of the bytes on disk
        self.pages = {}         # (prefix, number) -> page dict
        self.order = []         # page keys in reading order
        self.exhibits = {}      # normalised label -> exhibit dict
        self.transcripts = {}   # normalised witness -> transcript dict
        self.data = {}          # file name -> list of rows, row 1 the header
        self.rows = {c: [] for c in ("I1", "I2", "I3", "I4", "I5", "I6")}
        self.notes = []         # byte-order marks stripped, reported apart from the hits
        self.prefixes = set()   # Bates prefixes the record holds
        self.bad_labels = set() # exhibit labels on rows I4 refused, still known to the cite grammar

    # page text and tokens ---------------------------------------------------------------------

    def add_page(self, text, path, line, spelled):
        key = bates_key(spelled)
        prefix, number, digits = key
        pid = prefix + digits
        if (prefix, number) in self.pages:
            other = self.pages[(prefix, number)]
            self.rows["I2"].append("%s: Bates id %s appears twice, at %s line %d and %s line %d"
                                   % (path, pid, other["path"], other["line"], path, line))
            return
        letters = sum(1 for ch in text if ch.isalnum())
        page = {"id": pid, "prefix": prefix, "number": number, "width": len(digits), "text": text,
                "path": path, "line": line, "thin": letters < THIN}
        page.update(scan(text, self.date_order))
        self.pages[(prefix, number)] = page
        self.order.append((prefix, number))
        self.prefixes.add(prefix)
        if page["thin"]:
            self.rows["I3"].append("%s line %d: page %s is thin (%d letters and digits); it stays indexed"
                                   % (path, line, pid, letters))

    def page(self, prefix, number):
        return self.pages.get((prefix, number))

    def page_id(self, prefix, number, width):
        p = self.pages.get((prefix, number))
        return p["id"] if p else prefix + str(number).zfill(width)

    # lookups ----------------------------------------------------------------------------------

    def exhibit(self, label):
        return self.exhibits.get(label_norm(label))

    def transcript(self, witness):
        return self.transcripts.get(witness.casefold())

    def data_file(self, name):
        if name in self.data:
            return name, self.data[name]
        for k, v in self.data.items():
            if k.casefold() == name.casefold():
                return k, v
        return None, None

    def label_prefixes(self):
        out = set()
        for label in [ex["label"] for ex in self.exhibits.values()] + sorted(self.bad_labels):
            m = re.match(r"[A-Za-z]+", label)
            if m:
                out.add(m.group(0).upper())
        return out

    def grammar_names(self):
        """Names the cite grammar needs to tell a cite from prose. Names only, no record text."""
        return {"labels": sorted(set(self.exhibits) | self.bad_labels), "label_prefixes": sorted(self.label_prefixes()),
                "bates_prefixes": sorted(self.prefixes), "witnesses": sorted(self.transcripts),
                "data_files": sorted(self.data)}

    # search for hints -------------------------------------------------------------------------

    def all_texts(self):
        """(label, text, kind) for every page and every transcript page, in reading order."""
        for key in self.order:
            p = self.pages[key]
            yield p["id"], p, "page"
        for w in sorted(self.transcripts):
            t = self.transcripts[w]
            for pg in t["pages"]:
                yield "%s %s %d" % (t["witness"], "Dep.", pg), t["page_scan"][pg], "transcript"

    def find_figure(self, fig, limit=3):
        out = []
        for label, scanned, _ in self.all_texts():
            if any(s["pct"] == fig["pct"] and rounds_to(s["value"], fig) for s in scanned["figures"]):
                out.append(label)
            if len(out) >= limit:
                return out
        for name in sorted(self.data):
            for r, row in enumerate(self.data[name], 1):
                if r == 1:
                    continue
                for c, raw in enumerate(row):
                    num = cell_number(raw)
                    if num and cell_ties(num, fig):
                        out.append("%s!%s%d" % (name, col_letters(c), r))
                        if len(out) >= limit:
                            return out
        return out

    def find_date(self, dv, limit=3):
        out = []
        for label, scanned, _ in self.all_texts():
            if any(date_ties(dv, s) for d in scanned["dates"] for s in d["values"]):
                out.append(label)
                if len(out) >= limit:
                    break
        return out

    def find_text(self, quote, limit=3):
        """Where a quotation's words appear: pages sharing a run of SPAN words with it, so a
        quotation with one word changed still finds its source; a shorter quotation is found
        by its normalised text."""
        needle = norm_text(quote).casefold()
        mine = shingles(needle)
        out = []
        if not needle:
            return out
        for label, scanned, _ in self.all_texts():
            hit = (mine & scanned["shingles"]) if mine else (needle in scanned["norm"].casefold())
            if hit:
                out.append(label)
                if len(out) >= limit:
                    break
        return out


def col_letters(index):
    s, n = "", index + 1
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def cell_ties(num, fig):
    """A figure against a stored cell value: the rounding rule on the value, or for a
    percentage also on the value times 100, since a spreadsheet stores 9.5% as 0.095."""
    value, _ = num
    if rounds_to(value, fig):
        return True
    return fig["pct"] and rounds_to(CTX.multiply(value, D(100)), fig)


def scan(text, order=None):
    """Figures and dates on one text, with dates masked before figures are read. A slash date is
    read in the matter's date order, the same order the draft is read in, so a draft date with day
    and month swapped never ties a page's slash date. With no order (a caller outside the tool)
    it gives both readings. Docket numbers, clock times and two-digit-year slash dates are masked
    too, so none of their digits is read as a figure."""
    dates = []
    masked = list(text)
    for m in DATE.finditer(text):
        vals = date_values(m, order)
        if vals:
            dates.append({"raw": m.group(0), "values": sorted(vals, key=show_date), "start": m.start()})
            for i in range(m.start(), m.end()):
                masked[i] = "\x00"
    for a, b, _ in not_figures("".join(masked)):
        for i in range(a, b):
            masked[i] = "\x00"
    masked = "".join(masked)
    figures = [parse_figure(m) for m in FIGURE.finditer(masked)]
    return {"figures": figures, "dates": dates, "norm": norm_text(text), "shingles": shingles(norm_text(text)),
            "text": text}


# --- loading ------------------------------------------------------------------------------------


def _rel(root, path):
    return os.path.relpath(path, root).replace(os.sep, "/")


def ignored(name):
    """A file or folder the operating system writes, never part of the record: a name starting
    with a dot (.DS_Store, which Finder writes when someone opens the folder), Thumbs.db or
    desktop.ini (which Windows Explorer writes). The manifest and every listing skip it."""
    return name.startswith(".") or name.casefold() in IGNORED_NAMES


def _listing(folder):
    """The record files in one folder, sorted, without the ones the operating system writes."""
    return [n for n in sorted(os.listdir(folder)) if not ignored(n)]


def _text(index, path):
    """Read one record file for the index: I6 checks first, then the ported _read."""
    rel = _rel(index.root, path)
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
    except OSError as exc:
        index.rows["I6"].append("%s: unreadable: %s" % (rel, exc.strerror))
        return None, 0
    if raw.startswith(b"\xef\xbb\xbf"):
        index.notes.append("%s: byte-order mark stripped" % rel)
    try:
        raw.decode("utf-8")
        text = _read(path)
    except (UnicodeDecodeError, ValueError) as exc:
        index.rows["I6"].append("%s: not UTF-8 text (%s at byte %d)" % (rel, getattr(exc, "reason", exc),
                                                                       getattr(exc, "start", 0)))
        # keep reading with replacement characters, so the ids, markers and rows still load and
        # the one bad byte is not reported again as a missing page or exhibit; run stops on I6
        text = unicodedata.normalize("NFKC", raw.decode("utf-8", "replace"))
        text = COMMENT.sub(" ", "".join(ch for ch in text if unicodedata.category(ch) != "Cf"))
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return drop_marker(text)


def _csv(index, path, columns=None):
    """Rows of a CSV file after its marker line, with I6 row-length and header checks."""
    rel = _rel(index.root, path)
    text, dropped = _text(index, path)
    if text is None:
        return None, dropped
    rows = [r for r in csv.reader(io.StringIO(text))]
    numbered = [(i + 1 + dropped, r) for i, r in enumerate(rows) if r]
    if not numbered:
        index.rows["I6"].append("%s: no header row" % rel)
        return None, dropped
    header = [h.strip() for h in numbered[0][1]]
    seen = set()
    for h in header:
        if h.casefold() in seen:
            index.rows["I6"].append("%s line %d: header %r repeats" % (rel, numbered[0][0], h))
        seen.add(h.casefold())
    for line, r in numbered[1:]:
        if len(r) != len(header):
            index.rows["I6"].append("%s line %d: %d fields where the header has %d"
                                    % (rel, line, len(r), len(header)))
    return numbered, dropped


def load(root, date_order):
    """Build the Index for <root>/record/. Missing folders are empty, not errors. date_order is
    matter.json's order for slash dates, mdy or dmy, applied to every page, transcript and cell."""
    if date_order not in ("mdy", "dmy"):
        raise ValueError("date_order must be mdy or dmy, not %r" % (date_order,))
    index = Index(root, date_order)
    base = os.path.join(root, "record")
    for dirpath, dirs, names in os.walk(base):
        dirs[:] = sorted(d for d in dirs if not ignored(d))
        for name in sorted(n for n in names if not ignored(n)):
            full = os.path.join(dirpath, name)
            index.files[_rel(root, full)] = sha256_file(full)

    pages_dir = os.path.join(base, "pages")
    if os.path.isdir(pages_dir):
        for name in _listing(pages_dir):
            full = os.path.join(pages_dir, name)
            if not os.path.isfile(full):
                continue
            stem, ext = os.path.splitext(name)
            if ext.lower() != ".txt" or bates_key(stem) is None or " " in stem:
                index.rows["I1"].append("%s line 1: file name is not a Bates id" % _rel(root, full))
                continue
            text, dropped = _text(index, full)
            if text is not None:
                index.add_page(text, _rel(root, full), 1 + dropped, stem)

    docs_dir = os.path.join(base, "documents")
    sep = re.compile(r"^\s*===\s*(.*?)\s*===\s*$")
    if os.path.isdir(docs_dir):
        for name in _listing(docs_dir):
            full = os.path.join(docs_dir, name)
            if not os.path.isfile(full):
                continue
            rel = _rel(root, full)
            text, dropped = _text(index, full)
            if text is None:
                continue
            current, start, buf, bad = None, None, [], False

            def flush():
                if current:
                    index.add_page("\n".join(buf), rel, start, current)
                elif "".join(buf).strip() and not bad:
                    index.rows["I1"].append("%s line %d: text before the first separator has no Bates id"
                                            % (rel, start))

            for i, line in enumerate(text.split("\n"), 1 + dropped):
                m = sep.match(line)
                if not m:
                    if start is None:
                        start = i
                    buf.append(line)
                    continue
                flush()
                spelled = m.group(1)
                bad = bates_key(spelled) is None
                if bad:
                    index.rows["I1"].append("%s line %d: separator %r is not a Bates id" % (rel, i, spelled))
                current = None if bad else spelled
                start, buf = i, []
            flush()

    _load_exhibits(index, os.path.join(base, "exhibits.csv"))
    _load_transcripts(index, base)
    data_dir = os.path.join(base, "data")
    if os.path.isdir(data_dir):
        for name in _listing(data_dir):
            full = os.path.join(data_dir, name)
            if not os.path.isfile(full):
                continue
            if name.lower().endswith(".csv"):
                rows, _ = _csv(index, full)
                if rows is not None:
                    index.data[name] = [r for _, r in rows]
            elif name.lower().endswith(".xlsx"):
                index.rows["I6"].append("%s: .xlsx is not in this release (stage 4); export stored values to CSV"
                                        % _rel(root, full))
    return index


def _load_exhibits(index, path):
    if not os.path.isfile(path):
        return
    rel = _rel(index.root, path)
    rows, _ = _csv(index, path)
    if rows is None:
        return
    header = [h.strip().lower() for h in rows[0][1]]
    if header != EXHIBIT_COLUMNS:
        index.rows["I4"].append("%s line %d: columns are %s, expected %s"
                                % (rel, rows[0][0], ", ".join(header), ", ".join(EXHIBIT_COLUMNS)))
        return
    spans = []
    for line, r in rows[1:]:
        if len(r) != len(header):
            continue  # I6 already named the row
        label, title, first, last, fname = [c.strip() for c in r]
        norm = label_norm(label)
        fk, lk = bates_key(first), bates_key(last)
        reasons = []
        if not norm:
            reasons.append("empty exhibit label")
        elif norm in index.exhibits:
            reasons.append("label %s repeats" % label)
        if fk is None or (fk[0], fk[1]) not in index.pages:
            reasons.append("first_page %s is not in the index" % first)
        if lk is None or (lk[0], lk[1]) not in index.pages:
            reasons.append("last_page %s is not in the index" % last)
        if fk and lk and (fk[0] != lk[0] or lk[1] < fk[1]):
            reasons.append("last_page %s is before first_page %s" % (last, first))
        if fname and not os.path.isfile(os.path.join(index.root, "record", "documents", fname)):
            reasons.append("file %s is not in record/documents/" % fname)
        if fk and lk and fk[0] == lk[0]:
            for other, (op, a, b) in spans:
                if op == fk[0] and fk[1] <= b and a <= lk[1]:
                    reasons.append("pages overlap exhibit %s" % other)
        if reasons:
            index.rows["I4"].append("%s line %d: %s" % (rel, line, "; ".join(reasons)))
            if norm:
                index.bad_labels.add(norm)
            continue
        spans.append((label, (fk[0], fk[1], lk[1])))
        index.exhibits[norm] = {"label": label, "title": title, "prefix": fk[0], "first": fk[1],
                                "last": lk[1], "width": len(fk[2]), "file": fname, "line": line}


TMARK = re.compile(r"^\[(\d+):(\d+)\]\s?(.*)$")


def _load_transcripts(index, base):
    tdir = os.path.join(base, "transcripts")
    named = {}
    tcsv = os.path.join(base, "transcripts.csv")
    if os.path.isfile(tcsv):
        rows, _ = _csv(index, tcsv)
        if rows is not None:
            header = [h.strip().lower() for h in rows[0][1]]
            if header[:3] != TRANSCRIPT_COLUMNS:
                index.rows["I5"].append("%s line %d: columns are %s, expected %s"
                                        % (_rel(index.root, tcsv), rows[0][0], ", ".join(header),
                                           ", ".join(TRANSCRIPT_COLUMNS)))
            else:
                for line, r in rows[1:]:
                    if len(r) < 2:
                        continue
                    witness, fname = r[0].strip(), r[1].strip()
                    if not os.path.isfile(os.path.join(tdir, fname)):
                        index.rows["I5"].append("%s line %d: file %s is not in record/transcripts/"
                                                % (_rel(index.root, tcsv), line, fname))
                        continue
                    named[fname] = witness
    if not os.path.isdir(tdir):
        return
    for name in _listing(tdir):
        full = os.path.join(tdir, name)
        if not os.path.isfile(full) or not name.lower().endswith(".txt"):
            continue
        rel = _rel(index.root, full)
        text, dropped = _text(index, full)
        if text is None:
            continue
        lines, order, prev, seen = {}, [], None, set()
        for i, line in enumerate(text.split("\n"), 1 + dropped):
            if not line.strip():
                continue
            m = TMARK.match(line)
            if not m:
                index.rows["I5"].append("%s line %d: no [page:line] marker" % (rel, i))
                continue
            key = (int(m.group(1)), int(m.group(2)))
            if key in seen:
                index.rows["I5"].append("%s line %d: marker [%d:%d] repeats" % (rel, i, key[0], key[1]))
                continue
            if prev is not None and key < prev:
                index.rows["I5"].append("%s line %d: marker [%d:%d] comes after [%d:%d]"
                                        % (rel, i, key[0], key[1], prev[0], prev[1]))
                continue
            seen.add(key)
            prev = key
            lines[key] = m.group(3)
            order.append(key)
        pages = sorted({p for p, _ in order})
        page_scan = {}
        for pg in pages:
            page_scan[pg] = scan("\n".join(lines[k] for k in order if k[0] == pg), index.date_order)
        witness = named.get(name, os.path.splitext(name)[0])
        entry = {"witness": witness, "file": rel, "lines": lines, "order": order, "pages": pages,
                 "page_scan": page_scan, "thin": False}
        index.transcripts[witness.casefold()] = entry
        stem = os.path.splitext(name)[0].casefold()
        index.transcripts.setdefault(stem, entry)
