#!/usr/bin/env python3
"""Write the invented finding folder for agent run 01, and its archive.

Purpose: builds case/ (the letter as finding.md, internal audit's three questions and the evidence files) and
  gate/case.tar, a packed copy of case/ with fixed modes, owners, times and order. Every byte comes from this file:
  no clock, no locale, no randomness beyond a fixed counter, and no compression, so two runs on any machine give the
  same bytes.
Usage: python3 -I build/generate.py [--out <folder>]   (default: the folder above build/)
Reads: nothing. Writes: <out>/case/ (replaced whole) and <out>/gate/case.tar.
Network: none. Standard library only, Python 3.9 and later.
Everything in the case is invented. The institution, the finding, the roles, the staff numbers and every figure
are made up for this run.
"""
import argparse
import csv
import datetime
import email.utils
import io
import shutil
import sys
import tarfile
import zipfile
from pathlib import Path

D = datetime.date
SYNTHETIC = "SYNTHETIC. Everything in this folder is invented."
FINDING_ID = "MRA-PAM-05"

# ===================================================================== small helpers


def d(text):
    return D.fromisoformat(text)


def iso(day):
    return day.isoformat()


HOLIDAYS = {d("2026-04-03"), d("2026-04-06"), d("2026-05-04"), d("2026-05-25")}


def is_bd(day):
    return day.weekday() < 5 and day not in HOLIDAYS


def next_bd(day, n=1):
    while n:
        day += datetime.timedelta(days=1)
        if is_bd(day):
            n -= 1
    return day


def bdays(first, last):
    out, day = [], first
    while day <= last:
        if is_bd(day):
            out.append(day)
        day += datetime.timedelta(days=1)
    return out


def bd_between(start, end):
    """Business days after start, up to and including end."""
    return len([x for x in bdays(start + datetime.timedelta(days=1), end)])


class Counter:
    """A fixed sequence of numbers, the same on every run."""

    def __init__(self, seed):
        self.state = seed

    def next(self, n):
        self.state = (self.state * 1103515245 + 12345) % 2147483648
        return (self.state >> 8) % n


def allocate(total, days, weights=(23, 19, 20, 21, 17)):
    """Split a total over days by weekday weight, in whole numbers, largest remainder first."""
    w = [weights[x.weekday()] for x in days]
    s = sum(w)
    base = [total * x // s for x in w]
    rest = total - sum(base)
    order = sorted(range(len(days)), key=lambda i: (-(total * w[i] % s), i))
    for i in order[:rest]:
        base[i] += 1
    return base


def ascii_only(text, where):
    for ch in text:
        if ord(ch) > 126 or (ord(ch) < 32 and ch not in "\n\r\t"):
            raise SystemExit("non-ASCII character {!r} in {}".format(ch, where))
    return text


# ===================================================================== the case's data

# --- leavers processed by the HR feed --------------------------------------------------------

GO_LIVE = d("2026-03-16")


def build_leavers():
    segments = [
        (bdays(d("2026-03-02"), d("2026-03-13")), 136, True),
        (bdays(d("2026-03-16"), d("2026-03-19")), 27, False),
        (bdays(d("2026-03-20"), d("2026-03-31")), 74, False),
        (bdays(d("2026-04-01"), d("2026-04-30")), 384, False),
        (bdays(d("2026-05-01"), d("2026-05-31")), 371, False),
        (bdays(d("2026-06-01"), d("2026-06-29")), 380, False),
    ]
    leavers = []
    for days, total, backlog in segments:
        for day, n in zip(days, allocate(total, days)):
            for _ in range(n):
                leavers.append({"leave": day, "backlog": backlog, "type": "Employee"})
    for k, lv in enumerate(leavers, 1):
        lv["id"] = "L-{:04d}".format(k)
        lv["done"] = GO_LIVE if lv["backlog"] else next_bd(lv["leave"])
    assert len(leavers) == 1372
    april = [lv for lv in leavers if lv["leave"].month == 4]
    assert len(april) == 384
    # April contractors, from the contractor management log; each removed on the next business day.
    april_days = bdays(d("2026-04-01"), d("2026-04-30"))
    contractors = []
    for day, n in zip(april_days, allocate(61, april_days, (5, 3, 4, 3, 6))):
        for _ in range(n):
            contractors.append({"leave": day, "backlog": False, "type": "Contractor", "done": next_bd(day)})
    for k, c in enumerate(contractors, 1):
        c["id"] = "C-{:03d}".format(140 + k)
    assert len(contractors) == 61
    # The April sample: an interval of 11.125 through all 445 April leavers by leaving date, from the fifth.
    combined = []
    for day in april_days:
        emp = [x for x in april if x["leave"] == day]
        con = [x for x in contractors if x["leave"] == day]
        merged = list(emp)
        for j, c in enumerate(con):
            merged.insert((j + 1) * len(merged) // (len(con) + 1) + j, c)
        combined.extend(merged)
    assert len(combined) == 445
    for k, x in enumerate(combined):
        x["order"] = k
    sample = [combined[(4 * 1000 + 11125 * k) // 1000] for k in range(40)]
    assert len({x["id"] for x in sample}) == 40
    late = next(x for x in sample if x["type"] == "Employee" and x["leave"] >= d("2026-04-14"))
    late["done"] = next_bd(late["leave"], 2)
    sampled = {x["id"] for x in sample}
    # Exceptions: 23 employee leavers removed after the one-business-day deadline.
    exceptions = [late]
    pick = Counter(7)

    def choose(pool, n, gap, spread):
        out = []
        pool = [lv for lv in pool if lv["id"] not in sampled and lv not in exceptions]
        step = max(1, len(pool) // (n + 1))
        for i in range(n):
            lv = pool[step * (i + 1) - 1]
            out.append(lv)
            lv["done"] = next_bd(lv["leave"], gap + pick.next(spread))
        return out

    exceptions += choose([lv for lv in april if lv["leave"] <= d("2026-04-27")], 5, 2, 2)
    exceptions += choose([lv for lv in leavers if d("2026-05-01") <= lv["leave"] <= d("2026-05-27")], 8, 2, 2)
    exceptions += choose([lv for lv in leavers if d("2026-06-01") <= lv["leave"] <= d("2026-06-19")], 9, 2, 3)
    assert len(exceptions) == 23
    for lv in leavers + contractors:
        lv["bd"] = None if lv["backlog"] else bd_between(lv["leave"], lv["done"])
        assert lv["done"] <= d("2026-06-30")
    for lv in leavers + contractors:
        if not lv["backlog"] and lv not in exceptions:
            assert lv["bd"] == 1
    return leavers, contractors, sample, late, exceptions


LEAVERS, CONTRACTORS, SAMPLE, LATE, EXCEPTIONS = build_leavers()


def weekly_rows():
    weeks = {}
    for lv in LEAVERS:
        friday = lv["done"] + datetime.timedelta(days=(4 - lv["done"].weekday()) % 7)
        weeks.setdefault(friday, 0)
        weeks[friday] += 1
    return sorted(weeks.items())


# --- privileged accounts in the first quarterly review ---------------------------------------

REVIEWERS = [
    ("S20417", "Core banking database", "Platform owner", "pilot"),
    ("S20418", "Core banking database", "Database team lead", "pilot"),
    ("S20419", "Core banking database", "Database team lead", "main"),
    ("S20420", "Core banking database", "Deputy platform owner", "main"),
    ("S20531", "Payments gateway", "Platform owner", "pilot"),
    ("S20532", "Payments gateway", "Payments operations lead", "main"),
    ("S20533", "Payments gateway", "Payments engineering lead", "main"),
    ("S20534", "Payments gateway", "Deputy platform owner", "main"),
    ("S20761", "Customer channels", "Platform owner", "main"),
    ("S20762", "Customer channels", "Channels engineering lead", "pilot"),
    ("S20763", "Customer channels", "Channels operations lead", "main"),
    ("S20764", "Customer channels", "Deputy platform owner", "main"),
    ("S20941", "Data warehouse", "Platform owner", "pilot"),
    ("S20942", "Data warehouse", "Data engineering lead", "main"),
    ("S20943", "Data warehouse", "Deputy platform owner", "main"),
    ("S20101", "Directory and servers", "Platform owner", "pilot"),
    ("S20102", "Directory and servers", "Deputy platform owner", "main"),
    ("S20103", "Directory and servers", "Server team lead", "main"),
    ("S20104", "Directory and servers", "Directory team lead", "main"),
    ("S20105", "Directory and servers", "Server operations lead", "main"),
    ("S20187", "Network devices", "Platform owner", "main"),
    ("S20188", "Network devices", "Network engineering lead", "main"),
    ("S20189", "Network devices", "Deputy platform owner", "main"),
]
SESSIONS = {"pilot": d("2026-03-31"), "main": d("2026-04-02")}
PLATFORMS = [
    ("Core banking database", 72, 11),
    ("Payments gateway", 58, 8),
    ("Customer channels", 49, 7),
    ("Data warehouse", 41, 6),
    ("Directory and servers", 66, 10),
    ("Network devices", 32, 5),
]
WINDOW = (d("2026-04-07"), d("2026-04-17"))
DEPUTY_HELD = {"S20417": ("S20420", 3), "S20418": ("S20420", 2), "S20533": ("S20534", 1), "S20101": ("S20102", 2),
               "S20761": ("S20764", 1)}


def build_review():
    rnd = Counter(11)
    reviewer_ids = {r[0] for r in REVIEWERS}
    holders = []
    while len(holders) < 152:
        sid = "S1{:04d}".format(rnd.next(9000) + 1000)
        if sid not in holders:
            holders.append(sid)
    holders, spare = holders[:140], holders[140:]
    window_days = bdays(*WINDOW)
    rows = []
    extract_order = ["Payments gateway", "Customer channels", "Directory and servers", "Core banking database",
                     "Data warehouse", "Network devices"]
    for platform, count, revokes in sorted(PLATFORMS, key=lambda p: extract_order.index(p[0])):
        revs = [r for r in REVIEWERS if r[1] == platform]
        accounts = []
        special = []
        for holder, (deputy, n) in DEPUTY_HELD.items():
            if next(r for r in REVIEWERS if r[0] == holder)[1] == platform:
                special += [(holder, deputy)] * n
        for i in range(count):
            if i < len(special):
                holder, reviewer = special[i]
            else:
                holder = holders[rnd.next(len(holders))]
                reviewer = revs[i % len(revs)][0]
            assert holder != reviewer
            accounts.append({"platform": platform, "holder": holder, "reviewer": reviewer})
        order = sorted(range(count), key=lambda i: ((i * 37 + count // 2 + 5) % count, i))
        accounts = [accounts[i] for i in order]
        plain = [a for a in accounts if a["holder"] not in reviewer_ids]
        for a in plain[3:3 + revokes * 2:2]:
            a["decision"] = "revoke"
        for a in accounts:
            a.setdefault("decision", "keep")
            a["date"] = window_days[rnd.next(len(window_days))]
        rows.extend(accounts)
    revoked = [a for a in rows if a["decision"] == "revoke"]
    assert len(revoked) == 47 and len(rows) == 318
    for a in revoked:
        day = a["date"] + datetime.timedelta(days=3 + rnd.next(18))
        while not is_bd(day):
            day += datetime.timedelta(days=1)
        a["revoked"] = min(day, d("2026-05-07"))
    latest = max(range(len(revoked)), key=lambda k: (revoked[k]["date"], k))
    assert revoked[latest]["date"] >= d("2026-04-08")
    revoked[latest]["revoked"] = d("2026-05-08")
    for a in revoked:
        assert (a["revoked"] - a["date"]).days <= 30 and is_bd(a["revoked"])
    # twelve accounts disabled after the tool loaded them and before the review started; their holders hold no other
    disabled = []
    for k in range(12):
        platform = PLATFORMS[k % len(PLATFORMS)][0]
        disabled.append({"platform": platform, "holder": spare[k], "reviewer": "",
                         "decision": "not reviewed: disabled {} (leaver)".format(iso(d("2026-04-01") + datetime.timedelta(days=k % 2))),
                         "date": None})
    full = list(rows)
    slots = sorted({(k * 29 + 13) % 330 for k in range(12)})
    assert len(slots) == 12
    for slot, row in zip(slots, disabled):
        full.insert(slot, row)
    for k, a in enumerate(full):
        a["id"] = "PA-{}".format(1001 + k)
    for sid, platform, role, session in REVIEWERS:
        first = min((a["date"] for a in rows if a["reviewer"] == sid), default=None)
        assert first is not None and SESSIONS[session] < first
    return full, rows


EXTRACT, REVIEWED = build_review()


# --- orphaned privileged accounts -------------------------------------------------------------

def build_orphans():
    rnd = Counter(23)
    names = ["adm", "dba", "ops", "svc", "sys", "net", "app", "bkp"]
    platforms = [p[0] for p in PLATFORMS]
    removed_days = bdays(d("2026-03-02"), d("2026-03-31"))
    assigned_days = bdays(d("2026-03-09"), d("2026-05-29"))
    rows, taken = [], set()
    for k in range(214):
        platform = platforms[k % len(platforms)]
        while True:
            account = "{}_{}{:02d}".format(names[rnd.next(len(names))], platform.split()[0].lower()[:4], rnd.next(90) + 10)
            if account not in taken:
                taken.add(account)
                break
        rows.append({"id": "OA-{:03d}".format(k + 1), "platform": platform, "account": account})
    order = sorted(range(214), key=lambda i: ((i * 53) % 214, i))
    for n, i in enumerate(order):
        r = rows[i]
        if n < 131:
            r["outcome"], r["date"], r["owner"] = "removed", removed_days[rnd.next(len(removed_days))], ""
        else:
            r["outcome"], r["date"], r["owner"] = "assigned", assigned_days[rnd.next(len(assigned_days))], \
                "S1{:04d}".format(rnd.next(9000) + 1000)
    assigned = sorted((r for r in rows if r["outcome"] == "assigned"), key=lambda r: (r["date"], r["id"]))
    assigned[0]["date"] = d("2026-03-09")
    assigned[-1]["date"] = d("2026-05-29")
    assert len(assigned) == 83
    assert sum(r["date"] < d("2026-04-14") for r in assigned) >= 20
    return rows


ORPHANS = build_orphans()


# ===================================================================== PDF

HELV = [278, 278, 355, 556, 556, 889, 667, 191, 333, 333, 389, 584, 278, 333, 278, 278] + [556] * 10 + [
    278, 278, 584, 584, 584, 556, 1015, 667, 667, 722, 722, 667, 611, 778, 722, 278, 500, 667, 556, 833, 722, 778,
    667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 278, 278, 278, 469, 556, 333, 556, 556, 500, 556, 556,
    278, 556, 556, 222, 222, 500, 222, 833, 556, 556, 556, 556, 333, 500, 278, 556, 500, 722, 500, 500, 500, 334,
    260, 334, 584]
HELV_BOLD = [278, 333, 474, 556, 556, 889, 722, 238, 333, 333, 389, 584, 278, 333, 278, 278] + [556] * 10 + [
    333, 333, 584, 584, 584, 611, 975, 722, 722, 722, 722, 667, 611, 778, 722, 278, 556, 722, 611, 833, 722, 778,
    667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 333, 278, 333, 584, 556, 333, 556, 611, 556, 611, 556,
    333, 611, 611, 278, 278, 556, 278, 889, 611, 611, 611, 611, 389, 556, 333, 611, 556, 778, 556, 556, 500, 389,
    280, 389, 584]
assert len(HELV) == 95 and len(HELV_BOLD) == 95
FONTS = {"F1": ("Helvetica", HELV), "F2": ("Helvetica-Bold", HELV_BOLD)}
PAGE_W, PAGE_H = 612, 792
LEFT, RIGHT, TOP, BOTTOM = 72, 540, 732, 64


def width(text, font, size):
    table = FONTS[font][1]
    return sum(table[ord(c) - 32] for c in text) * size / 1000.0


def pdf_str(text):
    return "(" + text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") + ")"


def num(x):
    s = "{:.2f}".format(x).rstrip("0").rstrip(".")
    return s if s not in ("", "-0") else "0"


def wrap(text, font, size, room):
    words, lines, line = text.split(" "), [], ""
    for w in words:
        trial = w if not line else line + " " + w
        if width(trial, font, size) <= room or not line:
            line = trial
        else:
            lines.append(line)
            line = w
    if line:
        lines.append(line)
    return lines


class TextPage:
    """One page of a PDF laid out from blocks, top to bottom."""

    def __init__(self, footer):
        self.ops = []
        self.y = TOP
        self.footer = footer

    def put(self, x, y, text, font="F1", size=10):
        ascii_only(text, "PDF text")
        self.ops.append("BT /{} {} Tf 1 0 0 1 {} {} Tm {} Tj ET".format(font, num(size), num(x), num(y), pdf_str(text)))

    def need(self, h):
        if self.y - h < BOTTOM:
            raise SystemExit("page overflow at: {!r}".format(self.ops[-1][-80:] if self.ops else ""))

    def title(self, text):
        for line in wrap(text, "F2", 14, RIGHT - LEFT):
            self.need(19)
            self.y -= 14
            self.put(LEFT, self.y, line, "F2", 14)
            self.y -= 5
        self.y -= 8

    def heading(self, text):
        self.y -= 4
        for line in wrap(text, "F2", 11, RIGHT - LEFT):
            self.need(15)
            self.y -= 11
            self.put(LEFT, self.y, line, "F2", 11)
            self.y -= 4
        self.y -= 3

    def para(self, text, size=10, indent=0, bullet=None):
        lead = size * 1.35
        x = LEFT + indent + (12 if bullet else 0)
        lines = wrap(text, "F1", size, RIGHT - x)
        for k, line in enumerate(lines):
            self.need(lead)
            self.y -= size
            if k == 0 and bullet:
                self.put(LEFT + indent, self.y, bullet, "F1", size)
            self.put(x, self.y, line, "F1", size)
            self.y -= lead - size
        self.y -= 5

    def bullets(self, items, size=10):
        for item in items:
            self.para(item, size, bullet="-")
            self.y += 3

    def kv(self, pairs, size=10, key_width=150):
        lead = size * 1.4
        for k, v in pairs:
            lines = wrap(v, "F1", size, RIGHT - LEFT - key_width)
            for n, line in enumerate(lines):
                self.need(lead)
                self.y -= size
                if n == 0:
                    self.put(LEFT, self.y, k, "F2", size)
                self.put(LEFT + key_width, self.y, line, "F1", size)
                self.y -= lead - size
        self.y -= 6

    def table(self, head, rows, size=9, gap=14, lead=None):
        lead = lead or size * 1.38
        cols = len(head)
        widths = [max([width(head[c], "F2", size)] + [width(str(r[c]), "F1", size) for r in rows]) for c in range(cols)]
        total = sum(widths) + gap * (cols - 1)
        if LEFT + total > RIGHT + 30:
            raise SystemExit("table too wide: {}".format(head))
        xs, x = [], LEFT
        for w in widths:
            xs.append(x)
            x += w + gap
        self.need(lead)
        self.y -= size
        for c in range(cols):
            self.put(xs[c], self.y, head[c], "F2", size)
        self.y -= lead - size
        for r in rows:
            self.need(lead)
            self.y -= size
            for c in range(cols):
                cell = str(r[c])
                if cell:
                    self.put(xs[c], self.y, cell, "F1", size)
            self.y -= lead - size
        self.y -= 6

    def space(self, h=8):
        self.y -= h

    def signature(self, lines):
        self.space(10)
        for line in lines:
            self.need(14)
            self.y -= 10
            self.put(LEFT, self.y, line, "F1", 10)
            self.y -= 4

    def finish(self, number, total):
        text = "{} - page {} of {}".format(self.footer, number, total)
        self.put(LEFT, 40, text, "F1", 8)
        return "\n".join(self.ops).encode("ascii")


# --- a bitmap font for the scanned page -------------------------------------------------------

GLYPHS = {
    "A": ".###.#...##...#######...##...##...#", "B": "####.#...##...#####.#...##...#####.",
    "C": ".###.#...##....#....#....#...#.###.", "D": "####.#...##...##...##...##...#####.",
    "E": "######....#....####.#....#....#####", "F": "######....#....####.#....#....#....",
    "G": ".###.#...##....#.####...##...#.####", "H": "#...##...##...#######...##...##...#",
    "I": ".###...#....#....#....#....#...###.", "J": "..###...#....#....#....#.#..#..##..",
    "K": "#...##..#.#.#..##...#.#..#..#.#...#", "L": "#....#....#....#....#....#....#####",
    "M": "#...###.###.#.##.#.##...##...##...#", "N": "#...##...###..##.#.##..###...##...#",
    "O": ".###.#...##...##...##...##...#.###.", "P": "####.#...##...#####.#....#....#....",
    "Q": ".###.#...##...##...##.#.##..#..##.#", "R": "####.#...##...#####.#.#..#..#.#...#",
    "S": ".#####....#.....###.....#....#####.", "T": "#####..#....#....#....#....#....#..",
    "U": "#...##...##...##...##...##...#.###.", "V": "#...##...##...##...##...#.#.#...#..",
    "W": "#...##...##...##.#.##.#.##.#.#.#.#.", "X": "#...##...#.#.#...#...#.#.#...##...#",
    "Y": "#...##...#.#.#...#....#....#....#..", "Z": "#####....#...#...#...#...#....#####",
    "0": ".###.#...##..###.#.###..##...#.###.", "1": "..#...##....#....#....#....#...###.",
    "2": ".###.#...#....#...#...#...#...#####", "3": "#####...#...#.....#.....##...#.###.",
    "4": "...#...##..#.#.#..#.#####...#....#.", "5": "######....####.....#....##...#.###.",
    "6": "..##..#...#....####.#...##...#.###.", "7": "#####....#...#...#...#....#....#...",
    "8": ".###.#...##...#.###.#...##...#.###.", "9": ".###.#...##...#.####....#...#..##..",
    "-": "...............#####...............", ".": ".........................##...##...",
    ",": "....................##....#...#....", ":": ".....##...##.........##...##.......",
    "/": ".........#...#...#...#...#.........", "(": "...#...#...#....#....#.....#.....#.",
    ")": ".#.....#.....#....#....#...#...#...", " ": "." * 35,
    "'": "..#....#...#.......................",
}
for _k, _v in list(GLYPHS.items()):
    GLYPHS[_k] = (_v + "." * 35)[:35]


class Bitmap:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.px = bytearray(w * h)  # 0 white, 1 black

    def dot(self, x, y):
        if 0 <= x < self.w and 0 <= y < self.h:
            self.px[y * self.w + x] = 1

    def box(self, x0, y0, x1, y1, t=2):
        for x in range(x0, x1 + 1):
            for k in range(t):
                self.dot(x, y0 + k)
                self.dot(x, y1 - k)
        for y in range(y0, y1 + 1):
            for k in range(t):
                self.dot(x0 + k, y)
                self.dot(x1 - k, y)

    def text(self, x, y, s, scale=3):
        for ch in s:
            g = GLYPHS[ch]
            for row in range(7):
                for col in range(5):
                    if g[row * 5 + col] == "#":
                        for a in range(scale):
                            for b in range(scale):
                                self.dot(x + col * scale + a, y + row * scale + b)
            x += 6 * scale

    def scribble(self, x, y, length):
        """A signature: a looping pen line, the same on every run."""
        import math
        last = None
        for i in range(length * 4):
            t = i / 4.0
            px = int(x + t)
            py = int(y + 14 * math.sin(t / 9.0) + 7 * math.sin(t / 3.1))
            if last:
                steps = max(abs(px - last[0]), abs(py - last[1]), 1)
                for s in range(steps + 1):
                    qx = last[0] + (px - last[0]) * s // steps
                    qy = last[1] + (py - last[1]) * s // steps
                    for a in range(3):
                        for b in range(3):
                            self.dot(qx + a, qy + b)
            last = (px, py)

    def speckle(self, n, seed):
        rnd = Counter(seed)
        for _ in range(n):
            self.dot(rnd.next(self.w), rnd.next(self.h))

    def packed(self):
        """1 bit a pixel, rows padded to a byte, 1 for white as DeviceGray reads it."""
        out = bytearray()
        for y in range(self.h):
            row = self.px[y * self.w:(y + 1) * self.w]
            for k in range(0, self.w, 8):
                byte = 0
                for j in range(8):
                    black = row[k + j] if k + j < self.w else 0
                    byte = (byte << 1) | (0 if black else 1)
                out.append(byte)
        return bytes(out)


def run_length(data):
    out, i, n = bytearray(), 0, len(data)
    while i < n:
        j = i
        while j + 1 < n and data[j + 1] == data[i] and j - i < 127:
            j += 1
        if j > i:
            out += bytes([257 - (j - i + 1), data[i]])
            i = j + 1
            continue
        j = i
        while j + 1 < n and j - i < 127 and not (j + 2 < n and data[j + 1] == data[j + 2]):
            j += 1
        out += bytes([j - i]) + data[i:j + 1]
        i = j + 1
    out.append(128)
    return bytes(out)


def hex_lines(data):
    h = data.hex()
    return ("\n".join(h[k:k + 128] for k in range(0, len(h), 128)) + ">").encode("ascii")


def scan_image(lines):
    bm = Bitmap(850, 1100)
    y = 120
    for kind, text in lines:
        if kind == "gap":
            y += 40
        elif kind == "sig":
            bm.text(110, y, text)
            bm.scribble(340, y + 8, 260)
            y += 60
        else:
            bm.text(110, y, text, 4 if kind == "big" else 3)
            y += 50 if kind == "big" else 36
    bm.box(80, 80, 770, y + 30, 3)
    bm.speckle(900, 5)
    return bm


def build_pdf(pages, footer):
    """pages: a list whose items are a function laying out a TextPage, or ('scan', lines)."""
    objs = []

    def add(body):
        objs.append(body)
        return len(objs)

    font_ids = {}
    for key, (name, table) in FONTS.items():
        font_ids[key] = add("<< /Type /Font /Subtype /Type1 /BaseFont /{} /Encoding /WinAnsiEncoding /FirstChar 32 "
                            "/LastChar 126 /Widths [{}] >>".format(name, " ".join(map(str, table))).encode("ascii"))
    pages_id = add(None)
    kids = []
    total = len(pages)
    for number, spec in enumerate(pages, 1):
        if isinstance(spec, tuple) and spec[0] == "scan":
            bm = scan_image(spec[1])
            data = hex_lines(run_length(bm.packed()))
            img = add(b"<< /Type /XObject /Subtype /Image /Width 850 /Height 1100 /ColorSpace /DeviceGray "
                      b"/BitsPerComponent 1 /Filter [/ASCIIHexDecode /RunLengthDecode] /Length "
                      + str(len(data)).encode("ascii") + b" >>\nstream\n" + data + b"\nendstream")
            content = b"q 612 0 0 792 0 0 cm /Im1 Do Q"
            resources = "<< /XObject << /Im1 {} 0 R >> >>".format(img)
        else:
            page = TextPage(footer)
            spec(page)
            content = page.finish(number, total)
            resources = "<< /Font << /F1 {} 0 R /F2 {} 0 R >> >>".format(font_ids["F1"], font_ids["F2"])
        cid = add(b"<< /Length " + str(len(content)).encode("ascii") + b" >>\nstream\n" + content + b"\nendstream")
        kids.append(add("<< /Type /Page /Parent {} 0 R /MediaBox [0 0 612 792] /Resources {} /Contents {} 0 R >>".format(
            pages_id, resources, cid).encode("ascii")))
    objs[pages_id - 1] = "<< /Type /Pages /Kids [{}] /Count {} >>".format(
        " ".join("{} 0 R".format(k) for k in kids), len(kids)).encode("ascii")
    root = add("<< /Type /Catalog /Pages {} 0 R >>".format(pages_id).encode("ascii"))
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for n, body in enumerate(objs, 1):
        offsets.append(len(out))
        out += "{} 0 obj\n".format(n).encode("ascii") + body + b"\nendobj\n"
    xref = len(out)
    out += "xref\n0 {}\n".format(len(objs) + 1).encode("ascii") + b"0000000000 65535 f \n"
    out += b"".join("{:010d} 00000 n \n".format(o).encode("ascii") for o in offsets)
    out += "trailer\n<< /Size {} /Root {} 0 R >>\nstartxref\n{}\n%%EOF\n".format(len(objs) + 1, root, xref).encode("ascii")
    return bytes(out)


# ===================================================================== Office files

ZIP_TIME = (1980, 1, 1, 0, 0, 0)


def build_zip(parts):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as zf:
        for name, data in parts:
            info = zipfile.ZipInfo(name, date_time=ZIP_TIME)
            info.compress_type = zipfile.ZIP_STORED
            info.create_system = 3
            info.external_attr = 0o644 << 16
            zf.writestr(info, data)
    return buf.getvalue()


def xml_escape(text):
    ascii_only(text, "Office text")
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


SS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG = "http://schemas.openxmlformats.org/package/2006/relationships"


def col_name(n):
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def build_xlsx(sheets):
    """sheets: (name, rows, hidden, column widths). A cell is text or a whole number; dates are kept as text."""
    parts = []
    ctypes = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
              '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">',
              '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>',
              '<Default Extension="xml" ContentType="application/xml"/>',
              '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>',
              '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>']
    for k in range(len(sheets)):
        ctypes.append('<Override PartName="/xl/worksheets/sheet{}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'.format(k + 1))
    ctypes.append("</Types>")
    parts.append(("[Content_Types].xml", "".join(ctypes).encode("utf-8")))
    parts.append(("_rels/.rels", ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="{}">'
                                  '<Relationship Id="rId1" Type="{}/officeDocument" Target="xl/workbook.xml"/>'
                                  '</Relationships>').format(PKG, REL).encode("utf-8")))
    wb = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="{}" xmlns:r="{}">'.format(SS, REL),
          '<bookViews><workbookView activeTab="0"/></bookViews><sheets>']
    rels = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="{}">'.format(PKG)]
    for k, (name, rows, hidden, widths) in enumerate(sheets, 1):
        wb.append('<sheet name="{}" sheetId="{}"{} r:id="rId{}"/>'.format(xml_escape(name), k,
                                                                         ' state="hidden"' if hidden else "", k))
        rels.append('<Relationship Id="rId{}" Type="{}/worksheet" Target="worksheets/sheet{}.xml"/>'.format(k, REL, k))
        body = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?><worksheet xmlns="{}">'.format(SS)]
        if widths:
            body.append("<cols>")
            for c, w in enumerate(widths, 1):
                body.append('<col min="{0}" max="{0}" width="{1}" customWidth="1"/>'.format(c, w))
            body.append("</cols>")
        body.append("<sheetData>")
        for r, row in enumerate(rows, 1):
            if not row:
                continue
            body.append('<row r="{}">'.format(r))
            for c, cell in enumerate(row, 1):
                ref = "{}{}".format(col_name(c), r)
                if cell is None or cell == "":
                    continue
                if isinstance(cell, int):
                    body.append('<c r="{}"><v>{}</v></c>'.format(ref, cell))
                else:
                    body.append('<c r="{}" t="inlineStr"><is><t xml:space="preserve">{}</t></is></c>'.format(ref, xml_escape(cell)))
            body.append("</row>")
        body.append("</sheetData></worksheet>")
        parts.append(("xl/worksheets/sheet{}.xml".format(k), "".join(body).encode("utf-8")))
    wb.append("</sheets></workbook>")
    rels.append('<Relationship Id="rId{}" Type="{}/styles" Target="styles.xml"/>'.format(len(sheets) + 1, REL))
    rels.append("</Relationships>")
    parts.insert(2, ("xl/workbook.xml", "".join(wb).encode("utf-8")))
    parts.insert(3, ("xl/_rels/workbook.xml.rels", "".join(rels).encode("utf-8")))
    parts.append(("xl/styles.xml", ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><styleSheet xmlns="{}">'
                                    '<fonts count="1"><font><sz val="11"/><name val="Calibri"/></font></fonts>'
                                    '<fills count="2"><fill><patternFill patternType="none"/></fill>'
                                    '<fill><patternFill patternType="gray125"/></fill></fills>'
                                    '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
                                    '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
                                    '<cellXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/></cellXfs>'
                                    '</styleSheet>').format(SS).encode("utf-8")))
    return build_zip(parts)


WNS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def build_docx(paragraphs):
    """paragraphs: lists of runs, each ('t', text), ('b', bold text), ('ins', text, author, date) or
    ('del', text, author, date). A paragraph may start with ('style', 'Heading1')."""
    body, rid = [], [0]

    def run(text, bold=False):
        props = "<w:rPr><w:b/></w:rPr>" if bold else ""
        return '<w:r>{}<w:t xml:space="preserve">{}</w:t></w:r>'.format(props, xml_escape(text))

    for para in paragraphs:
        out, size = [], None
        for item in para:
            if item[0] == "size":
                size = item[1]
            elif item[0] == "t":
                out.append(run(item[1]))
            elif item[0] == "b":
                out.append(run(item[1], True))
            elif item[0] in ("ins", "del"):
                rid[0] += 1
                attrs = 'w:id="{}" w:author="{}" w:date="{}"'.format(rid[0], xml_escape(item[2]), item[3])
                if item[0] == "ins":
                    out.append("<w:ins {}>{}</w:ins>".format(attrs, run(item[1])))
                else:
                    out.append('<w:del {}><w:r><w:delText xml:space="preserve">{}</w:delText></w:r></w:del>'.format(
                        attrs, xml_escape(item[1])))
        ppr = ""
        if size:
            ppr = '<w:pPr><w:rPr><w:sz w:val="{}"/></w:rPr></w:pPr>'.format(size)
        body.append("<w:p>{}{}</w:p>".format(ppr, "".join(out)))
    doc = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="{}"><w:body>{}'
           '<w:sectPr><w:pgSz w:w="12240" w:h="15840"/><w:pgMar w:top="1440" w:right="1440" w:bottom="1440" '
           'w:left="1440" w:header="720" w:footer="720" w:gutter="0"/></w:sectPr></w:body></w:document>').format(
        WNS, "".join(body))
    parts = [
        ("[Content_Types].xml", ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                                 '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                                 '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                                 '<Default Extension="xml" ContentType="application/xml"/>'
                                 '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
                                 '</Types>').encode("utf-8")),
        ("_rels/.rels", ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="{}">'
                         '<Relationship Id="rId1" Type="{}/officeDocument" Target="word/document.xml"/>'
                         '</Relationships>').format(PKG, REL).encode("utf-8")),
        ("word/document.xml", doc.encode("utf-8")),
    ]
    return build_zip(parts)


def build_eml(sender, to, when, subject, body, cc=None):
    lines = ["From: " + sender, "To: " + to]
    if cc:
        lines.append("Cc: " + cc)
    lines += ["Date: " + email.utils.format_datetime(when), "Subject: " + subject, "MIME-Version: 1.0",
              'Content-Type: text/plain; charset="us-ascii"', "Content-Transfer-Encoding: 7bit", ""]
    text = "\r\n".join(lines) + "\r\n" + "\r\n".join(body.split("\n")) + "\r\n"
    return ascii_only(text, "email").encode("ascii")


def build_csv(header, rows):
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(header)
    for r in rows:
        w.writerow(["" if c is None else c for c in r])
    return ascii_only(buf.getvalue(), "CSV").encode("ascii")


def tz(hours):
    return datetime.timezone(datetime.timedelta(hours=hours))


# ===================================================================== the documents

def doc_board_minutes():
    f = "Board of directors, minutes of the meeting of 2026-02-12"

    def p1(pg):
        pg.title("Minutes of the meeting of the board of directors")
        pg.kv([("Date", "2026-02-12, 14:00"), ("Place", "Board room, head office"),
               ("Present, by role", "Chair of the board; Chief Executive Officer; Chief Financial Officer; Chief Risk "
                                    "Officer; chair of the Board Risk Committee; four independent non-executive directors"),
               ("In attendance", "Chief Information Security Officer (item 4); Chief Technology Officer (items 4 and 9); "
                                 "Company Secretary"),
               ("Quorum", "The chair confirmed that the meeting was quorate.")])
        pg.heading("Item 1. Declarations of interest")
        pg.para("No director declared an interest in the business of the meeting.")
        pg.heading("Item 2. Minutes of the previous meeting")
        pg.para("The minutes of the meeting of 2026-01-15 were approved as a true record.")
        pg.heading("Item 3. Chief Executive Officer's report")
        pg.para("The Chief Executive Officer reported on trading in January, the branch network review and the "
                "progress of the new mobile banking release. The board noted the report.")

    def p2(pg):
        pg.heading("Item 4. Remediation plan for supervisory finding " + FINDING_ID)
        pg.para("The Chief Information Security Officer presented the remediation plan for the Supervisor's letter of "
                "2026-01-20 on privileged access. The letter requires a plan approved by the board within 30 days. "
                "The plan sets five milestones, each with an owner role and a committed date.")
        pg.table(["Milestone", "Owner role", "Committed date"], [
            ["M1 Revise and approve the access management standard", "Chief Information Security Officer", "2026-03-31"],
            ["M2 Automate leaver notices; remove every leaver's access", "Head of Identity Services", "2026-04-30"],
            ["M3 Remove or assign an owner to every orphaned account", "Head of Infrastructure", "2026-05-31"],
            ["M4 Train reviewers; complete the first quarterly review", "Head of Identity Services", "2026-06-30"],
            ["M5 Extend the quarterly review to the cloud hosting platform", "Head of Infrastructure", "2026-07-31"],
        ], size=8.5, gap=10)
        pg.para("For M3, the Chief Information Security Officer estimated about 240 orphaned privileged accounts, a "
                "figure the baseline extract planned for the end of February would confirm.")
        pg.para("The board asked how the bank would know that each milestone was met. The Chief Information Security "
                "Officer said that each milestone owner would hold signed evidence, that internal audit would test "
                "the remediation before the bank asks the Supervisor to consider the matter, and that progress "
                "would be reported to the Board Risk Committee each quarter.")
        pg.para("Decision: the board approved the remediation plan for " + FINDING_ID + " with the milestones, owner "
                "roles and committed dates in the table above, and asked the Company Secretary to send the "
                "approved plan to the Supervisor.")

    def p3(pg):
        pg.heading("Item 5. Liquidity and funding")
        pg.para("The Chief Financial Officer presented the liquidity position at the end of January. All internal "
                "limits were met. The board noted the report.")
        pg.heading("Item 6. Operational resilience")
        pg.para("The Chief Risk Officer reported on the annual self-assessment of important business services. Two "
                "services need further testing of their recovery plans before the next self-assessment. The board "
                "asked for an update at its meeting in May.")
        pg.heading("Item 7. Committee reports")
        pg.para("The chair of the Board Risk Committee reported on the committee's meeting of 2026-01-29. The "
                "committee had reviewed the risk appetite statement and recommended no change. The board noted the "
                "report.")
        pg.heading("Item 8. Board effectiveness review")
        pg.para("The Company Secretary presented the timetable for this year's board effectiveness review. The board "
                "agreed the timetable.")

    def p4(pg):
        pg.heading("Item 9. Amendment to item 4")
        pg.para("The Chief Technology Officer reported that the cloud hosting platform moves to a new operating team "
                "in the second quarter, under the Head of Cloud Engineering, and that the move would leave too little "
                "time to bring the platform into the quarterly review by the date in item 4.")
        pg.para("Decision: the board amended the remediation plan approved under item 4. M5 is owned by the Head of "
                "Cloud Engineering, with a committed date of 2026-09-30. The other milestones stand as approved under "
                "item 4.")
        pg.heading("Item 10. Any other business")
        pg.para("There was no other business. The meeting closed at 16:10.")
        pg.signature(["Signed as a true record of the meeting.", "Company Secretary", "Date: 2026-02-19"])

    return build_pdf([p1, p2, p3, p4], f)


STANDARD_COMMON = {
    "p2": ("2. Purpose and scope", [
        "2.1 This standard sets how the Bank grants, reviews and removes access to its systems, so that each person "
        "holds only the access their role needs, and no longer than they need it.",
        "2.2 It applies to every account on every Bank system, held by employees, contractors and third parties.",
        "2.3 It applies to every platform the Bank runs, including the core banking database, the payments gateway, "
        "the customer channels, the data warehouse, the directory and servers, the network devices and the cloud "
        "hosting platform.",
        "2.4 The Chief Information Security Officer owns this standard. Each platform owner applies it on their "
        "platform."]),
    "p3": ("3. Definitions", [
        "Privileged account: an account that can change a system's configuration, its security settings, other "
        "accounts or data that other people rely on.",
        "Orphaned account: a privileged account with no named owner.",
        "Leaver: an employee or contractor whose work for the Bank has ended.",
        "Leaving date: the last day a leaver works for the Bank.",
        "Business day: a day other than a Saturday, a Sunday or a bank holiday.",
        "Reviewer: the platform owner, or a person the platform owner names, who decides for each privileged account "
        "whether it is still needed.",
        "Deputy reviewer: the reviewer who decides on an account that the usual reviewer cannot decide on."]),
    "p5": ("5. Privileged access", [
        "5.1 Each platform owner reviews every privileged account on it at least once in each calendar quarter.",
        "5.2 A reviewer completes the reviewer training before their first review.",
        "5.3 No reviewer certifies an account they hold. Such an account goes to the deputy reviewer.",
        "5.4 Access a reviewer decides to revoke is removed within 30 days of the decision.",
        "5.5 The review tool keeps each decision, its reviewer and its date for 7 years.",
        "5.6 An account without a named owner is dealt with under section 6, and joins the quarterly review once it has "
        "one."]),
    "p6": ("6. Orphaned accounts", [
        "6.1 Every privileged account has a named owner.",
        "6.2 An account found with no named owner is removed, or assigned a named owner, within 120 days of the date "
        "it was found.",
        "6.3 The platform owner records the outcome for each orphaned account, with its date."]),
    "p7": ("7. Governance", [
        "7.1 The Board Risk Committee approves this standard and any change to it.",
        "7.2 The Chief Information Security Officer may approve an exception to this standard for up to 90 days from "
        "the date of approval. Each exception is recorded in the exceptions register with its reason and its end date.",
        "7.3 The Chief Information Security Officer reviews this standard at least once a year and brings any change "
        "to the Board Risk Committee."]),
}


def doc_standard():
    f = "Access management standard, version 4.0"

    def p1(pg):
        pg.title("Access management standard")
        pg.heading("1. Document control")
        pg.kv([("Version", "4.0"), ("Status", "Approved"), ("Owner", "Chief Information Security Officer"),
               ("Approved by", "Board Risk Committee, 2026-03-26"), ("Effective date", "2026-04-01"),
               ("Replaces", "Version 3.2"), ("Next review", "2027-03-31")])
        pg.para("This standard is part of the Bank's information security policy framework. Where it conflicts with a "
                "local procedure, this standard applies.")

    def section(key):
        def lay(pg):
            title, items = STANDARD_COMMON[key]
            pg.heading(title)
            for item in items:
                pg.para(item)
        return lay

    def p4(pg):
        pg.heading("4. Leavers")
        pg.para("4.1 From 2026-04-01, the identity team removes a leaver's access within one business day of the "
                "leaving date.")
        pg.para("4.2 For an employee, the HR system sends a leaver notice to the identity tool. For a contractor, the "
                "contractor management team tells the identity team on the contractor's last day.")
        pg.para("4.3 A line manager who learns that a person has left, and sees no sign that their access was removed, "
                "tells the identity team the same day.")
        pg.para("4.4 The identity team keeps a record of each leaver, the leaving date and the date each account was "
                "removed, and reports how many leavers were removed outside the deadline each month.")

    def p8(pg):
        pg.heading("8. Document history")
        rows = [["3.2", "2024-09-12", "Board Risk Committee", "Annual review; no change of substance"],
                ["4.0", "2026-03-26", "Board Risk Committee", "Adds the leaver deadline (4.1), the quarterly review"],
                ["", "", "", "of privileged access (5.1 to 5.4) and orphaned accounts (6)"]]
        pg.table(["Version", "Approved on", "Approved by", "Change"], rows, size=9)
        pg.signature(["Signed for issue by the owner of this standard.", "Chief Information Security Officer",
                      "Date: 2026-03-27"])

    return build_pdf([p1, section("p2"), section("p3"), p4, section("p5"), section("p6"), section("p7"), p8], f)


def doc_brc_minutes():
    f = "Board Risk Committee, minutes of the meeting of 2026-03-26"

    def p1(pg):
        pg.title("Board Risk Committee: minutes")
        pg.kv([("Meeting", "2026-03-26, 10:00, head office"),
               ("Present, by role", "Committee chair; two independent non-executive directors; Chief Risk Officer"),
               ("In attendance", "Chief Information Security Officer (item 3); Head of Operational Risk (item 4); "
                                 "committee secretary"),
               ("Quorum", "Quorate")])
        pg.heading("Item 1. Minutes of the previous meeting")
        pg.para("The minutes of the meeting of 2026-01-29 were approved.")
        pg.heading("Item 2. Matters arising")
        pg.para("The Chief Risk Officer confirmed that the action on third-party risk reporting from the last meeting "
                "is complete. No other matters arose.")

    def p2(pg):
        pg.heading("Item 3. Access management standard")
        pg.para("The Chief Information Security Officer presented version 4.0 of the access management standard, "
                "which is milestone M1 of the remediation plan for " + FINDING_ID + ". Version 4.0 sets a deadline "
                "of one business day for removing a leaver's access, requires each platform owner to review every "
                "privileged account each quarter, requires reviewers to be trained before they review, and sets "
                "rules for orphaned accounts.")
        pg.para("The committee asked whether one business day could be met for contractors, who are not in the HR "
                "system. The Chief Information Security Officer said that the contractor management team would "
                "notify the identity team on each contractor's last day, as section 4.2 of the standard requires.")
        pg.para("Decision: the committee approved version 4.0 of the access management standard on 2026-03-26, with "
                "effect from 2026-04-01.")

    def p3(pg):
        pg.heading("Item 4. Operational risk report")
        pg.para("The Head of Operational Risk presented the operational risk report for February. Losses were within "
                "appetite. The committee noted the report.")
        pg.heading("Item 5. Any other business")
        pg.para("None. The next meeting is on 2026-04-23.")
        pg.signature(["Signed as a true record.", "Board Risk Committee chair", "Date: 2026-04-23"])

    return build_pdf([p1, p2, p3], f)


def doc_brc_terms():
    f = "Board Risk Committee, terms of reference"

    def p1(pg):
        pg.title("Board Risk Committee: terms of reference")
        pg.kv([("Approved by", "The board, 2025-11-20"), ("Next review", "2026-11-30")])
        pg.heading("1. Purpose")
        pg.para("The committee oversees the Bank's risk management framework on behalf of the board.")
        pg.heading("2. Duties")
        pg.bullets(["Recommend the risk appetite statement to the board.",
                    "Approve the Bank's risk policies and standards, including its information security standards, "
                    "and any change to them.",
                    "Receive progress reports on supervisory findings and their remediation.",
                    "Review the reports of the Chief Risk Officer and the Chief Information Security Officer."])
        pg.heading("3. Management forums")
        pg.para("Management forums support the committee. A management forum may approve procedures and guidance "
                "that apply a standard. It may not approve a policy or a standard, or a change to one.")

    def p2(pg):
        pg.heading("4. Membership and quorum")
        pg.para("The committee has at least three independent non-executive directors, one of whom chairs it. Two "
                "members form a quorum.")
        pg.heading("5. Meetings")
        pg.para("The committee meets at least six times a year. The committee secretary keeps the minutes, and the "
                "chair signs them once the committee has approved them.")
        pg.signature(["Signed for the board.", "Company Secretary", "Date: 2025-11-20"])

    return build_pdf([p1, p2], f)


def doc_change_record():
    f = "Change record CHG-2026-04417"

    def p1(pg):
        pg.title("Change record CHG-2026-04417")
        pg.kv([("Title", "Automated leaver notices from the HR system to the identity tool"),
               ("Requested by", "Head of Identity Services"),
               ("Risk rating", "Medium"),
               ("Approved", "Change advisory board, 2026-03-12"),
               ("Planned start", "2026-03-16, 05:30"),
               ("Implemented", "2026-03-16, 06:00")])
        pg.heading("Description")
        pg.para("The HR system sends a leaver notice to the identity tool at 06:00 each business day, for each employee "
                "whose leaving date has passed. The identity tool disables the leaver's directory account, which ends "
                "access to every platform that signs in through the directory, records the time, and raises a task "
                "for each account the leaver holds on a platform that does not. Contractors are not in the HR system, "
                "and this change does not cover them.")
        pg.heading("Back-out plan")
        pg.para("Switch off the feed and return to leaver notices by email from line managers.")

    def p2(pg):
        pg.heading("Post-implementation review, 2026-03-23")
        pg.para("The first run on 2026-03-16 processed the notices of every employee who had left since 2026-03-02 and "
                "whose access had not been removed. Each later run has completed before 08:00. No back-out was needed.")
        pg.para("Outcome: the change is successful and the record is complete.")
        pg.signature(["Change advisory board chair", "Date: 2026-03-23"])

    return build_pdf([p1, p2], f)


def doc_review_method():
    f = "Privileged access review method, version 2.3"

    def p1(pg):
        pg.title("Privileged access review method")
        pg.kv([("Version", "2.3"), ("Owner", "Head of Identity Services"),
               ("Approved by", "Chief Information Security Officer, 2026-03-30"),
               ("Applies", "Section 5 of the access management standard")])
        pg.heading("Method")
        pg.bullets(["The review tool loads every privileged account on the platforms in the review, with its holder "
                    "and the date it was last used.",
                    "Each reviewer decides keep or revoke for each account on their list. An account held by the "
                    "reviewer goes to the deputy reviewer.",
                    "A reviewer keeps an account unused for 90 days only with a recorded reason.",
                    "The identity team removes the access for each revoke decision and records the date in the tool.",
                    "The review report gives the accounts reviewed, kept and revoked for each platform, and any "
                    "account left out of the review with the reason."])

    def p2(pg):
        pg.heading("Changes")
        pg.table(["Version", "Date", "Change"], [
            ["2.2", "2025-10-06", "Review tool replaces the spreadsheet return"],
            ["2.3", "2026-03-30", "Aligned with version 4.0 of the access management standard"]], size=9)
        pg.signature(["Approved.", "Chief Information Security Officer", "Date: 2026-03-30"])

    return build_pdf([p1, p2], f)


def doc_leaver_mi():
    summary = [
        ["Leaver removal MI"],
        ["As at", "2026-06-30"],
        ["Source", "Identity governance MI report"],
        ["Measure", "Business days from the leaving date to the disabling of the leaver's directory account"],
        [],
        ["Item", "Value"],
        ["Feed go-live", "2026-03-16"],
        ["Leavers processed by the feed since go-live", 1372],
        ["Measured against the deadline (leaving date from 2026-04-01)", 1135],
        ["Removed within the deadline", 1112],
        ["Removed within the deadline, share", "98.0%"],
        ["Removed outside the deadline", 23],
        ["Deadline", "1 business day (access management standard, version 4.0)"],
        ["Contractor leavers", "Outside the feed; see the Monthly sheet"],
    ]
    assert 1112 + 23 == 1135 == 384 + 371 + 380 and round(1000 * 1112 / 1135) == 980
    weekly = [["Leavers processed by the feed, by week of processing"], [], ["Week ending", "Leavers processed", "Note"]]
    weeks = weekly_rows()
    assert dict(weeks)[d("2026-03-20")] == 163 and sum(n for _, n in weeks) == 1372
    for friday, n in weeks:
        note = "Includes the first run on 2026-03-16: a backlog of 136 leavers" if friday == d("2026-03-20") else ""
        label = iso(friday) if friday <= d("2026-06-30") else "2026-06-30 (week to date)"
        weekly.append([label, n, note])
    weekly.append(["Total", 1372, ""])
    monthly = [["Leavers by leaving month"], [],
               ["Leaving month", "Employees, processed by the feed", "Contractors, notified by email (outside the feed)",
                "Contractors removed within one business day", "All leavers"],
               ["March 2026 (includes the backlog from 2026-03-02)", 237, 38, "Not measured (before 2026-04-01)", 275],
               ["April 2026", 384, 61, 61, 445],
               ["May 2026", 371, 57, 57, 428],
               ["June 2026 (leaving dates to 2026-06-29)", 380, 59, 59, 439],
               ["Total", 1372, 215, 177, 1587],
               [],
               ["Contractor removal dates come from the contractor management log, which the identity team checks "
                "each month; the identity tool does not hold them."]]
    exceptions = [["Leavers removed outside the deadline"], [],
                  ["Leaver", "Leaving date", "Access removed", "Business days", "Reason"]]
    for k, lv in enumerate(sorted(EXCEPTIONS, key=lambda x: x["id"])):
        assert lv["bd"] > 1
        if lv is LATE:
            reason = "HR notice entered a day late"
        elif lv["bd"] == 2:
            reason = ("HR notice entered a day late", "Feed run failed; notice sent again on the next run")[k % 2]
        else:
            reason = ("Leaving date entered in the HR system after the leaving date",
                      "Notice held for a disputed leaving date")[k % 2]
        exceptions.append([lv["id"], iso(lv["leave"]), iso(lv["done"]), lv["bd"], reason])
    exceptions += [[], ["Business days exclude weekends and the bank holidays of 2026-04-03, 2026-04-06, 2026-05-04 "
                        "and 2026-05-25."]]
    calc = [["Bank holidays used in business day counts"], ["2026-04-03"], ["2026-04-06"], ["2026-05-04"],
            ["2026-05-25"], [], ["Deadline in business days"], ["From 2026-04-01", 1]]
    return build_xlsx([("Summary", summary, False, [58, 60]), ("Weekly", weekly, False, [22, 18, 58]),
                       ("Monthly", monthly, False, [46, 30, 44, 40, 12]),
                       ("Exceptions", exceptions, False, [10, 13, 15, 14, 60]),
                       ("Calc", calc, True, [40, 10])])


def doc_sample_test():
    f = "Leaver removal sample test, April 2026"
    rows = sorted(SAMPLE, key=lambda x: x["order"])
    employees = sum(x["type"] == "Employee" for x in SAMPLE)

    def p1(pg):
        pg.title("Leaver removal sample test, April 2026")
        pg.kv([("Prepared by", "IT controls testing team"), ("Milestone", "M2 of the remediation plan for " + FINDING_ID),
               ("Test period", "Leaving dates from 2026-04-01 to 2026-04-30")])
        pg.heading("Objective")
        pg.para("Confirm that every leaver's access, employee or contractor, is removed within one business day of "
                "the leaving date, as M2 of the remediation plan and section 4.1 of the access management standard "
                "require.")
        pg.heading("Population")
        pg.para("Leavers with a leaving date from 2026-04-01 to 2026-04-30: 445. Of these, 384 are employees recorded "
                "in the HR system and 61 are contractors recorded in the contractor management log (leaver removal "
                "MI, Monthly sheet).")
        pg.para("For context, the feed had processed 621 leavers with leaving dates up to the end of the test period, "
                "the March backlog included.")
        pg.heading("Method")
        pg.para("The testing team listed the 445 leavers by leaving date and drew 40 with the sampling tool's interval "
                "method, starting with the fifth. The sample holds {} employees and {} contractors. For each leaver it "
                "took the leaving date from the HR system or the contractor log, and the date each account was "
                "removed from the identity tool or the contractor log, and counted the business days between them. "
                "Results are on page 2 and the conclusion on page 3.".format(employees, 40 - employees))

    def p2(pg):
        pg.heading("Results")
        pg.table(["Leaver", "Type", "Leaving date", "Access removed", "Business days"],
                 [[x["id"], x["type"], iso(x["leave"]), iso(x["done"]), x["bd"]] for x in rows], size=8, gap=30,
                 lead=10.6)
        pg.para("Business days exclude weekends and the bank holidays of 2026-04-03 and 2026-04-06.", size=8)

    def p3(pg):
        pg.heading("Conclusion")
        pg.para("39 of the 40 leavers in the sample had their access removed within one business day of the leaving "
                "date. One employee leaver, {}, left on {} and was removed on {}, after 2 business days, because the "
                "HR notice was entered a day late.".format(LATE["id"], iso(LATE["leave"]), iso(LATE["done"])))
        pg.para("The testing team concludes that access is removed within the deadline in the great majority of cases, "
                "and that late entry of leaving dates in the HR system caused the exception found.")
        pg.heading("Approval")
        pg.para("The Head of IT Risk approved the method and the results of this test by email on 2026-05-06.")

    assert LATE["bd"] == 2 and sum(x["bd"] == 1 for x in SAMPLE) == 39
    return build_pdf([p1, p2, p3], f)


def doc_approval_email():
    assert 237 + 384 == 621
    body = ("Thanks for the April leaver removal sample test.\n\n"
            "I have reviewed the test and I approve its method and its results. The test drew 40 of the April "
            "leavers; the MI's Monthly sheet shows 348 employee leavers in April and 61 contractors. 39 of the 40 had "
            "their access removed within one business day of leaving, and the one exception came from a late HR "
            "entry.\n\n"
            "Head of IT Risk")
    return build_eml("Head of IT Risk <it.risk@corp.example>",
                     "Head of Identity Services <identity.services@corp.example>",
                     datetime.datetime(2026, 5, 8, 16, 42, 10, tzinfo=tz(1)),
                     "RE: Leaver removal sample test, April 2026", body)


def doc_cloud_email():
    body = ("The cloud hosting platform's privileged accounts will not be in the July quarterly review.\n\n"
            "The inventory of the platform's 64 privileged accounts is still being confirmed with the new operating "
            "team, and the review tool cannot yet read the platform's role assignments. The extension plan is still "
            "a draft and has not been approved.\n\n"
            "You approved exception EXC-2026-014 today for 90 days, so the platform stays outside the July review "
            "under it.\n\n"
            "So M5 is still in progress. We expect the first review that includes the cloud hosting platform to run "
            "in the first half of September 2026, before the committed date of 2026-09-30.\n\n"
            "Head of Cloud Engineering")
    return build_eml("Head of Cloud Engineering <cloud.engineering@corp.example>",
                     "Chief Information Security Officer <ciso.office@corp.example>",
                     datetime.datetime(2026, 6, 19, 9, 15, 0, tzinfo=tz(1)),
                     "Cloud hosting platform and the July privileged access review", body,
                     cc="Head of Identity Services <identity.services@corp.example>")


def doc_orphan_report():
    f = "Orphaned privileged accounts: clean-up report"

    def p1(pg):
        pg.title("Orphaned privileged accounts: clean-up report")
        pg.kv([("Prepared by", "Infrastructure risk team"), ("Owner", "Head of Infrastructure"),
               ("Milestone", "M3 of the remediation plan for " + FINDING_ID)])
        pg.heading("Summary")
        pg.para("This report records the clean-up of privileged accounts with no named owner, called orphaned accounts, "
                "found in the directory baseline of 2026-02-27. The access management standard requires that "
                '"every orphaned account is removed or given a named owner within 90 days" (section 6.2).')
        pg.para("The clean-up ran from 2026-03-02 to 2026-05-29. The method is on page 2 and the outcomes on page 3. "
                "The account by account list is in the outcomes extract of 2026-05-29. The sign-off is on page 4.")

    def p2(pg):
        pg.heading("Baseline and method")
        pg.para("The baseline extract of 2026-02-27 listed every privileged account whose owner field was empty or "
                "named a person who had left. It covered every platform in section 2.3 of the standard, and found 214 "
                "orphaned privileged accounts. For the cloud hosting platform the platform team exported the "
                "administrator roles by hand, and none was orphaned.")
        pg.para("For each account the platform team either removed the account, where nobody needed it, or found the "
                "person who needed it and recorded them as its named owner. The platform owner recorded the outcome "
                "and its date in the outcomes extract. The teams worked on removals and owner assignments in parallel.")
        pg.para("Each platform team completed the owner assignment briefing before assigning any owner.")

    def p3(pg):
        pg.heading("Outcomes")
        pg.table(["Outcome", "Accounts"], [["Removed", "131"], ["Assigned to a named owner", "83"],
                                          ["Total", "214"]], size=10, gap=60)
        pg.para("Every orphaned account in the baseline has an outcome.")

    return build_pdf([p1, p2, p3, ("scan", [
        ("big", "SIGN-OFF SHEET"), ("gap", ""),
        ("line", "ORPHANED PRIVILEGED ACCOUNTS:"), ("line", "CLEAN-UP REPORT"), ("line", "M3 OF THE REMEDIATION PLAN"),
        ("gap", ""), ("line", "I HAVE READ THIS REPORT AND I CONFIRM"), ("line", "THAT IT RECORDS THE CLEAN-UP AS"),
        ("line", "IT WAS CARRIED OUT."), ("gap", ""), ("line", "ROLE: HEAD OF INFRASTRUCTURE"),
        ("sig", "SIGNATURE:"), ("line", "DATE: 2026-06-05")])], f)


def doc_orphan_csv():
    header = ["orphan_id", "platform", "account_name", "baseline_date", "outcome", "outcome_date", "new_owner_staff_id"]
    rows = [[r["id"], r["platform"], r["account"], "2026-02-27", r["outcome"], iso(r["date"]) if r["date"] else "",
             r["owner"]] for r in ORPHANS]
    return build_csv(header, rows)


def doc_deck():
    f = "Reviewing privileged access: reviewer training, version 2, 2026-03-30"

    def s1(pg):
        pg.space(120)
        pg.title("Reviewing privileged access")
        pg.para("Reviewer training for platform owners and the reviewers they name", size=12)
        pg.para("Identity Services", size=12)

    def s2(pg):
        pg.title("Why this matters")
        pg.bullets(["The Supervisor found that leavers kept privileged access for weeks, that some privileged "
                    "accounts had no owner, and that nobody reviewed privileged access on a schedule.",
                    "The Board Risk Committee approved version 4.0 of the access management standard on 2026-03-26. "
                    "It takes effect on 2026-04-01.",
                    "From then, every privileged account is reviewed each quarter by a trained reviewer."], size=12)

    def s3(pg):
        pg.title("The rules you apply")
        pg.bullets(["Review every privileged account on your platform once a quarter.",
                    "Complete this training before your first review.",
                    "Never certify an account you hold. Pass it to your deputy reviewer.",
                    "Revoke what is not needed. The access is removed within 30 days of your decision."], size=12)

    def s4(pg):
        pg.title("How to review in the review tool")
        pg.bullets(["Open your review list. It shows each privileged account on your platform, its holder and when "
                    "it was last used.",
                    "For each account, choose keep or revoke. Add a reason for every keep on an account unused for "
                    "90 days.",
                    "Accounts you hold appear greyed out. Do not open them; your deputy reviewer sees them.",
                    "Submit your list before the review window closes."], size=12)

    def s5(pg):
        pg.title("A worked example")
        pg.bullets(["A database administrator account was last used 140 days ago by a person who moved to another "
                    "team.",
                    "Their new role needs no database access, so the reviewer chooses revoke.",
                    "The identity team removes the access, and the review tool records the date."], size=12)

    def s6(pg):
        pg.title("Sessions and support")
        pg.bullets(["Pilot session: 2026-03-31.", "Main session: 2026-03-02.",
                    "Questions go to Identity Services through the service desk."], size=12)

    return build_pdf([s1, s2, s3, s4, s5, s6], f)


def doc_training_register():
    comp = [["Reviewer training completion register"], ["Reviewers in scope", 23], [],
            ["Staff number", "Role", "Platform", "Session", "Completed on"]]
    for sid, platform, role, session in sorted(REVIEWERS, key=lambda r: (r[1], r[0])):
        comp.append([sid, role, platform, session.capitalize(), iso(SESSIONS[session])])
    comp += [[], ["Signed off by the Head of Identity Services on 2026-04-27."]]
    sessions = [["Reviewer training sessions"], [], ["Session", "Date", "Reviewers trained", "Trainer"],
                ["Pilot", "2026-03-31", 6, "Identity Services training lead"],
                ["Main", "2026-04-02", 17, "Identity Services training lead"],
                ["Total", "", 23, ""]]
    assert sum(1 for r in REVIEWERS if r[3] == "pilot") == 6
    assert sum(1 for r in REVIEWERS if r[3] == "main") == 17
    briefings = [["Briefings run by Identity Services for other teams"], [],
                 ["Briefing", "Date", "Attended", "Run for"],
                 ["Owner assignment briefing for platform teams (M3)", "2026-04-14", 18, "Infrastructure risk team"],
                 ["Leaver procedure briefing for the identity team (M2)", "2026-03-12", 11, "Head of Identity Services"]]
    return build_xlsx([("Completions", comp, False, [14, 28, 24, 12, 14]),
                       ("Sessions", sessions, False, [12, 12, 18, 34]),
                       ("Briefings", briefings, False, [52, 12, 10, 30])])


def doc_review_report():
    f = "First quarterly privileged access review: report"
    per = []
    for platform, count, revokes in PLATFORMS:
        rows = [a for a in REVIEWED if a["platform"] == platform]
        kept = sum(a["decision"] == "keep" for a in rows)
        rev = sum(a["decision"] == "revoke" for a in rows)
        assert kept + rev == count and rev == revokes
        per.append([platform, str(count), str(kept), str(rev)])
    per.append(["Total", "318", "271", "47"])

    def p1(pg):
        pg.title("First quarterly privileged access review: report")
        pg.kv([("Prepared by", "Identity Services"), ("Milestone", "M4 of the remediation plan for " + FINDING_ID)])
        pg.heading("Summary")
        pg.para("This report records the first quarterly review of privileged access under section 5 of the access "
                "management standard. All 23 reviewers completed the reviewer training before the review window "
                "opened.")
        pg.para("Scope and method are on page 2, results on page 3, revocations and exceptions on page 4, and the "
                "sign-off on page 5.")

    def p2(pg):
        pg.heading("Scope and method")
        pg.para("The review tool loaded the privileged accounts on the in-scope platforms on 2026-04-01. Accounts in "
                "the review: 318 active privileged accounts with a named holder, as at 2026-04-07, on six platforms: "
                "the core banking database, the payments gateway, the customer channels, the data warehouse, the "
                "directory and servers, and the network devices.")
        pg.para("Accounts still in the orphaned account clean-up (M3) stay outside the quarterly review until they "
                "have a named owner, as section 5.6 of the standard provides. The cloud hosting platform is outside "
                "this review under exception EXC-2026-011, which the Chief Information Security Officer approved on "
                "2026-03-31 for 90 days, until M5 brings the platform into the review.")
        pg.para("The review followed the review method, version 2.4 of 2026-04-01.")
        pg.para("The review window ran from 2026-04-07 to 2026-04-17. 23 reviewers took part. Each reviewer chose keep "
                "or revoke for each account on their review list in the review tool, which recorded the decision, the "
                "reviewer and the date.")

    def p3(pg):
        pg.heading("Results")
        pg.table(["Platform", "Accounts reviewed", "Kept", "Revoked"], per, size=10, gap=30)
        pg.para("Every account in the review received a decision before the window closed.")

    def p4(pg):
        pg.heading("Revocations and exceptions")
        pg.para("Revocations decided: 47. The identity team removed the access for each revocation and recorded the "
                "date in the review tool. The last of the 47 revocations was completed on 2026-05-08, within 30 days "
                "of its decision, as section 5.4 of the standard requires.")
        pg.para("Break-glass accounts: the 9 break-glass accounts on the six platforms were outside the review under "
                "exception EXC-2026-007, which the Chief Information Security Officer approved on 2026-01-05 for 90 "
                "days, while the accounts moved to the new credential safe.")

    def p5(pg):
        pg.heading("Sign-off")
        pg.para("The Head of Identity Services confirms that the review was carried out in line with section 5 of the "
                "access management standard.")
        pg.signature(["Head of Identity Services", "Date: 2026-05-12"])

    return build_pdf([p1, p2, p3, p4, p5], f)


def doc_review_extract():
    header = ["account_id", "platform", "holder_staff_id", "reviewer_staff_id", "decision", "decision_date",
              "revoked_on"]
    rows = [[a["id"], a["platform"], a["holder"], a["reviewer"], a["decision"],
             iso(a["date"]) if a["date"] else "", iso(a["revoked"]) if a.get("revoked") else ""] for a in EXTRACT]
    return build_csv(header, rows)


def doc_procedure():
    f = "Leaver access removal procedure, version 2.0"

    def p1(pg):
        pg.title("Leaver access removal procedure")
        pg.kv([("Version", "2.0"), ("Owner", "Head of Identity Services"), ("Effective date", "2026-03-16"),
               ("Applies", "Section 4 of the access management standard")])
        pg.heading("1. Purpose")
        pg.para("This procedure sets the steps the identity team follows to remove a leaver's access.")
        pg.heading("2. Roles")
        pg.bullets(["HR operations enters each employee's leaving date in the HR system.",
                    "The contractor management team tells the identity team when a contractor leaves.",
                    "The identity team removes access and keeps the record."])

    def p2(pg):
        pg.heading("3. Employees")
        pg.para("3.1 At 06:00 each business day the HR system sends the identity tool a leaver notice for each "
                "employee whose leaving date has passed.")
        pg.para("3.2 The identity tool disables the leaver's directory account and records the time.")
        pg.para("3.3 For each account on a platform that does not sign in through the directory, the tool raises a "
                "task. The platform team removes the account and closes the task.")
        pg.para("3.4 A notice that fails is sent again on the next run.")

    def p3(pg):
        pg.heading("4. Contractors")
        pg.para("4.1 Contractors are not recorded in the HR system, so the leaver feed does not cover them.")
        pg.para("4.2 The contractor management team emails the identity team on the contractor's last day. The "
                "identity team disables the contractor's accounts when it reads the email.")
        pg.heading("5. Records and reporting")
        pg.para("5.1 The identity tool keeps the leaving date and the removal time for each employee leaver.")
        pg.para("5.2 Identity Services publishes the leaver removal MI each month.")

    def p4(pg):
        pg.heading("6. Review of this procedure")
        pg.para("The owner reviews this procedure at least once a year and after any change to section 4 of the "
                "access management standard.")
        pg.signature(["Approved for issue.", "Head of Identity Services", "Date: 2026-03-13"])

    return build_pdf([p1, p2, p3, p4], f)


def doc_cloud_plan():
    who, when = "Head of Cloud Engineering", "2026-06-18T10:20:00Z"
    return build_docx([
        [("size", 32), ("b", "Cloud hosting platform: extending the quarterly privileged access review")],
        [("t", "Draft for discussion. Owner: Head of Cloud Engineering. Milestone M5 of the remediation plan.")],
        [("b", "Scope")],
        [("t", "The privileged accounts on the cloud hosting platform: the platform administrator roles, the "
               "break-glass accounts and the automation accounts that can change configuration.")],
        [("b", "Steps")],
        [("t", "1. Confirm the inventory of privileged accounts with the platform's operating team.")],
        [("t", "2. Connect the review tool to the platform's role assignments.")],
        [("t", "3. Name a reviewer and a deputy reviewer and train them before their first review.")],
        [("t", "4. Include the platform in the next quarterly review.")],
        [("b", "Timeline")],
        [("t", "Inventory confirmed by "), ("del", "2026-05-29", who, when), ("ins", "2026-08-14", who, when),
         ("t", ". First review that includes the platform: "), ("del", "July 2026", who, when),
         ("ins", "September 2026", who, when), ("t", ".")],
        [("b", "Status")],
        [("t", "Draft. Not yet approved.")],
    ])


def doc_quick_card():
    return build_docx([
        [("size", 28), ("b", "Reviewer quick reference card")],
        [("t", "1. Open your review list in the review tool.")],
        [("t", "2. For each account, choose keep or revoke.")],
        [("t", "3. Never certify an account you hold. Leave it for your deputy reviewer.")],
        [("t", "4. Revoked access is removed within 30 days of your decision.")],
        [("t", "5. Questions go to Identity Services through the service desk.")],
    ])


def doc_run_log():
    lines = ["HR to identity tool leaver feed: run log", "Environment: UAT", "Runs from 2026-03-16 to 2026-03-31", ""]
    rnd = Counter(31)
    for k, day in enumerate(bdays(GO_LIVE, d("2026-03-31")), 1):
        n = 48 if day == GO_LIVE else 4 + rnd.next(9)
        finish = "06:{:02d}".format(9 + (k * 7) % 40)
        lines.append("{} 06:00 run {:03d} notices received {}; accounts disabled for {} leavers; run finished "
                     "{}".format(iso(day), k, n, n, finish))
    return ascii_only("\n".join(lines) + "\n", "run log").encode("ascii")


def doc_status_report():
    f = "Chief Information Security Officer: report to the Board Risk Committee, 2026-07-03"

    def p1(pg):
        pg.title("Remediation of " + FINDING_ID + ": report to the Board Risk Committee")
        pg.kv([("From", "Chief Information Security Officer"), ("Date", "2026-07-03"), ("Position as at", "2026-06-30")])
        pg.heading("Progress since the last report")
        pg.para("The leaver feed has been in service since 2026-03-16. The first run cleared a backlog of 136 leavers, "
                "and the feed has processed 1,372 leavers since go-live (leaver removal MI, Summary sheet).")
        pg.para("The first quarterly review of privileged access kept 271 accounts and revoked 47 (review report, page "
                "3). The last revocation was completed on 2026-05-08.")
        pg.para("The orphaned account clean-up finished on 2026-05-29, and its report was signed on 2026-06-05.")

    def p2(pg):
        pg.heading("Milestone M5: the cloud hosting platform")
        pg.para("Status: in progress.")
        pg.para("The cloud hosting platform holds 54 privileged accounts (Head of Cloud Engineering's email of "
                "2026-06-19). The first quarterly review that includes them is planned for September 2026, before the "
                "committed date.")
        pg.para("The Head of Cloud Engineering owns M5, as the board agreed when it amended the plan.")

    def p3(pg):
        pg.heading("All milestones")
        pg.para("M1. Owner: Chief Information Security Officer. Committed: 2026-03-31. Position: standard approved by "
                "the committee on 2026-03-26.")
        pg.para("M2. Owner: Head of Identity Services. Committed: 2026-04-30. Position: feed in service since "
                "2026-03-16; since 2026-04-01, 100% of leavers removed within one business day.")
        pg.para("M3. Owner: Head of Infrastructure. Committed: 2026-06-30. Position: clean-up finished 2026-05-29.")
        pg.para("M4. Owner: Head of Identity Services. Committed: 2026-05-31. Position: first review finished "
                "2026-04-17.")
        pg.para("M5. Owner: Head of Cloud Engineering. Committed: 2026-09-30. Position: in progress (page 2).")
        pg.para("I ask the committee to note this report.")
        pg.signature(["Chief Information Security Officer", "Date: 2026-07-03"])

    return build_pdf([p1, p2, p3], f)


# ===================================================================== the letter and the questions

LETTER = SYNTHETIC + """
# Finding """ + FINDING_ID + """
Identifier: """ + FINDING_ID + """
Institution: Tallowmere Bank
Issuer: the Supervisor
Letter date: 2026-01-20
Kind of matter: supervisory finding
Owner role: Chief Information Security Officer

## Concern

The bank does not control privileged access to its systems. In the second half of 2025 the Supervisor found leavers, employees and contractors alike, whose privileged accounts stayed active for weeks after they left, privileged accounts with no named owner, and no regular review of who holds privileged access.

## Cause

The access management standard set no deadline for removing a leaver's access. The HR system did not tell the identity team when an employee left, and contractor leavers were reported by email when someone remembered. No one reviewed privileged access on a schedule, and the people who would review it were never trained.

## Consequence

Former staff and contractors could have used privileged access after they left, and accounts that no one owned could have been used without anyone noticing. The board could not be told how many people held privileged access or whether they still needed it.

## Corrective action

The bank must revise its access management standard to set a deadline for removing a leaver's access and to require a quarterly review of privileged access; automate leaver notices from the HR system and remove the access of every leaver, employee or contractor, within one business day; remove, or assign a named owner to, every privileged account that has none; train every reviewer before they review and complete a first quarterly review of privileged access; and extend the quarterly review to the cloud hosting platform.

## Commitment

The bank must send the Supervisor a written remediation plan approved by its board within 30 days of this letter, with an owner role and a committed date for each action. The Supervisor will consider the matter for closure only after internal audit has tested the remediation.
"""

QUESTIONS = SYNTHETIC + """
# Questions from internal audit, """ + FINDING_ID + """

Sent by internal audit to the finding owner on 2026-07-10. Please answer each question from the folder, with a cite to the page that supports each part of the answer.

1. M2: which document shows the date the HR leaver feed went live, and what is that date?
2. The plan: which record shows the board's approval of the remediation plan, and which role signed it on what date?
3. M3: the sign-off page of the orphaned account clean-up report is a scan. Who typed its text into the folder, and has a second person compared the typed text with the scan?
"""

EVIDENCE = [
    ("E-PLAN-1 Board minutes 2026-02-12.pdf", doc_board_minutes),
    ("E-PLAN-1 Board minutes 2026-02-12 (1).pdf", doc_board_minutes),
    ("EV-01 Access Management Standard v4.0 SIGNED.pdf", doc_standard),
    ("EV-02 Board Risk Committee minutes 2026-03-26.pdf", doc_brc_minutes),
    ("EV-03 Privileged access review method v2.3.pdf", doc_review_method),
    ("CHG-2026-04417 HR leaver feed go-live record.pdf", doc_change_record),
    ("EV-05 Leaver removal MI as at 2026-06-30.xlsx", doc_leaver_mi),
    ("EV-06 Leaver removal sample test April 2026.pdf", doc_sample_test),
    ("EV-07 RE Leaver removal sample test April 2026.eml", doc_approval_email),
    ("EV-08 Orphaned privileged accounts clean-up report.pdf", doc_orphan_report),
    ("EV-09 Orphaned accounts baseline and outcomes 2026-05-29.csv", doc_orphan_csv),
    ("EV-10 Privileged access reviewer training deck v2.pdf", doc_deck),
    ("EV-11 Reviewer training completion register.xlsx", doc_training_register),
    ("EV-12 First quarterly privileged access review report.pdf", doc_review_report),
    ("EV-13 First quarterly review extract 2026-05-11.csv", doc_review_extract),
    ("EV-14 Leaver access removal procedure v2.pdf", doc_procedure),
    ("EV-15 Cloud hosting platform review extension plan DRAFT.docx", doc_cloud_plan),
    ("EV-16 CISO report to Board Risk Committee 2026-07-03.pdf", doc_status_report),
    ("EV-17 Cloud hosting platform and the July review.eml", doc_cloud_email),
    ("EV-18 HR to identity feed run log 2026-03-16 to 2026-03-31.txt", doc_run_log),
    ("EV-19 Reviewer quick reference card.docx", doc_quick_card),
    ("EV-20 Board Risk Committee terms of reference.pdf", doc_brc_terms),
]


# ===================================================================== writing

TAR_TIME = 1767225600  # 2026-01-01T00:00:00Z


def pack(case_dir, tar_path):
    paths = sorted([p for p in case_dir.rglob("*")], key=lambda p: p.relative_to(case_dir.parent).as_posix())
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w", format=tarfile.USTAR_FORMAT) as tf:
        for p in [case_dir] + paths:
            name = p.relative_to(case_dir.parent).as_posix()
            info = tarfile.TarInfo(name)
            info.mtime, info.uid, info.gid, info.uname, info.gname = TAR_TIME, 0, 0, "", ""
            if p.is_dir():
                info.type, info.mode = tarfile.DIRTYPE, 0o755
                tf.addfile(info)
            else:
                data = p.read_bytes()
                info.size, info.mode = len(data), 0o644
                tf.addfile(info, io.BytesIO(data))
    tar_path.write_bytes(buf.getvalue())


def main(argv=None):
    ap = argparse.ArgumentParser(description="Write the invented case for agent run 01 and its archive.")
    ap.add_argument("--out", default=str(Path(__file__).resolve().parent.parent),
                    help="the folder case/ and gate/ are written in; the folder above build/ by default")
    args = ap.parse_args(argv)
    out = Path(args.out).resolve()
    case = out / "case"
    if case.exists():
        shutil.rmtree(case)
    (case / "evidence").mkdir(parents=True)
    (case / "finding.md").write_bytes(ascii_only(LETTER, "letter").encode("ascii"))
    (case / "audit-questions.md").write_bytes(ascii_only(QUESTIONS, "questions").encode("ascii"))
    built = {}
    for name, make in EVIDENCE:
        key = make
        if key in built:
            data = built[key]
        else:
            data = make()
            built[key] = data
        (case / "evidence" / name).write_bytes(data)
    (out / "gate").mkdir(exist_ok=True)
    pack(case, out / "gate" / "case.tar")
    files = sorted(p for p in case.rglob("*") if p.is_file())
    print("Wrote {} files in case/ and gate/case.tar.".format(len(files)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
