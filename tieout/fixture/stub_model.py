"""SYNTHETIC: a loopback stand-in for a chat-completions compatible endpoint, for tests only.

Purpose: an http.server on 127.0.0.1 that answers POST .../chat/completions in the
  chat-completions format, so the tie-out's chat adapter and its egress checks can be tested with
  no outside connection. Each request's path, query, headers and body are kept in server.seen, so
  a test can see the auth header, the extra headers and the fixed query the adapter sent. The
  default reply acts as a model that proposes what the rules proposer proposes for the chunk,
  numbers in words included, over matter 1's cite names, and picks candidate 1 for each job 4
  item. Options for a test:
    reply=fn     fn(request JSON) returns the message content to send back
    fail=[...]   the next requests get these HTTP statuses in turn; a 3xx carries a Location
    delay=s      wait s seconds before answering, to pass a client's timeout
  An error reply echoes the request body and the Authorization header it received, as some
  gateways do, so a test can show the tool saves the reply only in sent/, with the key removed.
  The same server answers a request sent to it as a proxy (an absolute URL in the request line),
  so a test can stand it up as counsel-terms' proxy_host and see Proxy-Authorization.
  server.connections counts the connections it accepted, so it can also stand in for a proxy
  the tool must never reach.
  serve() starts it on a thread on a port the system picks and returns it with server.url set;
  server.shutdown() and server.server_close() stop it.
  With --record it records the replay fixture: it copies matter 1 to a temporary folder, runs
  the tie-out there with provider chat and the invented model id synthetic-proposer-1 over the
  untagged twin, and copies that run's sent/ bodies and verdicts.json to
  matter-1/replay/untagged-chat/.
Reads: tieout/fixture/matter-1 (the record's cite names, and with --record the engagement it
  copies).
Writes: nothing as a library. With --record, matter-1/replay/untagged-chat/sent/ and its
  verdicts.json, replacing what is there, and a temporary folder it removes.
Network: listens on 127.0.0.1 only and never connects out.
Exit codes: as a script, 0 when recorded, 1 when the recording run did not give exit 1 (the
  untagged twin always has untagged claims), 2 on a usage error.
Run: python3 -I tieout/fixture/stub_model.py --record
"""
import argparse
import http.server
import json
import os
import shutil
import socketserver
import sys
import tempfile
import threading
import time
import urllib.parse

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
TOOL = os.path.dirname(HERE)
MATTER = os.path.join(HERE, "matter-1")
FIXTURE = os.path.join(MATTER, "replay", "untagged-chat")
MODEL = "synthetic-proposer-1"
_NAMES = {}


def rules_reply(req):
    """The default content: the rules proposer's reply for a chunk, or candidate 1 for job 4."""
    if TOOL not in sys.path:
        sys.path.insert(0, TOOL)
    import claims
    import record
    user = req["messages"][-1]["content"]
    msg = json.loads(user)
    if msg.get("job") == "candidates":
        return json.dumps([{"item": it["item"], "choice": 1} for it in msg["items"]])
    if "names" not in _NAMES:
        _NAMES["names"] = record.load(MATTER, "mdy").grammar_names()
    return json.dumps(claims.rules_propose(user, _NAMES["names"], "mdy"), ensure_ascii=False)


class Handler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        srv = self.server
        url = urllib.parse.urlsplit(self.path)
        body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        srv.seen.append({"path": url.path, "query": url.query, "headers": dict(self.headers.items()),
                         "proxied": bool(url.scheme), "body": body})
        status = srv.fail.pop(0) if srv.fail else 200
        if srv.delay:
            time.sleep(srv.delay)
        if status == 200 and not url.path.endswith("/chat/completions"):
            status = 404
        if status != 200:
            data = json.dumps({"error": {"message": "stub status %d" % status, "echo": body.decode("utf-8", "replace"),
                                         "authorization": self.headers.get("Authorization", "")}}).encode("utf-8")
            self.send_response(status)
            if 300 <= status < 400:
                self.send_header("Location", "http://localhost:9/elsewhere")
        else:
            req = json.loads(body.decode("utf-8"))
            content = srv.reply(req)
            data = json.dumps({"id": "stub-%d" % len(srv.seen), "object": "chat.completion", "created": 0,
                               "model": req.get("model", ""),
                               "choices": [{"index": 0, "finish_reason": "stop",
                                            "message": {"role": "assistant", "content": content}}],
                               "usage": {"prompt_tokens": len(body) // 4, "completion_tokens": len(content) // 4,
                                         "total_tokens": len(body) // 4 + len(content) // 4}},
                              ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
            self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True

    def server_bind(self):  # no reverse name lookup of the address, unlike HTTPServer's
        socketserver.TCPServer.server_bind(self)
        self.server_name, self.server_port = "127.0.0.1", self.server_address[1]

    def get_request(self):
        self.connections += 1
        return socketserver.TCPServer.get_request(self)

    def handle_error(self, request, client_address):  # a client that timed out and left: nothing to print
        pass


def serve(reply=None, fail=(), delay=0):
    srv = Server(("127.0.0.1", 0), Handler)
    srv.seen, srv.fail, srv.delay, srv.reply, srv.connections = [], list(fail), delay, reply or rules_reply, 0
    srv.url = "http://127.0.0.1:%d/v1" % srv.server_address[1]
    threading.Thread(target=srv.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True).start()
    return srv


def record_fixture():
    """Run the tie-out with provider chat against a fresh stub over the untagged twin, and keep
    the run's sent/ bodies and verdicts.json as the replay fixture."""
    sys.path.insert(0, TOOL)
    import tieout
    for name in [n for n in os.environ if n.startswith("TIEOUT_") or n.lower().endswith("_proxy")]:
        del os.environ[name]  # an invented engagement: no key, no header and no proxy from this shell
    srv = serve()
    tmp = tempfile.mkdtemp(prefix="tieout-record-")
    try:
        eng = os.path.join(tmp, "eng")
        shutil.copytree(MATTER, eng, ignore=shutil.ignore_patterns("key", "replay"))
        if tieout.main(["init", eng]) != 0:
            return 1
        for name, change in (("matter.json", {"provider": "chat", "model": MODEL, "draft": "report/draft-untagged.md",
                                              "key_env": ""}),
                             ("counsel-terms.json", {"endpoint_base_url": srv.url})):
            path = os.path.join(eng, name)
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            data.update(change)
            with open(path, "w", encoding="utf-8", newline="\n") as fh:
                json.dump(data, fh, indent=1)
        rc = tieout.main(["--engagement", eng, "run"])
        runs = sorted(os.listdir(os.path.join(eng, "run")))
        rid = [r for r in runs if not r.startswith(".")][-1]
        if rc != 1:
            print("stub_model: the recording run gave exit %d, expected 1" % rc, file=sys.stderr)
            return 1
        shutil.rmtree(os.path.join(FIXTURE, "sent"), ignore_errors=True)
        shutil.copytree(os.path.join(eng, "run", rid, "sent"), os.path.join(FIXTURE, "sent"))
        shutil.copyfile(os.path.join(eng, "run", rid, "verdicts.json"), os.path.join(FIXTURE, "verdicts.json"))
        print("stub_model: recorded %d calls to %s" % (len(srv.seen), os.path.relpath(FIXTURE, TOOL).replace(os.sep, "/")))
        return 0
    finally:
        srv.shutdown()
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description="A loopback chat-completions stub for the tie-out's tests.")
    ap.add_argument("--record", action="store_true", required=True,
                    help="record the replay fixture from a fresh stub")
    ap.parse_args(argv)
    return record_fixture()


if __name__ == "__main__":
    sys.exit(main())
