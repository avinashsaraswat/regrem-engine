"""Expert report tie-out: check every figure, date, quotation and citation in a draft against the record.

Purpose: a tie-out checks every figure, date, quotation and citation in a draft expert report
  against the record, item by item, in code. Anything code cannot tie goes to a drop log, which
  the expert rules on line by line. At sign-off the tool prints one fingerprint for the
  report's certification. Commands:
    init <folder>                       create an engagement folder with an empty ledger
    intake [--draft path] [--accept-tracked-changes]
                                        list record and cite problems (I1 to I7); writes nothing
    run [--draft path] [--accept-tracked-changes]
                                        intake, claims, proposer, verify, outputs, ledger line
    sign --run <id>                     S1 to S9, the confirmation walk, the fingerprint
    status [--run <id>] [--served file.docx]
                                        what is on disk against what the run recorded
    measure [--class name] [--freeze] [--declare] [--regress]
                                        planted errors on matter 1 as k of N (measure.py)
    measure --proposer                  each proposer against matter 1's answer-key labels (measure.py)
    --version                           the release version and whether the running code matches
  A run lists every number or date in words that words.py reads as a rules candidate in the
  drop log, checked only when a model proposes it. When counsel-terms.json sets
  candidate_snippets and the provider is a model (chat, or replay of a chat run), a run also
  asks the model to pick among up to five record locations code found for each drop-log item
  with no page-level cite (job 4); the pick is a hint on the row and never changes a verdict.
Reads: the engagement folder, which is the current folder or --engagement: matter.json,
  counsel-terms.json, report/, record/, run/ and ledger.jsonl; tieout/prompts/propose.txt,
  tieout/RELEASE.json and, for init, the two example configs beside this script. The runner
  never opens key/. measure reads tieout/fixture/matter-1 with its key/, as measure.py says,
  since the scorer runs outside the runner.
Writes: through gate.py only: run/<id>/ (intake.json, verdicts.json, tieout-report.md,
  drop-log.md, drop-log.csv, rulings.csv, proposals.json, draft.txt, signoff.json, and for a
  chat or replay proposer sent/ and receipts.jsonl), ledger.jsonl and run/.lock while a run or
  sign holds the folder; measure --freeze and --declare write tieout/FROZEN.json and
  tieout/batches/. init writes the starting layout of a new engagement folder.
Network: none with provider rules, which runs in this process, or replay, which answers from
  a prior run's sent/ bodies. With provider chat, providers.py sends each chunk of flagged
  paragraphs, and with candidate_snippets the record snippets job 4 offers, to the one endpoint
  counsel-terms.json names, behind the egress checks N2 to N9.
Exit codes: 0 when everything ties and nothing is untagged (run), clean (intake), signed (sign),
  consistent (status) or measured (measure); 1 when the drop log has open items or untagged
  claims, a ruling check refuses a sign, status finds the run void or different, or measure
  --regress finds catches fell or escapes or false flags rose; 2 on a usage, intake or input
  error or a replay miss; 3 on a gate, hash, policy or egress refusal, a live provider with no
  endpoint host in counsel-terms.json, or a network error, which prints its status, byte counts
  and receipt number only.
"""
import argparse
import csv
import datetime
import io
import json
import os
import re
import sys
import time

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import claims  # noqa: E402
import gate  # noqa: E402
import providers  # noqa: E402
import record  # noqa: E402
import verify  # noqa: E402

MAX_RETRIES = 1  # a rejected reply goes back once, with plain-English reasons per failed element
BLOCKING = ("I1", "I2", "I4", "I5", "I6", "I7")  # run continues past I3, with the flag recorded
NO_PAGE = ("no_cite", "ambiguous_association", "id_no_antecedent", "pin_missing")  # job 4: no page-level cite
CANDIDATES = 5  # job 4: the most record locations code offers the proposer for one item
SNIPPET = 160  # job 4: characters of record text each side of the value in a candidate's snippet
MATTER_FIELDS = {"matter_id": str, "expert": str, "draft": str, "tag_mode": str, "date_order": str,
                 "provider": str, "model": str, "max_calls": int, "max_tokens": int, "chunk_paragraphs": int,
                 "replay_from": str, "key_env": str}
TERMS_FIELDS = {"signed_by": str, "date": str, "endpoint_base_url": str, "proxy_host": str, "ca_file": str,
                "timeout_seconds": (int, float), "candidate_snippets": bool, "receipt_detail": str,
                "ledger_keeper": str}
DROP_COLUMNS = ["key", "para", "sentence", "kind", "span", "cite_text", "cite_resolved", "code", "reason",
                "weak_flags", "hint", "hint_source", "proposed_by", "state"]


class InputError(Exception):
    """A usage, intake or input error: exit 2."""


def err(msg):
    print(msg, file=sys.stderr)


# --- the engagement folder ----------------------------------------------------------------------


def same_folder(a, b):
    """Ported from the author's earlier private code: one folder, compared by identity."""
    try:
        return os.path.samefile(a, b)
    except (OSError, ValueError):  # either path missing or unreadable: not the same folder
        return False


def too_broad(root):
    """Ported from the author's earlier private code, the home and root refusals only: why the folder is
    refused as an engagement folder, or None."""
    real = os.path.realpath(root)
    if same_folder(real, os.path.expanduser("~")):
        return "%s is the home folder" % real
    if os.path.dirname(real) == real or same_folder(real, os.sep):
        return "%s is the filesystem root" % real
    return None


def _json_file(path, label):
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except OSError:
        raise InputError("%s is missing" % label)
    except ValueError as exc:
        raise InputError("%s is not valid JSON: %s" % (label, exc))
    if not isinstance(data, dict):
        raise InputError("%s must hold one JSON object" % label)
    return data


def _fields(data, spec, label):
    unknown = sorted(k for k in data if k not in spec and not k.startswith("_"))
    if unknown:
        raise InputError("%s: unknown field(s) %s; key values never go in a config file" % (label, ", ".join(unknown)))
    for k, t in spec.items():
        if k not in data:
            raise InputError("%s: field %s is missing" % (label, k))
        v = data[k]
        if isinstance(v, bool) and t is not bool:
            raise InputError("%s: field %s has the wrong type" % (label, k))
        if not isinstance(v, t):
            raise InputError("%s: field %s has the wrong type" % (label, k))


def load_config(root):
    matter = _json_file(os.path.join(root, "matter.json"), "matter.json")
    terms = _json_file(os.path.join(root, "counsel-terms.json"), "counsel-terms.json")
    _fields(matter, MATTER_FIELDS, "matter.json")
    _fields(terms, TERMS_FIELDS, "counsel-terms.json")
    if not matter["expert"].strip():
        raise InputError("matter.json: expert is empty; only the expert it names rules and signs")
    if matter["tag_mode"] not in ("comments", "inline"):
        raise InputError("matter.json: tag_mode must be comments or inline")
    if matter["date_order"] not in ("mdy", "dmy"):
        raise InputError("matter.json: date_order must be mdy or dmy")
    if matter["provider"] not in ("rules", "replay", "chat"):
        raise InputError("matter.json: provider must be one of rules, replay, chat")
    if matter["provider"] != "rules" and not matter["model"].strip():
        raise InputError("matter.json: provider %s needs a model id" % matter["provider"])
    if matter["provider"] == "replay":
        rel = os.path.normpath(matter["replay_from"].strip() or ".").replace(os.sep, "/")
        real_root = os.path.realpath(root)
        full = os.path.realpath(os.path.join(root, rel))
        if os.path.isabs(rel) or os.path.commonpath([real_root, full]) != real_root or full == real_root:
            raise InputError("matter.json: replay_from must name a folder inside the engagement folder, outside key/")
        refuse_key(root, full, "matter.json: replay_from %s" % rel)
        if not os.path.isdir(os.path.join(full, "sent")):
            raise InputError("matter.json: replay_from %s holds no sent/ folder" % rel)
    for k in ("max_calls", "max_tokens", "chunk_paragraphs"):
        if matter[k] < 1:
            raise InputError("matter.json: %s must be at least 1" % k)
    if not terms["timeout_seconds"] > 0:  # written this way so NaN is refused too
        raise InputError("counsel-terms.json: timeout_seconds must be more than 0")
    if not terms["signed_by"].strip():
        raise InputError("counsel-terms.json is not signed: signed_by is empty")
    try:
        datetime.date.fromisoformat(terms["date"])
    except ValueError:
        raise InputError("counsel-terms.json: date must be YYYY-MM-DD")
    if terms["receipt_detail"] not in ("full", "digest"):
        raise InputError("counsel-terms.json: receipt_detail must be full or digest")
    return matter, terms


def refuse_key(root, path, what):
    """Refuse a path that resolves into the engagement's key/ folder: the runner never opens
    key/. The path is resolved first, so a link into key/ is refused. When key/ exists, each
    folder above the path is compared with it by file identity, so a path that names key/ or
    the engagement folder in another case on a disk that ignores case is refused too. The
    name is also compared in any case, for a Key/ folder where key/ is absent. Every path the
    runner is handed (--draft, status --served, replay_from) comes through here."""
    real_root, real = os.path.realpath(root), os.path.realpath(path)
    try:
        key = os.stat(os.path.join(real_root, "key"))
    except OSError:  # no key/ folder: the name compare below still applies
        key = None
    probe = real
    while key is not None:
        try:
            inside = os.path.samestat(os.stat(probe), key)
        except OSError:  # a folder that does not exist cannot be key/
            inside = False
        if inside:
            raise InputError("%s: the runner never opens key/" % what)
        parent = os.path.dirname(probe)
        if parent == probe:
            break
        probe = parent
    try:
        first = os.path.relpath(real, real_root).replace(os.sep, "/").split("/")[0]
    except ValueError:  # another drive on Windows: outside the folder, so outside key/
        return
    if first.lower() == "key":
        raise InputError("%s: the runner never opens key/" % what)


def draft_path(root, matter, given):
    """The draft, inside the engagement folder and outside key/."""
    rel = given or matter["draft"]
    full = os.path.abspath(rel if os.path.isabs(rel) else os.path.join(root, rel))
    inside = os.path.relpath(full, os.path.abspath(root))
    if inside.startswith(os.pardir) or os.path.isabs(inside):
        raise InputError("the draft %s is outside the engagement folder" % rel)
    rel = inside.replace(os.sep, "/")
    refuse_key(root, full, "the draft %s" % rel)
    if not os.path.isfile(full):
        raise InputError("the draft %s is missing" % rel)
    return rel, full


def read_draft(full, matter, accept_tracked):
    import docx_reader
    try:
        draft = claims.read_draft(full, accept_tracked=accept_tracked)
    except docx_reader.DocxTracked as exc:
        raise InputError("refused: %s" % exc)
    except ValueError as exc:
        raise InputError(str(exc))
    want = "comments" if draft["type"] == "docx" else "inline"
    if matter["tag_mode"] != want:
        raise InputError("matter.json says tag_mode %s, but a .%s draft uses %s tags" % (matter["tag_mode"], draft["type"], want))
    return draft


def intake_checks(root, matter, full, accept_tracked, index=None, draft=None):
    """I1 to I7 as [{code, pass, rows}], the index, the draft, the grammar and the analysis.
    measure.py passes the record index it loaded once and a draft it read from text, so a
    planted item meets the same intake a run does."""
    index = record.load(root, matter["date_order"]) if index is None else index
    grammar = claims.Grammar(index.grammar_names(), matter["date_order"])
    draft = read_draft(full, matter, accept_tracked) if draft is None else draft
    analysis = claims.analyse(draft, grammar)
    rows = dict(index.rows)
    rows["I7"] = claims.intake_rows(draft, analysis, grammar)
    checks = [{"code": c, "pass": not rows[c], "rows": rows[c]} for c in ("I1", "I2", "I3", "I4", "I5", "I6", "I7")]
    return checks, index, draft, grammar, analysis


def print_checks(checks, notes):
    for c in checks:
        print("%s %s" % (c["code"], "PASS" if c["pass"] else "FAIL"))
        for r in c["rows"]:
            print("   " + r)
    for n in notes:
        print("note: " + n)


# --- run ----------------------------------------------------------------------------------------


def new_run_id(root, draft_sha):
    for _ in range(3):
        rid = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M%S") + "-" + draft_sha[:4]
        if not os.path.exists(os.path.join(root, "run", rid)):
            return rid
        time.sleep(1.0)
    raise gate.GateRefused("W4", "run folder %s exists" % rid)


def prompt_text():
    with open(os.path.join(HERE, "prompts", "propose.txt"), encoding="utf-8") as fh:
        return fh.read().replace("\r\n", "\n")


def propose(client, recorder, matter, draft, analysis):
    """The proposer over every chunk, with the one-retry shape of fsi loop.run_ticker: a rejected
    reply goes back once with plain-English reasons per failed element. Returns (accepted,
    proposals document, calls, egress)."""
    system = prompt_text()
    proposed_by = "rules" if client.name == "rules" else "model"
    doc = {"provider": client.name, "model": matter["model"], "proposed_by": proposed_by,
           "prompt_sha256": record.sha256_bytes(system.encode("utf-8")), "chunks": []}
    accepted, budget_hit = [], False
    for ci, chunk in enumerate(claims.chunks(draft, analysis, matter["chunk_paragraphs"]), 1):
        labels = [claims.where_label(w) for w in chunk["items"]]
        rejected, attempts, kept, short = None, [], [], False
        for attempt in range(MAX_RETRIES + 1):
            if client.name != "rules" and recorder.n >= matter["max_calls"]:
                budget_hit = short = True  # N7: the drop log is marked proposer_budget
                break
            user = claims.chunk_message(chunk, analysis, rejected)
            text, _ = recorder.call(client, model=matter["model"], system=system, user=user,
                                    max_tokens=matter["max_tokens"], paragraphs=labels, retry=attempt > 0)
            res = claims.accept(text, analysis, chunk, {}, proposed_by)
            kept = claims.merge_accepted(kept, res["accepted"])
            attempts.append({"attempt": attempt, "codes": sorted(res["codes"]), "rejected_whole": res["whole"],
                             "rows": [{"codes": r["codes"], "why": r["why"]} for r in res["rows"] if r["codes"]]})
            retry = res["codes"] - {"P7"}
            if not retry or attempt == MAX_RETRIES:
                break
            rejected = claims.retry_reasons(res)
        final = kept
        accepted += final
        doc["chunks"].append({"chunk": ci, "paragraphs": labels, "attempts": attempts, "budget": short,
                              "accepted": [dict({k: a[k] for k in ("value", "reason") if k in a},
                                                para=a["where"][1] if a["where"][0] == "para" else "fn%d" % a["where"][1],
                                                span=a["span"], cite=a["cite"], kind=a["kind"]) for a in final]})
    calls = recorder.n  # every call the Recorder made, a status retry included
    doc["calls"], doc["budget_hit"] = calls, budget_hit
    egress = {"calls": calls, "hosts": recorder.hosts, "bytes_out": recorder.bytes_out, "bytes_in": recorder.bytes_in,
              "paragraphs": recorder.paragraphs}
    return accepted, doc, calls, egress


def check_claims(client, recorder, matter, draft, analysis, grammar, index):
    """The proposer, the claims and the verifier, with no file written here: (claims, verdicts,
    verdicts.json bytes, proposals document, proposer calls, egress counts). A run and
    measure.py's scorer both come through this function."""
    accepted, prop_doc, calls, egress = propose(client, recorder, matter, draft, analysis)
    built = claims.build_claims(draft, analysis, grammar, accepted)
    verdicts = verify.verify_all(built, index)
    vbytes = verify.document(built, verdicts, analysis["not_checked"])
    return built, verdicts, vbytes, prop_doc, calls, egress


def snippet(index, location, claim):
    """What job 4 shows the proposer of one candidate: up to SNIPPET characters of record text
    each side of the first place the claim's value appears there, or a cell's header and row."""
    if "!" in location:
        name, cell = location.split("!", 1)
        rows = index.data.get(name, [])
        r = int(re.sub(r"\D", "", cell))
        return "%s row %d: %s" % (name, r, "; ".join("%s %s" % hv for hv in zip(rows[0], rows[r - 1])))
    for label, scanned, _ in index.all_texts():
        if label != location:
            continue
        text, at = scanned["text"], 0
        if claim["kind"] == "figure":
            f = claim["figures"][0]
            at = next((s["start"] for s in scanned["figures"] if s["pct"] == f["pct"] and
                       record.rounds_to(s["value"], f)), 0)
        elif claim["kind"] == "date":
            at = next((d["start"] for d in scanned["dates"] if
                       any(record.date_ties(claim["date"], v) for v in d["values"])), 0)
        else:
            at = max(0, text.casefold().find(record.norm_text(claim["span"]).strip('"\'').casefold()[:40]))
        return " ".join(text[max(0, at - SNIPPET):at + SNIPPET].split())
    return ""


def candidate_hints(client, recorder, matter, built, verdicts, index):
    """Job 4 of the model, run only for a model and only when counsel-terms.json sets
    candidate_snippets: for each drop-log item with no page-level cite, code finds up to
    CANDIDATES places the record holds its value and the model picks one from their snippets.
    measure.py also calls it with the rules client, which picks code's first candidate, to score
    that order as the baseline. The pick is a hint on the drop-log row and never a tie;
    verdicts.json keeps code's verdict, and the expert adopts a pick only by ruling
    record-supports with that location, which sign checks. Returns ({key: hint row fields}, the
    record for proposals.json, snippets sent)."""
    items, where = [], []
    for c, v in zip(built, verdicts):
        if v["pass"] or v["code"] not in NO_PAGE:
            continue
        found = verify.search(c, index, CANDIDATES)
        if found:
            items.append({"item": c["key"], "kind": c["kind"], "span": c["span"], "sentence": c["sentence_text"],
                          "candidates": [{"rank": i, "location": loc, "snippet": snippet(index, loc, c)}
                                         for i, loc in enumerate(found, 1)]})
            if claims.where_label(c["where"]) not in where:
                where.append(claims.where_label(c["where"]))
    if not items:
        return {}, {"asked": 0, "items": []}, 0
    user = json.dumps({"job": "candidates", "items": items}, ensure_ascii=False, sort_keys=True, indent=1)
    text, _ = recorder.call(client, model=matter["model"], system=prompt_text(), user=user,
                            max_tokens=matter["max_tokens"], paragraphs=where, retry=False)
    offered = {it["item"]: [c["location"] for c in it["candidates"]] for it in items}
    try:
        reply = json.loads(claims.unfence(text))  # one code fence round the reply, as for P1
    except (ValueError, RecursionError):
        reply = None
    picks = {}
    for r in reply if isinstance(reply, list) else []:  # anything but a rank offered for an item offered is dropped
        if isinstance(r, dict) and set(r) == {"item", "choice"} and isinstance(r["item"], str) and \
                r["item"] in offered and \
                type(r["choice"]) is int and 1 <= r["choice"] <= len(offered[r["item"]]):
            picks[r["item"]] = r["choice"]
    hints = {k: {"hint": "candidate %d of %d, picked by the model: %s" % (n, len(offered[k]), offered[k][n - 1]),
                 "hint_source": "model-candidate"} for k, n in picks.items()}
    doc = {"asked": len(items), "items": [{"item": k, "locations": offered[k], "choice": picks.get(k)} for k in offered]}
    return hints, doc, sum(len(v) for v in offered.values())


def previous_rulings(root, run_id):
    """Rulings from the most recent earlier run that has a rulings.csv: (run, {key: row} for each
    row that holds a ruling, notes). gate.read_rulings reads the file, the same reader sign uses,
    with any key allowed; the caller keeps only the keys still in the new drop log."""
    order = gate.run_order(root)
    earlier = order[:order.index(run_id)] if run_id in order else order
    for r in reversed(earlier):
        path = os.path.join(root, "run", r, "rulings.csv")
        if os.path.isfile(path):
            rows, quarantined = gate.read_rulings(path)
            notes = ["run %s: %s; not carried" % (r, q if q.startswith("rulings.csv") else "rulings.csv " + q)
                     for q in quarantined]
            return r, {k: row for k, row in rows.items() if row["ruling"]}, notes
    return None, {}, []


def _csv_bytes(header, rows):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(header)
    for r in rows:
        w.writerow(r)
    return ("\ufeff" + buf.getvalue()).encode("utf-8")  # a byte-order mark so Excel reads UTF-8


def _where(r):
    return "para %s" % r["para"] if r["para"] is not None else "fn %s" % r["footnote"]


def _cell(s):
    return str(s).replace("|", "\\|").replace("\n", " ")


def _item(r):
    text = "%s s%s %s %s (%s): %s" % (_where(r), r["sentence"], r["kind"], r["span"], r["cite_resolved"] or r["cite_text"]
                                      or "no cite", r["code"])
    return text if len(text) <= 160 else text[:157] + "..."


def words_candidates(analysis, rows):
    """The rules proposer's words candidates no model claim covers, for the drop log: each
    phrase words.py reads that holds no token, with its reading and code's pairing."""
    claimed = {(r["para"], r["footnote"], r["span"]) for r in rows if r["proposed_by"] == "model"}
    out = []
    for p in analysis.get("words", []):
        para, foot = (p["where"][1], None) if p["where"][0] == "para" else (None, p["where"][1])
        if not p["holds"] and (para, foot, p["text"]) not in claimed:
            out.append({"para": para, "footnote": foot, "sentence": p["sentence"], "span": p["text"],
                        "reads": p["reading"]["show"], "cite": p["pair"]["resolved"] or p["pair"]["code"]})
    return out


def write_outputs(run_rel, run_id, matter, intake, vdoc, vbytes, prop_doc, draft, carried, notes, analysis, egress,
                  hints=None):
    rows = vdoc["claims"]
    drops = [r for r in rows if not r["pass"]]
    for i, r in enumerate(drops):  # job 4's picks are hints on drop-log rows; verdicts.json keeps code's
        h = (hints or {}).get(r["key"])
        if h:
            drops[i] = dict(r, hint=(r["hint"] + "; " if r["hint"] else "") + h["hint"],
                            hint_source=(r["hint_source"] + ", " if r["hint"] else "") + h["hint_source"])
    expert = matter["expert"]
    states = {r["key"]: gate.state_of(carried.get(r["key"]), expert) for r in drops}
    gate.write(os.path.join(run_rel, "verdicts.json"), vbytes, create=True)
    gate.write(os.path.join(run_rel, "draft.txt"), claims.reads_as_text(draft).encode("utf-8"), create=True)
    gate.write(os.path.join(run_rel, "proposals.json"),
               (json.dumps(prop_doc, indent=1, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8"), create=True)
    gate.write(os.path.join(run_rel, "drop-log.csv"), _csv_bytes(DROP_COLUMNS, [
        [r["key"], _where(r).split(" ", 1)[1] if r["para"] is not None else "fn%s" % r["footnote"], r["sentence"],
         r["kind"], r["span"], r["cite_text"], r["cite_resolved"], r["code"], r["reason"], ";".join(r["weak_flags"]),
         r["hint"], r["hint_source"], r["proposed_by"], states[r["key"]]] for r in drops]), create=True)
    gate.write(os.path.join(run_rel, "rulings.csv"), _csv_bytes(gate.RULING_COLUMNS, [
        [r["key"], _item(r)] + [carried.get(r["key"], {}).get(c, "") for c in gate.RULING_COLUMNS[2:]] for r in drops]),
        create=True)
    gate.write(os.path.join(run_rel, "drop-log.md"), drop_log_md(run_id, matter, intake, rows, drops, states,
                                                                  vdoc["not_checked"], words_candidates(analysis, rows),
                                                                  prop_doc).encode("utf-8"), create=True)
    gate.write(os.path.join(run_rel, "tieout-report.md"),
               report_md(run_id, matter, intake, vdoc, drops, states, prop_doc, carried, notes, analysis,
                         egress).encode("utf-8"),
               create=True)


def _header(title, run_id, matter, intake):
    return ["# %s, run %s" % (title, run_id), "",
            "Matter %s. Expert %s. Draft %s, sha256 %s." % (matter["matter_id"], matter["expert"], intake["draft"]["path"],
                                                           intake["draft"]["sha256"]),
            "Record: %d files, manifest sha256 %s. Code sha256 %s." % (len(intake["record"]["files"]),
                                                                    intake["record"]["manifest_sha256"],
                                                                    intake["code_sha256"]),
            "Ledger head after intake: %s." % intake["ledger_head"], ""]


def drop_log_md(run_id, matter, intake, rows, drops, states, not_checked, phrases=(), prop_doc=None):
    out = _header("Drop log", run_id, matter, intake)
    counts = {}
    for s in states.values():
        counts[s] = counts.get(s, 0) + 1
    out.append("%d item(s) in the drop log%s. Only the expert named in matter.json clears an item, at sign." %
               (len(drops), (": " + ", ".join("%s %d" % kv for kv in sorted(counts.items()))) if drops else ""))
    out.append("")
    short = [p for c in (prop_doc or {}).get("chunks", []) if c.get("budget") for p in c["paragraphs"]]
    if short:
        out += ["## proposer_budget", "",
                "The model proposer stopped at max_calls (%d) before it proposed for paragraphs %s. Code still "
                "checked every token in them, with the pairing A1 to A4 make." % (matter["max_calls"], ", ".join(short)),
                ""]
    by_code = {}
    for r in drops:
        by_code.setdefault(r["code"], []).append(r)
    for code in sorted(by_code):
        out += ["## %s (%d)" % (code, len(by_code[code])), "",
                "| key | where | kind | span | cite | reason | hint | proposed by | state |",
                "|---|---|---|---|---|---|---|---|---|"]
        for r in by_code[code]:
            out.append("| %s |" % " | ".join(_cell(x) for x in (
                r["key"], "%s s%s" % (_where(r), r["sentence"]), r["kind"], r["span"],
                r["cite_resolved"] or r["cite_text"] or "none", r["reason"],
                ("%s (%s)" % (r["hint"], r["hint_source"])) if r["hint"] else "", r["proposed_by"], states[r["key"]])))
        out.append("")
    out += ["## Not checked (%d)" % len(not_checked), ""]
    for n in not_checked:
        where = "para %s" % n["para"] if n["para"] is not None else "fn %s" % n["footnote"]
        out.append("- %s s%s: %s (%s)" % (where, n["sentence"], n["span"], n["reason"]))
    out.append("")
    if phrases:
        out += ["## Numbers and dates in words, not checked (%d)" % len(phrases), "",
                "words.py reads each of these and code paired it as shown. The rules proposer lists them for the "
                "expert's eye and nothing checks them; a drafter's tag or an accepted model proposal makes one a claim.", ""]
        for n in phrases:
            where = "para %s" % n["para"] if n["para"] is not None else "fn %s" % n["footnote"]
            out.append("- %s s%s: %s, reads %s (%s)" % (where, n["sentence"], n["span"], n["reads"], n["cite"]))
        out.append("")
    weak = [r for r in rows if r["pass"] and r["weak_flags"]]
    out += ["## Weak-tie spot-check sample (%d)" % len(weak), "",
            "A weak tie counts as a tie and joins this sample for a person to check by eye.", ""]
    for r in weak:
        out.append("- %s %s s%s: %s at %s (%s)" % (r["key"], _where(r), r["sentence"], r["span"],
                                                 r["cite_resolved"] or "-", ", ".join(r["weak_flags"])))
    return "\n".join(out) + "\n"


def report_md(run_id, matter, intake, vdoc, drops, states, prop_doc, carried, notes, analysis, egress):
    rows = vdoc["claims"]
    out = _header("Tie-out report", run_id, matter, intake)
    tagged = [r for r in rows if r["proposed_by"] == "tag"]
    proposed = [r for r in rows if r["proposed_by"] != "tag"]
    out += ["## Result", "",
            "%d claims: %d tagged, %d untagged. %d tie; %d in the drop log." % (
                len(rows), len(tagged), len(proposed), sum(1 for r in rows if r["pass"]), len(drops)), "",
            "| code | claims |", "|---|---|"]
    for code, n in sorted(vdoc["counts"].items()):
        out.append("| %s | %d |" % (code, n))
    out.append("")
    issues = [c for c in intake["intake"] if not c["pass"]]
    if issues:
        out += ["Intake flags carried into this run: " + "; ".join("%s (%d)" % (c["code"], len(c["rows"])) for c in issues), ""]
    out += ["## Proposed claims, listed apart (%d)" % len(proposed), "",
            "Untagged tokens the tool found itself, each with the pairing code made. A proposed tie counts as a "
            "tie and always joins the spot-check sample.", ""]
    if proposed:
        out += ["| key | where | kind | span | pairing | cite | code |", "|---|---|---|---|---|---|---|"]
        for r in proposed:
            out.append("| %s |" % " | ".join(_cell(x) for x in (
                r["key"], "%s s%s" % (_where(r), r["sentence"]), r["kind"], r["span"], r["pairing"],
                r["cite_resolved"] or "none", r["code"])))
        out.append("")
    out += ["Untagged cite tokens in the draft: %d." % analysis["cite_count"], ""]
    out += ["## Tagged claims (%d)" % len(tagged), ""]
    if tagged:
        out += ["| key | where | kind | span | cite | code | weak flags |", "|---|---|---|---|---|---|---|"]
        for r in tagged:
            out.append("| %s |" % " | ".join(_cell(x) for x in (
                r["key"], "%s s%s" % (_where(r), r["sentence"]), r["kind"], r["span"], r["cite_resolved"], r["code"],
                ", ".join(r["weak_flags"]))))
        out.append("")
    out += ["## Rulings carried forward", ""]
    out.append("%d ruling(s) carried from %s by unchanged key." % (len(carried), intake.get("carried_from") or "no earlier run")
               if carried else "None carried.")
    for n in notes:
        out.append("- " + n)
    out += ["", "## Egress", ""]
    paragraphs = ", ".join(egress["paragraphs"]) or "none"
    if prop_doc["provider"] == "rules":
        out.append("Provider rules, run in this process: nothing left the machine.")
    elif prop_doc["provider"] == "replay":
        out.append("Provider replay, answered from the recorded calls in %s: nothing left the machine. Calls "
                   "answered: %d, %d bytes of requests matched and %d bytes read from the recorded calls, "
                   "paragraphs %s." % (matter["replay_from"], egress["calls"], egress["bytes_out"], egress["bytes_in"],
                                       paragraphs))
    else:
        out.append("Provider %s. Proposer calls: %d, host %s, %d bytes out and %d bytes in, paragraphs %s. Record "
                   "snippets sent for candidate locations: %d. These bytes went to the endpoint counsel-terms.json "
                   "names; sent/ holds each body and receipts.jsonl each call and the peers it reached."
                   % (prop_doc["provider"], egress["calls"], ", ".join(egress["hosts"]) or "none", egress["bytes_out"],
                      egress["bytes_in"], paragraphs, egress.get("snippets", 0)))
    return "\n".join(out) + "\n"


def egress_line(matter, terms):
    """What leaves the machine, for intake.json."""
    if matter["provider"] == "rules":
        return "none: provider rules runs in this process; nothing leaves the machine"
    if matter["provider"] == "replay":
        return "none: provider replay answers from %s; nothing leaves the machine" % matter["replay_from"]
    return ("provider chat: each chunk of flagged paragraphs and the footnotes they reference%s go to %s, the "
            "host counsel-terms.json names" % (", and record snippets for candidate locations," if
                                               terms["candidate_snippets"] else "",
                                               ", ".join(sorted(providers.allowed_hosts(terms)))))


def cmd_run(args, root):
    matter, terms = load_config(root)
    gate.configure(root, matter["key_env"])
    rel, full = draft_path(root, matter, args.draft)
    gate.lock()
    try:
        checks, index, draft, grammar, analysis = intake_checks(root, matter, full, args.accept_tracked_changes)
        blocking = [c for c in checks if c["code"] in BLOCKING and not c["pass"]]
        if blocking:
            print_checks([c for c in checks if not c["pass"]], index.notes)
            err("run: stopped on intake (%s); fix the record or the draft and run again" % ", ".join(c["code"] for c in blocking))
            return 2
        client = providers.make_client(matter, grammar.names(), terms, root)
        draft_sha = record.sha256_file(full)
        run_id = new_run_id(root, draft_sha)
        run_rel = os.path.join("run", run_id)
        release = gate.read_release()
        tracked = draft.get("tracked") or {}
        intake = {"schema": 1, "run": run_id, "tool_version": release.get("version", ""),
                  "code_sha256": gate.code_hash(), "release_code_sha256": release.get("code_sha256", ""),
                  "draft": {"path": rel, "sha256": draft_sha, "type": draft["type"], "tag_mode": matter["tag_mode"]},
                  "tracked_changes": "accepted" if tracked.get("accepted") else "none",
                  "insertions": tracked.get("insertions", 0), "deletions": tracked.get("deletions", 0),
                  "matter_sha256": record.sha256_file(os.path.join(root, "matter.json")),
                  "counsel_terms_sha256": record.sha256_file(os.path.join(root, "counsel-terms.json")),
                  "prompts": gate.prompt_hashes(), "record": {"files": index.files,
                                                              "manifest_sha256": record.tree_hash(index.files)},
                  "intake": checks, "notes": index.notes, "provider": matter["provider"], "model": matter["model"],
                  "egress": egress_line(matter, terms),
                  "time": gate.now()}
        intake_bytes = (json.dumps(intake, indent=1, sort_keys=True) + "\n").encode("utf-8")
        entry = gate.ledger_entry("intake", run_id, intake_bytes)
        gate.write(os.path.join(run_rel, "intake.json"), intake_bytes, create=True)
        intake["ledger_head"] = gate.ledger_append(entry)

        recorder = providers.Recorder(run_rel, terms["receipt_detail"], matter["max_calls"])
        built, verdicts, vbytes, prop_doc, calls, egress = check_claims(client, recorder, matter, draft, analysis,
                                                                        grammar, index)
        hints = {}
        if terms["candidate_snippets"] and client.name != "rules" and recorder.n < matter["max_calls"]:
            hints, prop_doc["candidates"], egress["snippets"] = candidate_hints(client, recorder, matter, built,
                                                                                verdicts, index)
            calls = prop_doc["calls"] = recorder.n
            egress.update(calls=calls, hosts=recorder.hosts, bytes_out=recorder.bytes_out, bytes_in=recorder.bytes_in,
                          paragraphs=recorder.paragraphs)
        vdoc = json.loads(vbytes.decode("utf-8"))
        prev_run, prev_rows, notes = previous_rulings(root, run_id)
        drops = [r for r in vdoc["claims"] if not r["pass"]]
        carried = {r["key"]: prev_rows[r["key"]] for r in drops if r["key"] in prev_rows}
        dropped = sorted(set(prev_rows) - {r["key"] for r in drops})
        if dropped:
            notes.append("%d ruling(s) from run %s not carried: their items are no longer in the drop log (%s)"
                         % (len(dropped), prev_run, ", ".join(dropped)))
        intake["carried_from"] = prev_run
        write_outputs(run_rel, run_id, matter, intake, vdoc, vbytes, prop_doc, draft, carried, notes, analysis, egress,
                      hints)
        gate.ledger_append(gate.ledger_entry("outputs", run_id, gate.outputs_payload(os.path.join(root, run_rel))))
    finally:
        gate.unlock()

    open_items = [r for r in drops if gate.state_of(carried.get(r["key"]), matter["expert"]) != "cleared"]
    untagged = [r for r in vdoc["claims"] if r["proposed_by"] != "tag"]
    # the rules proposer's calls are chunks handed to code in this process, so only a proposer
    # that builds a request body gets a count, and replay says its answers were read from disk
    via = ("proposer rules, in this process" if client.name == "rules" else
           "proposer replay, %d recorded call(s) read" % calls if client.name == "replay" else
           "proposer %s, %d call(s)" % (client.name, calls))
    print("run %s: %d claims, %d tie, %d drop-log item(s) (%d open), %d untagged; %s"
          % (run_id, len(vdoc["claims"]), sum(1 for r in vdoc["claims"] if r["pass"]), len(drops), len(open_items),
             len(untagged), via))
    for r in drops:
        print("  %s %-22s %s s%s %s (%s)" % (r["key"], r["code"], _where(r), r["sentence"], r["span"],
                                           r["cite_resolved"] or r["cite_text"] or "no cite"))
    print("report: %s" % os.path.join(run_rel, "tieout-report.md").replace(os.sep, "/"))
    return 1 if open_items or untagged else 0


# --- the other commands -------------------------------------------------------------------------


def cmd_intake(args, root):
    matter, _ = load_config(root)
    _, full = draft_path(root, matter, args.draft)
    checks, index, _, _, _ = intake_checks(root, matter, full, args.accept_tracked_changes)
    print_checks(checks, index.notes)
    hits = sum(len(c["rows"]) for c in checks)
    print("intake: %s" % ("clean" if not hits else "%d hit(s)" % hits))
    return 0 if not hits else 2


def cmd_sign(args, root):
    matter, _ = load_config(root)
    gate.configure(root, matter["key_env"])
    if not os.path.isdir(os.path.join(root, "run", args.run)):
        raise InputError("no run %s" % args.run)
    gate.lock()
    try:
        return gate.sign(root, args.run, matter)
    finally:
        gate.unlock()


def cmd_status(args, root):
    if args.served:
        refuse_key(root, args.served, "the served file %s" % args.served)
        if not os.path.isfile(args.served):
            raise InputError("the served file %s is missing" % args.served)
    if args.run and not os.path.isdir(os.path.join(root, "run", args.run)):
        raise InputError("no run %s" % args.run)
    return gate.status(root, args.run, args.served)


def cmd_init(args):
    folder = os.path.abspath(args.folder)
    why = too_broad(folder) if os.path.exists(folder) else None
    if why:
        raise InputError("init refused: %s; make a folder for the engagement" % why)
    try:
        made = gate.init_folder(folder, os.path.join(HERE, "matter.example.json"),
                                os.path.join(HERE, "counsel-terms.example.json"))
    except gate.GateRefused as exc:
        raise InputError("init refused: %s" % exc.reason)
    print("init %s: created %s" % (folder, ", ".join(made)))
    print("next: fill matter.json, have counsel sign counsel-terms.json, add the draft to report/ and the record to record/")
    return 0


def cmd_measure(args):
    """measure.py on matter 1, through this module's intake and checks."""
    import measure
    return measure.run(args, sys.modules[__name__])


def cmd_version():
    try:
        ok, version, rel_hash, running = gate.release_check()
    except (OSError, ValueError) as exc:
        err("tieout --version: RELEASE.json unreadable: %s" % exc)
        return 3
    print("tieout %s, code %s" % (version, running))
    print("RELEASE.json code %s: %s" % (rel_hash, "the running code matches" if ok else "MISMATCH"))
    return 0 if ok else 3


def parser():
    eng = argparse.ArgumentParser(add_help=False)
    eng.add_argument("--engagement", default=argparse.SUPPRESS, help="the engagement folder (default: the current folder)")
    ap = argparse.ArgumentParser(prog="tieout", description="Tie out a draft expert report against the record.")
    ap.add_argument("--engagement", default=".", help="the engagement folder (default: the current folder)")
    ap.add_argument("--version", action="store_true", help="print the release version and check the running code")
    sub = ap.add_subparsers(dest="cmd")
    p = sub.add_parser("init", help="create an engagement folder")
    p.add_argument("folder")
    p = sub.add_parser("intake", parents=[eng], help="list record and cite problems; writes nothing")
    p.add_argument("--draft")
    p.add_argument("--accept-tracked-changes", action="store_true")
    p = sub.add_parser("run", parents=[eng], help="run the tie-out")
    p.add_argument("--draft")
    p.add_argument("--accept-tracked-changes", action="store_true")
    p = sub.add_parser("sign", parents=[eng], help="sign a run at a terminal")
    p.add_argument("--run", required=True)
    p = sub.add_parser("status", parents=[eng], help="check a run against the disk")
    p.add_argument("--run")
    p.add_argument("--served")
    p = sub.add_parser("measure", help="measure the tool on matter 1's planted errors")
    p.add_argument("--class", dest="cls", metavar="NAME", help="one class only")
    p.add_argument("--freeze", action="store_true", help="write tieout/FROZEN.json")
    p.add_argument("--declare", action="store_true", help="declare a batch, then score it")
    p.add_argument("--regress", action="store_true", help="compare with the last declared batch")
    p.add_argument("--date", help="the batch date for --declare, YYYY-MM-DD (default: today, UTC)")
    p.add_argument("--proposer", action="store_true", help="each proposer against matter 1's answer-key labels")
    return ap


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):  # a console that cannot show a curly quote gets "?"
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    argv = list(sys.argv[1:] if argv is None else argv)
    ap = parser()
    args = ap.parse_args(argv)
    if args.version:
        return cmd_version()
    if not args.cmd:
        ap.print_usage(sys.stderr)
        return 2
    try:
        if args.cmd == "init":
            return cmd_init(args)
        if args.cmd == "measure":
            return cmd_measure(args)
        root = os.path.abspath(args.engagement)
        why = too_broad(root)
        if why:
            raise InputError("refused: %s cannot be an engagement folder" % why)
        if not os.path.isdir(root):
            raise InputError("no engagement folder %s" % root)
        return {"intake": cmd_intake, "run": cmd_run, "sign": cmd_sign, "status": cmd_status}[args.cmd](args, root)
    except InputError as exc:
        err("tieout %s: %s" % (args.cmd, exc))
        return 2
    except providers.ReplayMiss as exc:
        err("tieout %s: %s; nothing was sent" % (args.cmd, exc))
        return 2
    except providers.EgressError as exc:
        err("tieout %s: egress stopped, %s" % (args.cmd, exc))
        return 3
    except gate.GateRefused as exc:
        err("tieout %s: refused, %s" % (args.cmd, exc))
        return 3
    except (OSError, ValueError, KeyError) as exc:
        err("tieout %s: %s: %s" % (args.cmd, type(exc).__name__, exc))
        return 2


if __name__ == "__main__":
    sys.exit(main())
