pass
import json, re, hashlib, difflib, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import paths

def html_parts(path):
    h = open(path, encoding="utf-8").read()
    data = json.loads(re.search(r'<script id="mapdata" type="application/json">(.*?)</script>', h, re.S).group(1)
                      .replace("<\\/", "</"))
    topo = re.search(r'<script id="topo" type="application/json">(.*?)</script>', h, re.S).group(1)
    title = re.search(r"<title>(.*?)</title>", h, re.S).group(1)
    tpl = re.sub(r'(<script id="topo" type="application/json">).*?(</script>)', r"\1__TOPO__\2", h, flags=re.S)
    tpl = re.sub(r'(<script id="mapdata" type="application/json">).*?(</script>)', r"\1__DATA__\2", tpl, flags=re.S)
    
    blocks = list(re.finditer(r"<script>(.*?)</script>", tpl, re.S))
    libs = blocks[:2]
    for m, tag in zip(reversed(libs), ("/*__TOPOJSON__*/", "/*__D3__*/")):
        tpl = tpl[:m.start(1)] + tag + tpl[m.end(1):]
    lib_sha = [hashlib.sha1(m.group(1).encode()).hexdigest() for m in libs]
    return {"data": data, "topo_sha1": hashlib.sha1(topo.encode()).hexdigest(), "title": title, "template": tpl,
            "lib_sha1": lib_sha, "size": os.path.getsize(path)}


def json_diff(a, b, path=""):
    out = []
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b), key=str):
            p = f"{path}.{k}" if path else str(k)
            if k not in a:
                out.append({"path": p, "kind": "added", "b": b[k]})
            elif k not in b:
                out.append({"path": p, "kind": "removed", "a": a[k]})
            else:
                out += json_diff(a[k], b[k], p)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            out.append({"path": path, "kind": "length", "a": len(a), "b": len(b)})
        for i, (x, y) in enumerate(zip(a, b)):
            out += json_diff(x, y, f"{path}[{i}]")
    elif a != b or type(a) is not type(b):
        out.append({"path": path, "kind": "changed", "a": a, "b": b})
    return out


def compare_html(pa, pb):
    A_, B_ = html_parts(pa), html_parts(pb)
    res = {"title": None if A_["title"] == B_["title"] else [A_["title"], B_["title"]],
           "topo_equal": A_["topo_sha1"] == B_["topo_sha1"], "libs_equal": A_["lib_sha1"] == B_["lib_sha1"],
           "payload": json_diff(A_["data"], B_["data"]),
           "template": list(difflib.unified_diff(A_["template"].splitlines(), B_["template"].splitlines(),
                                                 "A", "B", n=0, lineterm="")),
           "size": [A_["size"], B_["size"]]}
    return res


def main():
    args = sys.argv[1:]
    out = None
    if "--json" in args:
        i = args.index("--json")
        out = args[i + 1]
        del args[i:i + 2]
    pa, pb = args
    result = compare_html(pa, pb)
    print(json.dumps({k: v for k, v in result.items() if k != "template"}, ensure_ascii=False))
    if out:
        with open(paths.writable(out), "w", encoding="utf-8") as fh:
            json.dump(result, fh, ensure_ascii=False, indent=1)

if __name__ == "__main__":
    main()
