pass
import hashlib, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import mpaths   

new = open(mpaths.MOBILE_HTML, encoding="utf-8").read()
old = open(mpaths.FINAL_HTML, encoding="utf-8").read()
res, bad = {}, []
for sid in ("mapdata", "topo"):
    pat = r'<script id="%s" type="application/json">(.*?)</script>' % sid
    a, b = re.findall(pat, new, re.S), re.findall(pat, old, re.S)
    same = len(a) == len(b) == 1 and a[0] == b[0]
    res[sid] = {"identical": same, "bytes": len(b[0].encode()) if b else None,
                "sha256": hashlib.sha256(a[0].encode()).hexdigest() if a else None}
    if not same:
        bad.append(f"{sid} differs")
for w in ("notional", "own calculation"):
    n = len(re.findall(w, new, re.I))
    res[f"count:{w}"] = n
    if n:
        bad.append(f"{n} matches for {w!r}")
sub = "Change in winner’s vote share 2022 → 2026"
res["subtitle_in_fallback_and_js"] = new.count(sub)
if new.count(sub) < 2:
    bad.append("WINNER subtitle missing from the fallback or the app")
res["bytes"] = {"final": len(old.encode()), "mobile": len(new.encode())}
res["failures"] = bad
json.dump(res, open(mpaths.writable(os.path.join(mpaths.BUILD, "parity.json")), "w"), ensure_ascii=False, indent=1)
print(json.dumps(res, ensure_ascii=False, indent=1))
sys.exit(1 if bad else 0)
