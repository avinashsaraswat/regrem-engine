#!/usr/bin/env python3
"""agent_loop: one job for one seat of the agent run, on a copy of a finding folder, through the model API named in
manifest.json.

Purpose: runs one job (plan, covers, memo, cross-read, proposed-rulings or audit-answers) in its seat (drafter or
  cross-reader), as the run's protocol sets out. It sends the job's prompt and a short brief to the model id in the
  manifest, using generateContent-style requests with function calling, carries out each function call the model
  makes, and stops when the model replies with no call, the turn limit is reached or the next call could pass the
  spend cap.
Tools offered to the model:
  list_files  lists the finding folder, the kit's Markdown pages (kit/...), and the run pages and output file the
              seat may read (run/..., out/...).
  read_file   reads one file. Markdown and text come back as text. A PDF, Word, Excel, CSV, email or .txt file in
              the finding folder comes back page by page through the kit's own reader, finding/documents.py, so the
              model reads what the check reads.
  write_file  writes a whole file, only where the job's allowlist in gate_diff.py allows. Every refused write, and
              every refused read, is logged as a "stopped" event and changes nothing.
  run_check   runs `python3 -I finding/finding.py check <folder> --today <date>` from the kit and returns its page.
              It is offered only when the manifest sets offer_run_check to true, because the protocol has the loop,
              not the agent, run the kit's commands.
The loop's own commands, by job: covers runs `finding covers` before the model starts and hands it the screen;
  proposed-rulings and audit-answers start with a check page, and --start-check gives any job one. Plan, covers and
  memo get the check page back once when the model first says it is done, after the loop saves what the job wrote
  in --out/first/. At the end plan and covers run `finding check`, and memo runs `finding check` and `finding eval`.
  Every screen and page is saved in --out.
Gate: after the start commands the folder is copied and snapshotted, and when the model is done gate_diff.py checks
  every changed path against the job's allowlist and reverts any change outside it from the copy.
Key: read only from the environment variable MODEL_API_KEY, when a request is sent, and sent only in the API's key
  header, only to the one host in the manifest's api.endpoint, over https, with no redirect followed. The person
  running the loop fills api.endpoint in their local manifest.json; the template holds a placeholder, and a run
  refuses to start on a placeholder, on plain http, or on an address with a user, a port other than 443, a query or
  a fragment. The key is never printed, logged or written: every line of output is scrubbed of it, a write whose
  content holds it is refused, and the kit's commands run with an environment that leaves it out.
Spend: prices per million tokens and the cap come from the manifest. Before each call the loop prices the largest
  the call could be (a token bound on the prompt, plus maxOutputTokens and the thinking bound) and stops the job if
  that would take the run's spend past the cap. After each call it prices the usage the API reports, charging cached
  tokens at the full input price, and appends one line to the spend ledger beside the manifest. A mock run keeps
  its own ledger, named with .mock, so it never counts toward the cap of a real one.
Usage:
  python3 -I tools/agent_loop.py --manifest manifest.json --seat drafter --job memo --folder run-01/memo/case \
      --repo <kit folder> --prompt prompts/memo.txt --out run-01/memo [--today YYYY-MM-DD] [--start-check] \
      [--hand <file>]... [--ledger <file>] [--mock replies.json]
  python3 -I tools/agent_loop.py --list-models --manifest manifest.json [--mock replies.json]
  A live call needs the manifest, which names the endpoint; only --mock runs without one.
  --mock reads canned replies from a JSON file, a list or {"replies": [...]}, and makes no network call. Each reply
  is a generateContent response body, a models list body for --list-models, or {"http_status": n, "body": {...}}
  for an error. Run jobs one at a time: the ledger is read before each call and written after it.
Reads: the manifest, the prompt and handed files, the finding folder, the kit's pages and finding/documents.py.
Writes: the --out folder (transcript.jsonl, summary.json, final-message.txt, gate-before.json, gate-after.json,
  gate.json, each kit screen or page, first/ and final/ copies of what the job wrote, and out/findings.tsv for the
  cross-read job), the files the job's allowlist names, and the spend ledger. Paths in output are relative to the
  run folder, the manifest's folder, and the kit's folder prints as <kit>.
Network: the model API at the manifest's api.endpoint, unless --mock.
Exit codes: 0 when the job finished and the gate found no change outside the allowlist; 1 when it stopped early
  (spend cap, turn limit, an API error, a reply with no content) or the gate found a change outside; 2 on usage or
  a refusal to start. Standard library only, Python 3.9 and later.
"""
import argparse
import datetime
import hashlib
import importlib.util
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parent
KEY_VAR = "MODEL_API_KEY"
KEY_HEADER = "x-goog-api-key"  # the request header the model API reads the key from
WITHHELD = "[withheld]"
PLACEHOLDER = re.compile(r"^\{[A-Z0-9_]+\}$")  # a template value such as {ENDPOINT}, not yet filled
HOST_NAME = re.compile(r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?$")
RETRY_STATUSES = (429, 500, 502, 503, 504)
RETRIES = 3
MODEL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
CHILD_ENV_KEEP = ("PATH", "LANG", "LC_ALL", "LC_CTYPE", "TMPDIR", "TEMP", "TMP", "SYSTEMROOT")
TEXT_READ = (".md", ".tsv", ".json", ".jsonl")
PROMPT_MARGIN = 1024  # tokens added to the prompt bound for each call, for the request's own framing
DEFAULT_LIMITS = {"max_turns_per_job": 60, "tool_result_max_chars": 60000, "write_max_bytes": 1000000,
                  "kit_timeout_seconds": 300, "http_timeout_seconds": 300}


sys.dont_write_bytecode = True  # importing gate_diff.py and the kit's reader leaves no cache beside them


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


gate = _load("regrem_gate_diff", TOOLS_DIR / "gate_diff.py")

# job: (kit commands before the model starts, check page handed back once at first finish, kit commands at the end)
JOB_COMMANDS = {
    "plan": ((), True, ("check",)),
    "covers": (("covers",), True, ("check",)),
    "memo": ((), True, ("check", "eval")),
    "cross-read": ((), False, ()),
    "proposed-rulings": (("check",), False, ()),
    "audit-answers": (("check",), False, ()),
}
# Files in the finding folder a job does not read, as its procedure says.
JOB_READ_DENY = {"cross-read": ("closure/rulings.md", "closure/proposed-rulings.md")}
# Run-folder pages each seat may read, beside the finding folder and the kit's Markdown pages.
SEAT_RUN_READS = {"drafter": (), "cross-reader": ("procedures/review-memo.md",)}
WRITES_PLAIN = {
    "plan": "plan.md: the rows of its table below the header row, and the lines below the table. The lines above "
            "the table and its header row stay as they are.",
    "covers": "the What line and the For line of each cover in evidence/, the files ending in .md. Every other line "
              "of a cover stays as it is.",
    "memo": "closure/memo.md.",
    "cross-read": "out/findings.tsv.",
    "proposed-rulings": "closure/proposed-rulings.md.",
    "audit-answers": "audit-answers.md, at the top of the finding folder.",
}


class Usage(Exception):
    """A reason the loop will not start, in plain words."""


class ApiError(Exception):
    def __init__(self, status, message):
        Exception.__init__(self, message)
        self.status, self.message = status, message


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def sha256_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def inside(path, base):
    try:
        Path(path).relative_to(base)
        return True
    except ValueError:
        return False


def child_env():
    """The environment the kit's commands run with: what Python needs to start, and never the API key."""
    env = {name: os.environ[name] for name in CHILD_ENV_KEEP if name in os.environ}
    env["PYTHONIOENCODING"] = "utf-8"
    env.pop(KEY_VAR, None)
    return env


# ---------------------------------------------------------------- output that can never carry the key or a path


class Scrubber:
    """Replaces the API key, and each machine path the run knows, in every string that leaves the loop."""

    def __init__(self):
        self.pairs = []

    def add_path(self, path, label):
        for variant in {str(path), os.path.abspath(str(path)), os.path.realpath(str(path))}:
            if len(variant) > 3:
                self.pairs.append((variant, label))
        self.pairs.sort(key=lambda pair: len(pair[0]), reverse=True)

    @staticmethod
    def key():
        value = os.environ.get(KEY_VAR, "")
        return value if len(value) >= 8 else ""

    def text(self, value):
        key = self.key()
        if key:
            value = value.replace(key, WITHHELD)
        for old, new in self.pairs:
            value = value.replace(old, new)
        return value

    def obj(self, value):
        if isinstance(value, str):
            return self.text(value)
        if isinstance(value, list):
            return [self.obj(item) for item in value]
        if isinstance(value, dict):
            return {self.text(str(k)): self.obj(v) for k, v in value.items()}
        return value


class Transcript:
    def __init__(self, path, scrub):
        self.path, self.scrub, self.seq = Path(path), scrub, 0

    def event(self, event_type_, **fields):
        self.seq += 1
        record = {"t": now(), "seq": self.seq, "type": event_type_}
        record.update(fields)
        line = json.dumps(self.scrub.obj(record), ensure_ascii=False)
        key = Scrubber.key()
        if key and key in line:
            line = line.replace(key, WITHHELD)
        with open(str(self.path), "a", encoding="utf-8", newline="\n") as fh:
            fh.write(line + "\n")
        return record


def say(scrub, message, err=False):
    print(scrub.text(message), file=sys.stderr if err else sys.stdout)


# ---------------------------------------------------------------- spend


class Prices:
    def __init__(self, table, required):
        self.input = table.get("input")
        self.output = table.get("output")
        self.input_long = table.get("input_long")
        self.output_long = table.get("output_long")
        self.long_above = table.get("long_above_prompt_tokens")
        for name in ("input", "output"):
            value = getattr(self, name)
            if value is None and not required:
                setattr(self, name, 0.0)
            elif not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
                raise Usage("set prices_usd_per_million_tokens.{} in the manifest to a number".format(name))

    def usd(self, prompt_tokens, output_tokens):
        long = isinstance(self.long_above, (int, float)) and prompt_tokens > self.long_above
        p_in = self.input_long if long and isinstance(self.input_long, (int, float)) else self.input
        p_out = self.output_long if long and isinstance(self.output_long, (int, float)) else self.output
        return (prompt_tokens * p_in + output_tokens * p_out) / 1000000.0


class Ledger:
    def __init__(self, path):
        self.path = Path(path)

    def total(self):
        if not self.path.is_file():
            return 0.0
        spent = 0.0
        for number, line in enumerate(self.path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                spent += float(json.loads(line)["usd"])
            except (ValueError, KeyError, TypeError):
                raise Usage("the spend ledger's line {} cannot be read, so the spend so far is not known".format(number))
        return spent

    def add(self, record):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(str(self.path), "a", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------- the API


def filled(value):
    """A manifest value as a string, with a template placeholder such as {MODEL_ID} read as not filled in."""
    value = "" if value is None else str(value)
    return "" if PLACEHOLDER.match(value.strip()) else value


def endpoint_host(endpoint):
    """The one host a live endpoint names, or None when the address is not a plain https address on a named host."""
    try:
        text = str(endpoint)
        parts = urllib.parse.urlsplit(text)
        host = parts.hostname or ""
        ok = not re.search(r"[\s\\]", text) and parts.scheme == "https" and bool(HOST_NAME.match(host)) \
            and parts.netloc.lower() in (host, host + ":443") and not parts.query and not parts.fragment
    except ValueError:
        ok = False
    return host if ok else None


def live_endpoint(endpoint):
    """The endpoint a real key may be sent to: the https address the person filled in the local manifest's
    api.endpoint, on one named host, with no user, no port but 443, no query and no fragment. Anything else is
    refused, and the key is then sent to that host only."""
    if endpoint_host(endpoint) is None:
        raise Usage("set api.endpoint in the manifest to the model API's https address, with no user, no port but "
                    "443, no query and no fragment; the key is sent to that host and nowhere else")
    return str(endpoint)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """A redirect is an error here, so the header that carries the key never follows one to another address."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class HttpTransport:
    def __init__(self, timeout):
        self.timeout = timeout
        self.opener = urllib.request.build_opener(NoRedirect)

    def send(self, method, url, body, headers):
        request = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                return response.status, response.read()
        except urllib.error.HTTPError as err:
            return err.code, err.read()


class MockTransport:
    def __init__(self, replies):
        self.replies = list(replies)

    def send(self, method, url, body, headers):
        if not self.replies:
            raise ApiError(0, "the mock replies ran out")
        item = self.replies.pop(0)
        if isinstance(item, dict) and "http_status" in item:
            return int(item["http_status"]), json.dumps(item.get("body", {})).encode("utf-8")
        return 200, json.dumps(item).encode("utf-8")


def _error_message(data):
    text = data.decode("utf-8", "replace") if isinstance(data, bytes) else str(data)
    try:
        error = json.loads(text).get("error") or {}
        text = " ".join(str(error.get(k)) for k in ("status", "message") if error.get(k)) or text
    except (ValueError, AttributeError):
        pass
    return text.strip()[:500]


class Client:
    def __init__(self, endpoint, transport, mock, on_retry=None):
        self.endpoint, self.transport, self.mock = endpoint.rstrip("/"), transport, mock
        self.host = None if mock else endpoint_host(self.endpoint)
        self.on_retry = on_retry

    def _for_host(self, url):
        """True when the request goes over https to the endpoint's own host, the only place the key may go."""
        try:
            parts = urllib.parse.urlsplit(str(url))
        except ValueError:
            return False
        return bool(self.host) and parts.scheme == "https" and parts.netloc.lower() in (self.host, self.host + ":443")

    def _headers(self, url):
        headers = {"Content-Type": "application/json"}
        key = os.environ.get(KEY_VAR, "")
        if key:
            if not self.mock and not self._for_host(url):
                raise ApiError(0, "the request was not for the host in api.endpoint, so the key was not sent")
            headers[KEY_HEADER] = key
        elif not self.mock:
            raise ApiError(0, "{} is not set in this shell".format(KEY_VAR))
        return headers

    def request(self, method, url, body=None):
        for attempt in range(RETRIES + 1):
            headers = self._headers(url)
            try:
                status, data = self.transport.send(method, url, body, headers)
                message = None if status == 200 else _error_message(data)
            except (urllib.error.URLError, socket.timeout, ConnectionError) as err:
                status, data = None, b""
                message = "network error: {}".format(getattr(err, "reason", None) or type(err).__name__)
            finally:
                headers = None
            if status == 200:
                try:
                    return json.loads(data.decode("utf-8"))
                except ValueError:
                    raise ApiError(status, "the reply was not JSON")
            if (status is None or status in RETRY_STATUSES) and attempt < RETRIES:
                wait = 0 if self.mock else 2 ** (attempt + 1)
                if self.on_retry:
                    self.on_retry(status, message, attempt + 1, wait)
                time.sleep(wait)
                continue
            raise ApiError(status, message)
        raise ApiError(None, "no reply")

    def generate(self, model, body):
        return self.request("POST", "{}/models/{}:generateContent".format(self.endpoint, model), body)

    def list_models(self):
        models, token = [], None
        for _ in range(50):
            url = "{}/models?pageSize=200".format(self.endpoint)
            if token:
                url += "&pageToken=" + urllib.parse.quote(token, safe="")
            page = self.request("GET", url)
            models.extend(page.get("models") or [])
            token = page.get("nextPageToken")
            if not token:
                break
        return models


# ---------------------------------------------------------------- the manifest


def load_json(path, what):
    try:
        with open(str(path), encoding="utf-8") as fh:
            return json.load(fh)
    except OSError:
        raise Usage("cannot read the {} at {}".format(what, Path(path).name))
    except ValueError:
        raise Usage("the {} at {} is not JSON".format(what, Path(path).name))


def clean_config(value):
    """The generation settings as sent: blank and null values left out, so a template field left empty is unset."""
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            v = clean_config(v)
            if v is not None and v != "" and v != {}:
                out[k] = v
        return out
    return value


def output_bound(generation, spend, mock):
    """The most tokens one call can bill as output: maxOutputTokens plus the thinking budget or the thinking bound."""
    most = generation.get("maxOutputTokens")
    if not isinstance(most, int) or isinstance(most, bool) or most <= 0:
        if not mock:
            raise Usage("set generation.maxOutputTokens in the manifest, so the cap can price a call before it is sent")
        most = 0
    budget = (generation.get("thinkingConfig") or {}).get("thinkingBudget")
    if isinstance(budget, int) and not isinstance(budget, bool) and budget >= 0:
        thinking = budget
    else:
        thinking = spend.get("thinking_tokens_bound_per_call")
        if not isinstance(thinking, int) or isinstance(thinking, bool) or thinking < 0:
            if not mock:
                raise Usage("set spend.thinking_tokens_bound_per_call, or a thinkingBudget, in the manifest")
            thinking = 0
    return most + thinking


def seal_check(manifest, run_dir, mock):
    """Compares every hash the manifest fills with the file it names. A sealed manifest must fill them all."""
    sealed = manifest.get("sealed") is True
    checks = [(TOOLS_DIR / "agent_loop.py", (manifest.get("tools_sha256") or {}).get("tools/agent_loop.py", ""),
               "tools/agent_loop.py"),
              (TOOLS_DIR / "gate_diff.py", (manifest.get("tools_sha256") or {}).get("tools/gate_diff.py", ""),
               "tools/gate_diff.py")]
    checks.append((run_dir / "tools" / "score.py", manifest.get("scorer_sha256", ""), "tools/score.py"))
    for entry in manifest.get("prompts") or []:
        rel = gate.normalize(str(entry.get("path", "")))
        checks.append((run_dir / rel, entry.get("sha256", ""), rel))
    if sealed and not filled((manifest.get("api") or {}).get("model")) and not mock:
        raise Usage("the manifest is sealed and names no model")
    for path, expected, name in checks:
        if not expected:
            if sealed:
                raise Usage("the manifest is sealed and gives no hash for " + name)
            continue
        if not path.is_file() or sha256_file(path) != expected:
            raise Usage("{} does not match the hash the manifest gives for it".format(name))
    return sealed


# ---------------------------------------------------------------- the tools the model calls


class Tools:
    def __init__(self, ctx):
        self.ctx = ctx
        self.documents = None
        self.pages = None
        self.check_runs = 0
        self.stopped = []
        self.calls = 0

    def declarations(self):
        decls = [
            {"name": "list_files",
             "description": "List files, with each file's size in bytes. Give no path for the whole finding folder, "
                            "a folder inside it such as evidence, kit for the kit's Markdown pages, run for the run "
                            "pages this seat may read, or out for this job's output folder.",
             "parameters": {"type": "OBJECT", "properties": {
                 "path": {"type": "STRING", "description": "The folder to list. Leave it out for the finding folder."}}}},
            {"name": "read_file",
             "description": "Read one file. A Markdown or text file comes back as its text. A PDF, Word, Excel, CSV "
                            "or email file in the finding folder comes back page by page as the check reads it, "
                            "under headings such as ## Page 2, and names any page the reader found no text on.",
             "parameters": {"type": "OBJECT", "properties": {
                 "path": {"type": "STRING", "description": "The file, such as evidence/EV-07 report.pdf or "
                                                           "kit/assistant/README.md."},
                 "page": {"type": "INTEGER", "description": "Return only this page of a PDF, Word, Excel, CSV or "
                                                            "email file."}},
                 "required": ["path"]}},
            {"name": "write_file",
             "description": "Write a whole file, replacing what was there. Only the paths this job may write are "
                            "accepted. Any other write is refused, changes nothing and is recorded.",
             "parameters": {"type": "OBJECT", "properties": {
                 "path": {"type": "STRING", "description": "The file to write."},
                 "content": {"type": "STRING", "description": "The whole new text of the file."}},
                 "required": ["path", "content"]}},
        ]
        if self.ctx.offer_check:
            decls.append({"name": "run_check",
                          "description": "Run finding check on the finding folder and return its page and exit code."})
        return decls

    # -- where a path points

    def place(self, path):
        """(area, rule path, file system path). Areas: folder, kit, run, out."""
        rel = gate.normalize("" if path is None else path)
        head, _, rest = rel.partition("/")
        if head == "kit":
            return "kit", rel, self.ctx.repo / rest
        if head == "run":
            return "run", rel, self.ctx.run_dir / rest
        if head == "out":
            return "out", rel, self.ctx.out / rest
        return "folder", rel, self.ctx.folder / rel

    @staticmethod
    def _no_links(base, rel):
        current = base
        for part in [p for p in rel.split("/") if p]:
            current = current / part
            if current.is_symlink():
                raise gate.Refusal("link", "outside allowlist", "the path goes through a link")

    def kit_pages(self):
        if self.pages is None:
            self.pages = self._kit_pages()
        return self.pages

    def _kit_pages(self):
        ctx = self.ctx
        skip = [p for p in (ctx.run_dir, ctx.folder, ctx.out) if inside(p, ctx.repo)]
        pages = []
        for root, dirs, names in os.walk(str(ctx.repo), followlinks=False):
            here = Path(root)
            dirs[:] = sorted(d for d in dirs if not d.startswith(".") and not (here / d).is_symlink()
                             and not (here == ctx.repo and d == "runs")
                             and not any(inside(here / d, s) for s in skip))
            for name in sorted(names):
                path = here / name
                if name.lower().endswith(".md") and not path.is_symlink():
                    pages.append(path.relative_to(ctx.repo).as_posix())
        return pages

    def readable(self, area, rel, target, listing=False):
        """Raises Refusal when this seat may not read or list the path."""
        ctx = self.ctx
        head, _, rest = rel.partition("/")
        if area == "folder":
            self._no_links(ctx.folder, rel)
            if rel in JOB_READ_DENY.get(ctx.job, ()):
                raise gate.Refusal("procedure-read", "read outside seat", "the {} job does not read {}, as its "
                                   "procedure says".format(ctx.job, rel))
            return
        if area == "kit":
            if listing and rest == "":
                return
            if rest in self.kit_pages():
                self._no_links(ctx.repo, rest)
                return
            raise gate.Refusal("read-outside", "read outside seat", "kit/ reads only the kit's Markdown pages")
        if area == "run":
            if (listing and rest == "") or rest in SEAT_RUN_READS[ctx.seat]:
                return
            raise gate.Refusal("read-outside", "read outside seat", "the {} seat reads no run page but {}".format(
                ctx.seat, " and ".join("run/" + p for p in SEAT_RUN_READS[ctx.seat]) or "none"))
        if area == "out":
            outs = [p for p in gate.allowed(ctx.job) if p.startswith("out/")]
            if (listing and rest == "" and outs) or rel in outs:
                return
            raise gate.Refusal("read-outside", "read outside seat", "this job has nothing to read in out/")

    # -- the calls

    def call(self, turn, call):
        name = call.get("name")
        args = call.get("args") or {}
        self.calls += 1
        self.ctx.log.event("tool_call", turn=turn, name=name, id=call.get("id"), args=args)
        handlers = {"list_files": self.list_files, "read_file": self.read_file, "write_file": self.write_file}
        if self.ctx.offer_check:
            handlers["run_check"] = self.run_check
        if name not in handlers:
            kind = "finding sign" if "sign" in str(name).lower() else "unknown tool"
            result = self.refuse(turn, "call", name, None, gate.Refusal(
                "unknown-tool", kind, "there is no tool named {}; the tools are {}".format(name, ", ".join(handlers))))
        elif not isinstance(args, dict):
            result = {"error": "the arguments are not a JSON object"}
        else:
            try:
                result = {"result": handlers[name](args)}
            except gate.Refusal as refusal:
                action = {"read_file": "read", "list_files": "list", "write_file": "write"}.get(name, "call")
                result = self.refuse(turn, action, name, args.get("path"), refusal)
            except ToolError as err:
                result = {"error": str(err)}
            except OSError as err:
                result = {"error": "the file could not be read or written: {}".format(
                    (err.strerror or "an error").lower())}
        result = {k: self.ctx.scrub.text(v) for k, v in result.items()}
        self.ctx.log.event("tool_result", turn=turn, name=name, id=call.get("id"), **result)
        response = {"name": name if isinstance(name, str) and name else "unknown", "response": result}
        if call.get("id"):
            response["id"] = call["id"]
        return {"functionResponse": response}

    def refuse(self, turn, action, tool, path, refusal):
        record = {"action": action, "tool": tool, "path": path, "rule": refusal.rule, "kind": refusal.kind,
                  "reason": refusal.reason}
        self.stopped.append(record)
        self.ctx.log.event("stopped", turn=turn, **record)
        return {"error": "refused: " + refusal.reason + "."}

    def list_files(self, args):
        area, rel, target = self.place(args.get("path"))
        self.readable(area, rel, target, listing=True)
        ctx = self.ctx
        if area == "kit":
            return "\n".join("kit/" + p for p in self.kit_pages())
        if area == "run":
            rows = ["run/" + p for p in SEAT_RUN_READS[ctx.seat] if (ctx.run_dir / p).is_file()]
            return "\n".join(rows) or "(nothing)"
        if area == "out":
            rows = []
            for p in gate.allowed(ctx.job):
                if p.startswith("out/") and (ctx.out / p[4:]).is_file():
                    rows.append("{}  {} bytes".format(p, (ctx.out / p[4:]).stat().st_size))
            return "\n".join(rows) or "(nothing yet)"
        if not target.exists():
            raise ToolError("no file or folder at " + (rel or "."))
        if target.is_file():
            return "{}  {} bytes".format(rel, target.stat().st_size)
        rows = []
        for root, dirs, names in os.walk(str(target), followlinks=False):
            dirs.sort()
            for name in sorted(names):
                path = Path(root) / name
                shown = path.relative_to(ctx.folder).as_posix()
                rows.append("{}  {}".format(shown, "link" if path.is_symlink() else "{} bytes".format(
                    path.stat().st_size)))
        return "\n".join(rows[:2000]) or "(empty)"

    def _documents(self):
        if self.documents is None:
            self.documents = _load("regrem_documents", self.ctx.repo / "finding" / "documents.py")
        return self.documents

    def read_file(self, args):
        area, rel, target = self.place(args.get("path"))
        if not rel:
            raise ToolError("name a file; list_files lists a folder")
        self.readable(area, rel, target)
        if not target.is_file():
            raise ToolError("no file at " + rel)
        page = args.get("page")
        if page is not None and (not isinstance(page, int) or isinstance(page, bool) or page < 1):
            raise ToolError("page is a whole number from 1")
        suffix = target.suffix.lower()
        documents = self._documents()
        if area == "folder" and suffix in documents.READABLE:
            text = self._read_document(rel, target, page, documents)
        elif suffix in TEXT_READ:
            text = target.read_bytes().decode("utf-8-sig", "replace")
            if page is not None:
                text = "(A Markdown or text file is one page, so it comes back whole.)\n" + text
        else:
            raise ToolError("there is no reader for {} files; a person types the pages the memo cites into the "
                            "file's cover".format(suffix or "these"))
        most = self.ctx.limits["tool_result_max_chars"]
        if len(text) > most:
            text = text[:most] + "\n[cut at {} of {} characters; ask for one page with the page argument]".format(
                most, len(text))
        return text

    @staticmethod
    def _read_document(rel, target, page, documents):
        result = documents.read(target)
        if result["problem"]:
            return "{}: not read: {}. A person types the pages the memo cites into the file's cover.".format(
                rel, result["problem"])
        pages = result["pages"]
        lines = ["{}, as the check reads it: {} page{}.".format(rel, len(pages), "" if len(pages) == 1 else "s")]
        if result["partly"]:
            lines.append("Read only in part: page{} {}.".format("" if len(result["partly"]) == 1 else "s",
                                                                ", ".join(str(n) for n in result["partly"])))
        for number in sorted(result["hidden"]):
            lines.append("Page {} holds words a reader cannot see; they are left out.".format(number))
        lines.extend("Note: " + note for note in result["notes"])
        if page is not None and page > len(pages):
            raise ToolError("{} has {} page{}".format(rel, len(pages), "" if len(pages) == 1 else "s"))
        for number, body in enumerate(pages, 1):
            if page is not None and number != page:
                continue
            lines.append("")
            lines.append("## Page {}".format(number))
            lines.append(body if body.strip() else "(no text on this page: a scan, for a person to type into the "
                                                   "cover)")
        return "\n".join(lines)

    def write_file(self, args):
        ctx = self.ctx
        path, content = args.get("path"), args.get("content")
        if not isinstance(content, str):
            raise ToolError("content is the whole text of the file")
        key = Scrubber.key()
        if key and key in content:
            raise gate.Refusal("secret", "outside allowlist", "the content holds the API key, so nothing was written")
        if len(content.encode("utf-8")) > ctx.limits["write_max_bytes"]:
            raise gate.Refusal("too-large", "outside allowlist", "the content is over {} bytes".format(
                ctx.limits["write_max_bytes"]))
        area, rel, target = self.place(path)
        if not rel:
            raise gate.Refusal("bad-path", "outside allowlist", "name a file")
        if not any(gate.matches(rel, pattern) for pattern in gate.allowed(ctx.job)):
            raise gate.write_refusal(ctx.seat, ctx.job, rel, None, content)  # decided on the path, nothing read
        if area == "folder":
            self._no_links(ctx.folder, rel)
        elif area == "out":
            self._no_links(ctx.out, rel[4:])
        old = None
        if target.is_file():
            try:
                old = target.read_bytes().decode("utf-8")
            except UnicodeDecodeError:
                raise gate.Refusal("binary", "outside allowlist", "the file there is not UTF-8 text")
        elif target.exists():
            raise gate.Refusal("bad-path", "outside allowlist", "that path is a folder")
        refusal = gate.write_refusal(ctx.seat, ctx.job, rel, old, content)
        if refusal is not None:
            raise refusal
        if not target.parent.is_dir():
            raise ToolError("the folder for {} does not exist".format(rel))
        with open(str(target), "w", encoding="utf-8", newline="") as fh:
            fh.write(content)
        return "Wrote {}, {} bytes.".format(rel, len(content.encode("utf-8")))

    def run_check(self, args):
        if args:
            raise ToolError("run_check takes no arguments")
        code, page = self.ctx.kit("check", "tool")
        self.check_runs += 1
        return "finding check, exit code {}:\n{}".format(code, page)


class ToolError(Exception):
    """A call the tool cannot carry out; it changes nothing and is not a refusal."""


# ---------------------------------------------------------------- one job


class Job:
    def __init__(self, args, manifest, manifest_path, scrub):
        self.args = args
        self.manifest = manifest
        self.manifest_path = manifest_path
        self.run_dir = manifest_path.parent
        self.scrub = scrub
        self.seat, self.job = args.seat, args.job
        self.mock = args.mock is not None
        self.repo = Path(args.repo).resolve()
        self.folder = Path(args.folder).resolve()
        self.out = Path(args.out).resolve()
        self.limits = dict(DEFAULT_LIMITS)
        self.limits.update({k: v for k, v in (manifest.get("limits") or {}).items() if isinstance(v, int)})
        self.offer_check = manifest.get("offer_run_check") is True
        self.today = args.today or manifest.get("check_today") or datetime.date.today().isoformat()
        self.log = None
        self.saved = []
        self.generation = {}
        self.spend = []

    def show(self, path):
        """A path for output: relative to the run folder, under <kit> in the kit, or its bare name."""
        path = Path(path).resolve()
        bases = sorted(((self.repo, "<kit>"), (self.run_dir.resolve(), "")), key=lambda b: len(str(b[0])),
                       reverse=True)
        for base, label in bases:
            if inside(path, base):
                rel = path.relative_to(base).as_posix()
                return (label + "/" + rel if label and rel else label or rel) or "."
        return path.name

    def kit(self, verb, when):
        """Runs one kit command on the folder from the kit's folder, without the key; returns (exit code, page)."""
        command = [sys.executable, "-I", "finding/finding.py", verb, str(self.folder)]
        if verb == "check":
            command += ["--today", self.today]
        try:
            done = subprocess.run(command, cwd=str(self.repo), env=child_env(), stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, timeout=self.limits["kit_timeout_seconds"])
            page = done.stdout.decode("utf-8", "replace")
            if done.stderr.strip():
                page += ("\n" if page and not page.endswith("\n") else "") + done.stderr.decode("utf-8", "replace")
            code = done.returncode
        except subprocess.TimeoutExpired:
            code, page = None, "finding {} did not finish within {} seconds.".format(
                verb, self.limits["kit_timeout_seconds"])
        page = self.scrub.text(page)
        name = "{}-{}.txt".format(verb, when)
        if when != "tool":
            (self.out / name).write_text(page, encoding="utf-8")
            self.saved.append(name)
        self.log.event("kit_command", command="finding {}".format(verb), when=when, exit_code=code,
                       page_file=name if when != "tool" else None, page_sha256=sha256_text(page))
        return code, page

    def copy_written(self, where):
        """Copies each file the job may write, as it stands now, into --out/<where>/."""
        copied = []
        for pattern in gate.allowed(self.job):
            if pattern.startswith("out/"):
                continue
            if pattern.endswith("/*.md"):
                base = self.folder / pattern[:-len("/*.md")]
                rels = [p.relative_to(self.folder).as_posix() for p in sorted(base.glob("*.md")) if p.is_file()]
            else:
                rels = [pattern] if (self.folder / pattern).is_file() else []
            for rel in rels:
                target = self.out / where / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(self.folder / rel), str(target))
                copied.append(rel)
        return copied

    def brief(self, handed):
        lines = ["Job: {}. Seat: {}.".format(self.job, self.seat), "", "Paths you give a tool:",
                 "- a path such as closure/memo.md or evidence/ is in the finding folder you are given;",
                 "- kit/ and a page's path in the kit, such as kit/assistant/README.md, is one of the kit's "
                 "Markdown pages, read only;"]
        lines += ["- run/{} is the run's page of that name, read only;".format(p) for p in SEAT_RUN_READS[self.seat]]
        lines += ["- {} is in your output folder, outside the finding folder.".format(p)
                  for p in gate.allowed(self.job) if p.startswith("out/")]
        lines += ["", "This job may write " + WRITES_PLAIN[self.job],
                  "Any other write, and any read outside these paths, is refused and recorded."]
        deny = JOB_READ_DENY.get(self.job)
        if deny:
            lines.append("This job does not read {}.".format(" or ".join(deny)))
        if self.offer_check:
            lines.append("run_check runs finding check on the finding folder as of {} and returns its page.".format(
                self.today))
        lines.append("When the job is done, reply with a short summary and call no tool.")
        for title, text in handed:
            lines += ["", title, "", text.rstrip("\n")]
        return "\n".join(lines)

    def validate(self):
        repo, folder, out = self.repo, self.folder, self.out
        if self.seat != gate.JOBS[self.job][0]:
            raise Usage("the {} job runs in the {} seat".format(self.job, gate.JOBS[self.job][0]))
        if not (repo / "finding" / "finding.py").is_file() or not (repo / "finding" / "documents.py").is_file():
            raise Usage("--repo names no kit: finding/finding.py and finding/documents.py are not there")
        if not (folder / "finding.md").is_file():
            raise Usage("--folder names no finding folder: there is no finding.md in it")
        for shipped in ("finding", "library", "tieout"):
            if inside(folder, repo / shipped):
                raise Usage("--folder is inside the kit; copy the finding folder out and name the copy")
        if (folder / ".git").exists():
            raise Usage("--folder holds .git; name a plain copy of the finding folder")
        for name in ("kit", "run", "out"):
            if (folder / name).exists():
                raise Usage("--folder holds {}, which the tools read as one of the loop's own paths".format(name))
        if inside(out, folder):
            raise Usage("--out is inside the finding folder; name a folder outside it")
        if (out / "transcript.jsonl").exists():
            raise Usage("--out holds a transcript already; name a new folder for each job")

    def run(self, client, prompts, hands, ledger, prices, model, out_most, sealed):
        self.out.mkdir(parents=True, exist_ok=True)
        self.log = log = Transcript(self.out / "transcript.jsonl", self.scrub)
        tools = Tools(self)
        cap = float((self.manifest.get("spend") or {}).get("cap_usd", 0) or 0)
        started = time.time()
        log.event("job_start", seat=self.seat, job=self.job, model=model, mock=self.mock, today=self.today,
                  folder=self.show(self.folder), out=self.show(self.out),
                  manifest={"file": self.show(self.manifest_path), "sha256": sha256_file(self.manifest_path),
                            "sealed": sealed},
                  tools={"tools/agent_loop.py": sha256_file(TOOLS_DIR / "agent_loop.py"),
                         "tools/gate_diff.py": sha256_file(TOOLS_DIR / "gate_diff.py")},
                  kit={"finding/finding.py": sha256_file(self.repo / "finding" / "finding.py"),
                       "finding/documents.py": sha256_file(self.repo / "finding" / "documents.py")},
                  prompts=[{"file": self.show(p), "sha256": sha256_text(t), "chars": len(t)} for p, t in prompts],
                  handed=[{"file": self.show(p), "sha256": sha256_text(t), "chars": len(t)} for p, t in hands],
                  generation=self.generation, offer_run_check=self.offer_check, cap_usd=cap,
                  run_usd_before=round(ledger.total(), 6), ledger=self.show(ledger.path), limits=self.limits)
        start_cmds, send_back, end_cmds = JOB_COMMANDS[self.job]
        if self.args.start_check and "check" not in start_cmds:
            start_cmds = tuple(start_cmds) + ("check",)
        handed = []
        for verb in start_cmds:
            code, page = self.kit(verb, "start")
            title = ("The loop ran finding covers on the folder before you started. Its screen:" if verb == "covers"
                     else "The loop ran finding {} on the folder as of {}. Its page:".format(verb, self.today))
            handed.append((title, page))
        handed += [("Handed to you, {}:".format(Path(p).name), t) for p, t in hands]

        scratch = self.out / ".gate-copy"  # removed when the job ends; the gate reverts from it
        if scratch.exists():
            shutil.rmtree(str(scratch))
        copy = scratch / "before"
        shutil.copytree(str(self.folder), str(copy), symlinks=True)
        before = gate.snapshot(self.folder)
        write_json(self.out / "gate-before.json", before)

        status, turns, final_text = "crash", 0, ""
        try:
            status, turns, final_text = self.converse(client, tools, prompts, handed, ledger, prices, model, out_most,
                                                      cap, send_back)
        except KeyboardInterrupt:
            status = "interrupted"
            log.event("error", message="stopped from the keyboard")
        except Exception as err:  # the transcript and the gate still close the job
            log.event("error", message="{}: {}".format(type(err).__name__, err))
        finally:
            after = gate.snapshot(self.folder)
            report = gate.diff(before, after, self.seat, self.job, folder=self.folder, revert_from=copy)
            shutil.rmtree(str(scratch), ignore_errors=True)
            write_json(self.out / "gate-after.json", after)
            write_json(self.out / "gate.json", report)
            log.event("gate", ok=report["ok"], counts=report["counts"], summary=report["summary"],
                      changed=report["changed"])
        for verb in end_cmds:
            self.kit(verb, "final")
        final_copies = self.copy_written("final")
        (self.out / "final-message.txt").write_text(self.scrub.text(final_text) + "\n", encoding="utf-8")
        usd = round(sum(e.get("usd", 0) for e in self.spend), 6)
        by_kind = {}
        for record in tools.stopped:
            by_kind[record["kind"]] = by_kind.get(record["kind"], 0) + 1
        tokens = {k: sum(e.get(k, 0) for e in self.spend) for k in ("prompt_tokens", "candidates_tokens",
                                                                  "thoughts_tokens", "total_tokens")}
        summary = {"seat": self.seat, "job": self.job, "model": model, "mock": self.mock, "status": status,
                   "turns": turns, "tool_calls": tools.calls, "check_runs_by_agent": tools.check_runs,
                   "stopped": len(tools.stopped),
                   "stopped_writes": sum(1 for r in tools.stopped if r["action"] in ("write", "call")),
                   "stopped_reads": sum(1 for r in tools.stopped if r["action"] in ("read", "list")),
                   "stopped_by_kind": by_kind, "tokens": tokens, "usd": usd,
                   "run_usd_after": round(ledger.total(), 6), "cap_usd": cap, "gate_ok": report["ok"],
                   "gate_summary": report["summary"], "saved": self.saved, "final_copies": final_copies,
                   "elapsed_seconds": round(time.time() - started, 3)}
        write_json(self.out / "summary.json", self.scrub.obj(summary))
        log.event("job_end", final_text=final_text, **summary)
        line = "{} job, {} seat: {} after {} turn{}, {} tool call{}, {} stopped, ${:.4f} spent (run ${:.4f} of " \
               "${:.2f}). {} Transcript: {}.".format(
                   self.job, self.seat, status, turns, "" if turns == 1 else "s", tools.calls,
                   "" if tools.calls == 1 else "s", len(tools.stopped), usd, summary["run_usd_after"], cap,
                   report["summary"], self.show(self.out / "transcript.jsonl"))
        say(self.scrub, line)
        return 0 if status == "done" and report["ok"] else 1

    def converse(self, client, tools, prompts, handed, ledger, prices, model, out_most, cap, send_back):
        log = self.log
        system = "\n\n".join(text.rstrip("\n") for _, text in prompts)
        contents = [{"role": "user", "parts": [{"text": self.brief(handed)}]}]
        decls = tools.declarations()
        logged, last_len, last_in, last_out = 0, None, None, None
        turns, sent_back, final_text = 0, False, ""
        while True:
            if turns >= self.limits["max_turns_per_job"]:
                log.event("turn_limit", turns=turns)
                return "turn_limit", turns, final_text
            body = {"systemInstruction": {"parts": [{"text": system}]}, "contents": contents,
                    "tools": [{"functionDeclarations": decls}],
                    "toolConfig": {"functionCallingConfig": {"mode": "AUTO"}}, "generationConfig": self.generation}
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            if last_len is None:
                prompt_bound = len(data)  # no token is shorter than one byte of the text it stands for
            else:
                added = len(json.dumps(contents[last_len:], ensure_ascii=False).encode("utf-8"))
                prompt_bound = last_in + last_out + added + PROMPT_MARGIN
            bound = prices.usd(prompt_bound, out_most)
            spent = ledger.total()
            if spent + bound > cap:
                log.event("spend_cap", turn=turns + 1, run_usd=round(spent, 6), call_bound_usd=round(bound, 6),
                          cap_usd=cap, prompt_tokens_bound=prompt_bound, output_tokens_bound=out_most)
                return "spend_cap", turns, final_text
            turns += 1
            request = {"turn": turns, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                       "prompt_tokens_bound": prompt_bound, "output_tokens_bound": out_most,
                       "call_bound_usd": round(bound, 6), "run_usd_before": round(spent, 6),
                       "contents_from": logged, "contents": contents[logged:]}
            if logged == 0:
                request.update(system_instruction=system, tools=body["tools"], tool_config=body["toolConfig"],
                               generation_config=self.generation)
            log.event("request", **request)
            logged, last_len = len(contents), len(contents)
            try:
                reply = client.generate(model, data)
            except ApiError as err:
                log.event("api_error", turn=turns, status=err.status, message=err.message)
                return "api_error", turns, final_text
            log.event("response", turn=turns, body=reply)
            usage = reply.get("usageMetadata") or {}
            counts = {"prompt_tokens": usage.get("promptTokenCount"),
                      "candidates_tokens": usage.get("candidatesTokenCount", 0) or 0,
                      "thoughts_tokens": usage.get("thoughtsTokenCount", 0) or 0,
                      "tool_use_prompt_tokens": usage.get("toolUsePromptTokenCount", 0) or 0,
                      "cached_tokens": usage.get("cachedContentTokenCount", 0) or 0,
                      "total_tokens": usage.get("totalTokenCount", 0) or 0}
            if isinstance(counts["prompt_tokens"], int):
                last_in = counts["prompt_tokens"] + counts["tool_use_prompt_tokens"]
                last_out = counts["candidates_tokens"] + counts["thoughts_tokens"]
                usd, priced = prices.usd(last_in, last_out), "reported usage"
            else:
                counts["prompt_tokens"] = 0
                last_in, last_out = prompt_bound, out_most
                usd, priced = bound, "the call's bound, because the reply gave no usage"
            entry = dict(counts, usd=round(usd, 8))
            self.spend.append(entry)
            ledger.add({"t": now(), "job": self.job, "seat": self.seat, "out": self.show(self.out), "turn": turns,
                        "mock": self.mock, "usd": round(usd, 8)})
            run_usd = spent + usd
            log.event("usage", turn=turns, priced_from=priced, call_bound_usd=round(bound, 6),
                      run_usd=round(run_usd, 6), **entry)
            if usd > bound + 1e-12:
                log.event("bound_exceeded", turn=turns, usd=round(usd, 8), call_bound_usd=round(bound, 8))
            if run_usd > cap:
                log.event("spend_cap", turn=turns, run_usd=round(run_usd, 6), cap_usd=cap, passed=True)
                return "spend_cap", turns, final_text
            candidates = reply.get("candidates") or []
            if not candidates:
                reason = (reply.get("promptFeedback") or {}).get("blockReason") or "no candidate"
                log.event("no_content", turn=turns, reason=reason)
                return "no_content", turns, final_text
            candidate = candidates[0]
            parts = (candidate.get("content") or {}).get("parts") or []
            finish = candidate.get("finishReason") or ""
            if not parts:
                log.event("no_content", turn=turns, reason=finish or "empty")
                return "no_content" if not finish else "finish_" + finish.lower(), turns, final_text
            contents.append({"role": "model", "parts": parts})  # as received, thought signatures included
            calls = [p["functionCall"] for p in parts if isinstance(p, dict) and isinstance(p.get("functionCall"), dict)]
            if calls:
                contents.append({"role": "user", "parts": [tools.call(turns, c) for c in calls]})
                continue
            final_text = "\n".join(p.get("text", "") for p in parts
                                   if isinstance(p, dict) and p.get("text") and not p.get("thought"))
            if finish not in ("", "STOP"):
                log.event("finish", turn=turns, reason=finish)
                return "finish_" + finish.lower(), turns, final_text
            if send_back and not sent_back:
                sent_back = True
                copied = self.copy_written("first")
                code, page = self.kit("check", "first")
                log.event("first_finish", turn=turns, final_text=final_text, copied=copied, check_exit_code=code)
                contents.append({"role": "user", "parts": [{"text":
                    "The loop ran finding check on the folder as of {}, after you said you were done. Its page is "
                    "handed back to you once. Act on it as your procedure says, then reply with a short summary and "
                    "call no tool.\n\n{}".format(self.today, page.rstrip("\n"))}]})
                continue
            return "done", turns, final_text


def write_json(path, data):
    with open(str(path), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(data, fh, indent=1, ensure_ascii=False)
        fh.write("\n")


def read_text(path, what):
    try:
        return Path(path).read_bytes().decode("utf-8-sig")
    except OSError:
        raise Usage("cannot read the {} {}".format(what, Path(path).name))
    except UnicodeDecodeError:
        raise Usage("the {} {} is not UTF-8 text".format(what, Path(path).name))


def mock_replies(path):
    data = load_json(path, "mock replies")
    replies = data.get("replies") if isinstance(data, dict) else data
    if not isinstance(replies, list):
        raise Usage("the mock replies file holds a list, or an object with a replies list")
    return replies


def list_models(args, scrub):
    manifest = load_json(args.manifest, "manifest") if args.manifest else {}
    endpoint = filled((manifest.get("api") or {}).get("endpoint"))
    mock = args.mock is not None
    if not mock:
        live_endpoint(endpoint)
    transport = MockTransport(mock_replies(args.mock)) if mock else HttpTransport(DEFAULT_LIMITS["http_timeout_seconds"])
    try:
        models = Client(endpoint, transport, mock).list_models()
    except ApiError as err:
        say(scrub, "agent_loop: the model list could not be read: {}".format(err.message), err=True)
        return 1
    shown = 0
    for model in sorted(models, key=lambda m: str(m.get("name", ""))):
        if "generateContent" not in (model.get("supportedGenerationMethods") or []):
            continue
        name = str(model.get("name", "")).split("/", 1)[-1]
        say(scrub, "{}  {}  input {} tokens, output {} tokens{}".format(
            name, model.get("displayName", ""), model.get("inputTokenLimit", "?"), model.get("outputTokenLimit", "?"),
            ", thinking" if model.get("thinking") else ""))
        shown += 1
    say(scrub, "{} model{} this key can call with generateContent.".format(shown, "" if shown == 1 else "s"))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="agent_loop.py", description="Run one job of the agent run for one seat.")
    parser.add_argument("--manifest")
    parser.add_argument("--seat", choices=gate.SEATS)
    parser.add_argument("--job", choices=sorted(gate.JOBS))
    parser.add_argument("--folder")
    parser.add_argument("--repo")
    parser.add_argument("--prompt", action="append", default=[])
    parser.add_argument("--out")
    parser.add_argument("--today")
    parser.add_argument("--start-check", action="store_true")
    parser.add_argument("--hand", action="append", default=[])
    parser.add_argument("--ledger")
    parser.add_argument("--mock")
    parser.add_argument("--list-models", action="store_true")
    args = parser.parse_args(argv)
    scrub = Scrubber()
    scrub.add_path(Path.home(), "~")
    try:
        if args.list_models:
            return list_models(args, scrub)
        missing = [flag for flag, value in (("--manifest", args.manifest), ("--seat", args.seat), ("--job", args.job),
                                            ("--folder", args.folder), ("--repo", args.repo), ("--out", args.out))
                   if not value]
        if missing or not args.prompt:
            raise Usage("a job needs " + ", ".join(missing + ([] if args.prompt else ["--prompt"])))
        if args.today and not re.match(r"^\d{4}-\d\d-\d\d$", args.today):
            raise Usage("--today is a date as YYYY-MM-DD")
        manifest_path = Path(args.manifest).resolve()
        manifest = load_json(manifest_path, "manifest")
        mock = args.mock is not None
        job = Job(args, manifest, manifest_path, scrub)
        scrub.add_path(job.repo, "<kit>")
        scrub.add_path(job.run_dir, ".")
        scrub.add_path(job.folder, job.show(job.folder))
        scrub.add_path(job.out, job.show(job.out))
        job.validate()
        sealed = seal_check(manifest, job.run_dir, mock)
        model = filled((manifest.get("api") or {}).get("model")).split("/", 1)[-1]
        if not model and mock:
            model = "mock"
        if not MODEL_ID.match(model):
            raise Usage("set api.model in the manifest to a model id from --list-models")
        if not mock and not os.environ.get(KEY_VAR):
            raise Usage("{} is not set in this shell".format(KEY_VAR))
        prices = Prices(manifest.get("prices_usd_per_million_tokens") or {}, required=not mock)
        spend = manifest.get("spend") or {}
        cap = spend.get("cap_usd")
        if not isinstance(cap, (int, float)) or isinstance(cap, bool) or cap <= 0:
            raise Usage("set spend.cap_usd in the manifest to a number above 0")
        job.generation = clean_config(manifest.get("generation") or {})
        out_most = output_bound(job.generation, spend, mock)
        if args.ledger:
            ledger_path = Path(args.ledger).resolve()
        else:
            name = gate.normalize(str(spend.get("ledger") or "spend-ledger.jsonl"))
            if not name:
                raise Usage("spend.ledger in the manifest names no file")
            ledger_path = job.run_dir / name
            if mock:
                ledger_path = ledger_path.with_name(ledger_path.stem + ".mock" + ledger_path.suffix)
        ledger = Ledger(ledger_path)
        ledger.total()
        prompts = [(Path(p).resolve(), read_text(p, "prompt")) for p in args.prompt]
        hands = [(Path(p).resolve(), read_text(p, "handed file")) for p in args.hand]
        endpoint = filled((manifest.get("api") or {}).get("endpoint"))
        if not mock:
            live_endpoint(endpoint)
        transport = MockTransport(mock_replies(args.mock)) if mock else HttpTransport(job.limits["http_timeout_seconds"])
        job.spend = []

        def on_retry(status, message, attempt, wait):
            job.log.event("api_retry", status=status, message=message, attempt=attempt, wait_seconds=wait)

        client = Client(endpoint, transport, mock, on_retry)
        return job.run(client, prompts, hands, ledger, prices, model, out_most, sealed)
    except Usage as err:
        say(scrub, "agent_loop: " + str(err), err=True)
        return 2
    except gate.Refusal as err:
        say(scrub, "agent_loop: " + err.reason, err=True)
        return 2


if __name__ == "__main__":
    sys.exit(main())
