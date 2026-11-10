pass
import hashlib, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import mpaths   

ROOT = mpaths.OUT_ROOT
before = {}
for ln in open(os.path.join(mpaths.MOBILE, "manifest_before.txt"), encoding="utf-8"):
    h, p = ln.rstrip("\n").split("  ", 1)
    before[p] = h
after = {}
for d, dirs, files in os.walk(ROOT):
    if d == ROOT:
        dirs[:] = [x for x in dirs if x != ".venv"]
    for f in files:
        full = os.path.join(d, f)
        rel = "./" + os.path.relpath(full, ROOT)
        if os.path.islink(full) or not os.path.isfile(full):
            continue
        hh = hashlib.sha256()
        with open(full, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                hh.update(chunk)
        after[rel] = hh.hexdigest()
allowed = lambda p: p.startswith("./maps/mobile/") or p == "./maps/Quebec_2026_Swing_Map_FINAL_mobile.html"
added = sorted(set(after) - set(before))
removed = sorted(set(before) - set(after))
modified_all = sorted(p for p in set(before) & set(after) if before[p] != after[p])


OS_META = lambda p: os.path.basename(p) == ".DS_Store"
os_meta_changed = [p for p in modified_all if OS_META(p)]
modified = [p for p in modified_all if not OS_META(p)]
bad_add = [p for p in added if not allowed(p)]
lines = [f"{after[p]}  {p}" for p in sorted(after)]
open(mpaths.writable(os.path.join(mpaths.MOBILE, "manifest_after.txt")), "w", encoding="utf-8").write("\n".join(lines) + "\n")
res = {"before": len(before), "after": len(after), "added": len(added), "added_disallowed": bad_add,
       "removed": removed, "modified": modified, "os_metadata_changed": os_meta_changed,
       "added_outside_mobile": [p for p in added if not p.startswith("./maps/mobile/")]}
json.dump(res, open(mpaths.writable(os.path.join(mpaths.BUILD, "manifest_diff.json")), "w"), indent=1)
print(json.dumps(res, indent=1))
ok = not bad_add and not removed and not modified
print("MANIFEST:", ("OK (originals untouched" + (f"; macOS Finder metadata changed: {os_meta_changed}" if os_meta_changed else "") + ")")
      if ok else "FAIL")
sys.exit(0 if ok else 1)
