"""Read the text of an evidence file, page by page, with the standard library.

Purpose: `read(path)` returns each page's text for a PDF with a text layer, a Word file, an Excel
  workbook (one page per visible sheet), a CSV, a plain text file or an email saved as .eml. A
  scanned page has no text layer, so it comes back empty and a person types it into the file's
  cover. Nothing here guesses: a file this reader cannot read returns a plain reason, and the check
  falls back to the typed cover.
What a reader cannot see is not text. On a PDF page these are left out: white or transparent text,
  text outside the page, clipped text, tiny text, text on a layer that is switched off, and text
  under a filled shape or an image. An invisible text layer, the way a scanner stores its optical
  character recognition, is machine output nobody has checked, so it is left out too: a page that
  is an image with such a layer has no text, and a person types it. Invisible text stays only where
  no image covers the page and a drawn shape sits under it, as when a writer draws its letters as
  shapes. Hidden Excel sheets, rows and columns are left out, and pages number by visible sheets. A
  Word file with hidden text is refused in words, as tracked changes are. An email reads as the
  HTML a person sees, with hidden parts left out, and is refused when its plain part disagrees. A
  style-sheet rule hides text only when the reader can apply its selector exactly and the sheet
  comes first; text a rule may hide that the reader cannot be sure of is left out, and the page
  is read only in part, so a person types it. In Markdown evidence every tag is blanked, attributes
  included, and what a rendered page may not show is left out, for a person to write plainly.
Reads: the one file it is given. Writes: nothing.
Network: none. Standard library only, Python 3.9 and later.
Caps: work and memory are counted for each file, never timed, so the same file gives the same page
  on every run. A file over a cap is refused in words. The caps are the MAX_ names below.
Limits: no optical character recognition; encrypted PDFs are not read; a font with no way back to
  Unicode reads as no text; a form nested too deep or a filled form's values are not read, and the
  page says it was read in part; an Excel date reads as its serial number and a percent as its fraction;
  a Word file's comments are not read, and the notes count each one that holds words.
  What cannot be decided counts as seen: white text over an image, a bar that is rotated or curved,
  a soft mask, a pattern fill, text on text, and Excel font colours and number formats. A style
  sheet linked from outside the email is not fetched, and a style that shows again what a rule
  hides is not followed, so that text stays left out. A style for dark mode only is not followed.
"""
import base64
import bisect
import csv
import email
import email.policy
import email.utils
import html as html_module
import io
import math
import re
import sys
import zipfile
import zlib
from pathlib import Path
from xml.etree import ElementTree

READABLE = (".pdf", ".docx", ".xlsx", ".csv", ".eml", ".txt")
MAX_FILE = 256 * 1024 * 1024
MAX_TEXT = 16 * 1024 * 1024  # characters of text in one file, and in all of a finding's files: the check's index
#   of every page it reads holds about 30 bytes a character
MAX_FIGURES = 500 * 1000  # runs of digits in one file, and in all of a finding's files: about 1.4 KB each in that index
MAX_STREAM = 64 * 1024 * 1024
MAX_DEPTH = 40
MAX_FORM_DEPTH = 6
MAX_DECODED = 1024 * 1024 * 1024  # bytes sliced or decoded from one file, repeats included
MAX_STEPS = 60 * 1000 * 1000  # tokens, table entries, and the weightier work below at its own rate, for one file
GLYPH_STEPS = 6  # the steps one glyph costs
PAINT_STEPS = 4  # the steps one painted shape costs
MAX_PAGE_GLYPHS = 500 * 1000
MAX_PAGE_PAINTS = 200 * 1000
MAX_PAGE_FORMS = 10 * 1000
MAX_PATH = 1024  # subpaths held before a path is kept as its outline only
MAX_ROW = 1024 * 1024  # bytes in one predictor row
MAX_FONT_TABLE = 1024 * 1024  # entries in one font's map or widths
MAX_SAVED = 64 * 1024  # graphics states saved by q and not yet restored
MAX_ZIP_DIRECTORY = 16 * 1024 * 1024  # bytes in a Word or Excel file's list of parts
ENTRY_COST = 256  # bytes one object held in the tables costs
FONT_COST = 16 * 1024  # bytes one font costs
PARSED_COST = 8  # a parsed object is held in memory at about this many times its size in the file
MAX_SHEETS = 1000
MAX_HEADERS = 1024 * 1024  # email header bytes in one message
MAX_HEADER = 256 * 1024  # bytes in one email header
MAX_PARTS = 1000  # parts in one email
MAX_ENCODED_WORDS = 1000  # =?...?= words in one email's headers: the header parser's memory grows with their square
# The header parser's work grows with the square of the spaces and punctuation in one header, so they are counted
# before parsing in each header the reader asks it to read: 10,000 in one, enough for a To line of about 700 named
# people, and 20,000 in all, under a second and a half at worst.
MAX_HEADER_SEPARATORS = 10 * 1000
MAX_SEPARATORS = 20 * 1000
PARSED_HEADERS = ("from", "to", "date", "subject", "content-type", "content-disposition", "content-transfer-encoding",
                  "content-id")
SEPARATORS = ' \t()<>[]:;@\\,."=/?'
MAX_EMAIL = 64 * 1024 * 1024  # the email parser holds several copies, so it gets a smaller limit than other files
MAX_WORD_TAGS = 6 * 1000 * 1000  # the Word reader keeps every paragraph, at many times its size in the file
MAX_SHEET_TAGS = 2 * 1000 * 1000  # tags in one workbook part, about four a cell: its parsed tree takes about 80 bytes a tag
TAG_STEPS = 8  # the steps one HTML tag costs
TOO_MUCH = "the file is too large or too tangled for this reader; save a smaller copy"
TOO_MUCH_TEXT = "the file holds more text than the check can hold; cite a shorter extract of it"
TANGLED_HEADERS = "the email's header lines are too tangled to read"
DAMAGED = "the file is damaged or built in a way this reader cannot follow; save a fresh copy"
OLE_HEADER = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
_DIGITS = re.compile(r"\d+")


class Unreadable(Exception):
    """This reader cannot read the file; args[0] says why, in plain words."""


class Damaged(Exception):
    """A PDF's cross-reference table cannot be trusted, so the file is read by scanning instead."""


class Spent:
    """What one read has used so far, and what it noticed beside the text."""

    def __init__(self):
        self.bytes = 0
        self.steps = 0
        self.partly = []
        self.hidden = {}
        self.notes = []


_spent = Spent()


def _spend_bytes(n):
    _spent.bytes += n
    if _spent.bytes > MAX_DECODED:
        raise Unreadable(TOO_MUCH)


def _spend_steps(n):
    _spent.steps += n
    if _spent.steps > MAX_STEPS:
        raise Unreadable(TOO_MUCH)


def _check_text_fits(pages):
    """The check indexes every page it is given, so what comes back here has to fit that index."""
    total = figures = 0
    for page in pages:
        total += len(page)
        if total > MAX_TEXT:
            raise Unreadable(TOO_MUCH_TEXT)
        for _ in _DIGITS.finditer(page):
            figures += 1
            if figures > MAX_FIGURES:
                raise Unreadable(TOO_MUCH_TEXT)


def read(path):
    """{"pages": [text, ...], "problem": None or a plain reason, "partly": [page numbers read only in
    part], "hidden": {page number: words a reader cannot see}, "notes": [plain sentences]}.
    Never raises on a bad file."""
    global _spent
    _spent = Spent()
    out = {"pages": [], "problem": None, "partly": [], "hidden": {}, "notes": []}
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix not in READABLE:
        out["problem"] = "this reader does not read {} files".format(suffix or "these")
        return out
    try:
        if path.stat().st_size > MAX_FILE:
            raise Unreadable("the file is over 256 MB")
        reader = {".pdf": read_pdf, ".docx": read_docx, ".xlsx": read_xlsx, ".csv": read_csv, ".eml": read_eml,
                  ".txt": read_txt}[suffix]
        pages = reader(path)
        _check_text_fits(pages)
        out.update(pages=pages, partly=_spent.partly, hidden=_spent.hidden, notes=_spent.notes)
    except Unreadable as exc:
        out["problem"] = exc.args[0]
    except Exception:  # the promise above: every failure comes back as a reason, whatever raised it
        out["problem"] = DAMAGED
    return out


# ---------------------------------------------------------------- the simple formats


def _decode_text(data, what):
    """Text by its byte-order mark, UTF-8 otherwise. Leftover NUL means the encoding is not known."""
    encoding = "utf-16" if data[:2] in (b"\xff\xfe", b"\xfe\xff") else "utf-8-sig"
    text = data.decode(encoding, "replace")
    if len(text) > MAX_TEXT:
        raise Unreadable(TOO_MUCH_TEXT)
    if "\0" in text:
        raise Unreadable("the {} holds NUL characters, so its encoding is not known".format(what))
    return text


def read_csv(path):
    text = _decode_text(path.read_bytes(), "CSV")
    # Fields and rows are counted before parsing, because the parser holds them all until a row ends.
    _spend_steps(text.count(",") + text.count("\n") + text.count("\r"))
    csv.field_size_limit(MAX_FILE)
    return ["\n".join("\t".join(row) for row in csv.reader(io.StringIO(text, newline="")))]


def read_txt(path):
    return [_decode_text(path.read_bytes(), "text file")]


_VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}
_UNSHOWN = {"head", "title", "template"}
_RAW_TEXT = {"style", "script"}
_INLINE = {"a", "abbr", "b", "bdi", "bdo", "big", "cite", "code", "em", "font", "i", "ins", "kbd", "mark", "nobr", "q",
           "s", "small", "span", "strike", "strong", "sub", "sup", "tt", "u", "var", "wbr", "o:p"}
_CELL = {"td", "th"}
# Words one of which a style sheet holds when a rule in it may hide text. A sheet with none of them is passed over.
_HIDING = ("display", "visibility", "mso-hide", "font", "opacity", "height", "width", "color", "position", "clip",
           "transform", "text-indent", ":-")
_WHITE_INK = {"#fff", "#ffffff", "white", "rgb(255,255,255)"}
# A colour with no paint: transparent, or an alpha of nothing, as in rgba(0,0,0,0) or rgb(0 0 0 / 0).
_NO_INK = re.compile(r"transparent|(?:rgb|hsl)a?\((?:(?:[^,/()]*,){3}|[^,/()]*/)0*(?:\.0*)?%?\)")
_FAR = re.compile(r"-0*[1-9][0-9]{2,}(?:\.[0-9]*)?(?:[a-z]+|%)?")  # a hundred units or more to the left or the top
_CSS_COMMENT = re.compile(r"/\*.*?(?:\*/|\Z)", re.S)
_ZERO = re.compile(r"[+-]?(?:0+(?:\.0*)?|\.0+)(?:[a-z]+|%)?")  # 0, 0px, 0.0em, 0%: a size of nothing
_TAG_START = re.compile(r"</?([a-zA-Z][^\s/>]*)")
_TAG_STOP = re.compile(r"[>\"']")
_ATTR = re.compile(r"""([^\s=/>"']+)(?:\s*=\s*("[^"]*"|'[^']*'|[^\s>]+))?""")
_HTML_SPACE = re.compile(r"[ \t\n\f\r]+")
_ASCII_LOWER = str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz")
# A CSS name in ASCII, or any character past it, so no Unicode table decides a match and every Python agrees.
_CSS_NAME = r"[a-z0-9_\-\x80-\U0010ffff]+"
_COMPOUND = re.compile(r"([a-z][a-z0-9-]*|\*)?((?:[.#]" + _CSS_NAME + r")*)")
_COMPOUND_PART = re.compile(r"[.#]" + _CSS_NAME)
_ATTRIBUTE_SELECTOR = re.compile(r"\[\s*([a-z_:][-a-z0-9_:.]*)\s*(?:([~|^$*]?=)\s*(\"[^\"]*\"|'[^']*'|[^\]\s]+)"
                                 r"(?:\s+[is])?\s*)?\]")
# At-rules whose blocks select nothing on the page a person reads, which is light: a block for dark mode only is one.
_SELECTS_NOTHING = re.compile(r"@(?:-[a-z]+-)?(?:keyframes|font-face|page|counter-style|property|font-feature-values)"
                              r"|@media(?!.*(?:,|not|\bor\b))(?=.*\(\s*prefers-color-scheme\s*:\s*dark\s*\))", re.S)
_CSS_TOKEN = re.compile(r"\"(?:\\.|[^\"\\\n])*\"?|'(?:\\.|[^'\\\n])*'?|url\([^)\"']*\)?|([{};])\s*", re.I)
_BLANK = set(" \t\n\r\f\v\xa0\xad\u034f\u200b\u200c\u200d\u200e\u200f\u2060\ufeff")  # what fills a preheader: no text


def _tag_end(text, pos):
    """The position of the > that ends a tag, past any quoted attribute value, or -1."""
    while True:
        stop = _TAG_STOP.search(text, pos)
        if stop is None:
            return -1
        if stop.group(0) == ">":
            return stop.start()
        closing = text.find(stop.group(0), stop.end())
        if closing < 0:
            return text.find(">", stop.end())
        pos = closing + 1


def _style_flat(value):
    return "".join(_CSS_COMMENT.sub("", html_module.unescape(value)).split()).lower()


def _declarations(flat):
    """{property: value} of a style with its spaces taken out. A later line wins, as in a browser."""
    out = {}
    for part in flat.split(";"):
        prop, colon, value = part.partition(":")
        if colon:
            out[prop] = value.replace("!important", "")
    return out


def _style_hides(style):
    """True when a style keeps text from a person's eye. Each property is read whole, so font-size:0.9em shows. A box
    of no height or width hides what it clips, and the font shorthand hides at a size of nothing, as in font:0/0 a."""
    style = _CSS_COMMENT.sub("", style)
    found = _declarations("".join(style.split()).lower())
    fonts = [value for prop, colon, value in (part.partition(":") for part in style.lower().split(";"))
             if colon and prop.strip() == "font"]

    def nothing(prop):
        return _ZERO.fullmatch(found.get(prop, "x")) is not None

    return (found.get("display") == "none" or found.get("visibility") == "hidden" or found.get("mso-hide") == "all"
            or any(nothing(prop) for prop in ("font-size", "opacity", "max-height"))
            or any(_NO_INK.fullmatch(found.get(prop, "x")) for prop in ("color", "-webkit-text-fill-color"))
            or (found.get("overflow") == "hidden" and any(nothing(prop) for prop in ("height", "width", "max-width")))
            or (bool(fonts) and any(_ZERO.fullmatch(word.split("/")[0]) for word in fonts[-1].split())))


def _style_doubt(style, white=False):
    """True when a style may keep text from a person's eye in a way the reader cannot settle: a box placed on its
    own, clipped or transformed, text pushed a hundred units or more out to the left or the top, and with white,
    white ink with no background of its own, as a style sheet's class may give it."""
    found = _declarations(_style_flat(style))
    return (found.get("position") in ("absolute", "fixed") or any(prop in found for prop in ("clip", "clip-path", "transform"))
            or any(_FAR.fullmatch(found.get(prop, "x")) for prop in ("left", "top", "text-indent", "margin-left", "margin-top"))
            or (white and found.get("color") in _WHITE_INK and not any(prop.startswith("background") for prop in found)))


def _hides(attrs):
    """True when an element's own attributes keep it from a person's eye."""
    return "hidden" in attrs or _style_hides(html_module.unescape(attrs.get("style", "")))


def _white_ink(attrs):
    colour = _style_flat(attrs.get("color", ""))
    return colour in _WHITE_INK or _declarations(_style_flat(attrs.get("style", ""))).get("color") in _WHITE_INK


def _paints_behind(attrs):
    style = _style_flat(attrs.get("style", ""))
    return "bgcolor" in attrs or "background" in attrs or "background" in style


def _css_rules(css):
    """(selectors, declarations, nested) for each rule of a style sheet, comments left out. A rule nested in another
    block, as inside @media, holds only on some screens, and one inside @keyframes or a block for dark mode only
    selects nothing. An at-rule statement such as @import or @charset ends at its semicolon, never one in quotes or
    url(...), so the rule after it holds. Past MAX_DEPTH blocks deep the reader stops, and any element may be reached."""
    css = re.sub(r"/\*.*?(?:\*/|\Z)|<!--|-->", " ", css, flags=re.S).lstrip()
    stack, start, opened = [], 0, -1  # open blocks: [prelude, where its body starts, selects nothing]
    for token in _CSS_TOKEN.finditer(css):
        if (mark := token.group(1)) is None or (mark == ";" and not css.startswith("@", start)):
            continue  # quoted text, url(...) or a semicolon that ends no at-rule statement
        if mark == "{" and len(stack) >= MAX_DEPTH:
            yield "*", "display:none", True
            return
        if mark == "{":
            prelude = css[start:token.start()].strip().translate(_ASCII_LOWER)
            stack.append([prelude, token.end(), bool(stack and stack[-1][2]) or _SELECTS_NOTHING.match(prelude) is not None])
            opened = token.end()
        elif mark == "}" and stack:
            prelude, body, nothing = stack.pop()
            if body == opened and not nothing and not prelude.startswith("@"):  # the last block opened holds no block
                yield prelude, css[body:token.start()], bool(stack)
        start = token.end()  # where the next prelude starts


def _compound(match):
    name = match.group(1)
    return (None if name in (None, "*") else name), frozenset(_COMPOUND_PART.findall(match.group(2)))


def _attribute_needs(match):
    """What an element must carry for one attribute selector to reach it: [class=a] and [class~=a] need the class
    .a, [id=a] needs #a, and any other, as [class*=hide] or [title], needs the attribute itself, as @class."""
    name, op, value = match.group(1), match.group(2), (match.group(3) or "").strip("\"'")
    words = [word for word in _HTML_SPACE.split(value) if word]
    if name == "class" and op in ("=", "~=") and words:
        return {"." + word for word in words}
    if name == "id" and op == "=" and len(words) == 1:
        return {"#" + words[0]}
    return {"@" + name}


def _subject(selector):
    """(exact, (element name or None, frozenset of .class, #id and @attribute)) for one selector of a hiding rule.
    It is exact when the selector is one compound such as p.note or #preview, which the reader tests whole on an
    element's own tag. Otherwise the compound is what the reader can test of the selector's last part, which an
    element must carry for the rule to reach it: .preheader of .wrapper .preheader, .gmail-fix of
    *[class="gmail-fix"], @title of [title], or every element for *."""
    whole = _COMPOUND.fullmatch(selector)
    if whole and selector != "*":
        return True, _compound(whole)
    found = []

    def mark(match):
        found.append(match)
        return "\x00{}\x00".format(len(found) - 1)

    last = re.split(r"[ \t\n\r\f>+~]+", _ATTRIBUTE_SELECTOR.sub(mark, selector).strip(" \t\n\r\f"))[-1]
    needs = set()
    for k in re.findall(r"\x00([0-9]+)\x00", last):
        needs |= _attribute_needs(found[int(k)])
    last = re.sub(r"\x00[0-9]+\x00|\[[^\]]*\]?|::?[a-z-]+(?:\([^)]*\)?)?", "", last)
    part = _COMPOUND.fullmatch(last)
    name, carried = _compound(part) if part else (None, frozenset())
    return False, (name, frozenset(carried | needs))


class _Sheets:
    """The hiding rules of every style sheet in an HTML body, and where each sheet starts."""

    def __init__(self, text):
        # By one simple selector an element must carry: {compound: [start of the first sheet that hides it exactly, or
        # None; True when a rule the reader cannot apply exactly may reach it]}.
        self.rules = {}
        # Outlook marks a tag data-ogsc or data-ogsb as it paints it dark, so a rule on them needs a tag marked so.
        self.light = re.search(r"<[a-z][^<>]*\sdata-ogs[cb]", text, re.I) is None

    def add(self, start, css, media):
        if _SELECTS_NOTHING.match("@media " + media) or not any(word in "".join(css.split()).lower() for word in _HIDING):
            return
        _spend_steps(TAG_STEPS * css.count("}") + css.count(";"))
        for selectors, body, nested in _css_rules(css):
            hides = _style_hides(body)
            if not hides and not _style_doubt(body, white=True):
                continue
            for selector in selectors.split(","):
                selector = selector.strip(" \t\n\r\f")
                if not selector or (self.light and re.search(r"\[\s*data-ogs[cb]", selector)):
                    continue
                exact, compound = _subject(selector)
                name, carried = compound
                key = min(carried) if carried else ("<" + name if name else "*")
                entry = self.rules.setdefault(key, {}).setdefault(compound, [None, False])
                if hides and exact and not nested and media in ("", "all", "screen"):
                    entry[0] = start if entry[0] is None else entry[0]
                else:
                    entry[1] = True

    def verdict(self, at, name, attrs):
        """"hidden" when a sheet before the element at `at` hides it exactly, "unsure" when a rule may reach it and
        the reader cannot be sure, as for a sheet after it, or None."""
        if not self.rules:
            return None
        carried = {"." + word for word in _HTML_SPACE.split(attrs.get("class", "").translate(_ASCII_LOWER)) if word}
        if attrs.get("id"):
            carried.add("#" + attrs["id"].translate(_ASCII_LOWER))
        carried |= {"@" + key for key in attrs}
        _spend_steps(len(carried))
        unsure = False
        for key in sorted(carried | {"<" + name, "*"}):
            for (rule_name, needs), (first, inexact) in self.rules.get(key, {}).items():
                _spend_steps(1)
                if (rule_name is None or rule_name == name) and needs <= carried:
                    if first is not None and first < at:
                        return "hidden"
                    unsure = True
        return "unsure" if unsure else None


def _html_events(text, spend):
    """The tags of an HTML body in order, with the text between them: ("text", start, end), ("<", position) for a <
    that starts no tag, ("style", tag start, sheet start, sheet end, attributes start, tag end) and ("tag", tag start,
    name, closing, attributes start, tag end). A comment, a declaration and a script are passed over, and so is all
    after a tag left open."""
    i, n = 0, len(text)
    while i < n:
        lt = text.find("<", i)
        if lt < 0:
            yield "text", i, n
            return
        if lt > i:
            yield "text", i, lt
        if text.startswith("<!--", lt):
            end = text.find("-->", lt + 4)
            i = end + 3 if end >= 0 else n
            continue
        if text[lt + 1:lt + 2] in ("!", "?"):
            end = text.find(">", lt)
            i = end + 1 if end >= 0 else n
            continue
        if spend:
            _spend_steps(TAG_STEPS)
        match = _TAG_START.match(text, lt)
        if match is None:
            yield "<", lt
            i = lt + 1
            continue
        end = _tag_end(text, match.end())
        if end < 0:
            return
        name = match.group(1).lower()
        closing = text[lt + 1] == "/"
        i = end + 1
        if name in _RAW_TEXT and not closing:
            close = re.compile("</" + name, re.I).search(text, i)
            if name == "style":
                yield "style", lt, i, close.start() if close else n, match.end(), end
            i = _tag_end(text, close.end()) + 1 if close else n
            if i <= 0:
                i = n
            continue
        yield "tag", lt, name, closing, match.end(), end


def _lines(pieces):
    joined = html_module.unescape("".join(pieces)).replace("\xa0", " ")
    return "\n".join(line for line in (re.sub(r"[ \t\r\f\v]+", " ", part).strip() for part in joined.split("\n")) if line)


def visible_html(text):
    """What a person sees of an HTML body."""
    return read_html(text)[0]


def read_html(text):
    """(what a person sees of an HTML body, the text left out because the reader cannot tell whether it shows). One
    pass over the text for its style sheets and one to read it, written here and not left to html.parser, because
    that parser's work grows with the square of a bad file and its results move between Python versions. An unclosed
    comment or hidden element hides the rest. A style sheet counts wherever it sits, in <head> as most email puts it,
    or inside a hidden element. Its rule hides an element when the reader can apply the selector exactly and the
    sheet comes first. A rule it cannot apply exactly, as .wrapper .preheader or one inside @media, or a sheet after
    the element, leaves the element out as text the reader cannot be sure of, for a person to type."""
    _spend_steps(len(text) >> 4)
    sheets = _Sheets(text)
    for event in _html_events(text, False):
        if event[0] == "style":
            media = _ATTR.finditer(text, event[4], event[5])
            media = {m.group(1).lower(): (m.group(2) or "").strip("\"'") for m in media}.get("media", "")
            # A sheet for print or small screens holds only some of the time, as @media does, and one for dark mode never.
            sheets.add(event[1], text[event[2]:event[3]], "".join(media.split()).lower())
    out, doubtful, painted = [], [], []  # painted: the open elements that paint a background
    skipping, depth, unsure = None, 0, False  # the hidden element being skipped, how deep, and whether it may show
    for event in _html_events(text, True):
        kind = event[0]
        if kind == "text":
            if skipping is None:
                out.append(text[event[1]:event[2]])
            elif unsure:
                doubtful.append(text[event[1]:event[2]])
            continue
        if kind == "<":
            if skipping is None:
                out.append("<")
            continue
        if kind == "style":
            continue
        _, at, name, closing, attrs_start, end = event
        if skipping is not None:
            if name == skipping:
                depth += -1 if closing else 1
                if depth == 0:
                    skipping = None
            elif unsure and not closing and name not in _INLINE:
                doubtful.append("\n")
            continue
        if closing:
            if painted and painted[-1] == name:
                painted.pop()
            if name not in _INLINE:
                out.append(" " if name in _CELL else "\n")
            continue
        attrs = {m.group(1).lower(): (m.group(2) or "").strip("\"'") for m in _ATTR.finditer(text, attrs_start, end)}
        if name in _VOID:
            if name not in _INLINE:
                out.append("\n")
            continue
        verdict = "hidden" if name in _UNSHOWN or _hides(attrs) else (
            "unsure" if _style_doubt(html_module.unescape(attrs.get("style", ""))) else sheets.verdict(at, name, attrs))
        if verdict is not None:
            skipping, depth, unsure = name, 1, verdict == "unsure"
            doubtful.append("\n")
            continue
        if _paints_behind(attrs):
            painted.append(name)
        elif _white_ink(attrs) and not painted:
            skipping, depth, unsure = name, 1, False
            continue
        if name not in _INLINE:
            out.append(" " if name in _CELL else "\n")
    doubt = _lines(doubtful)
    return _lines(out), (doubt if any(ch not in _BLANK for ch in doubt) else "")


# A tag as Markdown reads one: </name>, <name attributes> or <name/>.
_MD_TAG = re.compile(r"<(/?)([A-Za-z][A-Za-z0-9-]*)((?:\s+[A-Za-z_:][A-Za-z0-9_.:-]*"
                     r"(?:\s*=\s*(?:[^\s\"'=<>`]+|'[^']*'|\"[^\"]*\"))?)*)\s*(/?)>")
_MD_UNSHOWN = {"style", "script", "template", "title"}
_MD_PLAIN_STYLE = {"font-weight", "font-style", "text-decoration", "text-align"}  # properties that never hide text
_LINK_DEFINITION = re.compile(r" {0,3}\[[^\]\n]+\]:[ \t]*(?:<[^<>\n]*>|[^\s<]\S*)"
                              r"(?:[ \t]+(?:\"[^\"\n]*\"|'[^'\n]*'|\([^()\n]*\)))?[ \t]*")


def _blank(text):
    return re.sub(r"[^\n]", " ", text)


def _md_left_out(name, attrs, styled):
    """True when a rendered page may not show what an element holds: an element that never shows, one marked hidden,
    one with a colour of its own or with any style beyond bold, italic, underline and alignment, and, when the file
    holds a style sheet, one with a class or an id."""
    style = _declarations(_style_flat(attrs.get("style", "")))
    return (name in _MD_UNSHOWN or "hidden" in attrs or "color" in attrs or any(prop not in _MD_PLAIN_STYLE for prop in style)
            or (styled and ("class" in attrs or "id" in attrs)))


def markdown_read(text, styled=None):
    """(Markdown text as a rendered page shows it, True when it left out text that may show). Every tag is blanked
    character for character, attributes included, so lines keep their numbers and an alt or title text is no text.
    What an element holds is left out when a rendered page may not show it, and a link reference definition is
    blanked. An element left open hides the rest of the text, as in a browser, except one that never shows, such
    as <Title>: a template's placeholder written in angle brackets is no element. Each tag is passed once, so the
    work grows with the length of the text."""
    if styled is None:
        styled = markdown_styled(text)
    tags = list(_MD_TAG.finditer(text))
    same = {}  # name: [index of each tag of that name]
    for k, tag in enumerate(tags):
        same.setdefault(tag.group(2).lower(), []).append(k)
    cursor = {name: 0 for name in same}
    unclosed = set()  # names with no closing tag after the last place one was looked for
    kept, pos, doubt = [], 0, False
    for k, tag in enumerate(tags):
        if tag.start() < pos:
            continue
        name = tag.group(2).lower()
        kept.extend((text[pos:tag.start()], _blank(tag.group(0))))
        pos = tag.end()
        if tag.group(1) or tag.group(4) or name in _VOID:
            continue
        attrs = {m.group(1).lower(): (m.group(2) or "").strip("\"'") for m in _ATTR.finditer(tag.group(3))}
        if not _md_left_out(name, attrs, styled):
            continue
        order = same[name]
        while cursor[name] < len(order) and order[cursor[name]] <= k:
            cursor[name] += 1
        end, depth = None, 1
        for j in range(cursor[name], len(order) if name not in unclosed else 0):
            other = tags[order[j]]
            if other.group(1):
                depth -= 1
            elif not other.group(4) and name not in _MD_UNSHOWN:
                depth += 1
            if depth == 0:
                end = other.end()
                break
        if end is None:
            unclosed.add(name)
            if name in _MD_UNSHOWN and len(attrs) <= 1 and "hidden" not in attrs and "style" not in attrs:
                continue  # a placeholder such as <Title> or <Template ACK-1>
            end = len(text)
        held = text[pos:end]
        doubt = doubt or bool(_MD_TAG.sub("", held).strip())
        kept.append(_blank(held))
        pos = end
    lines = ("".join(kept) + text[pos:]).split("\n")
    # A definition cannot break into a paragraph, so it counts only at the start of a block.
    starts = True
    for k, line in enumerate(lines):
        if not line.strip():
            starts = True
        elif starts and _LINK_DEFINITION.fullmatch(line):
            lines[k] = _blank(line)
        else:
            starts = line.lstrip().startswith("#")
    return "\n".join(lines), doubt


def markdown_styled(text):
    """True when Markdown text holds a style sheet, which may hide any element with a class or an id."""
    return re.search(r"<style[\s/>]", text, re.I) is not None


def markdown_shown(text):
    """Markdown text as a rendered page shows it, as markdown_read gives it."""
    return markdown_read(text)[0]


def _figures(text):
    return set(re.findall(r"\d(?:[\d,.]*\d)?", re.sub(r"https?://\S+", " ", text)))


def _email_text(part):
    """The body part's text. A character set Python does not know is decoded only if plain ASCII."""
    if part is None:
        return None
    try:
        return part.get_content()
    except LookupError:
        raw = part.get_payload(decode=True) or b""
        if any(byte > 127 for byte in raw):
            raise Unreadable("the email names a character set this reader does not know")
        return raw.decode("ascii")


_RFC_DATE = re.compile(r"(?:(?:mon|tue|wed|thu|fri|sat|sun)[ \t]*,[ \t]*)?[0-9]{1,2}[ \t]+"
                       r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[ \t]+[0-9]{4}[ \t]+[0-9]{2}:[0-9]{2}(?::[0-9]{2})?"
                       r"[ \t]+(?:[+-][0-9]{4}|ut|utc|gmt|z|[ecmp][sd]t)(?:[ \t]*\([^()]*\))?[ \t]*")


def _date_line(msg):
    """The Date header as Python 3.13 shows it, worked out the same way on every Python: a date in the form of RFC
    5322 in its standard form, anything else as written. The standard header parser is not used, because on Python
    3.9 it raises on a date in any other form, such as an export's 2026-05-30T10:00:00Z."""
    for key, value in msg.raw_items():
        if key.lower() == "date":
            value = re.sub(r"[\r\n]", "", value).encode("utf-8", "surrogateescape").decode("utf-8", "replace")
            if _RFC_DATE.fullmatch(value.translate(_ASCII_LOWER)):
                try:
                    return email.utils.format_datetime(email.utils.parsedate_to_datetime(value))
                except (TypeError, ValueError, OverflowError):
                    pass
            return value
    return ""


def read_eml(path):
    if path.stat().st_size > MAX_EMAIL:
        raise Unreadable("the email is over 64 MB; type the pages it needs into its cover")
    data = path.read_bytes()
    # Reading a header takes time that grows faster than its length, so length is capped before any parsing,
    # and each line costs steps, because the parser walks lines one at a time, twice here.
    _spend_steps(2 * (data.count(b"\n") + data.count(b"\r")))
    rough = email.message_from_bytes(data)
    total = 0
    parts = 0
    encoded = 0
    separators = 0
    for part in rough.walk():
        parts += 1
        for key, value in part.raw_items():
            total += len(value)
            encoded += value.count("=?")
            if len(value) > MAX_HEADER or total > MAX_HEADERS or encoded > MAX_ENCODED_WORDS:
                raise Unreadable("the email's header lines are too long to read")
            if key.lower() in PARSED_HEADERS:
                marks = sum(map(value.count, SEPARATORS))
                separators += marks
                if marks > MAX_HEADER_SEPARATORS or separators > MAX_SEPARATORS:
                    raise Unreadable(TANGLED_HEADERS)
    if parts > MAX_PARTS:
        raise Unreadable("the email has too many parts to read")
    msg = email.message_from_bytes(data, policy=email.policy.default)
    head = []
    for key in ("From", "To", "Date", "Subject"):
        value = _date_line(msg) if key == "Date" else msg[key]
        if value:
            head.append("{}: {}".format(key, value))
    plain = _email_text(msg.get_body(preferencelist=("plain",)))
    html_body = _email_text(msg.get_body(preferencelist=("html",)))
    text, doubtful = (plain or "", "") if html_body is None else read_html(html_body)
    if html_body is not None and plain is not None and plain.strip():
        shown, plain_figures = _figures(text), _figures(plain)
        # Text the reader cannot be sure of may be in the plain part or not, but nothing else may differ.
        if not shown <= plain_figures <= shown | _figures(doubtful):
            raise Unreadable("the email's plain part and its HTML part hold different figures")
    if doubtful:
        _spent.partly = [1]  # a style sheet may hide part of the page, so a person types what it shows
    elif not text.strip():
        raise Unreadable("the email has no body text of its own, so its content is in an attachment")
    return ["\n".join(head) + "\n\n" + text]


W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _on(value):
    """A Word or Excel switch: absent is off, and a bare element or an empty value is on."""
    return value is None or value.lower() not in ("0", "false", "off")


def _word_on(props, name):
    mark = props.find(W + name) if props is not None else None
    return None if mark is None else _on(mark.get(W + "val"))


def _pale(value):
    """True for white and for a colour no one could read on white."""
    value = (value or "").lower()
    return len(value) == 6 and all(c in "0123456789abcdef" for c in value) and all(
        int(value[k:k + 2], 16) >= 0xF5 for k in (0, 2, 4))


def _word_ink(props):
    mark = props.find(W + "color") if props is not None else None
    if mark is None:
        return None
    return _pale(mark.get(W + "val")) or mark.get(W + "themeColor") in ("background1", "light1")


def _word_fill(props):
    """True when these properties paint a background a person could read white text on."""
    if props is None:
        return False
    shade = props.find(W + "shd")
    if shade is not None:
        fill = (shade.get(W + "fill") or "").lower()
        if fill and fill != "auto" and not _pale(fill):
            return True
    mark = props.find(W + "highlight")
    return mark is not None and (mark.get(W + "val") or "none").lower() not in ("none", "white")


class WordStyles:
    """The vanish, colour and shading a Word file's styles set, following basedOn."""

    def __init__(self, data):
        self.styles = {}
        self.defaults = None
        self.default_paragraph = None
        if data is None:
            return
        root = ElementTree.fromstring(data)
        for style in root.iter(W + "style"):
            self.styles[style.get(W + "styleId")] = style
            if style.get(W + "type") == "paragraph" and _on(style.get(W + "default") or "0"):
                self.default_paragraph = style.get(W + "styleId")
        defaults = root.find(W + "docDefaults")
        if defaults is not None:
            self.defaults = defaults.find(W + "rPrDefault/" + W + "rPr")

    def chain(self, style_id):
        seen = set()
        while style_id in self.styles and style_id not in seen and len(seen) < 32:
            seen.add(style_id)
            yield self.styles[style_id]
            based = self.styles[style_id].find(W + "basedOn")
            style_id = based.get(W + "val") if based is not None else None

    def run_value(self, read, run_style, para_style):
        for style_id in (run_style, para_style or self.default_paragraph):
            for style in self.chain(style_id):
                got = read(style.find(W + "rPr"))
                if got is not None:
                    return got
        return read(self.defaults)

    def fills(self, para_style):
        return any(_word_fill(style.find(W + "pPr")) for style in self.chain(para_style or self.default_paragraph))


def _word_hides_text(parts):
    """True when a run that holds text is marked hidden, or is white with nothing painted behind it."""
    styles = WordStyles(parts.get("word/styles.xml"))

    def walk(el, filled, para_style):
        for child in el:
            _spend_steps(1)
            name = child.tag.rsplit("}", 1)[-1] if isinstance(child.tag, str) else ""
            if name == "r":
                props = child.find(W + "rPr")
                if any((t.text or "").strip() for t in child.iter(W + "t")):
                    mark = props.find(W + "rStyle") if props is not None else None
                    run_style = mark.get(W + "val") if mark is not None else None
                    vanish = _word_on(props, "vanish")
                    if vanish is None:
                        vanish = styles.run_value(lambda p: _word_on(p, "vanish"), run_style, para_style)
                    if vanish:
                        return True
                    ink = _word_ink(props)
                    if ink is None:
                        ink = styles.run_value(_word_ink, run_style, para_style)
                    if ink and not (filled or _word_fill(props)):
                        return True
                if walk(child, filled, para_style):
                    return True
                continue
            below, style = filled, para_style
            if name == "p":
                ppr = child.find(W + "pPr")
                mark = ppr.find(W + "pStyle") if ppr is not None else None
                style = mark.get(W + "val") if mark is not None else None
                below = filled or _word_fill(ppr) or styles.fills(style)
            elif name == "tc":
                below = filled or _word_fill(child.find(W + "tcPr"))
            elif name == "tbl":
                tpr = child.find(W + "tblPr")
                below = filled or _word_fill(tpr) or (tpr is not None and tpr.find(W + "tblStyle") is not None)
            elif name == "txbxContent":
                below = True  # a text box's fill is drawn by its shape, which is not worked out here
            elif name in ("rPr", "pPr", "tcPr", "tblPr", "trPr", "sectPr"):
                continue
            if walk(child, below, style):
                return True
        return False

    for name in ("word/document.xml", "word/footnotes.xml"):
        if name in parts:
            root = ElementTree.fromstring(parts[name])
            backdrop = root.find(W + "background")
            painted = backdrop is not None and not _pale(backdrop.get(W + "color")) and (
                backdrop.get(W + "color") or "auto").lower() != "auto"
            if walk(root, painted, None):
                return True
    return False


def _holds_doctype(data):
    """NUL bytes out first, so a UTF-16 part cannot hide the DOCTYPE from the search."""
    return re.search(rb"<!DOCTYPE", data.replace(b"\0", b""), re.I) is not None


def _check_zip_directory(path, noun, old):
    """An OLE file in place of a zip is a locked or old Office file, refused in words. A zip's list of parts is read
    whole by zipfile, so a file of millions of parts is refused first."""
    with path.open("rb") as fh:
        if fh.read(8) == OLE_HEADER:
            raise Unreadable("{} is password protected, or is an old {} file".format(noun, old))
        fh.seek(0, 2)
        size = fh.tell()
        fh.seek(max(0, size - 66000))
        tail = fh.read()
    at = tail.rfind(b"PK\x05\x06")
    if at >= 0 and int.from_bytes(tail[at + 12:at + 16], "little") > MAX_ZIP_DIRECTORY:
        raise Unreadable(TOO_MUCH)


def _word_parts(path):
    """The parts the Word reader opens, plus the styles, searched for a DOCTYPE before anything parses them.
    The Word reader in tieout/ searches too, but it cannot see through UTF-16 and is frozen."""
    with zipfile.ZipFile(str(path)) as zf:
        names = set(zf.namelist())
        return {name: _member(zf, name, "the Word file", MAX_WORD_TAGS) for name in
                ("word/document.xml", "word/footnotes.xml", "word/comments.xml", "word/styles.xml") if name in names}


def read_docx(path):
    kit = str(Path(__file__).resolve().parent.parent / "tieout")
    if kit not in sys.path:
        sys.path.insert(0, kit)
    sys.dont_write_bytecode = True
    import docx_reader  # noqa: E402
    _check_zip_directory(path, "the Word file", ".doc")
    parts = _word_parts(path) if zipfile.is_zipfile(str(path)) else {}
    try:
        result = docx_reader.read(str(path))
    except docx_reader.DocxTracked:
        raise Unreadable("the Word file still holds tracked changes")
    except docx_reader.DocxError as exc:
        # No path and no file name: a path differs by machine, and either may hold a word on the deny list, which
        # would refuse the whole page with no word of which file. The XML parser's own words are left out too,
        # because they are not plain and they move between Python versions.
        reason = str(exc)
        reason = reason[len(str(path)) + 2:] if reason.startswith(str(path) + ": ") else reason.replace(str(path), "the file")
        reason = re.sub(r" does not parse: .*", " does not parse", reason, flags=re.S)
        raise Unreadable("the Word file could not be read: " + reason)
    if _word_hides_text(parts):
        raise Unreadable("the Word file holds hidden or white text; show or delete it in Word")
    # A comment's words are no part of the page, as the tie-out reader reads only its TIE: tags, so the screen counts them.
    said = sum(1 for c in ElementTree.fromstring(parts.get("word/comments.xml") or "<x/>").iter(W + "comment")
               if "".join(t.text or "" for t in c.iter(W + "t")).strip())
    if said:
        _spent.notes.append("{} comment{} not read".format(said, "" if said == 1 else "s"))
    return ["\n".join(block["text"] for block in result["blocks"] if block.get("text"))]


def _member(zf, name, noun="the workbook", most=None):
    """One part of a workbook or a Word file, with `noun` naming which in a refusal. `most` is its cap on tags,
    MAX_SHEET_TAGS when not given."""
    info = zf.getinfo(name)
    if info.file_size > MAX_STREAM:
        raise Unreadable(noun + " is too large to read")
    data = zf.read(name)
    _spend_bytes(len(data))
    if _holds_doctype(data):
        raise Unreadable(noun + " holds a DOCTYPE, which the reader refuses")
    # The parsed tree takes many times the part's bytes, so tags are counted before parsing.
    tags = data.count(b"<")
    if tags > (MAX_SHEET_TAGS if most is None else most):
        raise Unreadable(noun + " is too large to read")
    _spend_steps(tags)
    return data


def _column(ref, fallback):
    """A cell's column number from its reference such as C7. The reference is optional."""
    letters = re.match(r"[A-Za-z]+", ref or "")
    if letters is None:
        return fallback
    number = 0
    for ch in letters.group(0).upper():
        number = number * 26 + ord(ch) - 64
    return number


def _flat_zero(value):
    """True for a width or height of nothing, which hides a column or row as surely as the flag does."""
    try:
        return value is not None and float(value) == 0
    except ValueError:
        return False


def _small_number(text):
    """A cell's or column's number. Python 3.9 reads a long run of digits in time that grows with its square, and
    3.11 and later refuse one, so a run too long for any workbook is damage on every Python."""
    if len(text or "") > 12:
        raise Unreadable(DAMAGED)
    return int(text)


def _hidden_note(sheets, rows, columns):
    counts = [(sheets, "sheet"), (rows, "row"), (columns, "column")]
    words = ["{} hidden {}{}".format(n, word, "" if n == 1 else "s") for n, word in counts if n]
    return "{} left out".format(", ".join(words)) if words else None


def read_xlsx(path):
    main = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    rel = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
    _check_zip_directory(path, "the workbook", ".xls")
    with zipfile.ZipFile(str(path)) as zf:
        names = set(zf.namelist())
        shared = []
        if "xl/sharedStrings.xml" in names:
            for si in ElementTree.fromstring(_member(zf, "xl/sharedStrings.xml")).iter(main + "si"):
                shared.append("".join(t.text or "" for t in si.iter(main + "t")))
        targets = {}
        rels = ElementTree.fromstring(_member(zf, "xl/_rels/workbook.xml.rels"))
        for r in rels:
            targets[r.get("Id")] = r.get("Target", "")
        sheets = list(ElementTree.fromstring(_member(zf, "xl/workbook.xml")).iter(main + "sheet"))
        if len(sheets) > MAX_SHEETS:
            raise Unreadable("the workbook has too many sheets to read")
        pages = []
        read_members = set()
        hidden_sheets = hidden_rows = hidden_columns = 0
        text_size = 0  # characters on the pages so far, as the check will count them
        for sheet in sheets:
            if sheet.get("state") in ("hidden", "veryHidden"):
                hidden_sheets += 1
                continue
            target = targets.get(sheet.get(rel), "")
            member = target.lstrip("/") if target.startswith("/") else "xl/" + target
            lines = [sheet.get("name", "")]
            text_size += len(lines[0])
            if member in names:
                if member in read_members:
                    raise Unreadable("the workbook lists the same sheet twice, so its page numbers cannot be trusted")
                read_members.add(member)
                root = ElementTree.fromstring(_member(zf, member))
                hidden = []
                for col in root.iter(main + "col"):
                    if col.get("hidden") in ("1", "true") or _flat_zero(col.get("width")):
                        hidden.append((_small_number(col.get("min", "0")), _small_number(col.get("max", "0"))))
                        hidden_columns += 1
                for row in root.iter(main + "row"):
                    _spend_steps(1)
                    if row.get("hidden") in ("1", "true") or _flat_zero(row.get("ht")):
                        hidden_rows += 1
                        continue
                    cells = []
                    position = 0
                    for c in row.iter(main + "c"):
                        _spend_steps(1)
                        position = _column(c.get("r"), position + 1)
                        if hidden and any(lo <= position <= hi for lo, hi in hidden):
                            continue
                        kind = c.get("t")
                        v = c.find(main + "v")
                        if kind == "s" and v is not None:
                            value = shared[_small_number(v.text)]
                        elif kind == "inlineStr":
                            value = "".join(t.text or "" for t in c.iter(main + "t"))
                        elif v is not None and v.text:
                            value = v.text
                        else:
                            continue
                        # One shared string can fill every cell, so each cell counts against the caps before the row
                        # is joined: a tiny file can never build a page larger than the check can hold.
                        text_size += len(value) + 1
                        if text_size > MAX_TEXT:
                            raise Unreadable(TOO_MUCH_TEXT)
                        _spend_bytes(2 * (len(value) + 1))
                        cells.append(value)
                    if cells:
                        lines.append("\t".join(cells))
                del root  # one sheet's tree in memory at a time
            pages.append("\n".join(lines))
    note = _hidden_note(hidden_sheets, hidden_rows, hidden_columns)
    if note:
        _spent.notes.append(note)
    return pages


# ---------------------------------------------------------------- PDF objects


class Name(str):
    """A PDF name such as /Font, without its slash."""


class Op(str):
    """A content-stream operator or a bare PDF keyword."""


class Ref(tuple):
    """An indirect reference: (object number, generation)."""


WS = b" \t\r\n\f\0"
DELIM = b"()<>[]{}/%"
_NUMBER = re.compile(rb"[+-]?(?:\d+\.?\d*|\.\d+)")
_REF_TAIL = re.compile(rb"[ \t\r\n\f\0]+(\d+)[ \t\r\n\f\0]+R(?![A-Za-z0-9])")
_OBJ = re.compile(rb"(?<![0-9])(\d{1,10})[ \t\r\n\f\0]+(\d{1,5})[ \t\r\n\f\0]+obj(?![A-Za-z0-9])")
_STREAM_START = re.compile(rb">>[ \t\r\n\f\0]*stream")
_ESCAPES = {ord("n"): 10, ord("r"): 13, ord("t"): 9, ord("b"): 8, ord("f"): 12, ord("("): 40, ord(")"): 41, ord("\\"): 92}
_TOKEN_END = re.compile(rb"[ \t\r\n\f\0()<>\[\]{}/%]")
_SPACE_RUN = re.compile(rb"[ \t\r\n\f\0]*")
_LINE_END = re.compile(rb"[\r\n]")
_LITERAL_STOP = re.compile(rb"[\\()]")


class Lexer:
    """Reads PDF values from bytes. `refs` turns "12 0 R" into a Ref in object syntax."""

    def __init__(self, data, pos=0, refs=True):
        self.data = data
        self.pos = pos
        self.refs = refs

    def skip(self):
        data = self.data
        pos = self.pos
        while True:
            pos = _SPACE_RUN.match(data, pos).end()
            if data[pos:pos + 1] != b"%":
                break
            stop = _LINE_END.search(data, pos)
            pos = stop.start() if stop else len(data)
            _spent.steps += 1
        if pos - self.pos > 1024:
            _spend_steps((pos - self.pos) >> 4)
        self.pos = pos

    def value(self, depth=0):
        """The next value, or None at the end of the data. Closing tokens come back as Op."""
        if depth > MAX_DEPTH:
            raise ValueError("nesting too deep")
        _spent.steps += 1
        if _spent.steps > MAX_STEPS:
            raise Unreadable(TOO_MUCH)
        self.skip()
        data, pos = self.data, self.pos
        if pos >= len(data):
            return None
        ch = data[pos]
        if ch == 47:  # /name
            return self._name()
        if ch == 40:  # (string)
            return self._literal()
        if ch == 60:  # < or <<
            if data[pos:pos + 2] == b"<<":
                self.pos = pos + 2
                return self._dict(depth)
            return self._hex()
        if ch == 91:  # [
            self.pos = pos + 1
            items = []
            while True:
                item = self.value(depth + 1)
                if item is None or (isinstance(item, Op) and item == "]"):
                    return items
                items.append(item)
        if data[pos:pos + 2] == b">>":
            self.pos = pos + 2
            return Op(">>")
        if ch == 93:
            self.pos = pos + 1
            return Op("]")
        if ch in (62, 41, 123, 125):  # stray closers
            self.pos = pos + 1
            return Op(chr(ch))
        m = _NUMBER.match(data, pos)
        if m and (m.end() >= len(data) or data[m.end()] in WS or data[m.end()] in DELIM):
            self.pos = m.end()
            text = m.group(0)
            if self.refs and b"." not in text:
                tail = _REF_TAIL.match(data, self.pos)
                if tail:
                    self.pos = tail.end()
                    return Ref((int(text), int(tail.group(1))))
            return float(text) if b"." in text else int(text)
        stop = _TOKEN_END.search(data, pos)
        end = stop.start() if stop else len(data)
        if end == pos:
            end = pos + 1
        _spent.steps += (end - pos) >> 4
        self.pos = end
        word = data[pos:end].decode("latin-1")
        if word == "true":
            return True
        if word == "false":
            return False
        return Op(word)

    def _name(self):
        data = self.data
        pos = self.pos + 1
        stop = _TOKEN_END.search(data, pos)
        end = stop.start() if stop else len(data)
        _spent.steps += (end - pos) >> 4
        self.pos = end
        raw = data[pos:end]
        if b"#" in raw:
            raw = re.sub(rb"#([0-9A-Fa-f]{2})", lambda m: bytes([int(m.group(1), 16)]), raw)
        return Name(raw.decode("latin-1"))

    def _literal(self):
        data, n = self.data, len(self.data)
        pos = self.pos + 1
        out = bytearray()
        depth = 1
        while pos < n:
            stop = _LITERAL_STOP.search(data, pos)
            end = stop.start() if stop else n
            out += data[pos:end]
            pos = end
            if pos >= n:
                break
            _spent.steps += 1
            if _spent.steps > MAX_STEPS:
                raise Unreadable(TOO_MUCH)
            ch = data[pos]
            if ch == 92 and pos + 1 < n:  # backslash
                nxt = data[pos + 1]
                if nxt in _ESCAPES:
                    out.append(_ESCAPES[nxt])
                    pos += 2
                elif 48 <= nxt <= 55:
                    k = pos + 1
                    val = 0
                    while k < n and k < pos + 4 and 48 <= data[k] <= 55:
                        val = val * 8 + data[k] - 48
                        k += 1
                    out.append(val & 255)
                    pos = k
                elif nxt in b"\r\n":
                    pos += 2
                    if nxt == 13 and pos < n and data[pos] == 10:
                        pos += 1
                else:
                    out.append(nxt)
                    pos += 2
                continue
            if ch == 40:
                depth += 1
            elif ch == 41:
                depth -= 1
                if depth == 0:
                    pos += 1
                    break
            out.append(ch)
            pos += 1
        _spent.steps += len(out) >> 4
        self.pos = pos
        return bytes(out)

    def _hex(self):
        end = self.data.find(b">", self.pos)
        if end < 0:
            end = len(self.data)
        _spend_steps((end - self.pos) >> 4)
        digits = re.sub(rb"[^0-9A-Fa-f]", b"", self.data[self.pos + 1:end])
        self.pos = end + 1
        if len(digits) % 2:
            digits += b"0"
        return bytes.fromhex(digits.decode("ascii"))

    def _dict(self, depth):
        out = {}
        while True:
            key = self.value(depth + 1)
            if key is None or (isinstance(key, Op) and key == ">>"):
                return out
            if not isinstance(key, Name):
                continue
            val = self.value(depth + 1)
            if val is None or (isinstance(val, Op) and val == ">>"):
                return out
            out[str(key)] = val


class Stream:
    def __init__(self, head, raw):
        self.head = head
        self.raw = raw


def _lzw(data, early=1):
    _spend_steps(len(data))
    out = bytearray()
    table = [bytes([i]) for i in range(256)] + [b"", b""]
    bits = 9
    buf = count = 0
    prev = None
    for byte in data:
        buf = (buf << 8) | byte
        count += 8
        while count >= bits:
            count -= bits
            code = (buf >> count) & ((1 << bits) - 1)
            buf &= (1 << count) - 1
            if code == 256:
                table = table[:258]
                bits = 9
                prev = None
                continue
            if code == 257:
                return bytes(out)
            if code < len(table):
                entry = table[code]
            elif prev is not None:
                entry = prev + prev[:1]
            else:
                return bytes(out)
            out += entry
            if len(out) > MAX_STREAM:
                raise Unreadable("a stream in the PDF is too large to read")
            if prev is not None:
                table.append(prev + entry[:1])
                if len(table) + early >= (1 << bits) and bits < 12:
                    bits += 1
            prev = entry
    return bytes(out)


def _inflate(raw):
    d = zlib.decompressobj()
    try:
        out = d.decompress(raw, MAX_STREAM)
    except zlib.error:
        # A damaged stream: keep what can be read, trying a raw deflate as some writers produce.
        d = zlib.decompressobj(-15)
        try:
            out = d.decompress(raw[2:], MAX_STREAM)
        except zlib.error:
            return b""
    if d.unconsumed_tail:
        raise Unreadable("a stream in the PDF is too large to read")
    return out


def _predictor(data, parms):
    pred = parms.get("Predictor", 1) if isinstance(parms, dict) else 1
    if not isinstance(pred, int) or pred < 10:
        return data
    columns = parms.get("Columns", 1)
    colors = parms.get("Colors", 1)
    bpc = parms.get("BitsPerComponent", 8)
    width = max(1, (columns * colors * bpc + 7) // 8)
    bpp = max(1, (colors * bpc + 7) // 8)
    if width > MAX_ROW:
        raise Unreadable("a stream in the PDF is too large to read")
    _spend_steps(len(data))
    out = bytearray()
    prev = bytearray(width)
    for start in range(0, len(data), width + 1):
        tag = data[start]
        row = bytearray(data[start + 1:start + 1 + width])
        row.extend(b"\0" * (width - len(row)))
        if tag == 0:
            out += row
            prev = row
            continue
        for i in range(width):
            a = row[i - bpp] if i >= bpp else 0
            b = prev[i]
            c = prev[i - bpp] if i >= bpp else 0
            if tag == 1:
                row[i] = (row[i] + a) & 255
            elif tag == 2:
                row[i] = (row[i] + b) & 255
            elif tag == 3:
                row[i] = (row[i] + (a + b) // 2) & 255
            elif tag == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                row[i] = (row[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        out += row
        prev = row
    return bytes(out)


def _run_length(data):
    _spend_steps(len(data) >> 1)
    out = bytearray()
    k = 0
    while k < len(data) and data[k] != 128:
        length = data[k]
        if length < 128:
            out += data[k + 1:k + 2 + length]
            k += length + 2
        else:
            out += data[k + 1:k + 2] * (257 - length)
            k += 2
        if len(out) > MAX_STREAM:
            raise Unreadable("a stream in the PDF is too large to read")
    return bytes(out)


def _is_null(value):
    return value is None or (isinstance(value, Op) and value == "null")


class Pdf:
    """The file's objects, found through its cross-reference table, as a viewer finds them, so bytes
    the table does not point at cannot stand in for a page. A table that cannot be followed falls
    back to scanning (`scan=True`), and the screen says so."""

    def __init__(self, data, scan=False):
        self.data = data
        self.base = max(0, data.find(b"%PDF-"))
        self.scanned = scan
        self.cache = {}
        self.compressed = {}
        self.offsets = {}
        self.object_streams = {}
        self.fonts = {}
        self.places = {}
        self.root = None
        self.catalog = None
        self.encrypted = False
        self.reading_length = False
        self.layers_off = None
        if scan:
            self._scan()
        else:
            try:
                self._follow_xref()
            except (ValueError, TypeError, IndexError, KeyError, AttributeError, RecursionError, OverflowError, zlib.error):
                raise Damaged()
            self.cache.clear()  # anything resolved while the tables were still empty

    # ---- the cross-reference table

    def _follow_xref(self):
        data = self.data
        at = data.rfind(b"startxref")
        if at < 0:
            raise Damaged()
        queue = [Lexer(data, at + 9, refs=False).value()]
        visited = set()
        entries = {}
        while queue:
            pos = queue.pop(0)
            if not isinstance(pos, int) or isinstance(pos, bool) or pos <= 0:
                raise Damaged()
            if pos in visited:
                continue
            visited.add(pos)
            section, trailer = self._xref_section(pos)
            for num, entry in section.items():
                entries.setdefault(num, entry)
            if self.root is None:
                self.root = trailer.get("Root")
            if not _is_null(trailer.get("Encrypt")):
                self.encrypted = True
            if isinstance(trailer.get("Prev"), int) and trailer["Prev"] > 0:
                queue.append(trailer["Prev"])
        for num, entry in entries.items():
            if isinstance(entry, int):
                self.offsets[num] = entry
            elif entry is not None:
                self.compressed[num] = entry

    def _xref_section(self, pos):
        """({object number: offset, (object stream, index) or None when free}, trailer dict)."""
        data = self.data
        for at in (self.base + pos, pos):
            lex = Lexer(data, at, refs=False)
            lex.skip()
            if data[lex.pos:lex.pos + 4] == b"xref":
                return self._xref_table(lex.pos + 4)
            head = _OBJ.match(data, lex.pos)
            if head is not None:
                value = self._parse_at(head.end())
                if isinstance(value, Stream) and value.head.get("Type") == "XRef":
                    return self._xref_stream(value), value.head
        raise Damaged()

    def _xref_table(self, pos):
        lex = Lexer(self.data, pos, refs=False)
        section = {}
        while True:
            first = lex.value()
            if isinstance(first, Op) and first == "trailer":
                break
            count = lex.value()
            if not isinstance(first, int) or not isinstance(count, int):
                raise Damaged()
            _spend_bytes(count * ENTRY_COST)
            for k in range(count):
                offset, _gen, kind = lex.value(), lex.value(), lex.value()
                if kind == "n" and isinstance(offset, int):
                    section[first + k] = offset
                elif kind == "f":
                    section[first + k] = None
                else:
                    raise Damaged()
        trailer = Lexer(self.data, lex.pos).value()
        if not isinstance(trailer, dict):
            raise Damaged()
        if isinstance(trailer.get("XRefStm"), int):
            # A hybrid file: objects this table lists as free live in the stream it names.
            hidden, _ = self._xref_section(trailer["XRefStm"])
            for num, entry in hidden.items():
                if section.get(num) is None:
                    section[num] = entry
        return section, trailer

    def _xref_stream(self, stream):
        widths = [int(w) for w in stream.head["W"]]
        table = self.stream_bytes(stream)
        size = sum(widths)
        index = stream.head.get("Index") or [0, stream.head.get("Size")]
        section = {}
        pos = 0
        for i in range(0, len(index) - 1, 2):
            for num in range(index[i], index[i] + index[i + 1]):
                if pos + size > len(table):
                    return section
                _spend_steps(1)
                _spend_bytes(ENTRY_COST)
                kind = int.from_bytes(table[pos:pos + widths[0]], "big") if widths[0] else 1
                second = int.from_bytes(table[pos + widths[0]:pos + widths[0] + widths[1]], "big")
                third = int.from_bytes(table[pos + widths[0] + widths[1]:pos + size], "big")
                pos += size
                if kind == 0:
                    section[num] = None
                elif kind == 1:
                    section[num] = second
                elif kind == 2:
                    section[num] = (second, third)
        return section

    def _object_stream(self, number):
        """(decoded data, {object number: its offset}) for one object stream."""
        if number not in self.object_streams:
            stream = self.resolve(Ref((number, 0)))
            if not isinstance(stream, Stream):
                raise Damaged()
            data = self.stream_bytes(stream)
            n, first = self.resolve(stream.head.get("N")), self.resolve(stream.head.get("First"))
            lex = Lexer(data[:first], 0, refs=False)
            table = {}
            for _ in range(n or 0):
                num, off = lex.value(), lex.value()
                if not isinstance(num, int) or not isinstance(off, int):
                    break
                table[num] = first + off
            self.object_streams[number] = (data, table)
        return self.object_streams[number]

    # ---- the scan, for a file whose table cannot be followed

    def _scan(self):
        """Every object header outside a stream body, the last definition in the file winning."""
        data = self.data
        bodies = []
        pos = 0
        while True:
            start = _STREAM_START.search(data, pos)
            if start is None:
                break
            end = data.find(b"endstream", start.end())
            if end < 0:
                break
            bodies.append((start.end(), end))
            pos = end + 9
        starts = [a for a, _ in bodies]
        positions = []
        for m in _OBJ.finditer(data):
            k = bisect.bisect_right(starts, m.start()) - 1
            if k >= 0 and m.start() < bodies[k][1]:
                continue  # stream bytes that happen to read like an object header
            _spend_bytes(ENTRY_COST)
            num = int(m.group(1))
            self.offsets[num] = m.end()
            self.places[num] = m.start()
            positions.append(m.start())
        self._index_object_streams(positions)
        for m in re.finditer(rb"trailer", data):
            trailer = Lexer(data, m.end()).value()
            if isinstance(trailer, dict) and not _is_null(trailer.get("Encrypt")):
                self.encrypted = True
        for m in re.finditer(rb"/XRef\b", data):
            i = bisect.bisect_right(positions, m.start()) - 1
            head = _OBJ.match(data, positions[i]) if i >= 0 else None
            value = self._parse_at(head.end()) if head else None
            if isinstance(value, Stream) and not _is_null(value.head.get("Encrypt")):
                self.encrypted = True

    def _index_object_streams(self, positions):
        for m in re.finditer(rb"/ObjStm", self.data):
            i = bisect.bisect_right(positions, m.start()) - 1
            if i < 0:
                continue
            head = _OBJ.match(self.data, positions[i])
            if head is None:
                continue
            value = self._parse_at(head.end())
            if not isinstance(value, Stream) or value.head.get("Type") != "ObjStm":
                continue
            data = self.stream_bytes(value)
            n, first = self.resolve(value.head.get("N")), self.resolve(value.head.get("First"))
            lex = Lexer(data[:first], 0, refs=False)
            pairs = []
            for _ in range(n or 0):
                num, off = lex.value(), lex.value()
                if not isinstance(num, int) or not isinstance(off, int):
                    break
                pairs.append((num, first + off))
            for num, off in pairs:
                # Keep a compressed object unless a later plain definition overrides it.
                if self.places.get(num, -1) < m.start():
                    self.compressed[num] = (data, off)
                    self.offsets.pop(num, None)
                    self.places[num] = m.start()

    # ---- reading one object

    def _parse_at(self, pos):
        lex = Lexer(self.data, pos)
        value = lex.value()
        _spend_bytes((lex.pos - pos) * PARSED_COST)
        if not isinstance(value, dict):
            return value
        lex.skip()
        if self.data[lex.pos:lex.pos + 6] != b"stream":
            return value
        start = lex.pos + 6
        if self.data[start:start + 2] == b"\r\n":
            start += 2
        elif self.data[start:start + 1] in (b"\n", b"\r"):
            start += 1
        length = value.get("Length")
        if isinstance(length, Ref):
            if self.reading_length:
                length = None  # a length that needs another stream's length is no length
            else:
                self.reading_length = True
                try:
                    length = self.resolve(length)
                finally:
                    self.reading_length = False
        if isinstance(length, int) and length >= 0:
            end = start + length
            if self.data[end:end + 20].lstrip(WS).startswith(b"endstream"):
                _spend_bytes(length)
                return Stream(value, self.data[start:end])
        end = self.data.find(b"endstream", start)
        if end < 0:
            end = len(self.data)
        _spend_bytes(end - start)
        return Stream(value, self.data[start:end].rstrip(b"\r\n"))

    def _load(self, num):
        if num in self.offsets:
            if self.scanned:
                return self._parse_at(self.offsets[num])
            for at in (self.base + self.offsets[num], self.offsets[num]):
                lex = Lexer(self.data, at, refs=False)
                lex.skip()
                head = _OBJ.match(self.data, lex.pos)
                if head is not None and int(head.group(1)) == num:
                    return self._parse_at(head.end())
            raise Damaged()  # the table points at something else
        if num in self.compressed:
            where = self.compressed[num]
            if isinstance(where[0], bytes):
                data, off = where
            else:
                data, table = self._object_stream(where[0])
                if num not in table:
                    raise Damaged()
                off = table[num]
            lex = Lexer(data, off)
            value = lex.value()
            _spend_bytes((lex.pos - off) * PARSED_COST)
            return value
        return None

    def resolve(self, value, hops=0):
        while isinstance(value, Ref):
            hops += 1
            if hops > 32:
                return None
            num = value[0]
            if num in self.cache:
                value = self.cache[num]
                continue
            got = self._load(num)
            self.cache[num] = got
            value = got
        return value

    def stream_bytes(self, stream):
        data = stream.raw
        filters = self.resolve(stream.head.get("Filter", stream.head.get("F")))
        parms = self.resolve(stream.head.get("DecodeParms", stream.head.get("DP")))
        filters = filters if isinstance(filters, list) else ([filters] if filters else [])
        parms = parms if isinstance(parms, list) else [parms] * max(1, len(filters))
        for i, f in enumerate(filters):
            f = self.resolve(f)
            if isinstance(f, Op) and f == "null":
                continue  # a null filter is no filter
            parm = self.resolve(parms[i]) if i < len(parms) else None
            parm = {k: self.resolve(v) for k, v in parm.items()} if isinstance(parm, dict) else {}
            if f in ("FlateDecode", "Fl"):
                data = _predictor(_inflate(data), parm)
            elif f in ("LZWDecode", "LZW"):
                data = _predictor(_lzw(data, 0 if parm.get("EarlyChange") == 0 else 1), parm)
            elif f in ("ASCII85Decode", "A85"):
                _spend_steps(len(data) >> 2)
                data = base64.a85decode(data.strip().rstrip(b"~>").lstrip(b"<~"), adobe=False, ignorechars=b" \t\r\n\f\v\0")
            elif f in ("ASCIIHexDecode", "AHx"):
                digits = re.sub(rb"[^0-9A-Fa-f]", b"", data.split(b">")[0])
                data = bytes.fromhex((digits + b"0" * (len(digits) % 2)).decode("ascii"))
            elif f == "RunLengthDecode" or f == "RL":
                data = _run_length(data)
            else:
                return b""  # an image codec: no text here
            _spend_bytes(len(data))
        return data

    # ---- the document's structure

    def _box(self, value):
        value = self.resolve(value)
        if not isinstance(value, list) or len(value) != 4:
            return None
        nums = [self.resolve(v) for v in value]
        if not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in nums):
            return None
        return (min(nums[0], nums[2]), min(nums[1], nums[3]), max(nums[0], nums[2]), max(nums[1], nums[3]))

    def _page_box(self, media, crop):
        """The page a viewer shows: the crop box inside the media box, or either alone."""
        media, crop = self._box(media), self._box(crop)
        if media is not None and crop is not None:
            both = (max(media[0], crop[0]), max(media[1], crop[1]), min(media[2], crop[2]), min(media[3], crop[3]))
            if both[2] - both[0] > 1 and both[3] - both[1] > 1:
                return both
            return media
        box = media or crop
        return box if box is not None and box[2] - box[0] > 1 and box[3] - box[1] > 1 else None

    def _last_catalog(self):
        """For a file read by scanning: the catalog latest in the file. One unusable object costs that object."""
        root = None
        for num in sorted(set(self.offsets) | set(self.compressed), key=lambda n: self.places.get(n, 0)):
            try:
                value = self.resolve(Ref((num, 0)))
            except (ValueError, RecursionError):
                continue
            if isinstance(value, dict) and value.get("Type") == "Catalog":
                root = value
        return root

    def pages(self):
        """Every page dict in reading order, each with its inherited resources and its visible box."""
        root = self.resolve(self.root) if self.root is not None else None
        if not isinstance(root, dict) or self.resolve(root.get("Pages")) is None:
            if not self.scanned:
                raise Damaged()
            root = self._last_catalog()
        self.catalog = root
        out = []
        seen = set()
        path = set()

        def walk(node, resources, media, crop, depth):
            if depth > MAX_DEPTH:
                return
            node_id = node[0] if isinstance(node, Ref) else None
            if node_id is not None:
                if node_id in path:
                    return  # a loop in the tree
                if node_id in seen:
                    raise Unreadable("the PDF lists the same page twice, so its page numbers cannot be trusted")
                seen.add(node_id)
                path.add(node_id)
            value = self.resolve(node)
            if isinstance(value, dict):
                res = value.get("Resources", resources)
                box_m, box_c = value.get("MediaBox", media), value.get("CropBox", crop)
                kids = self.resolve(value.get("Kids"))
                if isinstance(kids, list):
                    for kid in kids:
                        walk(kid, res, box_m, box_c, depth + 1)
                elif value.get("Type") != "Pages":
                    out.append((value, res, self._page_box(box_m, box_c)))
            if node_id is not None:
                path.discard(node_id)

        if root is not None:
            walk(root.get("Pages"), None, None, None, 0)
        if not out:
            if not self.scanned:
                raise Damaged()
            for num in sorted(set(self.offsets) | set(self.compressed)):
                try:
                    value = self.resolve(Ref((num, 0)))
                except (ValueError, RecursionError):
                    continue
                if isinstance(value, dict) and value.get("Type") == "Page":
                    out.append((value, value.get("Resources"), self._page_box(value.get("MediaBox"), value.get("CropBox"))))
        return out

    # ---- layers

    def _off_groups(self):
        """The object numbers of the optional-content groups the default view switches off."""
        if self.layers_off is None:
            off = set()
            props = self.resolve(self.catalog.get("OCProperties")) if isinstance(self.catalog, dict) else None
            view = self.resolve(props.get("D")) if isinstance(props, dict) else None
            if isinstance(view, dict):
                def numbers(key, source=view):
                    items = self.resolve(source.get(key))
                    return {x[0] for x in items if isinstance(x, Ref)} if isinstance(items, list) else set()

                if self.resolve(view.get("BaseState")) == "OFF":
                    off = numbers("OCGs", props) - numbers("ON")
                off |= numbers("OFF")
            self.layers_off = off
        return self.layers_off

    def layer_off(self, value):
        """True when a group or a membership named on content is switched off in the default view."""
        if value is None:
            return False
        off = self._off_groups()
        if not off:
            return False
        if isinstance(value, Ref) and value[0] in off:
            return True
        item = self.resolve(value)
        if not isinstance(item, dict) or self.resolve(item.get("Type")) != "OCMD":
            return False
        groups = self.resolve(item.get("OCGs"))
        groups = groups if isinstance(groups, list) else [item.get("OCGs")]
        states = [g[0] in off for g in groups if isinstance(g, Ref)]
        if not states:
            return False
        policy = self.resolve(item.get("P")) or "AnyOn"
        if policy == "AllOn":
            return any(states)
        if policy == "AnyOff":
            return not any(states)
        if policy == "AllOff":
            return not all(states)
        return all(states)


# ---------------------------------------------------------------- fonts


GLYPHS = {
    "space": " ", "exclam": "!", "quotedbl": '"', "numbersign": "#", "dollar": "$", "percent": "%", "ampersand": "&",
    "quotesingle": "'", "parenleft": "(", "parenright": ")", "asterisk": "*", "plus": "+", "comma": ",", "hyphen": "-",
    "minus": "-", "period": ".", "slash": "/", "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4",
    "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9", "colon": ":", "semicolon": ";", "less": "<",
    "equal": "=", "greater": ">", "question": "?", "at": "@", "bracketleft": "[", "backslash": "\\",
    "bracketright": "]", "underscore": "_", "quoteleft": "‘", "quoteright": "’", "quotedblleft": "“",
    "quotedblright": "”", "endash": "–", "emdash": "—", "bullet": "•", "section": "§",
    "fi": "fi", "fl": "fl", "ff": "ff", "ffi": "ffi", "ffl": "ffl", "sterling": "£", "Euro": "€",
    "nbspace": " ", "sfthyphen": "-", "ellipsis": "...", "degree": "°", "registered": "®", "copyright": "©",
}
LIGATURES = str.maketrans({"ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi", "ﬄ": "ffl",
                           " ": " ", "‑": "-", "­": ""})


def _glyph(name):
    if name in GLYPHS:
        return GLYPHS[name]
    if len(name) == 1:
        return name
    m = re.match(r"^uni([0-9A-Fa-f]{4})$", name) or re.match(r"^u([0-9A-Fa-f]{4,6})$", name)
    if m:
        return chr(int(m.group(1), 16))
    return ""


def _blocks(data, begin, end):
    """The bytes between each begin marker and its end marker, in one pass over the data."""
    out = []
    pos = 0
    while True:
        start = data.find(begin, pos)
        if start < 0:
            return out
        start += len(begin)
        stop = data.find(end, start)
        if stop < 0:
            return out
        out.append(data[start:stop])
        pos = stop + len(end)


_CMAP_TOKEN = re.compile(rb"<([0-9A-Fa-f]*)>|(\[)|(\])")


def _cmap(data):
    """(code to text, byte length of a code or None) from a ToUnicode stream."""
    table = {}
    lengths = set()
    for block in _blocks(data, b"begincodespacerange", b"endcodespacerange"):
        for lo in re.findall(rb"<([0-9A-Fa-f]+)>\s*<[0-9A-Fa-f]+>", block):
            lengths.add(len(lo) // 2)

    def text(hexes):
        raw = bytes.fromhex(hexes.decode("ascii") + ("0" if len(hexes) % 2 else ""))
        try:
            return raw.decode("utf-16-be")
        except UnicodeDecodeError:
            return ""

    def assign(lo, hi, rest):
        first, last = int(lo, 16), int(hi, 16)
        if last - first > 65535:
            return
        _spend_steps(max(0, last - first + 1))
        if len(table) > MAX_FONT_TABLE:
            raise Unreadable(TOO_MUCH)
        if isinstance(rest, list):
            for k, dst in enumerate(rest):
                if first + k <= last:
                    table[first + k] = text(dst)
            return
        base = bytes.fromhex(rest.decode("ascii") + ("0" if len(rest) % 2 else ""))
        for code in range(first, last + 1):
            bumped = int.from_bytes(base, "big") + code - first if base else 0
            try:
                table[code] = bumped.to_bytes(max(len(base), 2), "big").decode("utf-16-be")
            except (UnicodeDecodeError, OverflowError):
                table[code] = ""

    for block in _blocks(data, b"beginbfchar", b"endbfchar"):
        for src, dst in re.findall(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]*)>", block):
            table[int(src, 16)] = text(dst)
            lengths.add(len(src) // 2)
    for block in _blocks(data, b"beginbfrange", b"endbfrange"):
        # One token at a time, so an unclosed array cannot make the work grow with the square of the data.
        args = []
        array = None
        for m in _CMAP_TOKEN.finditer(block):
            hexes, opening, closing = m.groups()
            if opening:
                array = []
            elif closing:
                if array is not None and len(args) == 2 and args[0] and args[1]:
                    assign(args[0], args[1], array)
                args, array = [], None
            elif array is not None:
                array.append(hexes)
            else:
                args.append(hexes)
                if len(args) == 3:
                    if args[0] and args[1]:
                        assign(args[0], args[1], args[2])
                    args = []
    width = lengths.pop() if len(lengths) == 1 else None
    return table, width


class Font:
    def __init__(self, pdf, obj):
        self.table = None
        self.width_of = {}
        self.default_width = 500.0
        self.guessed = True  # the default width is the reader's guess, not one the font gives
        self.single = {}
        self.readable = True
        _spend_bytes(FONT_COST)
        obj = pdf.resolve(obj)
        if not isinstance(obj, dict):
            obj = {}
        subtype = pdf.resolve(obj.get("Subtype"))
        self.type3 = subtype == "Type3"
        self.two_byte = subtype == "Type0"
        to_unicode = pdf.resolve(obj.get("ToUnicode"))
        if isinstance(to_unicode, Stream):
            table, width = _cmap(pdf.stream_bytes(to_unicode))
            if table:
                self.table = {code: "" if ch and ch[0] < " " else ch for code, ch in table.items()}
                if width == 1:
                    self.two_byte = False
                elif width == 2:
                    self.two_byte = True
        if subtype == "Type0":
            self._cid_widths(pdf, obj)
            encoding = pdf.resolve(obj.get("Encoding"))
            if self.table is None and not (isinstance(encoding, str) and "UCS2" in encoding):
                self.readable = False
        else:
            self._simple_widths(pdf, obj)
            if self.table is None:
                self._encoding(pdf, pdf.resolve(obj.get("Encoding")))

    def _simple_widths(self, pdf, obj):
        first = pdf.resolve(obj.get("FirstChar"))
        widths = pdf.resolve(obj.get("Widths"))
        if isinstance(first, int) and isinstance(widths, list):
            for k, w in enumerate(widths):
                w = pdf.resolve(w)
                if isinstance(w, (int, float)):
                    self.width_of[first + k] = float(w)
        descriptor = pdf.resolve(obj.get("FontDescriptor"))
        if isinstance(descriptor, dict):
            missing = pdf.resolve(descriptor.get("MissingWidth"))
            if isinstance(missing, (int, float)) and missing > 0:
                self.default_width, self.guessed = float(missing), False

    def _cid_widths(self, pdf, obj):
        self.default_width, self.guessed = 1000.0, False
        kids = pdf.resolve(obj.get("DescendantFonts"))
        kid = pdf.resolve(kids[0]) if isinstance(kids, list) and kids else None
        if not isinstance(kid, dict):
            return
        dw = pdf.resolve(kid.get("DW"))
        if isinstance(dw, (int, float)):
            self.default_width = float(dw)
        w = pdf.resolve(kid.get("W"))
        if not isinstance(w, list):
            return
        i = 0
        while i < len(w):
            first = pdf.resolve(w[i])
            nxt = pdf.resolve(w[i + 1]) if i + 1 < len(w) else None
            if isinstance(nxt, list):
                for k, width in enumerate(nxt):
                    width = pdf.resolve(width)
                    if isinstance(first, int) and isinstance(width, (int, float)):
                        self.width_of[first + k] = float(width)
                i += 2
            else:
                last = nxt
                width = pdf.resolve(w[i + 2]) if i + 2 < len(w) else None
                if isinstance(first, int) and isinstance(last, int) and isinstance(width, (int, float)) and last - first < 70000:
                    _spend_steps(max(0, last - first + 1))
                    if len(self.width_of) > MAX_FONT_TABLE:
                        raise Unreadable(TOO_MUCH)
                    for code in range(first, last + 1):
                        self.width_of[code] = float(width)
                i += 3

    def _encoding(self, pdf, encoding):
        base = "cp1252"
        name = encoding if isinstance(encoding, str) else None
        differences = None
        if isinstance(encoding, dict):
            name = pdf.resolve(encoding.get("BaseEncoding"))
            differences = pdf.resolve(encoding.get("Differences"))
        if name == "MacRomanEncoding":
            base = "mac_roman"
        for code in range(256):
            # A code below 32 is no character, so a font with no map reads as no text.
            self.single[code] = "" if code < 32 else bytes([code]).decode(base, "replace").replace("�", "")
        self.single.update({0x27: "'", 0x60: "`"})
        if isinstance(differences, list):
            code = 0
            for item in differences:
                item = pdf.resolve(item)
                if isinstance(item, int):
                    code = item
                elif isinstance(item, str):
                    self.single[code] = _glyph(str(item))
                    code += 1

    def codes(self, raw):
        if self.two_byte:
            return [(raw[i] << 8) | raw[i + 1] for i in range(0, len(raw) - 1, 2)]
        return list(raw)

    def char(self, code):
        if self.table is not None and code in self.table:
            return self.table[code]
        if self.table is not None and not self.two_byte:
            return self.single.get(code, chr(code) if 32 <= code < 127 else "")
        if self.two_byte:
            return chr(code) if self.readable and 32 <= code < 0xD800 and self.table is None else ""
        return self.single.get(code, "")


# ---------------------------------------------------------------- page text


def _mul(m, n):
    """m applied first, then n; each is (a, b, c, d, e, f)."""
    return (m[0] * n[0] + m[1] * n[2], m[0] * n[1] + m[1] * n[3],
            m[2] * n[0] + m[3] * n[2], m[2] * n[1] + m[3] * n[3],
            m[4] * n[0] + m[5] * n[2] + n[4], m[4] * n[1] + m[5] * n[3] + n[5])


def _apply(c, x, y):
    return (x * c[0] + y * c[2] + c[4], x * c[1] + y * c[3] + c[5])


def _rect(points):
    """(x0, y0, x1, y1) when the points trace an upright rectangle, or None."""
    if len(points) == 5 and points[4] == points[0]:
        points = points[:4]
    if len(points) != 4:
        return None
    (ax, ay), (bx, by), (cx, cy), (dx, dy) = points
    near = 0.01
    if ((abs(ax - bx) < near and abs(by - cy) < near and abs(cx - dx) < near and abs(dy - ay) < near)
            or (abs(ay - by) < near and abs(bx - cx) < near and abs(cy - dy) < near and abs(dx - ax) < near)):
        return (min(ax, cx), min(ay, cy), max(ax, cx), max(ay, cy))
    return None


def _bounds(points):
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return (min(xs), min(ys), max(xs), max(ys))


def _inside(rect, other):
    """A rectangle cut down to another, or unchanged when the other is None."""
    if other is None:
        return rect
    return (max(rect[0], other[0]), max(rect[1], other[1]), min(rect[2], other[2]), min(rect[3], other[3]))


def _beyond(rect, xs, ys):
    """True when every place from (xs[0], ys[0]) to (xs[1], ys[1]) lies past one edge of the rectangle, so none is inside it."""
    return rect is not None and not (min(xs) <= rect[2] and max(xs) >= rect[0] and min(ys) <= rect[3] and max(ys) >= rect[1])


def _apart(rects):
    """True when no two rectangles overlap, so a fill of them cannot be a frame with a hole in it."""
    if len(rects) == 1:
        return True
    if len(rects) > 16:
        return False
    for i, r in enumerate(rects):
        for s in rects[i + 1:]:
            if r[0] < s[2] and s[0] < r[2] and r[1] < s[3] and s[1] < r[3]:
                return False
    return True


IDENTITY = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
BLACK = (0.0, 0.0, 0.0)
WHITE = (1.0, 1.0, 1.0)
PATTERN = "pattern"  # a fill that may be partly see-through
ALPHA_GONE = 0.05  # at or under this, paint cannot be seen
ALPHA_SOLID = 0.95  # at or over this, paint hides what is under it
SAME_COLOUR = 0.04  # ink this close to what is under it cannot be read
SMALLEST_GLYPH = 1.0  # points; a glyph under this cannot be read
WIDEST_GLYPH = 1.5  # of the font size; wider than any glyph of the standard fonts, the ones a PDF may name with no widths
NARROWEST_GLYPH = 0.138  # of the font size; the narrowest glyph of the standard fonts, the thin vertical bar of ZapfDingbats
SMALLEST_COVER = 0.4  # of a glyph's height: a thinner bar is a rule or a strike-through, and the glyph shows
IMAGE_SHARE = 0.5  # images over this share of the page make it a picture of a page
FALLBACK_PAGE_AREA = 400000.0  # about a Letter or A4 page, when a page gives no box
DROPPED_CODES = 3  # different codes with no map before a page counts as read only in part; one code is a separator
NO_COVER_ANNOTS = {"Link", "Widget", "Highlight", "Underline", "StrikeOut", "Squiggly", "Popup", "Text"}
STATE_NUMBERS = {"TL": "leading", "Tc": "tc", "Tw": "tw", "Ts": "rise", "w": "line"}  # operators that set one slot of State


class State:
    """The graphics state that q and Q save and restore and a form inherits. The text matrix is not in it."""

    __slots__ = ("ctm", "font", "size", "tc", "tw", "th", "rise", "leading", "tr", "fill", "stroke", "fill_space",
                 "stroke_space", "ca", "CA", "soft", "blend", "clip", "clip_known", "line")

    def __init__(self, ctm=IDENTITY):
        self.ctm = ctm
        self.font = None
        self.size = self.tc = self.tw = self.rise = self.leading = 0.0
        self.th = 1.0
        self.tr = 0
        self.fill = self.stroke = BLACK
        self.fill_space = self.stroke_space = "G"
        self.ca = self.CA = 1.0
        self.soft = self.blend = False
        self.clip = None
        self.clip_known = True
        self.line = 1.0

    def copy(self):
        new = State.__new__(State)
        for name in State.__slots__:
            setattr(new, name, getattr(self, name))
        return new


def _cmyk(c, m, y, k):
    return ((1 - c) * (1 - k), (1 - m) * (1 - k), (1 - y) * (1 - k))


def _colour(space, stack):
    """A fill or stroke colour from a colour space's numbers: RGB, or PATTERN, or None when not known."""
    if space == "P":
        return PATTERN
    nums = []
    for v in reversed(stack):
        if not isinstance(v, (int, float)) or isinstance(v, bool):
            break
        nums.insert(0, float(v))
    if space == "G" and nums:
        return (nums[-1],) * 3
    if space == "RGB" and len(nums) >= 3:
        return tuple(nums[-3:])
    if space == "CMYK" and len(nums) >= 4:
        return _cmyk(*nums[-4:])
    return None


class Page:
    def __init__(self, pdf, box=None):
        self.pdf = pdf
        self.box = box
        self.pieces = []
        self.paints = []  # (x0, y0, x1, y1, colour or None, hides what is under it, a drawn shape), in drawing order
        self.image_area = 0.0
        self.hidden, self.last = [], None  # the words a reader cannot see, and where the last hidden glyph ended
        self.dropped = set()
        self.forms = 0
        self.capture = True
        self.unread = False  # some of this page cannot be read: a form too deep, an annotation, damage

    def font(self, resources, name):
        res = self.pdf.resolve(resources)
        table = self.pdf.resolve(res.get("Font")) if isinstance(res, dict) else None
        obj = table.get(str(name)) if isinstance(table, dict) else None
        key = obj[0] if isinstance(obj, Ref) else id(obj)
        fonts = self.pdf.fonts
        if key not in fonts:
            fonts[key] = Font(self.pdf, obj)
        return fonts[key]

    def paint(self, rect, colour, covers, shape, g):
        """Note one thing painted, for what is drawn before it and after it. Thin lines hide nothing."""
        if len(self.paints) >= MAX_PAGE_PAINTS:
            self.unread = True
            return
        rect = _inside(rect, g.clip)
        if rect[2] - rect[0] < 1.0 or rect[3] - rect[1] < 1.0:
            return
        _spent.steps += 1
        self.paints.append((rect[0], rect[1], rect[2], rect[3], colour, covers, shape))

    def fill(self, path, g):
        _spend_steps(PAINT_STEPS * len(path))
        solid_paint = g.ca >= ALPHA_SOLID and not g.soft and not g.blend and g.fill != PATTERN and g.clip_known
        rects = [None if curved else _rect(points) for points, curved in path]
        colour = g.fill if solid_paint and isinstance(g.fill, tuple) else None
        solid = solid_paint and all(rects) and _apart(rects)
        for rect, (points, _curved) in zip(rects, path):
            if rect is None:
                self.paint(_bounds(points), None, False, True, g)
            else:
                self.paint(rect, colour if solid else None, solid, False, g)

    def stroke(self, path, g):
        """One straight upright line, wide enough to hide text, is a bar. Anything else stroked hides nothing."""
        if len(path) != 1 or path[0][1] or len(path[0][0]) != 2:
            return
        (ax, ay), (bx, by) = path[0][0]
        half = g.line * math.hypot(g.ctm[0], g.ctm[1]) / 2
        if half < 0.5:
            return
        if abs(ax - bx) < 0.01:
            rect = (ax - half, min(ay, by), ax + half, max(ay, by))
        elif abs(ay - by) < 0.01:
            rect = (min(ax, bx), ay - half, max(ax, bx), ay + half)
        else:
            return
        solid = g.CA >= ALPHA_SOLID and not g.soft and not g.blend and g.stroke != PATTERN and g.clip_known
        self.paint(rect, g.stroke if solid and isinstance(g.stroke, tuple) else None, solid, False, g)

    def image(self, g, masked):
        corners = [_apply(g.ctm, 0, 0), _apply(g.ctm, 1, 0), _apply(g.ctm, 1, 1), _apply(g.ctm, 0, 1)]
        rect = _rect(corners)
        if rect is None:
            self.image_area += abs(g.ctm[0] * g.ctm[3] - g.ctm[1] * g.ctm[2])
            self.paint(_bounds(corners), None, False, False, g)
            return
        seen = _inside(_inside(rect, g.clip), self.box)
        self.image_area += max(0.0, seen[2] - seen[0]) * max(0.0, seen[3] - seen[1])
        solid = not masked and g.ca >= ALPHA_SOLID and not g.soft and not g.blend and g.clip_known
        self.paint(rect, None, solid, False, g)

    def colour_space(self, resources, name):
        """"G", "RGB", "CMYK", "P" for a pattern, or None for a space whose colours are not worked out here."""
        name = str(name)
        known = {"DeviceGray": "G", "G": "G", "CalGray": "G", "DeviceRGB": "RGB", "RGB": "RGB", "CalRGB": "RGB",
                 "DeviceCMYK": "CMYK", "CMYK": "CMYK", "Pattern": "P"}
        if name in known:
            return known[name]
        res = self.pdf.resolve(resources)
        table = self.pdf.resolve(res.get("ColorSpace")) if isinstance(res, dict) else None
        space = self.pdf.resolve(table.get(name)) if isinstance(table, dict) else None
        if isinstance(space, str):
            return known.get(str(space))
        if isinstance(space, list) and space:
            family = self.pdf.resolve(space[0])
            if family == "ICCBased" and len(space) > 1:
                profile = self.pdf.resolve(space[1])
                n = self.pdf.resolve(profile.head.get("N")) if isinstance(profile, Stream) else None
                return {1: "G", 3: "RGB", 4: "CMYK"}.get(n)
            return known.get(str(family))
        return None

    def graphics_state(self, resources, name, g):
        res = self.pdf.resolve(resources)
        table = self.pdf.resolve(res.get("ExtGState")) if isinstance(res, dict) else None
        ext = self.pdf.resolve(table.get(str(name))) if isinstance(table, dict) else None
        if not isinstance(ext, dict):
            return
        resolve = self.pdf.resolve
        if isinstance(resolve(ext.get("ca")), (int, float)):
            g.ca = float(resolve(ext["ca"]))
        if isinstance(resolve(ext.get("CA")), (int, float)):
            g.CA = float(resolve(ext["CA"]))
        if "SMask" in ext:
            g.soft = resolve(ext["SMask"]) != "None"
        if "BM" in ext:
            blend = resolve(ext["BM"])
            blend = resolve(blend[0]) if isinstance(blend, list) and blend else blend
            g.blend = blend not in ("Normal", "Compatible")

    def run(self, data, resources, g, depth=0, off=0):
        lex = Lexer(data, 0, refs=False)
        stack = []
        saved = []
        marks = []
        path = []
        pending_clip = False
        text_clip = False
        tm = lm = IDENTITY
        slack = (0.0, 0.0)  # how far a guessed width may have put the text matrix from where tm says, low and high

        def line(new):
            """Put the text matrix at a place known exactly, the start of a line, so no guessed width carries over."""
            nonlocal tm, lm, slack
            tm = lm = new
            slack = (0.0, 0.0)

        def show(raw):
            nonlocal tm, text_clip, slack
            font = g.font
            if font is None or not self.capture:
                return
            _spend_steps(GLYPH_STEPS * (len(raw) >> 1 if font.two_byte else len(raw)))
            if len(self.pieces) + (len(raw) >> 1 if font.two_byte else len(raw)) > MAX_PAGE_GLYPHS:
                raise Unreadable(TOO_MUCH)
            ctm, size, th, tc, tw, rise = g.ctm, g.size, g.th, g.tc, g.tw, g.rise
            box, clip = self.box, g.clip
            type3 = font.type3
            # A Type 3 font paints with its own marks, so render mode and tiny sizes do not apply to it.
            mode = 0 if type3 else g.tr
            if mode >= 4:
                text_clip = True
            ghost = mode in (3, 7)
            unsure = g.soft or g.blend
            alpha = g.CA if mode in (1, 5) else g.ca
            gone = off > 0 or (not ghost and not unsure and alpha <= ALPHA_GONE)
            if type3 or ghost or unsure:
                colour = None
            elif mode in (0, 4):
                colour = g.fill
            elif mode in (1, 5):
                colour = g.stroke
            else:
                colour = g.fill if g.fill == g.stroke else None
            if not isinstance(colour, tuple):
                colour = None
            drawn = len(self.paints)
            for code in font.codes(raw):
                ch = font.char(code)
                at = _mul(tm, ctm)
                m = _mul((size * th, 0, 0, size, 0, rise), at)
                w = font.width_of.get(code, font.default_width) / 1000.0
                tx = (w * size + tc + (tw if code == 32 and not font.two_byte else 0.0)) * th
                tm = _mul((1, 0, 0, 1, tx, 0), tm)
                end = _mul(tm, ctm)
                x0, y0, x1, y1 = m[4], m[5], end[4], end[5]
                height = math.hypot(m[2], m[3])
                length = math.hypot(m[0], m[1])
                cx = (x0 + x1) / 2 + 0.33 * m[2]
                cy = (y0 + y1) / 2 + 0.33 * m[3]
                # A width the font does not give may be from the narrowest glyph to the widest, or none for a code that reads as
                # nothing, so a glyph after one is off the page or outside the clip only where it is outside at each such width.
                lo, hi = slack
                if font.guessed and code not in font.width_of:
                    span = sorted((((NARROWEST_GLYPH if ch else 0.0) - w) * size * th, (WIDEST_GLYPH - w) * size * th))
                    slack = (lo + span[0], hi + span[1])
                    lo, hi = lo + span[0] / 2, hi + span[1] / 2
                xs, ys = (cx + lo * at[0], cx + hi * at[0]), (cy + lo * at[1], cy + hi * at[1])
                if (gone or (not type3 and (height < SMALLEST_GLYPH or length < SMALLEST_GLYPH))
                        or _beyond(box, xs, ys) or _beyond(clip, xs, ys)):
                    if ch.strip():  # a hidden word starts where the last hidden glyph does not touch this one
                        self.hidden.append(ch if self.last is None or math.dist(self.last, (x0, y0)) > 0.16 * max(height, 1.0)
                                           else (self.hidden.pop() + ch)[:60])
                    self.last = (x1, y1) if ch.strip() else None
                    continue
                if not ch:
                    if not ghost:
                        self.dropped.add(code)
                    continue
                ux, uy = (m[0] / length, m[1] / length) if length else (1.0, 0.0)
                self.pieces.append((ch, x0, y0, x1, y1, height, ux, uy, cx, cy, colour, drawn, ghost))

        def finish():
            nonlocal pending_clip
            if pending_clip and path:
                outline = _bounds([p for points, _ in path for p in points])
                rect = _rect(path[0][0]) if len(path) == 1 and not path[0][1] else None
                g.clip = _inside(rect or outline, g.clip)
                if rect is None:
                    g.clip_known = False
            pending_clip = False
            path.clear()

        def add_path(points, curved):
            if len(path) >= MAX_PATH:
                outline = _bounds([p for pts, _ in path for p in pts])
                path[:] = [[[(outline[0], outline[1]), (outline[2], outline[3])], True]]
            path.append([points, curved])

        def extend_path(points, curved):
            if not path:
                add_path(points, curved)
                return
            path[-1][0].extend(points)
            path[-1][1] = path[-1][1] or curved
            if len(path[-1][0]) > 256:
                outline = _bounds(path[-1][0])
                path[-1] = [[(outline[0], outline[1]), (outline[2], outline[3])], True]

        while True:
            token = lex.value()
            if token is None:
                return
            if not isinstance(token, Op):
                stack.append(token)
                if len(stack) > 512:
                    del stack[:256]
                continue
            op = str(token)
            try:
                if op == "q":
                    if len(saved) >= MAX_SAVED:
                        raise Unreadable(TOO_MUCH)
                    saved.append(g)
                    g = g.copy()
                elif op == "Q":
                    if saved:
                        g = saved.pop()
                elif op == "cm":
                    g.ctm = _mul(tuple(float(v) for v in stack[-6:]), g.ctm)
                elif op == "BT":
                    line(IDENTITY)
                elif op == "ET":
                    if text_clip:
                        g.clip_known = False
                        text_clip = False
                elif op == "Tf":
                    g.font = self.font(resources, stack[-2])
                    g.size = float(stack[-1])
                elif op == "Td":
                    line(_mul((1, 0, 0, 1, float(stack[-2]), float(stack[-1])), lm))
                elif op == "TD":
                    g.leading = -float(stack[-1])
                    line(_mul((1, 0, 0, 1, float(stack[-2]), float(stack[-1])), lm))
                elif op == "Tm":
                    line(tuple(float(v) for v in stack[-6:]))
                elif op == "T*":
                    line(_mul((1, 0, 0, 1, 0, -g.leading), lm))
                elif op in STATE_NUMBERS:
                    setattr(g, STATE_NUMBERS[op], float(stack[-1]))
                elif op == "Tz":
                    g.th = float(stack[-1]) / 100.0
                elif op == "Tr":
                    g.tr = int(stack[-1])
                elif op == "Tj":
                    show(stack[-1])
                elif op == "'":
                    line(_mul((1, 0, 0, 1, 0, -g.leading), lm))
                    show(stack[-1])
                elif op == '"':
                    g.tw, g.tc = float(stack[-3]), float(stack[-2])
                    line(_mul((1, 0, 0, 1, 0, -g.leading), lm))
                    show(stack[-1])
                elif op == "TJ":
                    for item in stack[-1]:
                        if isinstance(item, bytes):
                            show(item)
                        elif isinstance(item, (int, float)):
                            tm = _mul((1, 0, 0, 1, -float(item) / 1000.0 * g.size * g.th, 0), tm)
                elif op == "re":
                    x, y, w, h = [float(v) for v in stack[-4:]]
                    c = g.ctm
                    add_path([_apply(c, x, y), _apply(c, x + w, y), _apply(c, x + w, y + h), _apply(c, x, y + h)], False)
                elif op == "m":
                    add_path([_apply(g.ctm, float(stack[-2]), float(stack[-1]))], False)
                elif op == "l":
                    extend_path([_apply(g.ctm, float(stack[-2]), float(stack[-1]))], False)
                elif op == "c":
                    nums = [float(v) for v in stack[-6:]]
                    extend_path([_apply(g.ctm, nums[k], nums[k + 1]) for k in (0, 2, 4)], True)
                elif op in ("v", "y"):
                    nums = [float(v) for v in stack[-4:]]
                    extend_path([_apply(g.ctm, nums[k], nums[k + 1]) for k in (0, 2)], True)
                elif op in ("f", "F", "f*", "B", "B*", "b", "b*"):
                    if path and not off:
                        self.fill(path, g)
                    finish()
                elif op in ("S", "s"):
                    if path and not off:
                        self.stroke(path, g)
                    finish()
                elif op == "n":
                    finish()
                elif op in ("W", "W*"):
                    pending_clip = True
                elif op == "g":
                    g.fill = (float(stack[-1]),) * 3
                    g.fill_space = "G"
                elif op == "G":
                    g.stroke = (float(stack[-1]),) * 3
                    g.stroke_space = "G"
                elif op == "rg":
                    g.fill = tuple(float(v) for v in stack[-3:])
                    g.fill_space = "RGB"
                elif op == "RG":
                    g.stroke = tuple(float(v) for v in stack[-3:])
                    g.stroke_space = "RGB"
                elif op == "k":
                    g.fill = _cmyk(*[float(v) for v in stack[-4:]])
                    g.fill_space = "CMYK"
                elif op == "K":
                    g.stroke = _cmyk(*[float(v) for v in stack[-4:]])
                    g.stroke_space = "CMYK"
                elif op == "cs":
                    g.fill_space = self.colour_space(resources, stack[-1])
                    g.fill = {"P": PATTERN, None: None}.get(g.fill_space, BLACK)
                elif op == "CS":
                    g.stroke_space = self.colour_space(resources, stack[-1])
                    g.stroke = {"P": PATTERN, None: None}.get(g.stroke_space, BLACK)
                elif op in ("sc", "scn"):
                    g.fill = _colour(g.fill_space, stack)
                elif op in ("SC", "SCN"):
                    g.stroke = _colour(g.stroke_space, stack)
                elif op == "gs":
                    self.graphics_state(resources, stack[-1], g)
                elif op == "sh":
                    if not off and (g.clip or self.box):
                        self.paint(g.clip or self.box, None, False, False, g)
                elif op == "BMC":
                    marks.append(False)
                elif op == "BDC":
                    hides = False
                    if len(stack) >= 2 and stack[-2] == "OC":
                        res = self.pdf.resolve(resources)
                        table = self.pdf.resolve(res.get("Properties")) if isinstance(res, dict) else None
                        hides = isinstance(table, dict) and self.pdf.layer_off(table.get(str(stack[-1])))
                    marks.append(hides)
                    off += 1 if hides else 0
                elif op == "EMC":
                    if marks and marks.pop():
                        off -= 1
                elif op == "Do":
                    self.form(resources, stack[-1], g, depth, off)
                elif op == "ID":  # an inline image: skip to its end
                    if not off:
                        masked = any(str(stack[k]) in ("IM", "ImageMask") and stack[k + 1] is True
                                     for k in range(len(stack) - 1) if isinstance(stack[k], str))
                        self.image(g, masked)
                    m = re.compile(rb"[ \t\r\n\f\0]EI(?![A-Za-z0-9])").search(data, lex.pos)
                    end = m.end() if m else len(data)
                    _spend_steps((end - lex.pos) >> 4)
                    lex.pos = end
            except (IndexError, TypeError, ValueError, AttributeError):
                pass  # one malformed operator costs that operator, not the page
            stack.clear()

    def form(self, resources, name, g, depth, off):
        res = self.pdf.resolve(resources)
        table = self.pdf.resolve(res.get("XObject")) if isinstance(res, dict) else None
        obj = self.pdf.resolve(table.get(str(name))) if isinstance(table, dict) else None
        if not isinstance(obj, Stream):
            return
        if self.pdf.layer_off(obj.head.get("OC")):
            off += 1
        subtype = self.pdf.resolve(obj.head.get("Subtype"))
        if subtype == "Image":
            if not off:
                self.image(g, self.pdf.resolve(obj.head.get("ImageMask")) is True or "SMask" in obj.head or "Mask" in obj.head)
        elif subtype == "Form":
            self.forms += 1
            if depth >= MAX_FORM_DEPTH or self.forms > MAX_PAGE_FORMS:
                self.unread = True
                return
            inner = g.copy()
            matrix = self.pdf.resolve(obj.head.get("Matrix"))
            if isinstance(matrix, list) and len(matrix) == 6:
                inner.ctm = _mul(tuple(float(self.pdf.resolve(v)) for v in matrix), g.ctm)
            self.form_clip(inner, self.pdf._box(obj.head.get("BBox")))
            self.run(self.pdf.stream_bytes(obj), obj.head.get("Resources", resources), inner, depth + 1, off)

    def form_clip(self, g, bbox):
        """A form draws only inside its box."""
        if bbox is None:
            return
        corners = [_apply(g.ctm, bbox[0], bbox[1]), _apply(g.ctm, bbox[2], bbox[1]),
                   _apply(g.ctm, bbox[2], bbox[3]), _apply(g.ctm, bbox[0], bbox[3])]
        rect = _rect(corners)
        g.clip = _inside(rect or _bounds(corners), g.clip)
        if rect is None:
            g.clip_known = False

    def annotations(self, page_dict, resources):
        """Comments and stamps draw over the page, so what they paint can hide its text. A page with one
        that holds an appearance has content this reader does not read."""
        resolve = self.pdf.resolve
        items = resolve(page_dict.get("Annots"))
        if not isinstance(items, list):
            return
        for item in items:
            _spend_steps(1)
            ann = resolve(item)
            if not isinstance(ann, dict):
                continue
            flags = resolve(ann.get("F"))
            if (isinstance(flags, int) and flags & 34) or self.pdf.layer_off(ann.get("OC")):
                continue  # hidden, or not for viewing
            subtype = resolve(ann.get("Subtype"))
            if subtype == "Link":
                continue
            look = resolve(ann.get("AP"))
            look = resolve(look.get("N")) if isinstance(look, dict) else None
            if isinstance(look, dict):
                look = resolve(look.get(str(resolve(ann.get("AS")))))
            rect = self.pdf._box(ann.get("Rect"))
            if isinstance(look, Stream):
                self.unread = True
            if subtype in NO_COVER_ANNOTS or rect is None:
                continue
            g = State()
            opacity = resolve(ann.get("CA"))
            if isinstance(opacity, (int, float)):
                g.ca = g.CA = float(opacity)
            if isinstance(look, Stream):
                self.appearance(look, rect, g, resources)
            elif subtype == "Square":
                inner = resolve(ann.get("IC"))
                if isinstance(inner, list) and len(inner) in (1, 3, 4):
                    nums = [float(resolve(v)) for v in inner]
                    g.fill = (nums[0],) * 3 if len(nums) == 1 else tuple(nums) if len(nums) == 3 else _cmyk(*nums)
                    self.fill([[[(rect[0], rect[1]), (rect[2], rect[1]), (rect[2], rect[3]), (rect[0], rect[3])], False]], g)

    def appearance(self, look, rect, g, resources):
        """Run an annotation's appearance for what it paints, with its box mapped onto the annotation's rectangle."""
        matrix = self.pdf.resolve(look.head.get("Matrix"))
        matrix = tuple(float(self.pdf.resolve(v)) for v in matrix) if isinstance(matrix, list) and len(matrix) == 6 else IDENTITY
        bbox = self.pdf._box(look.head.get("BBox")) or (0.0, 0.0, rect[2] - rect[0], rect[3] - rect[1])
        shown = _bounds([_apply(matrix, bbox[0], bbox[1]), _apply(matrix, bbox[2], bbox[1]),
                         _apply(matrix, bbox[2], bbox[3]), _apply(matrix, bbox[0], bbox[3])])
        sx = (rect[2] - rect[0]) / (shown[2] - shown[0]) if shown[2] > shown[0] else 1.0
        sy = (rect[3] - rect[1]) / (shown[3] - shown[1]) if shown[3] > shown[1] else 1.0
        place = (sx, 0.0, 0.0, sy, rect[0] - shown[0] * sx, rect[1] - shown[1] * sy)
        g.ctm = _mul(matrix, place)
        self.form_clip(g, bbox)
        self.capture = False
        try:
            self.run(self.pdf.stream_bytes(look), look.head.get("Resources", resources), g, 1)
        finally:
            self.capture = True

    def picture_of_a_page(self):
        area = FALLBACK_PAGE_AREA
        if self.box is not None:
            area = (self.box[2] - self.box[0]) * (self.box[3] - self.box[1])
        return self.image_area >= IMAGE_SHARE * area

    def read_in_part(self):
        return self.unread or len(self.dropped) >= DROPPED_CODES or self.picture_of_a_page()

    def _paint_grid(self):
        """Paints by coarse cell, so each glyph tests only the paints near it. Cells stay in drawing order."""
        xs = [p[8] for p in self.pieces]
        ys = [p[9] for p in self.pieces]
        left, right, low, high = min(xs), max(xs), min(ys), max(ys)
        size = max(32.0, (right - left) / 64, (high - low) / 64)
        grid = {}
        for k, paint in enumerate(self.paints):
            if paint[2] < left or paint[0] > right or paint[3] < low or paint[1] > high:
                continue
            ax, bx = int((max(paint[0], left) - left) / size), int((min(paint[2], right) - left) / size)
            ay, by = int((max(paint[1], low) - low) / size), int((min(paint[3], high) - low) / size)
            _spend_steps((bx - ax + 1) * (by - ay + 1))
            for i in range(ax, bx + 1):
                for j in range(ay, by + 1):
                    grid.setdefault((i, j), []).append(k)
        return grid, left, low, size

    def text(self):
        """The characters a reader can see, in stream order, with a space or a line break wherever position
        calls for one. Glyphs a later paint hides, and ink the colour of what is under it, drop out here."""
        pieces, paints = self.pieces, self.paints
        grid = None
        if paints and pieces:
            grid, left, low, size = self._paint_grid()
        picture = self.picture_of_a_page()
        out = []
        prev = self.last = None
        for ch, x0, y0, x1, y1, height, ux, uy, cx, cy, colour, drawn, ghost in pieces:
            under = None
            gone = False
            if grid is not None:
                nearby = grid.get((int((cx - left) / size), int((cy - low) / size)), ())
                _spent.steps += len(nearby)
                if _spent.steps > MAX_STEPS:
                    raise Unreadable(TOO_MUCH)
                for k in reversed(nearby):
                    paint = paints[k]
                    if paint[0] <= cx <= paint[2] and paint[1] <= cy <= paint[3]:
                        if k < drawn:
                            under = paint
                            break
                        if paint[5] and min(paint[2] - paint[0], paint[3] - paint[1]) >= SMALLEST_COVER * height:
                            gone = True
                            break
            if ghost:
                gone = gone or picture or under is None or not under[6]
            elif not gone and colour is not None:
                back = WHITE if under is None else under[4]
                gone = back is not None and (abs(colour[0] - back[0]) < SAME_COLOUR
                                             and abs(colour[1] - back[1]) < SAME_COLOUR
                                             and abs(colour[2] - back[2]) < SAME_COLOUR)
            if gone:
                if ch.strip():
                    self.hidden.append(ch if self.last is None or math.dist(self.last, (x0, y0)) > 0.16 * max(height, 1.0)
                                       else (self.hidden.pop() + ch)[:60])
                self.last = (x1, y1) if ch.strip() else None
                continue
            if prev is not None:
                px1, py1, pheight = prev
                em = max(height, pheight, 1.0)
                # Gaps along and across the text's own direction, so rotated text keeps its words.
                dx = (x0 - px1) * ux + (y0 - py1) * uy
                dy = abs((y0 - py1) * ux - (x0 - px1) * uy)
                if dy > 0.3 * em:
                    out.append("\n")
                elif dx > 0.16 * em:
                    if not (out and out[-1].endswith((" ", "\n"))) and ch != " ":
                        out.append(" ")
                elif dx < -2.0 * em:
                    out.append("\n")
            out.append(ch)
            prev = (x1, y1, height)
        text = "".join(out).translate(LIGATURES)
        lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
        return "\n".join(line for line in lines if line)


def _read_pdf_pages(data, scan):
    pdf = Pdf(data, scan)
    if pdf.encrypted:
        raise Unreadable("the PDF is encrypted")
    pages = pdf.pages()
    if not pages:
        if b"/Encrypt" in data:
            raise Unreadable("the PDF is encrypted")
        raise Unreadable("no pages were found in the PDF")
    out = []
    partly = []
    hidden = {}
    for number, (page_dict, resources, box) in enumerate(pages, 1):
        page = Page(pdf, box)
        contents = pdf.resolve(page_dict.get("Contents"))
        parts = contents if isinstance(contents, list) else [contents]
        blob = []
        total = 0
        for part in parts:
            stream = pdf.resolve(part)
            if isinstance(stream, Stream):
                blob.append(pdf.stream_bytes(stream))
                total += len(blob[-1])
                if total > MAX_STREAM:
                    raise Unreadable("a page in the PDF is too large to read")
        _spend_bytes(total)
        try:
            page.run(b"\n".join(blob), resources, State())
        except (ValueError, IndexError, TypeError, KeyError, RecursionError, zlib.error):
            page.unread = True  # keep whatever the page gave before the damage
        try:
            page.annotations(page_dict, resources)
        except (ValueError, IndexError, TypeError, KeyError, RecursionError, zlib.error):
            page.unread = True
        text = page.text()
        out.append(text)
        if text.strip() and page.read_in_part():
            partly.append(number)
        if page.hidden:
            hidden[number] = page.hidden
    _spent.partly, _spent.hidden = partly, hidden
    return out


def read_pdf(path):
    data = Path(path).read_bytes()
    if b"%PDF-" not in data[:1024]:
        raise Unreadable("the file does not start like a PDF")
    try:
        pages = _read_pdf_pages(data, False)
    except Damaged:
        pages = _read_pdf_pages(data, True)
        _spent.notes.append("its cross-reference table cannot be followed, so its pages were found by scanning; "
                            "compare them with the file")
    return pages
