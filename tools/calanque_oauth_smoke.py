"""End-to-end MCP OAuth smoke test against a Calanque dev server (DEV_LOGIN=1).

Usage: python -I calanque_oauth_smoke.py [base_url]
"""
import base64
import hashlib
import html
import http.cookiejar
import json
import re
import secrets
import sys
import urllib.parse
import urllib.request

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5173").rstrip("/")
REDIRECT = "http://127.0.0.1:9999/callback"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


class LocalhostPolicy(http.cookiejar.DefaultCookiePolicy):
    """Browsers send Secure cookies to http://localhost; urllib does not."""

    def return_ok_secure(self, cookie, request):
        return True


jar = http.cookiejar.CookieJar(LocalhostPolicy())
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar), NoRedirect)


def req(method, path, body=None, headers=None):
    url = path if path.startswith("http") else BASE + path
    r = urllib.request.Request(url, data=body, method=method, headers=headers or {})
    try:
        resp = opener.open(r)
    except urllib.error.HTTPError as e:
        resp = e
    return resp.status, dict(resp.headers), resp.read().decode()


def step(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + (f"  {detail}" if detail else ""))
    if not ok:
        sys.exit(1)


s, h, _ = req("POST", "/mcp", b"{}", {"content-type": "application/json"})
step("unauthenticated /mcp is 401 with challenge", s == 401 and "resource_metadata" in h.get("WWW-Authenticate", h.get("www-authenticate", "")))

s, _, b = req("GET", "/.well-known/oauth-protected-resource/mcp")
prm = json.loads(b)
step("protected resource metadata", s == 200, prm.get("resource"))

s, _, b = req("GET", "/.well-known/oauth-authorization-server")
asm = json.loads(b)
step("authorization server metadata", s == 200 and "registration_endpoint" in asm)

s, _, b = req("POST", asm["registration_endpoint"], json.dumps({"client_name": "Smoke <b>test</b>", "redirect_uris": [REDIRECT], "token_endpoint_auth_method": "none"}).encode(), {"content-type": "application/json"})
client = json.loads(b)
step("dynamic client registration", s == 201, client.get("client_id", b)[:40])

verifier = secrets.token_urlsafe(48)
challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
query = urllib.parse.urlencode({
    "response_type": "code", "client_id": client["client_id"], "redirect_uri": REDIRECT, "scope": "calanque offline_access",
    "state": "st4te", "code_challenge": challenge, "code_challenge_method": "S256", "resource": prm["resource"],
})
s, h, _ = req("GET", "/authorize?" + query)
step("signed-out /authorize sends to sign-in", s == 302 and h.get("Location", h.get("location")) == "/")

s, h, _ = req("GET", "/auth/dev")
back = h.get("Location", h.get("location", ""))
step("sign-in returns to consent", s == 302 and back.startswith("/authorize?"), back[:60])

s, h, page = req("GET", back)
handle = re.search(r'name="handle" value="([^"]+)"', page)
step("consent page shows escaped client name", s == 200 and handle and "Smoke &#60;b&#62;test" in page and "<b>test</b>" not in page)
step("consent page cannot be framed", "frame-ancestors" in str(h).lower() or "x-frame-options" in str(h).lower())

form = urllib.parse.urlencode({"handle": html.unescape(handle.group(1)), "decision": "approve"}).encode()
s, h, _ = req("POST", "/authorize", form, {"content-type": "application/x-www-form-urlencoded", "origin": BASE})
loc = urllib.parse.urlparse(h.get("Location", h.get("location", "")))
params = urllib.parse.parse_qs(loc.query)
step("approve redirects to client with code", s == 302 and loc.netloc == "127.0.0.1:9999" and params.get("state") == ["st4te"] and "code" in params)

tok_body = urllib.parse.urlencode({
    "grant_type": "authorization_code", "code": params["code"][0], "redirect_uri": REDIRECT, "client_id": client["client_id"],
    "code_verifier": verifier, "resource": prm["resource"],
}).encode()
s, _, b = req("POST", asm["token_endpoint"], tok_body, {"content-type": "application/x-www-form-urlencoded"})
tokens = json.loads(b)
step("code exchanges for tokens", s == 200 and "access_token" in tokens and "refresh_token" in tokens, tokens.get("scope", ""))

auth = {"authorization": "Bearer " + tokens["access_token"], "content-type": "application/json", "accept": "application/json, text/event-stream"}


def rpc(method, params=None, id_=1):
    s, _, b = req("POST", "/mcp", json.dumps({"jsonrpc": "2.0", "id": id_, "method": method, "params": params or {}}).encode(), auth)
    return s, json.loads(b) if b else None


s, r = rpc("initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "smoke", "version": "0"}})
step("initialize with OAuth token", s == 200 and r["result"]["serverInfo"]["name"] == "calanque")
s, r = rpc("tools/call", {"name": "list_areas", "arguments": {}})
step("tools/call list_areas", s == 200 and not r["result"].get("isError"), f"{len(r['result']['structuredContent']['areas'])} areas")

s, _, b = req("POST", asm["token_endpoint"], urllib.parse.urlencode({"grant_type": "refresh_token", "refresh_token": tokens["refresh_token"], "client_id": client["client_id"]}).encode(), {"content-type": "application/x-www-form-urlencoded"})
step("refresh token works", s == 200 and "access_token" in json.loads(b))

auth["authorization"] = "Bearer wrong"
s, _ = rpc("ping")
step("bad token rejected", s == 401)
print("all passed")
