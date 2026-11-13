"""Compare two setup-audit baselines: tool error rates and session intent met-rate.
Usage: python3 audit_compare.py <old baseline dir> <new baseline dir>
Each dir holds snapshot.json (collector output) and sessions/*.json (session-intent-audit rows)."""
import json, sys, glob, collections

def load(d):
    t = json.load(open(f"{d}/snapshot.json"))["transcripts"]
    tools = {r["tool"]: r for r in t["tool_errors"]["by_tool"]}
    rows = [json.load(open(f)) for f in glob.glob(f"{d}/sessions/*.json") if "/wf-" not in f]
    return t, tools, rows

(ot, otools, orows), (nt, ntools, nrows) = load(sys.argv[1]), load(sys.argv[2])
print(f"sessions {ot['sessions_measured']} -> {nt['sessions_measured']}; baseline ctx median {ot['context_baseline_tokens']['median']:.0f} -> {nt['context_baseline_tokens']['median']:.0f}")
for name in sorted(set(otools) | set(ntools)):
    o, n = otools.get(name, {}), ntools.get(name, {})
    print(f"{name:18} fail {o.get('failure_rate') or 0:.3f} -> {n.get('failure_rate') or 0:.3f}  cats {o.get('categories', {})} -> {n.get('categories', {})}")
for label, rows in (("old", orows), ("new", nrows)):
    c = collections.Counter(r["outcome"] for r in rows)
    print(f"{label} intent: {len(rows)} sessions, met {c['met']} ({c['met'] / max(len(rows), 1):.0%}), partial {c['partial']}, unmet {c['unmet']}; causes {collections.Counter(r['cause'] for r in rows).most_common(5)}")
