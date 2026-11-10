pass
import json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import mpaths   

html_p, label = sys.argv[1], sys.argv[2]
s = open(html_p, encoding="utf-8").read()
out_dir = mpaths.mkdir(os.path.join(mpaths.TMP, "escheck"))


PATTERNS = {
    "regex lookbehind (?<= / (?<! [iOS 16.4]": r"\(\?<[=!]",
    "logical assignment ??= ||= &&= [iOS 14]": r"\?\?=|\|\|=|&&=",
    "Array/String .at( [iOS 15.4]": r"\.at\(",
    "structuredClone [iOS 15.4]": r"\bstructuredClone\b",
    "replaceAll [iOS 13.4]": r"\.replaceAll\(",
    "findLast [iOS 15.4]": r"\.findLast(Index)?\(",
    "Object.hasOwn [iOS 15.4]": r"\bObject\.hasOwn\(",
    "private #field (this.#x) [iOS 14.5]": r"\bthis\.#[A-Za-z_$]",
    "class static block [iOS 16.4]": r"\bstatic\s*\{",
    "numeric separator 1_000 [iOS 13]": r"\b\d+_\d+\b",
    "top-level await / import.meta": r"\bimport\.meta\b",
    
    "optional chaining ?. (ES2020, iOS 13.4)": r"\?\.(?![0-9])",
    "nullish ?? (ES2020, iOS 13.4)": r"\?\?(?!=)",
}
INFO_ONLY = {k for k in PATTERNS if "ES2020" in k}

res = {"file": os.path.relpath(html_p, mpaths.OUT_ROOT), "scripts": [], "blocking": 0}
n = 0
for m in re.finditer(r"<script([^>]*)>(.*?)</script>", s, re.S):
    attrs, body = m.group(1), m.group(2)
    if "application/json" in attrs:
        continue
    n += 1
    name = f"{label}_script{n}.js"
    open(mpaths.writable(os.path.join(out_dir, name)), "w", encoding="utf-8").write(body)
    
    hits = {}
    for k, pat in PATTERNS.items():
        c = len(re.findall(pat, body))
        if c:
            hits[k] = c
    kind = ("error net" if "showBootError" in body and "function showBootError" in body and len(body) < 3000 else
            "d3 v7.9.0" if "d3js.org" in body[:400] else
            "topojson-client" if "topojson" in body[:400] and len(body) < 20000 else
            "head flag" if len(body) < 400 else "app")
    blocking = {k: v for k, v in hits.items() if k not in INFO_ONLY}
    res["blocking"] += sum(blocking.values())
    res["scripts"].append({"n": n, "kind": kind, "bytes": len(body), "hits": hits, "blocking": blocking})
json.dump(res, open(mpaths.writable(os.path.join(mpaths.BUILD, f"static_{label}.json")), "w"), indent=1)
for sc in res["scripts"]:
    print(f"script {sc['n']} ({sc['kind']}, {sc['bytes']} B): {sc['hits'] or 'no flagged syntax'}")
print("BLOCKING HITS:", res["blocking"])
