"""Numbers and dates written in words, read to the value the tie-out checks.

Purpose: read a figure or date the draft spells out, so code can check it like one written in
  digits. It reads cardinals from zero into the
  trillions, with hyphens and "and" ("four thousand eight hundred and twelve", "seventy-five",
  "twelve hundred"); a half, a quarter or three quarters after "and" ("two and a half"); a
  closing scale word as a scale, as the rounding rule treats "2 million"; "percent" or "per
  cent" after the number; a day written as an ordinal before "of", a month and a year ("the
  fourteenth of March 2019"); and a quarter written as an ordinal ("the first quarter of
  2019"). read() takes one phrase and returns its reading or None. find() lists every phrase it
  reads in a text, dates first, and leaves out a lone "one", which in prose is far more often a
  pronoun than a count. A reading is {"kind": "figure", "figure": {...}, "show": "4812"} with
  the figure in the shape record.parse_figure gives, or {"kind": "date", "date": (precision,
  value), "show": "2019-03-14"} in record's date shape. show is the canonical value a proposal
  states and P8 compares (same_value). The case table, CASES, is the stage 3 probe of this file.
Reads: nothing.
Writes: nothing.
Network: none.
Exit codes: none; a library module. Self-test scenario 22 checks the case table through
  check_cases().
"""
import datetime
import decimal
import re

D = decimal.Decimal

UNITS = ("one", "two", "three", "four", "five", "six", "seven", "eight", "nine")
TEENS = ("ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen",
         "nineteen")
TENS = ("twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety")
SMALL = dict([(w, i) for i, w in enumerate(UNITS, 1)] + [(w, i) for i, w in enumerate(TEENS, 10)])
TEN = {w: 10 * i for i, w in enumerate(TENS, 2)}
SCALES = {"thousand": D(1000), "million": D(10) ** 6, "billion": D(10) ** 9, "trillion": D(10) ** 12}
FRACTIONS = {"a half": D("0.5"), "one half": D("0.5"), "a quarter": D("0.25"), "three quarters": D("0.75")}
ORDINAL_DAYS = ("first", "second", "third", "fourth", "fifth", "sixth", "seventh", "eighth", "ninth", "tenth",
                "eleventh", "twelfth", "thirteenth", "fourteenth", "fifteenth", "sixteenth", "seventeenth",
                "eighteenth", "nineteenth", "twentieth")
ORDINAL = dict((w, i) for i, w in enumerate(ORDINAL_DAYS, 1))
ORDINAL.update(("twenty-" + w, 20 + i) for i, w in enumerate(ORDINAL_DAYS[:9], 1))
ORDINAL.update({"thirtieth": 30, "thirty-first": 31})
MONTHS = ("january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
          "november", "december")

NUMBER_WORDS = sorted(list(SMALL) + list(TEN) + ["zero", "hundred"] + list(SCALES), key=len, reverse=True)
_W = r"(?:%s)" % "|".join(NUMBER_WORDS)
_ORD = r"(?:%s)" % "|".join(sorted((k.replace("-", "[- ]") for k in ORDINAL), key=len, reverse=True))
_MON = r"(?:%s)" % "|".join(m.capitalize() for m in MONTHS)
CARDINAL = re.compile(
    r"(?i)(?<![\w-])" + _W + r"(?:(?:\s+|-|\s+and\s+)" + _W + r")*"
    r"(?:\s+and\s+(?:a\s+half|one\s+half|a\s+quarter|three\s+quarters))?"
    r"(?:\s+(?:thousand|million|billion|trillion))?(?:\s+(?:percent|per\s+cent))?(?![\w-])")
DAY_OF = re.compile(r"(?i)(?<![\w-])(?:the\s+)?(?P<day>" + _ORD + r")(?:\s+day)?\s+of\s+(?P<mon>" + _MON +
                    r"),?\s+(?P<year>(?:19|20)\d\d)(?!\w)")
QUARTER = re.compile(r"(?i)(?<![\w-])(?:the\s+)?(?P<q>first|second|third|fourth)\s+quarter\s+of\s+"
                     r"(?P<year>(?:19|20)\d\d)(?!\w)")


def _words(phrase):
    return [w for w in re.split(r"[\s-]+", phrase.strip().lower()) if w]


def _upto99(ws, i):
    """A number from one to ninety-nine at ws[i]: (value, next index) or (None, i)."""
    if i < len(ws) and ws[i] in SMALL:
        return SMALL[ws[i]], i + 1
    if i < len(ws) and ws[i] in TEN:
        if i + 1 < len(ws) and ws[i + 1] in UNITS:
            return TEN[ws[i]] + SMALL[ws[i + 1]], i + 2
        return TEN[ws[i]], i + 1
    return None, i


def _group(ws, i):
    """One group below a thousand: "eight hundred and twelve", "twelve hundred", "seventy-five"."""
    v, j = _upto99(ws, i)
    if v is None:
        return None, i
    if j < len(ws) and ws[j] == "hundred":
        v, j = v * 100, j + 1
        k = j + 1 if j < len(ws) and ws[j] == "and" else j
        rest, k2 = _upto99(ws, k)
        if rest is not None:
            return v + rest, k2
        if k != j:
            return None, i  # "and" with nothing after it
    return v, j


def _cardinal(ws):
    """(value, closing scale) of a cardinal as a list of words, or None. Groups below a thousand
    each take a scale word smaller than the one before; the closing scale is the scale word
    that ends a single group ("two million"), else 1."""
    if ws == ["zero"]:
        return D(0), D(1)
    total, i, last = 0, 0, None
    groups = 0
    while i < len(ws):
        g, i = _group(ws, i)
        if g is None:
            return None
        groups += 1
        if i < len(ws) and ws[i] in SCALES:
            s = SCALES[ws[i]]
            if last is not None and s >= last:
                return None
            total, last, i = total + g * s, s, i + 1
            if i < len(ws) and ws[i] == "and":
                i += 1
                if i == len(ws):
                    return None
        elif i == len(ws):
            total += g
        else:
            return None
    if groups == 1 and ws[-1] in SCALES:
        return D(total), SCALES[ws[-1]]
    return D(total), D(1)


def _figure(phrase):
    text = " ".join(phrase.split()).lower()
    pct = False
    m = re.search(r"\s+(?:percent|per cent)$", text)
    if m:
        pct, text = True, text[:m.start()]
    scale_word = ""
    m = re.search(r"\s+and\s+(a half|one half|a quarter|three quarters)(?:\s+(thousand|million|billion|trillion))?$",
                  text)
    frac = D(0)
    if m:
        frac, scale_word, text = FRACTIONS[m.group(1)], m.group(2) or "", text[:m.start()]
    ws = _words(text)
    if not ws:
        return None
    read = _cardinal(ws)
    if read is None:
        return None
    whole, scale = read
    if frac:
        if scale != 1:
            return None  # "two million and a half": the fraction belongs before the scale word
        mantissa, scale = whole + frac, SCALES[scale_word] if scale_word else D(1)
    else:
        mantissa = whole / scale
    places = len(str(frac).split(".")[1]) if frac else 0
    mantissa = mantissa.quantize(D(1).scaleb(-places)) if places else D(int(mantissa))
    value = mantissa * scale
    scaled = scale != 1
    word = {D(1000): "thousand", D(10) ** 6: "million", D(10) ** 9: "billion", D(10) ** 12: "trillion"}.get(scale, "")
    raw = str(mantissa) + (" " + word if scaled else "") + ("%" if pct else "")
    fig = {"raw": raw, "mantissa": mantissa, "places": places, "scale": scale, "scaled": scaled,
           "negative": False, "pct": pct, "value": value, "start": 0, "end": len(phrase), "money": False}
    show = format(value.normalize(), "f") if value else "0"
    return {"kind": "figure", "figure": fig, "show": show + ("%" if pct else "")}


def _date(phrase):
    text = " ".join(phrase.split())
    m = DAY_OF.fullmatch(text)
    if m:
        day = ORDINAL[re.sub(r"[- ]+", "-", m.group("day").lower())]
        try:
            d = datetime.date(int(m.group("year")), MONTHS.index(m.group("mon").lower()) + 1, day)
        except ValueError:
            return None
        return {"kind": "date", "date": ("d", d), "show": d.isoformat()}
    m = QUARTER.fullmatch(text)
    if m:
        q = ("first", "second", "third", "fourth").index(m.group("q").lower()) + 1
        y = int(m.group("year"))
        return {"kind": "date", "date": ("q", (y, q)), "show": "%04d-Q%d" % (y, q)}
    return None


def read(phrase):
    """The reading of one phrase written in words, or None when it is not one this file reads."""
    if not isinstance(phrase, str) or not phrase.strip():
        return None
    return _date(phrase) or _figure(phrase)


def find(text):
    """Every phrase read() reads in text, as (start, end, reading) in text order: date phrases
    first, then cardinals outside them. A run of number words that does not read whole is read
    piece by piece between its "and"s, so "two and three" gives two and three."""
    out, taken = [], []
    for rx in (DAY_OF, QUARTER):
        for m in rx.finditer(text):
            r = _date(m.group(0))
            if r:
                out.append((m.start(), m.end(), r))
                taken.append((m.start(), m.end()))
    for m in CARDINAL.finditer(text):
        if any(a < m.end() and m.start() < b for a, b in taken):
            continue
        pieces = [(m.start(), m.end())]
        if _figure(m.group(0)) is None:
            pieces, pos = [], m.start()
            for sep in re.finditer(r"\s+and\s+", m.group(0)):
                pieces.append((pos, m.start() + sep.start()))
                pos = m.start() + sep.end()
            pieces.append((pos, m.end()))
        for a, b in pieces:
            r = _figure(text[a:b])
            if r and text[a:b].strip().lower() != "one":
                out.append((a, b, r))
    return sorted(out, key=lambda x: x[0])


def same_value(stated, reading):
    """P8: the value a proposal states equals the reading. A figure compares as a number, so
    "4812", "4,812" and 4812 agree, and a percent must say so; a date compares as its canonical
    text, 2019-03-14, 2019-03 or 2019-Q1."""
    if reading is None or isinstance(stated, bool) or not isinstance(stated, (str, int, float)):
        return False
    s = str(stated).strip()
    if reading["kind"] == "date":
        return s == reading["show"]
    pct = s.endswith("%")
    s = s.rstrip("%").replace(",", "").replace("$", "").strip()
    try:
        return pct == reading["figure"]["pct"] and D(s) == reading["figure"]["value"]
    except decimal.InvalidOperation:
        return False


# --- the case table -----------------------------------------------------------------------------

# (phrase, what read() gives as show, or None when it reads nothing)
CASES = [
    ("four thousand eight hundred and twelve", "4812"),
    ("four thousand eight hundred", "4800"),
    ("seventy-five", "75"),
    ("Seventy five", "75"),
    ("one hundred and five", "105"),
    ("twelve hundred", "1200"),
    ("four thousand and twelve", "4012"),
    ("nineteen", "19"),
    ("zero", "0"),
    ("two million", "2000000"),
    ("two and a half million", "2500000"),
    ("three million four hundred thousand", "3400000"),
    ("two and a half percent", "2.5%"),
    ("two and a half per cent", "2.5%"),
    ("twelve percent", "12%"),
    ("six and three quarters", "6.75"),
    ("the fourteenth of March 2019", "2019-03-14"),
    ("fourteenth of March, 2019", "2019-03-14"),
    ("the twenty-first day of June 2022", "2022-06-21"),
    ("the thirty-first of December 2023", "2023-12-31"),
    ("the first quarter of 2019", "2019-Q1"),
    ("the fourth quarter of 2023", "2023-Q4"),
    ("the thirtieth of February 2023", None),
    ("the fifth quarter of 2023", None),
    ("hundred", None),
    ("two three", None),
    ("five thousand thousand", None),
    ("thousand million", None),
    ("two and", None),
    ("two million and a half", None),
    ("units", None),
    ("", None),
]
# (text, the phrases find() lists in it, in order)
FIND_CASES = [
    ("planned only four thousand eight hundred units for Q4 2023 and none for the first quarter of 2024.",
     ["four thousand eight hundred", "the first quarter of 2024"]),
    ("the deposition testimony of two witnesses, one unit and a lower one", ["two"]),
    ("a twenty-year term, two-thirds of it, on the twenty-first of June 2022",
     ["the twenty-first of June 2022"]),
    ("a margin of two and a half percent over seventy-five units", ["two and a half percent", "seventy-five"]),
    ("between two and three shifts", ["two", "three"]),
    ("the first deliveries and the second supplier", []),
]


def check_cases():
    """Every case table row that reads otherwise than the table says, as text; empty when all hold."""
    bad = []
    for phrase, want in CASES:
        r = read(phrase)
        got = r["show"] if r else None
        if got != want:
            bad.append("read(%r) gives %r, the table says %r" % (phrase, got, want))
        elif r and not same_value(want, r):
            bad.append("same_value(%r) refuses its own reading of %r" % (want, phrase))
    for text, want in FIND_CASES:
        got = [text[a:b] for a, b, _ in find(text)]
        if got != want:
            bad.append("find(%r) gives %r, the table says %r" % (text, got, want))
    return bad
