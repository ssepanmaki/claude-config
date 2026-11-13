#!/usr/bin/env python3
"""list-sessions: print title + claude.ai/code link for your Claude Code sessions.

Usage: list-sessions.py [--limit N] [--match TEXT] [--json]
Auth: $CLAUDE_CODE_OAUTH_TOKEN (claude setup-token) or ~/.claude/.credentials.json.
Optional: $CLAUDE_ORG_UUID if the API asks for an org. Stdlib only.
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request


def token():
    t = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN")
    if t:
        return t
    p = os.path.join(os.environ.get("CLAUDE_CONFIG_DIR", os.path.expanduser("~/.claude")), ".credentials.json")
    try:
        return json.load(open(p))["claudeAiOauth"]["accessToken"]
    except (OSError, KeyError, ValueError):
        sys.exit("no token: set CLAUDE_CODE_OAUTH_TOKEN or log in with `claude`")


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--limit", type=int, default=100)
    a.add_argument("--match", default="")
    a.add_argument("--json", action="store_true")
    a = a.parse_args()
    h = {"Authorization": "Bearer " + token(), "anthropic-version": "2023-06-01",
         "anthropic-beta": "ccr-byoc-2025-07-29,oauth-2025-04-20"}
    if os.environ.get("CLAUDE_ORG_UUID"):
        h["x-organization-uuid"] = os.environ["CLAUDE_ORG_UUID"]
    rows, after = [], None
    while len(rows) < a.limit:
        url = "https://api.anthropic.com/v1/sessions?beta=true" + (f"&after_id={after}" if after else "")
        try:
            d = json.load(urllib.request.urlopen(urllib.request.Request(url, headers=h)))
        except urllib.error.HTTPError as e:
            sys.exit(f"HTTP {e.code}: {e.read()[:300].decode(errors='replace')}")
        rows += d.get("data", [])
        if not d.get("has_more") or not d.get("data"):
            break
        after = d.get("last_id") or d["data"][-1]["id"]
    rows = [r for r in rows if a.match.lower() in (r.get("title") or "").lower()][: a.limit]
    for r in rows:
        sid = r["id"].replace("cse_", "session_", 1)
        url = f"https://claude.ai/code/{sid}"
        if a.json:
            print(json.dumps({"id": sid, "title": r.get("title"), "url": url}))
        else:
            print(f"{(r.get('updated_at') or '')[:16]}  {r.get('title') or '(untitled)':40.40}  {url}")


if __name__ == "__main__":
    main()
