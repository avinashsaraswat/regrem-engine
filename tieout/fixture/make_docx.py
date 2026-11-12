"""Word writer for the tie-out selftest: a .docx built from a tagged .md draft.

Purpose: build the Word twins the stage 1 scenarios need from report/draft.md, with the standard
  library only (zipfile and string building, no Word). Each inline tag {{words | cite}} becomes
  the words in the body with a Word comment on them whose text starts "TIE:", the way a drafter
  tags in Word. Footnotes go to word/footnotes.xml, numbered in the order the body references
  them. List items use Word numbering, so their numbers are structure and not text, and headings
  use the Heading styles. Options add what a scenario needs:
    comments=False   the served form: the tags' words stay, the comments and their ranges go
    tracked=True     one tracked deletion (w:del) and one tracked insertion (w:ins); accepting
                     both gives back the untracked text
    change=(a, b)    replace text a with b in the .md once before building (a served file with
                     one figure changed)
    certify=text     a closing paragraph with this text (the certification that quotes the
                     fingerprint), and certify_tracked=True writes it as a tracked insertion
  A tagged range is written as two runs where it holds a space, so a reader has to join runs to
  read the span. The zip entries are written in a fixed order with a fixed date, so one input
  gives one sha256.
  The parser here is its own, kept apart from claims.py on purpose: a .docx twin that yields the
  same claim keys as the .md draft then shows that two readers agree, not that one reader agrees
  with itself.
Reads: as a script, the .md draft named on the command line. As a library, nothing: build()
  takes the draft text.
Writes: as a script, the .docx path named on the command line. As a library, nothing: build()
  returns the bytes.
Network: none.
Exit codes: as a script, 0 written, 2 on a usage error or an unreadable draft.
Run: python3 -I tieout/fixture/make_docx.py report/draft.md report/draft.docx [--served]
"""
import argparse
import io
import re
import sys
import zipfile

sys.dont_write_bytecode = True

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
DECL = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
WHEN = "2026-11-01T09:00:00Z"  # an invented date for every comment and tracked change
ZIP_DATE = (1980, 1, 1, 0, 0, 0)

TAG_OR_REF = re.compile(r"\{\{(.*?)\}\}|\[\^(\d+)\]", re.S)
FOOTDEF = re.compile(r"^\[\^(\d+)\]:\s*")
LIST_MARK = re.compile(r"^(?:\d+\.|[-*])\s+")


# --- the .md draft as blocks --------------------------------------------------------------------


def blocks(md):
    """The draft's blocks in order: {kind, n, style, numbered, parts}. kind is para or foot; parts
    are ("text", s), ("tag", words, comment) and ("ref", n)."""
    md = md.replace("\r\n", "\n").replace("\r", "\n")
    first, _, rest = md.partition("\n")
    if first.lstrip("﻿").startswith("SYNTHETIC:"):
        md = rest  # the fixture marker line, which a reader drops
    out, cur = [], []
    for line in md.split("\n") + [""]:
        if line.strip():
            cur.append(line)
            continue
        if not cur:
            continue
        raw = " ".join(cur)
        m = FOOTDEF.match(raw)
        if m:
            out.append({"kind": "foot", "n": int(m.group(1)), "style": "FootnoteText", "numbered": False,
                        "parts": _parts(raw[m.end():])})
        elif raw.startswith("#"):
            level = len(raw) - len(raw.lstrip("#"))
            out.append({"kind": "para", "n": 0, "style": "Heading%d" % min(level, 3), "numbered": False,
                        "parts": _parts(raw.lstrip("#").strip())})
        elif raw.startswith(">"):
            body = " ".join(re.sub(r"^>\s?", "", ln) for ln in cur)
            out.append({"kind": "para", "n": 0, "style": "Quote", "numbered": False, "parts": _parts(body)})
        else:
            m = LIST_MARK.match(raw)
            out.append({"kind": "para", "n": 0, "style": "", "numbered": bool(m),
                        "parts": _parts(raw[m.end():] if m else raw)})
        cur = []
    return out


def _parts(raw):
    parts, pos = [], 0
    for m in TAG_OR_REF.finditer(raw):
        if m.start() > pos:
            parts.append(("text", raw[pos:m.start()]))
        if m.group(2) is not None:
            parts.append(("ref", int(m.group(2))))
        else:
            pieces = m.group(1).split("|")
            words = pieces[0].strip()
            rest = [p.strip() for p in pieces[1:] if p.strip()]
            parts.append(("tag", words, "TIE: " + " | ".join(rest)))
        pos = m.end()
    if pos < len(raw):
        parts.append(("text", raw[pos:]))
    return parts


# --- XML ----------------------------------------------------------------------------------------


def escape(text):
    """XML character escapes for element text. Written here because xml.sax.saxutils imports
    urllib, and this helper stays clear of every network module."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _run(text, deleted=False):
    if not text:
        return ""
    tag = "w:delText" if deleted else "w:t"
    return '<w:r><%s xml:space="preserve">%s</%s></w:r>' % (tag, escape(text), tag)


def _split_runs(words):
    """A tagged range as two runs when it holds a space, so the reader must join them."""
    cut = words.find(" ")
    if cut <= 0:
        return _run(words)
    return _run(words[:cut + 1]) + _run(words[cut + 1:])


class _Builder:
    def __init__(self, comments):
        self.comments = comments
        self.comment_xml = []
        self.foot_ids = {}  # footnote number in the .md -> id in footnotes.xml, by first reference

    def foot_id(self, n):
        if n not in self.foot_ids:
            self.foot_ids[n] = len(self.foot_ids) + 1
        return self.foot_ids[n]

    def content(self, parts):
        xml = []
        for p in parts:
            if p[0] == "text":
                xml.append(_run(p[1]))
            elif p[0] == "ref":
                xml.append('<w:r><w:rPr><w:rStyle w:val="FootnoteReference"/></w:rPr>'
                           '<w:footnoteReference w:id="%d"/></w:r>' % self.foot_id(p[1]))
            elif not self.comments:
                xml.append(_run(p[1]))  # served: the words stay, the tag goes
            else:
                cid = len(self.comment_xml)
                self.comment_xml.append(
                    '<w:comment w:id="%d" w:author="Drafter" w:date="%s" w:initials="D"><w:p>'
                    '<w:pPr><w:pStyle w:val="CommentText"/></w:pPr>%s</w:p></w:comment>' % (cid, WHEN, _run(p[2])))
                xml.append('<w:commentRangeStart w:id="%d"/>%s<w:commentRangeEnd w:id="%d"/>'
                           '<w:r><w:rPr><w:rStyle w:val="CommentReference"/></w:rPr>'
                           '<w:commentReference w:id="%d"/></w:r>' % (cid, _split_runs(p[1]), cid, cid))
        return "".join(xml)


def _ppr(style, numbered, inserted=False):
    inner = ""
    if style:
        inner += '<w:pStyle w:val="%s"/>' % style
    if numbered:
        inner += '<w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr>'
    if inserted:
        inner += '<w:rPr><w:ins w:id="9003" w:author="Reviewer" w:date="%s"/></w:rPr>' % WHEN
    return "<w:pPr>%s</w:pPr>" % inner if inner else ""


def build(md, comments=True, tracked=False, change=None, certify="", certify_tracked=False):
    """The .docx bytes for one tagged .md draft."""
    if change:
        if md.count(change[0]) != 1:
            raise ValueError("change: %r is in the draft %d times, not once" % (change[0], md.count(change[0])))
        md = md.replace(change[0], change[1])
    b = _Builder(comments)
    body, feet = [], {}
    for blk in blocks(md):
        if blk["kind"] == "foot":
            feet[blk["n"]] = blk
            continue
        body.append([blk["style"], blk["numbered"], b.content(blk["parts"])])
    if tracked:
        # a deletion of words the accepted text never had, and an insertion of the heading's
        # last word, so accepting both gives back the untracked text
        style, numbered, xml = body[0]
        words = re.findall(r'<w:t xml:space="preserve">([^<]*)</w:t>', xml)
        head = "".join(words)
        cut = head.rstrip().rfind(" ") + 1
        kept, moved = head[:cut], head[cut:]
        body[0][2] = ('<w:del w:id="9001" w:author="Reviewer" w:date="%s">%s</w:del>' % (WHEN, _run("DRAFT ", deleted=True))
                      + _run(kept) + '<w:ins w:id="9002" w:author="Reviewer" w:date="%s">%s</w:ins>' % (WHEN, _run(moved)))
    paras = ["<w:p>%s%s</w:p>" % (_ppr(style, numbered), xml) for style, numbered, xml in body]
    if certify:
        if certify_tracked:
            paras.append('<w:p>%s<w:ins w:id="9004" w:author="Reviewer" w:date="%s">%s</w:ins></w:p>'
                         % (_ppr("", False, inserted=True), WHEN, _run(certify)))
        else:
            paras.append("<w:p>%s</w:p>" % _run(certify))
    foot_xml = []
    for n, fid in sorted(b.foot_ids.items(), key=lambda kv: kv[1]):
        blk = feet.get(n)
        if blk is None:
            raise ValueError("footnote %d is referenced and never defined" % n)
        foot_xml.append('<w:footnote w:id="%d"><w:p>%s<w:r><w:rPr><w:rStyle w:val="FootnoteReference"/></w:rPr>'
                        '<w:footnoteRef/></w:r>%s%s</w:p></w:footnote>'
                        % (fid, _ppr("FootnoteText", False), _run(" "), b.content(blk["parts"])))
    document = (DECL + '<w:document xmlns:w="%s" xmlns:r="%s"><w:body>%s<w:sectPr/></w:body></w:document>'
                % (W_NS, R_NS, "".join(paras)))
    footnotes = (DECL + '<w:footnotes xmlns:w="%s">'
                 '<w:footnote w:type="separator" w:id="-1"><w:p><w:r><w:separator/></w:r></w:p></w:footnote>'
                 '<w:footnote w:type="continuationSeparator" w:id="0"><w:p><w:r><w:continuationSeparator/></w:r>'
                 '</w:p></w:footnote>%s</w:footnotes>' % (W_NS, "".join(foot_xml)))
    entries = [("[Content_Types].xml", _content_types(comments)), ("_rels/.rels", _root_rels()),
               ("word/_rels/document.xml.rels", _document_rels(comments)), ("word/document.xml", document),
               ("word/styles.xml", _styles()), ("word/numbering.xml", _numbering()),
               ("word/footnotes.xml", footnotes)]
    if comments:
        entries.append(("word/comments.xml", DECL + '<w:comments xmlns:w="%s">%s</w:comments>'
                        % (W_NS, "".join(b.comment_xml))))
    return _zip(entries)


def _zip(entries):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, text in entries:
            info = zipfile.ZipInfo(name, ZIP_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, text.encode("utf-8"))
    return buf.getvalue()


def _content_types(comments):
    main = "application/vnd.openxmlformats-officedocument.wordprocessingml"
    parts = [("/word/document.xml", main + ".document.main+xml"), ("/word/styles.xml", main + ".styles+xml"),
             ("/word/numbering.xml", main + ".numbering+xml"), ("/word/footnotes.xml", main + ".footnotes+xml")]
    if comments:
        parts.append(("/word/comments.xml", main + ".comments+xml"))
    return (DECL + '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            + "".join('<Override PartName="%s" ContentType="%s"/>' % p for p in parts) + "</Types>")


def _root_rels():
    return (DECL + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="%s/officeDocument" Target="word/document.xml"/></Relationships>' % R_NS)


def _document_rels(comments):
    rels = [("rId1", "styles", "styles.xml"), ("rId2", "numbering", "numbering.xml"),
            ("rId3", "footnotes", "footnotes.xml")]
    if comments:
        rels.append(("rId4", "comments", "comments.xml"))
    return (DECL + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            + "".join('<Relationship Id="%s" Type="%s/%s" Target="%s"/>' % (i, R_NS, t, f) for i, t, f in rels)
            + "</Relationships>")


def _styles():
    names = [("Heading1", "heading 1"), ("Heading2", "heading 2"), ("Heading3", "heading 3"), ("Quote", "Quote"),
             ("FootnoteText", "footnote text"), ("CommentText", "annotation text")]
    chars = [("FootnoteReference", "footnote reference"), ("CommentReference", "annotation reference")]
    return (DECL + '<w:styles xmlns:w="%s">' % W_NS
            + "".join('<w:style w:type="paragraph" w:styleId="%s"><w:name w:val="%s"/></w:style>' % s for s in names)
            + "".join('<w:style w:type="character" w:styleId="%s"><w:name w:val="%s"/></w:style>' % s for s in chars)
            + "</w:styles>")


def _numbering():
    return (DECL + '<w:numbering xmlns:w="%s"><w:abstractNum w:abstractNumId="0"><w:lvl w:ilvl="0">'
            '<w:start w:val="1"/><w:numFmt w:val="decimal"/><w:lvlText w:val="%%1."/></w:lvl></w:abstractNum>'
            '<w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num></w:numbering>' % W_NS)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Build a .docx twin of a tagged .md draft.")
    ap.add_argument("draft", help="the tagged .md draft")
    ap.add_argument("out", help="the .docx to write")
    ap.add_argument("--served", action="store_true", help="leave the comments out, as a served file")
    args = ap.parse_args(argv)
    try:
        with open(args.draft, encoding="utf-8") as fh:
            md = fh.read()
        data = build(md, comments=not args.served)
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        print("make_docx: %s" % exc, file=sys.stderr)
        return 2
    with open(args.out, "wb") as fh:
        fh.write(data)
    print("make_docx: wrote %s (%d bytes)" % (args.out, len(data)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
