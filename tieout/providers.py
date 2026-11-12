"""Provider interface for the tie-out's proposer: the adapters, the egress controls and receipts.

Purpose: one interface, kept from the fsi harness, is all the runner sees:
  complete(*, model, system, user, max_tokens) -> (text, usage). The runner cannot tell which
  adapter it holds. Three adapters:
    rules   deterministic and offline, the default and the baseline. It reads the chunk in the
            user message and proposes every figure and date in digits, every quotation in quote
            marks, and the cite the fixed pairing rules give each, and lists every number or date
            in words that words.py reads as a words candidate. Asked for job 4 (a message with
            "job": "candidates"), which only measure.py's baseline asks it, it picks each item's
            first candidate, code's own order; a run asks job 4 of a model only.
    chat    chat-completions compatible: POST {endpoint_base_url}/chat/completions with model,
            messages (system, user), temperature 0 and max_tokens. The key, from the
            variable matter.json's key_env names, goes in the header TIEOUT_AUTH_HEADER names
            (default Authorization) after TIEOUT_AUTH_SCHEME (default Bearer); with key_env set
            to "", for a self-hosted server that takes no key, no auth header is sent. TIEOUT_EXTRA_HEADERS adds
            "Name: value" headers separated by ";" and TIEOUT_QUERY adds fixed query parameters
            "a=b&c=d". A firm can point it at any chat-completions compatible endpoint.
    replay  answers from a prior run's sent/ bodies, keyed by the sha256 of the exact request
            body the chat adapter would send. A miss raises ReplayMiss (exit 2) and nothing is
            sent anywhere.
  Egress controls, from counsel-terms.json and nothing else:
    N2, N3  watch() adds a sys.addaudithook observer once per process. It refuses any name
            lookup (socket.getaddrinfo, gethostbyname or gethostbyaddr) for a host other than the
            endpoint host or the proxy host, and any socket.connect to an address getaddrinfo did
            not return for one of those hosts in this process, before the connection is made. A
            wrapper on socket.getaddrinfo records what each lookup returned, since an audit event
            does not carry the result.
    N4      the opener has no redirect handler, so a 3xx is refused with its status only.
    N5      https only, except to 127.0.0.1, ::1 or localhost.
    N6      the opener is built with ProxyHandler({}), so neither the environment's proxy
            variables nor the system's proxy settings or bypass list (no_proxy included) are
            read. Counsel-terms' proxy_host, when set, is set on each request; TIEOUT_PROXY_AUTH
            gives the proxy's user:password, sent as Proxy-Authorization.
    N7      counsel-terms' timeout_seconds limits each wait on the endpoint, to connect or for
            the next part of a reply (a socket timeout, so a call that keeps sending can last
            longer); one retry on 429 or a 5xx, which counts against max_calls like any call.
    N8      the key travels only in its header and is refused in the URL, TIEOUT_QUERY or an
            extra header; an empty key variable stops the run before it connects, unless
            key_env is ""; every network error is wrapped, and its message gives status, byte
            counts, the receipt number and where an error reply was saved, never its text.
    N9      receipts.jsonl holds one line per call with the peers the observer saw, and
            verify_receipts(), which status runs, checks each sent/ body against its line and
            each peer against counsel-terms.json. A call that saw a refused peer stops the run.
  The Recorder writes each call's exact bodies, with no headers, to sent/NNNN-request.json and
  NNNN-response.json, or for an HTTP error the endpoint's reply with the key and proxy password
  removed to NNNN-error.json, and one line to receipts.jsonl, through the gate, for an adapter that
  builds a request body: chat, and replay, which keeps the body it matched. The rules adapter
  sends nothing and builds no body, so a rules run has no sent/ folder and no receipts.jsonl;
  proposals.json keeps each of its attempts.
Reads: the rules adapter reads only the user message it is handed; replay reads the sent/ folder
  matter.json's replay_from names; chat reads the environment variables above and counsel-terms'
  ca_file; verify_receipts reads a run's receipts.jsonl and sent/.
Writes: nothing itself; the Recorder hands bytes to gate.write and gate.append, and with no run
  folder (measure.py's scoring) writes nothing.
Network: the chat adapter only, to the one endpoint, or through the one proxy, counsel-terms.json
  names. This is the one module allowed to import urllib, http, socket, ssl or select (N1).
Exit codes: none; a library module. EgressError means exit 3 and ReplayMiss exit 2 in the CLI.
"""
import base64
import datetime
import json
import os
import re
import socket
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

import claims
import gate
import record

LOOPBACK = ("127.0.0.1", "::1", "localhost")
HEADER_NAME = re.compile(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+")
_WATCH = {"hooked": False, "hosts": set(), "resolved": {}, "peers": []}


class EgressError(Exception):
    """An egress refusal or a wrapped network failure, exit 3. The reason never holds a URL, a
    body, a header value or the key."""

    def __init__(self, code, reason, retry=False):
        Exception.__init__(self, "%s: %s" % (code, reason))
        self.code, self.reason, self.retry = code, reason, retry


class ReplayMiss(Exception):
    """Replay has no recorded response for a request: exit 2, and nothing is sent."""


class ProviderClient:
    """The interface every adapter keeps (ported from fsi src/harness/providers.py). exchange is
    set by an adapter that builds a request body, so the Recorder can keep the exact bytes."""

    name = "abstract"
    host = ""
    exchange = None

    def complete(self, *, model, system, user, max_tokens):
        """Returns (text, usage) with usage = {input_tokens, output_tokens}."""
        raise NotImplementedError


class RulesClient(ProviderClient):
    """Deterministic and offline. Its reply is the rules proposer's JSON array for the chunk."""

    name = "rules"
    host = "local"

    def __init__(self, names, date_order):
        self.names, self.date_order = names, date_order

    def complete(self, *, model, system, user, max_tokens):
        req = json.loads(user)
        if req.get("job") == "candidates":
            return json.dumps([{"item": it["item"], "choice": 1} for it in req["items"]]), {"input_tokens": 0,
                                                                                          "output_tokens": 0}
        proposals = claims.rules_propose(user, self.names, self.date_order)
        return json.dumps(proposals, ensure_ascii=False), {"input_tokens": 0, "output_tokens": 0}


# --- the chat-completions compatible body, shared by chat and replay -----------------------------


def chat_body(model, system, user, max_tokens):
    """The exact request body, compact and with sorted keys, so one request has one sha256."""
    body = {"model": model, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": 0, "max_tokens": max_tokens}
    return json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def reply_text(data):
    """(text, usage) from a chat completion. An envelope that does not parse gives empty text,
    which P1 rejects like any reply that is not JSON."""
    try:
        doc = json.loads(data.decode("utf-8"))
        text = doc["choices"][0]["message"]["content"]
        u = doc.get("usage") or {}
        usage = {"input_tokens": int(u.get("prompt_tokens", 0)), "output_tokens": int(u.get("completion_tokens", 0))}
    except (ValueError, KeyError, IndexError, TypeError, AttributeError, OverflowError, RecursionError):
        return "", {"input_tokens": 0, "output_tokens": 0}
    return (text if isinstance(text, str) else ""), usage


# --- N2, N3: the observer ------------------------------------------------------------------------


def _name(host):
    return (host.decode("ascii", "replace") if isinstance(host, bytes) else str(host)).lower()


def _observe(event, args):
    if event in ("socket.getaddrinfo", "socket.gethostbyname", "socket.gethostbyaddr"):
        host = _name(args[0])
        if host not in _WATCH["hosts"]:
            _WATCH["peers"].append({"host": host, "peer": "", "ok": False})
            raise EgressError("N2", "a name lookup for %s, which counsel-terms.json does not name" % host)
    elif event == "socket.connect":
        addr = args[1]
        peer = (str(addr[0]), int(addr[1])) if isinstance(addr, tuple) and len(addr) >= 2 else (str(addr), 0)
        host = next((h for h in sorted(_WATCH["hosts"]) if peer in _WATCH["resolved"].get(h, ())), None)
        _WATCH["peers"].append({"host": host or "", "peer": "%s:%d" % peer, "ok": host is not None})
        if host is None:
            raise EgressError("N3", "a connection to %s:%d, an address no allowed host resolved to" % peer)


def watch(hosts):
    """Allow lookups of these hosts only, from now on in this process, and connections only to
    the addresses their lookups return. The audit hook is added once; it cannot be removed."""
    _WATCH["hosts"] = {_name(h) for h in hosts}
    if not getattr(socket.getaddrinfo, "_tieout", False):
        real = socket.getaddrinfo

        def getaddrinfo(host, port, *args, **kwargs):
            found = real(host, port, *args, **kwargs)
            _WATCH["resolved"].setdefault(_name(host), set()).update((str(r[4][0]), int(r[4][1])) for r in found)
            return found
        getaddrinfo._tieout = True
        socket.getaddrinfo = getaddrinfo
    if not _WATCH["hooked"]:
        sys.addaudithook(_observe)
        _WATCH["hooked"] = True


def allowed_hosts(terms):
    """The endpoint host and the proxy host counsel-terms.json names, lower case."""
    out = set()
    host = urllib.parse.urlsplit((terms.get("endpoint_base_url") or "").strip()).hostname
    if host:
        out.add(host.lower())
    proxy = (terms.get("proxy_host") or "").strip()
    if proxy:
        p = urllib.parse.urlsplit("//" + proxy).hostname
        if p:
            out.add(p.lower())
    return out


# --- the live adapter and replay -----------------------------------------------------------------


class ChatClient(ProviderClient):
    """Chat-completions compatible, on urllib, behind N2 to N8."""

    name = "chat"

    def __init__(self, matter, terms, root=".", env=None):
        env = os.environ if env is None else env
        base = (terms.get("endpoint_base_url") or "").strip().rstrip("/")
        parts = urllib.parse.urlsplit(base)
        self.host = (parts.hostname or "").lower()
        if not self.host:
            raise EgressError("N2", "counsel-terms.json names no endpoint host, so provider %s does not run"
                              % matter.get("provider", "chat"))
        if parts.scheme != "https" and not (parts.scheme == "http" and self.host in LOOPBACK):
            raise EgressError("N5", "endpoint_base_url must use https; plain http is allowed only to 127.0.0.1, "
                                    "::1 or localhost")
        if parts.username or parts.password or parts.query or parts.fragment:
            raise EgressError("N8", "endpoint_base_url holds a user, password, query or fragment; fixed query "
                                    "parameters go in TIEOUT_QUERY and the key in its header")
        key_env = matter.get("key_env", "TIEOUT_API_KEY")  # "" declares an endpoint that takes no key
        key = env.get(key_env, "") if key_env else ""
        if key_env and not key:
            raise EgressError("N8", "%s is empty, so nothing is sent; set the key, or set key_env to \"\" in "
                                    "matter.json for an endpoint that takes no key" % key_env)
        query = env.get("TIEOUT_QUERY", "").strip()
        if query:
            try:
                query = urllib.parse.urlencode(urllib.parse.parse_qsl(query, keep_blank_values=True,
                                                                      strict_parsing=True))
            except ValueError:
                raise ValueError("TIEOUT_QUERY is not in the form a=b&c=d")
        extra = {}
        for i, line in enumerate(env.get("TIEOUT_EXTRA_HEADERS", "").split(";"), 1):
            if line.strip():
                name, colon, value = line.partition(":")
                if not colon or not HEADER_NAME.fullmatch(name.strip()):
                    raise ValueError("TIEOUT_EXTRA_HEADERS entry %d is not in the form Name: value" % i)
                extra[name.strip()] = value.strip()
        if key and (key in urllib.parse.unquote(base) or key in urllib.parse.unquote_plus(query)
                    or key in env.get("TIEOUT_EXTRA_HEADERS", "")):
            raise EgressError("N8", "the key may travel only in the header TIEOUT_AUTH_HEADER names, never in "
                                    "a URL, TIEOUT_QUERY or another header")
        self.url = base + "/chat/completions" + ("?" + query if query else "")
        self.headers = dict(extra)
        self.headers["Content-Type"] = "application/json"
        if key:
            scheme = env.get("TIEOUT_AUTH_SCHEME")
            scheme = "Bearer" if scheme is None else scheme.strip()
            self.headers[env.get("TIEOUT_AUTH_HEADER", "").strip() or "Authorization"] = (scheme + " " + key).strip()
        self.proxy = (terms.get("proxy_host") or "").strip()
        if self.proxy:
            p = urllib.parse.urlsplit("//" + self.proxy)
            if not p.hostname or not p.port or p.username or p.path:
                raise ValueError("counsel-terms.json: proxy_host must be host:port")
            auth = env.get("TIEOUT_PROXY_AUTH", "")
            if auth:
                self.headers["Proxy-Authorization"] = "Basic " + base64.b64encode(auth.encode("utf-8")).decode("ascii")
        ca = (terms.get("ca_file") or "").strip()
        if ca and not os.path.isabs(ca):
            ca = os.path.join(root, ca)
        self.opener = urllib.request.OpenerDirector()  # no redirect handler (N4), no environment proxy (N6)
        for h in (urllib.request.ProxyHandler({}), urllib.request.HTTPHandler(),
                  urllib.request.HTTPSHandler(context=ssl.create_default_context(cafile=ca or None)),
                  urllib.request.HTTPDefaultErrorHandler(), urllib.request.HTTPErrorProcessor()):
            self.opener.add_handler(h)
        self.timeout = terms.get("timeout_seconds", 60)
        self.secrets = [s for s in (key, env.get("TIEOUT_PROXY_AUTH", "")) if s]
        self.secrets += [v for v in extra.values() if len(v) >= 8]  # a gateway token; shorter values are flags
        watch(allowed_hosts(terms))

    def scrub(self, data):
        """An error reply as received, with the key and the proxy password removed, plain,
        percent-encoded or base64, since some gateways echo the headers they were sent."""
        for s in self.secrets:
            raw = s.encode("utf-8")
            for form in (raw, urllib.parse.quote(s, safe="").encode("ascii"), base64.b64encode(raw)):
                data = data.replace(form, b"[removed]")
        return data

    def complete(self, *, model, system, user, max_tokens):
        body = chat_body(model, system, user, max_tokens)
        self.exchange = {"request": body, "response": None, "error": None, "bytes_in": 0, "status": "not sent"}
        data = self.send(body)
        self.exchange.update(response=data, bytes_in=len(data), status="ok")
        return reply_text(data)

    def send(self, body):
        req = urllib.request.Request(self.url, data=body, headers=self.headers, method="POST")
        if self.proxy:  # set on the request: a ProxyHandler would first consult no_proxy and the OS bypass list
            req.set_proxy(self.proxy, "http")
        try:
            with self.opener.open(req, timeout=self.timeout) as resp:
                return resp.read()
        except EgressError:
            raise
        except urllib.error.HTTPError as exc:
            try:
                err = exc.read() or b""
            except Exception:  # noqa: BLE001 - an unreadable error body is kept as empty
                err = b""
            self.exchange.update(bytes_in=len(err), error=self.scrub(err), status="http %d" % exc.code)
            if 300 <= exc.code < 400:
                raise EgressError("N4", "status http %d; the tool follows no redirect" % exc.code)
            raise EgressError("N8", "status http %d" % exc.code, retry=exc.code == 429 or exc.code >= 500)
        except Exception as exc:  # noqa: BLE001 - N8: every other failure is wrapped; its text may hold a URL
            self.exchange["status"] = type(getattr(exc, "reason", None) or exc).__name__
            raise EgressError("N8", "status %s" % self.exchange["status"])


class ReplayClient(ProviderClient):
    """Answers from a prior run's sent/ bodies by the sha256 of the exact request body."""

    name = "replay"
    host = "replay"

    def __init__(self, folder):
        self.answers = {}
        sent = os.path.join(folder, "sent")
        for n in sorted(os.listdir(sent)):
            answer = os.path.join(sent, n[:-len("request.json")] + "response.json")
            if n.endswith("-request.json") and os.path.isfile(answer):
                with open(os.path.join(sent, n), "rb") as fh, open(answer, "rb") as fa:
                    self.answers[record.sha256_bytes(fh.read())] = fa.read()
        watch(())  # nothing may resolve or connect while a replay runs

    def complete(self, *, model, system, user, max_tokens):
        body = chat_body(model, system, user, max_tokens)
        data = self.answers.get(record.sha256_bytes(body))
        if data is None:
            raise ReplayMiss("replay has no recorded response for request sha256 %s" % record.sha256_bytes(body))
        self.exchange = {"request": body, "response": data, "bytes_in": len(data), "status": "ok"}
        return reply_text(data)


def make_client(matter, names, terms=None, root="."):
    """The adapter matter.json names. A live adapter refuses unless counsel-terms.json names its
    endpoint host (N2) over https or loopback http (N5)."""
    provider = matter.get("provider", "rules")
    if provider == "rules":
        return RulesClient(names, matter.get("date_order", "mdy"))
    if provider == "replay":
        return ReplayClient(os.path.join(root, matter["replay_from"]))
    if provider == "chat":
        return ChatClient(matter, terms or {}, root)
    raise ValueError("matter.json: provider %r is not one of rules, replay, chat" % provider)


# --- receipts ------------------------------------------------------------------------------------


class Recorder:
    """sent/NNNN-request.json and NNNN-response.json hold the exact bodies; receipts.jsonl holds
    one line per call, a retry included. Only an adapter that sets exchange, one that builds a
    request body, gets either; the rules adapter sends nothing and leaves neither, and its calls
    are only counted. With receipt_detail digest the bodies are not written.
    With run_rel None nothing is written and only the counts are kept: measure.py scores a
    planted item that way, through the same proposer path a run takes. max_calls bounds the one
    retry on 429 or a 5xx (N7)."""

    def __init__(self, run_rel, detail="full", max_calls=None):
        self.run_rel, self.detail, self.max_calls, self.n = run_rel, detail, max_calls, 0
        self.bytes_out = self.bytes_in = 0
        self.paragraphs, self.hosts = [], []

    def call(self, client, *, model, system, user, max_tokens, paragraphs, retry):
        for again in (False, True):
            self.n += 1
            started = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            t0, seen, failed = time.time(), len(_WATCH["peers"]), None
            client.exchange, text, usage = None, "", {"input_tokens": 0, "output_tokens": 0}
            try:
                text, usage = client.complete(model=model, system=system, user=user, max_tokens=max_tokens)
            except EgressError as exc:
                failed = exc
            elapsed = int((time.time() - t0) * 1000)
            ex = client.exchange
            peers = _WATCH["peers"][seen:]
            if failed is None and any(not p["ok"] for p in peers):  # N9: a refused peer stops the run
                failed = EgressError("N9", "the observer refused a peer during the call")
            self.paragraphs += [p for p in paragraphs if p not in self.paragraphs]
            if client.host not in self.hosts:
                self.hosts.append(client.host)
            if ex is None:  # an adapter that builds no body (rules) sends nothing: no body, no receipt
                if failed is None:
                    return text, usage
                raise failed
            self.bytes_out += len(ex["request"])
            self.bytes_in += ex["bytes_in"]
            if self.run_rel is not None:
                self._write(ex, usage, client.host, peers, paragraphs, started, elapsed, retry or again)
            if failed is None:
                return text, usage
            if not again and failed.retry and (self.max_calls is None or self.n < self.max_calls):
                continue
            kept = (self.run_rel is not None and self.detail == "full" and ex.get("error") is not None)
            raise EgressError(failed.code, "%s (receipt %d, %d bytes out, %d bytes in)%s"
                              % (failed.reason, self.n, len(ex["request"]), ex["bytes_in"],
                                 "; the endpoint's reply is in %s" % "/".join((self.run_rel.replace(os.sep, "/"),
                                                                               "sent", "%04d-error.json" % self.n))
                                 if kept else ""))

    def _write(self, ex, usage, host, peers, paragraphs, started, elapsed, retry):
        sent = os.path.join(self.run_rel, "sent", "%04d-" % self.n)
        if self.detail == "full":
            gate.write(sent + "request.json", ex["request"], create=True)
            if ex["response"] is not None:
                gate.write(sent + "response.json", ex["response"], create=True)
            if ex.get("error") is not None:
                gate.write(sent + "error.json", ex["error"], create=True)
        receipt = {"n": self.n, "request_sha256": record.sha256_bytes(ex["request"]),
                   "response_sha256": record.sha256_bytes(ex["response"]) if ex["response"] is not None else "",
                   "bytes_out": len(ex["request"]), "bytes_in": ex["bytes_in"], "tokens": usage,
                   "status": ex["status"], "host": host, "peers": peers, "paragraphs": paragraphs,
                   "start": started, "elapsed_ms": elapsed, "retry": retry, "detail": self.detail}
        if ex.get("error") is not None:
            receipt["error_sha256"] = record.sha256_bytes(ex["error"])
        gate.append(os.path.join(self.run_rel, "receipts.jsonl"),
                    (json.dumps(receipt, sort_keys=True) + "\n").encode("utf-8"), create=self.n == 1)


def verify_receipts(run_dir, terms):
    """N9 for status: one receipt line per call, numbered from 1; each sent/ body hashes to its
    line and the request's length is its bytes_out; a live call names a host counsel-terms.json
    allows, observed at least one connection when it succeeded, and every peer the observer saw
    was allowed. Returns the problems found."""
    path = os.path.join(run_dir, "receipts.jsonl")
    out = []
    if not os.path.isfile(path):
        return out
    allowed = allowed_hosts(terms or {})
    with open(path, encoding="utf-8") as fh:
        lines = [ln for ln in fh if ln.strip()]
    for i, line in enumerate(lines, 1):
        try:
            rec = json.loads(line)
        except ValueError:
            out.append("receipt line %d does not parse" % i)
            continue
        n = rec.get("n", 0)
        if n != i:
            out.append("receipt line %d is numbered %s" % (i, n))
        for side in ("request", "response", "error"):
            p = os.path.join(run_dir, "sent", "%04d-%s.json" % (n, side))
            if os.path.isfile(p):
                with open(p, "rb") as fb:
                    data = fb.read()
                if record.sha256_bytes(data) != rec.get(side + "_sha256"):
                    out.append("sent/%04d-%s.json does not match receipt %d" % (n, side, i))
                elif side == "request" and len(data) != rec.get("bytes_out"):
                    out.append("sent/%04d-request.json is not the %s bytes receipt %d counts" % (n, rec.get("bytes_out"), i))
            elif rec.get("detail", "full") == "full" and (side == "request" or rec.get(side + "_sha256")):
                out.append("sent/%04d-%s.json is missing" % (n, side))
        if rec.get("host") in ("local", "replay"):
            continue
        if rec.get("host") not in allowed:
            out.append("receipt %d names host %s, which counsel-terms.json does not" % (i, rec.get("host")))
        peers = rec.get("peers") or []
        if rec.get("status") == "ok" and not peers:
            out.append("receipt %d: the observer saw no connection for a call that succeeded" % i)
        for p in peers:
            if not p.get("ok") or p.get("host") not in allowed:
                out.append("receipt %d: peer %s (%s) is outside the configured set" % (i, p.get("peer"), p.get("host")))
    return out
