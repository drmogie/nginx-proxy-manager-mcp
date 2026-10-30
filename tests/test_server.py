"""Tests against a fake NPM server. Run: python tests/test_server.py"""

import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nginx_proxy_manager_mcp import server as s  # noqa: E402

PASSWORD = "s3cret-pass-XYZ"
ALLOWED = set(s.KINDS["proxy-hosts"]["fields"])
DB = {"hosts": {}, "next": 1, "logins": 0, "expire_next": False}
READ_ONLY = {"id": 0, "created_on": "x", "modified_on": "x", "owner_user_id": 1,
             "owner": {}, "certificate": None, "access_list": None, "is_deleted": 0}


class Fake(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, obj):
        raw = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n)) if n else None

    def _authed(self):
        if DB["expire_next"]:
            DB["expire_next"] = False
            return False
        return self.headers.get("Authorization", "").startswith("Bearer tok-")

    def do_POST(self):
        body = self._body()
        if self.path == "/api/tokens":
            if body.get("identity") == "me@x.io" and body.get("secret") == PASSWORD:
                DB["logins"] += 1
                return self._send(200, {"token": f"tok-{DB['logins']}",
                                        "expires": "2099-01-01T00:00:00.000Z"})
            return self._send(401, {"error": {"code": 401, "message": "Invalid password"}})
        if not self._authed():
            return self._send(401, {"error": {"message": "Unauthorized"}})
        if self.path == "/api/nginx/proxy-hosts":
            extra = set(body) - ALLOWED
            if extra:
                return self._send(400, {"error": {"message": f"extra props {sorted(extra)}"}})
            hid = DB["next"]
            DB["next"] += 1
            DB["hosts"][hid] = {**READ_ONLY, **body, "id": hid}
            return self._send(201, DB["hosts"][hid])
        for verb in ("enable", "disable"):
            if self.path.endswith("/" + verb):
                hid = int(self.path.split("/")[-2])
                DB["hosts"][hid]["enabled"] = verb == "enable"
                return self._send(200, True)
        self._send(404, {"error": {"message": "nope"}})

    def do_PUT(self):
        body = self._body()
        if not self._authed():
            return self._send(401, {"error": {"message": "Unauthorized"}})
        hid = int(self.path.split("?")[0].split("/")[-1])
        extra = set(body) - ALLOWED
        if extra:
            return self._send(400, {"error": {"message": f"extra props {sorted(extra)}"}})
        DB["hosts"][hid].update(body)
        self._send(200, DB["hosts"][hid])

    def do_DELETE(self):
        if not self._authed():
            return self._send(401, {"error": {"message": "Unauthorized"}})
        hid = int(self.path.split("/")[-1])
        DB["hosts"].pop(hid, None)
        self._send(200, True)

    def do_GET(self):
        p = self.path.split("?")[0]
        if p == "/api/":
            return self._send(200, {"status": "OK", "version": {"major": 2, "minor": 12}})
        if not self._authed():
            return self._send(401, {"error": {"message": "Unauthorized"}})
        if p == "/api/reports/hosts":
            return self._send(200, {"proxy": len(DB["hosts"]), "redirection": 0,
                                    "stream": 0, "dead": 0})
        if p == "/api/nginx/proxy-hosts":
            return self._send(200, list(DB["hosts"].values()))
        if p.startswith("/api/nginx/proxy-hosts/"):
            hid = int(p.split("/")[-1])
            if hid in DB["hosts"]:
                return self._send(200, DB["hosts"][hid])
            return self._send(404, {"error": {"message": "Not Found"}})
        if p == "/api/audit-log":
            return self._send(200, [
                {"created_on": "2026-01-01", "action": "created", "object_type": "proxy-host",
                 "object_id": 1, "user": {"name": "Mogie"}, "meta": {}},
                {"created_on": "2026-02-01", "action": "updated", "object_type": "proxy-host",
                 "object_id": 1, "user": {"name": "Mogie"}, "meta": {}}])
        self._send(404, {"error": {"message": "nope"}})


passed = failed = 0


def check(name, cond, extra=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"ok   {name}")
    else:
        failed += 1
        print(f"FAIL {name} {extra}")


def main():
    srv = HTTPServer(("127.0.0.1", 0), Fake)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    for k in ("NPM_URL", "NPM_EMAIL", "NPM_PASSWORD"):
        os.environ.pop(k, None)

    # classification
    check("classify GET read", s.classify("GET", "/api/nginx/proxy-hosts") == "read")
    check("classify POST change", s.classify("POST", "/api/nginx/proxy-hosts") == "change")
    check("classify DELETE destructive", s.classify("DELETE", "/api/nginx/proxy-hosts/1") == "destructive")
    check("classify users PUT destructive", s.classify("PUT", "/api/users/1") == "destructive")
    check("classify settings PUT destructive", s.classify("PUT", "/api/settings/x") == "destructive")

    # no config
    r = s.npm_status()
    check("missing env gives clear error", r["ok"] is False and "NPM_URL" in r["error"], r)

    os.environ["NPM_URL"] = f"http://127.0.0.1:{srv.server_port}"
    os.environ["NPM_EMAIL"] = "me@x.io"
    os.environ["NPM_PASSWORD"] = "wrong"
    r = s.npm_status()
    check("bad login fails clearly", r["ok"] is False and "login failed" in r["error"], r)
    check("bad password not echoed", "wrong" not in json.dumps(r), r)

    os.environ["NPM_PASSWORD"] = PASSWORD
    s._state.update(token=None, exp=0.0)
    r = s.npm_status()
    check("status ok", r["ok"] and r["server"]["status"] == "OK", r)
    check("status counts", r["counts"]["proxy"] == 0, r)

    # create needs confirm
    body = {"domain_names": ["a.example.com"], "forward_host": "192.168.1.5", "forward_port": 8080}
    r = s.npm_hosts("proxy-hosts", "create", data=body)
    check("create without confirm asks", r.get("needs_confirm") is True, r)
    check("create preview has defaults", r["preview"]["block_exploits"] is True, r)
    check("nothing created yet", len(DB["hosts"]) == 0)
    r = s.npm_hosts("proxy-hosts", "create", data=body, confirm=True)
    check("create with confirm works", r["ok"] and r["data"]["id"] == 1, r)

    r = s.npm_hosts("proxy-hosts", "create", data={"domain_names": ["b"], "forward_host": "h"}, confirm=True)
    check("create missing field rejected", r["ok"] is False and "forward_port" in r["error"], r)
    r = s.npm_hosts("proxy-hosts", "create", data={**body, "owner": 1}, confirm=True)
    check("create unknown field rejected", r["ok"] is False and "Unknown" in r["error"], r)

    # list summary
    r = s.npm_hosts("proxy-hosts")
    check("list summary is short", r["ok"] and "created_on" not in r["data"][0], r)
    r = s.npm_hosts("proxy-hosts", full=True)
    check("list full has all", "created_on" in r["data"][0], r)
    r = s.npm_hosts("proxy-hosts", "get", id=1)
    check("get works", r["ok"] and r["data"]["forward_port"] == 8080, r)
    r = s.npm_hosts("proxy-hosts", "get", id=99)
    check("get missing gives 404", r["ok"] is False and r["status"] == 404, r)

    # update merges and strips read-only fields
    r = s.npm_hosts("proxy-hosts", "update", id=1, data={"forward_port": 9090})
    check("update asks first", r.get("needs_confirm") and r["preview"]["changes"]["forward_port"]["to"] == 9090, r)
    r = s.npm_hosts("proxy-hosts", "update", id=1, data={"forward_port": 9090}, confirm=True)
    check("update works (read-only fields stripped)", r["ok"] and DB["hosts"][1]["forward_port"] == 9090, r)
    check("update kept other fields", DB["hosts"][1]["forward_host"] == "192.168.1.5")

    # enable / disable
    r = s.npm_hosts("proxy-hosts", "disable", id=1)
    check("disable asks first", r.get("needs_confirm"), r)
    s.npm_hosts("proxy-hosts", "disable", id=1, confirm=True)
    check("disable works", DB["hosts"][1]["enabled"] is False)
    s.npm_hosts("proxy-hosts", "enable", id=1, confirm=True)
    check("enable works", DB["hosts"][1]["enabled"] is True)

    # delete
    r = s.npm_hosts("proxy-hosts", "delete", id=1)
    check("delete asks first", r.get("needs_confirm") and "delete proxy-hosts 1" in r["message"], r)
    r = s.npm_hosts("proxy-hosts", "delete", id=1, confirm=True)
    check("delete needs phrase", r.get("needs_confirm") and 1 in DB["hosts"], r)
    r = s.npm_hosts("proxy-hosts", "delete", id=1, confirm=True, confirm_phrase="nope")
    check("delete wrong phrase refused", r.get("needs_confirm") and 1 in DB["hosts"], r)
    r = s.npm_hosts("proxy-hosts", "delete", id=1, confirm=True, confirm_phrase="delete proxy-hosts 1")
    check("delete with phrase works", r["ok"] and 1 not in DB["hosts"], r)

    # bad kind / action
    check("bad kind", s.npm_hosts("nope")["ok"] is False)
    check("bad action", s.npm_hosts("proxy-hosts", "explode")["ok"] is False)
    r = s.npm_hosts("certificates", "create", data={"a": 1}, confirm=True)
    check("certificates create points to npm_call", r["ok"] is False and "npm_call" in r["error"], r)

    # npm_call
    r = s.npm_call("GET", "/api/nginx/proxy-hosts")
    check("npm_call GET runs", r["ok"] and r["tier"] == "read", r)
    r = s.npm_call("DELETE", "/api/nginx/proxy-hosts/5")
    check("npm_call DELETE asks", r.get("needs_confirm") and "DELETE /api/nginx/proxy-hosts/5" in r["message"], r)
    r = s.npm_call("GET", "/api/tokens")
    check("npm_call blocks tokens", r["ok"] is False and "blocked" in r["error"], r)
    r = s.npm_call("GET", "https://evil.example/api/x")
    check("npm_call blocks other hosts", r["ok"] is False, r)
    r = s.npm_call("GET", "/api/../etc")
    check("npm_call blocks ..", r["ok"] is False, r)
    r = s.npm_call("TRACE", "/api/x")
    check("npm_call bad method", r["ok"] is False, r)

    # audit log
    r = s.npm_audit_log(limit=1)
    check("audit log newest first", r["ok"] and r["data"][0]["action"] == "updated" and len(r["data"]) == 1, r)

    # token expiry: server says 401 once, tool logs in again
    before = DB["logins"]
    DB["expire_next"] = True
    r = s.npm_hosts("proxy-hosts")
    check("re-login after 401", r["ok"] and DB["logins"] == before + 1, r)

    # secrets never leak
    text = json.dumps([s.npm_status(), s.npm_hosts("proxy-hosts", full=True)])
    check("password never in output", PASSWORD not in text)
    check("token never in output", "tok-" not in text)

    # unreachable server
    os.environ["NPM_URL"] = "http://127.0.0.1:1"
    r = s.npm_status()
    check("unreachable gives clear error", r["ok"] is False and "Cannot reach" in r["error"], r)

    print(f"\n{passed} passed, {failed} failed")
    srv.shutdown()
    sys.exit(1 if failed else 0)


main()
