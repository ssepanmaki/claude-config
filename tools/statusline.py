import json
import sys

try:
    d = json.load(sys.stdin)
except ValueError:
    d = {}
model = (d.get("model") or {}).get("display_name") or "?"
pct = (d.get("context_window") or {}).get("used_percentage")
cost = (d.get("cost") or {}).get("total_cost_usd")
ctx = f"{pct:.0f}%" if isinstance(pct, (int, float)) else "--"
usd = f"${cost:.2f}" if isinstance(cost, (int, float)) else "--"
print(f"{model} | ctx {ctx} | {usd}")
