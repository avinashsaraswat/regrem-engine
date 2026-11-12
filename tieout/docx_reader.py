"""Word reader for the tie-out: the text, comment tags and footnotes of a .docx draft.

Purpose: read a .docx with zipfile and xml.etree only, into the block form claims.py uses for
  every draft. A Word comment whose text starts "TIE:" on a selected range is a tag: the range
  is the span and the rest of the comment is the cite, "skip" or "calc: <expr>". Footnotes come
  from word/footnotes.xml and attach to the paragraph that carries the reference, numbered in
  the order the body references them. Tracked changes (w:ins and w:del, and Word's move marks
  w:moveTo and w:moveFrom) are refused by default with the count of each; with
  accept_tracked=True every insertion is applied and every deletion dropped. The served-file
  mode (served=True) reads with comments removed and changes accepted, for status --served.
  A list marker typed at the start of a paragraph is removed as the .md reader removes it, and
  its number is kept for the not-checked list; a number Word's own list numbering shows is not
  in the three parts this reader opens, so it has no row.
Reads: word/document.xml, word/comments.xml and word/footnotes.xml inside the .docx and nothing
  else. Each entry is capped at 64 MB and the three together at 256 MB; an entry that holds a
  DOCTYPE is refused before it is parsed.
Writes: nothing.
Network: none.
Exit codes: none; a library module. A refusal raises DocxError (DocxTracked for tracked
  changes), which the CLI reports as an input error, exit 2.
"""
import re
import xml.etree.ElementTree as ET
import zipfile

import claims

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
ENTRY_CAP = 64 * 1024 * 1024
TOTAL_CAP = 256 * 1024 * 1024
PARTS = ("word/document.xml", "word/comments.xml", "word/footnotes.xml")
SKIP = {"pPr", "rPr", "sectPr", "tblPr", "tblGrid", "trPr", "tcPr", "instrText", "delInstrText",
        "footnoteRef", "endnoteReference", "commentReference", "annotationRef"}
INSERT, DELETE = ("ins", "moveTo"), ("del", "moveFrom")
HEADING_STYLES = re.compile(r"^(?:Heading\d*|Title|Subtitle)$", re.I)
QUOTE_STYLES = re.compile(r"^(?:Quote|IntenseQuote|BlockText|Block Text)$", re.I)


class DocxError(ValueError):
    pass


class DocxTracked(DocxError):
    def __init__(self, insertions, deletions):
        DocxError.__init__(self, "the .docx holds tracked changes (%d insertions, %d deletions); accept or reject "
                           "them in Word, or run with --accept-tracked-changes" % (insertions, deletions))
        self.insertions, self.deletions = insertions, deletions


def local(tag):
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def _entries(path):
    """The three parts as bytes, under the caps and with no DOCTYPE."""
    out, total = {}, 0
    try:
        zf = zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError) as exc:
        raise DocxError("%s: not a readable .docx (%s)" % (path, exc))
    with zf:
        names = set(zf.namelist())
        for name in PARTS:
            if name not in names:
                continue
            info = zf.getinfo(name)
            if info.file_size > ENTRY_CAP:
                raise DocxError("%s: %s is over the 64 MB entry cap" % (path, name))
            with zf.open(name) as fh:
                data = fh.read(ENTRY_CAP + 1)
            if len(data) > ENTRY_CAP:
                raise DocxError("%s: %s is over the 64 MB entry cap" % (path, name))
            total += len(data)
            if total > TOTAL_CAP:
                raise DocxError("%s: the parts read are over the 256 MB total cap" % path)
            if re.search(rb"<!DOCTYPE", data, re.I):
                raise DocxError("%s: %s holds a DOCTYPE, which the reader refuses" % (path, name))
            out[name] = data
    if "word/document.xml" not in out:
        raise DocxError("%s: no word/document.xml" % path)
    return out


def _parse(data, name):
    try:
        return ET.fromstring(data)
    except ET.ParseError as exc:
        raise DocxError("%s does not parse: %s" % (name, exc))


def _count_changes(el, counts, in_props=False):
    """Insertions and deletions outside property blocks (a w:ins inside w:rPr only marks a
    paragraph mark, not inserted text)."""
    for child in el:
        name = local(child.tag)
        props = in_props or name in ("rPr", "pPr")
        if not props:
            if name in INSERT:
                counts[0] += 1
            elif name in DELETE:
                counts[1] += 1
        _count_changes(child, counts, props)


class _Para:
    """Text of one paragraph as it is walked, with footnote references and comment marks."""

    def __init__(self):
        self.parts, self.refs, self.starts, self.ends = [], [], {}, {}

    def pos(self):
        return sum(len(p) for p in self.parts)

    def text(self):
        return "".join(self.parts)


def _walk(el, para):
    for child in el:
        name = local(child.tag)
        if name in SKIP or name in DELETE:
            continue  # deletions are dropped: changes are accepted, or the reader refused first
        if name == "t":
            para.parts.append(child.text or "")
        elif name in ("tab", "br", "cr"):
            para.parts.append(" ")
        elif name == "noBreakHyphen":
            para.parts.append("-")
        elif name == "footnoteReference":
            para.refs.append((para.pos(), child.get(W + "id")))
        elif name == "commentRangeStart":
            para.starts[child.get(W + "id")] = para.pos()
        elif name == "commentRangeEnd":
            para.ends[child.get(W + "id")] = para.pos()
        else:
            _walk(child, para)


def _paragraphs(root):
    """Every w:p in document order, tables and content controls included, with its style and
    whether Word numbers it."""
    out = []

    def visit(el):
        for child in el:
            name = local(child.tag)
            if name == "p":
                style, numbered = "", False
                ppr = child.find(W + "pPr")
                if ppr is not None:
                    st = ppr.find(W + "pStyle")
                    style = st.get(W + "val", "") if st is not None else ""
                    numbered = ppr.find(W + "numPr") is not None
                para = _Para()
                _walk(child, para)
                out.append((para, style, numbered))
            elif name in ("tbl", "tr", "tc", "sdt", "sdtContent", "body", "customXml", "footnote") or name in INSERT:
                visit(child)

    visit(root)
    return out


def _comments(data):
    out = {}
    if data is None:
        return out
    for c in _parse(data, "word/comments.xml").iter(W + "comment"):
        texts = []
        for p in c.iter(W + "p"):
            texts.append("".join(t.text or "" for t in p.iter(W + "t")))
        out[c.get(W + "id")] = " ".join(texts).strip()
    return out


def _strip_marker(text, heading, block_quote):
    """A literal list marker is structure in the .md reader too; strip it the same way and keep
    the number it held, which is listed as not checked. Numbering Word applies itself lives in
    word/numbering.xml, which this reader does not open, so such a number is never text here."""
    if heading or block_quote:
        return text, 0, ""
    return claims.strip_list_marker(text)


def read(path, accept_tracked=False, served=False):
    """The draft as {"blocks", "errors", "tracked"}; raises DocxError or DocxTracked."""
    parts = _entries(path)
    doc = _parse(parts["word/document.xml"], "word/document.xml")
    feet = _parse(parts["word/footnotes.xml"], "word/footnotes.xml") if "word/footnotes.xml" in parts else None
    counts = [0, 0]
    _count_changes(doc, counts)
    if feet is not None:
        _count_changes(feet, counts)
    accepted = served or accept_tracked
    if (counts[0] or counts[1]) and not accepted:
        raise DocxTracked(counts[0], counts[1])
    comments = {} if served else _comments(parts.get("word/comments.xml"))
    errors, blocks = [], []
    body = doc.find(W + "body")
    body = doc if body is None else body

    raw_paras, n = [], 0
    for para, style, numbered in _paragraphs(body):
        text = para.text()
        if not text.strip():
            continue
        n += 1
        raw_paras.append((("para", n), para, HEADING_STYLES.match(style or "") is not None,
                          QUOTE_STYLES.match(style or "") is not None))

    order = []  # footnote ids in the order the body first references them
    for _, para, _, _ in raw_paras:
        for _, fid in para.refs:
            if fid not in order:
                order.append(fid)
    number = {fid: i for i, fid in enumerate(order, 1)}
    raw_feet = []
    if feet is not None:
        for fn in feet.iter(W + "footnote"):
            fid = fn.get(W + "id")
            if fn.get(W + "type") in ("separator", "continuationSeparator", "continuationNotice") or fid not in number:
                continue
            joined = _Para()
            for para, _, _ in _paragraphs(fn):
                if joined.parts and para.text().strip():
                    joined.parts.append(" ")
                base = joined.pos()
                joined.parts.extend(para.parts)
                joined.refs += [(base + o, f) for o, f in para.refs]
                joined.starts.update({k: base + v for k, v in para.starts.items()})
                joined.ends.update({k: base + v for k, v in para.ends.items()})
            raw_feet.append((("foot", number[fid]), joined, False, False))
    raw_feet.sort(key=lambda x: x[0][1])

    for where, para, heading, quote in raw_paras + raw_feet:
        text, cut, list_num = _strip_marker(para.text(), heading, quote)
        text = text.rstrip()
        tags = []
        if not served:
            ids = set(para.starts) | set(para.ends)
            for cid in sorted(ids, key=lambda k: para.starts.get(k, -1)):
                body_text = comments.get(cid, "")
                if not body_text.startswith("TIE:"):
                    continue
                if cid not in para.starts or cid not in para.ends:
                    errors.append(("I7", where, "TIE: comment %s spans more than one paragraph" % cid))
                    continue
                a, b = para.starts[cid] - cut, para.ends[cid] - cut
                a, b = max(a, 0), max(b, 0)
                seg = text[a:b]
                a += len(seg) - len(seg.lstrip())
                b -= len(seg) - len(seg.rstrip())
                span = text[a:b]
                t, cite, calc, skip, problem = claims._parse_tag(span + " | " + body_text[4:].strip())
                tags.append({"start": a, "end": b, "text": span, "cite": cite, "calc": calc, "skip": skip,
                             "raw": "TIE: " + body_text[4:].strip(), "problem": problem})
        refs = [(min(max(o - cut, 0), len(text)), number[f]) for o, f in para.refs if f in number]
        block = claims.finish_block(where[0], where[1], text, sorted(tags, key=lambda t: t["start"]), refs, heading, quote,
                                    list_number=list_num)
        if "{{" in text or "}}" in text:
            errors.append(("I7", where, "inline {{ }} tag in a .docx; a draft has one tag mode"))
        blocks.append(block)
    return {"blocks": blocks, "errors": errors,
            "tracked": {"insertions": counts[0], "deletions": counts[1],
                        "accepted": bool(accepted and (counts[0] or counts[1]))}}
