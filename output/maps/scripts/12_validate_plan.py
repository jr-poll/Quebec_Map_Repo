pass
import itertools, json, math, os, sys
import yaml
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import mapdata as M   
from mapstyle import MAP_X, MAP_Y, MAP_W, MAP_H, EMU_PER_IN, MODES   

PLAN = os.path.join(M.MAPS, "plan")
frames = json.load(open(os.path.join(PLAN, "frames_plan.json")))["frames"]
cfg = yaml.safe_load(open(os.path.join(PLAN, "frames_config.yaml"), encoding="utf-8"))
byid = {f["id"]: f for f in frames}
M_RID, M_CLU = 36576 + 36000, 36576 + 60000
errors, rows = [], []


def to_slide(f, x, y):
    x0, y0, x1, y1 = f["extent"]
    return MAP_X + (x - x0) / f["mpe"], MAP_Y + (y1 - y) / f["mpe"]


def fits(f, x, y, offs, margin):
    X, Y = to_slide(f, x, y)
    for m in MODES:
        o = offs[m]
        for dx, dy in ([(0, 0)] if o is None else o):
            if not (MAP_X + margin <= X + dx <= MAP_X + MAP_W - margin and MAP_Y + margin <= Y + dy <= MAP_Y + MAP_H - margin):
                return False
    return True


def shown_individually(fid):
    pass
    f = byid[fid]
    s = {i["code"] for i in f["individuals"]}
    for c in f["clusters"]:
        s |= shown_individually(c["child"]) if c["child"] != fid else set()
    return s


for f in frames:
    assert f["id"] in cfg["frames"], f"frame {f['id']} has no name in frames_config.yaml"
    mem = set(f["members"])
    ind_m = [i["code"] for i in f["individuals"] if not i["context"]]
    clu_m = [c for cl in f["clusters"] for c in cl["members"]]
    
    allrep = ind_m + clu_m
    if sorted(allrep) != sorted(mem):
        errors.append(f"{f['id']}: (a) members represented {len(allrep)} times for {len(mem)} members")
    ctx = [i["code"] for i in f["individuals"] if i["context"]]
    if set(ctx) & mem:
        errors.append(f"{f['id']}: context overlaps members")
    
    pts = [to_slide(f, i["x"], i["y"]) for i in f["individuals"]] + [to_slide(f, c["x"], c["y"]) for c in f["clusters"]]
    dmin = min((math.dist(p, q) for p, q in itertools.combinations(pts, 2)), default=float("inf"))
    if dmin < f["s_min_emu"] - 1:
        errors.append(f"{f['id']}: (b) min spacing {dmin:.0f} < {f['s_min_emu']}")
    
    for i in f["individuals"]:
        if not fits(f, i["x"], i["y"], M.offsets("riding", i["code"]), M_RID):
            errors.append(f"{f['id']}: (c) arrow of {M.NAME[i['code']]} leaves the map box")
    for c in f["clusters"]:
        if not fits(f, c["x"], c["y"], M.offsets("cluster", c["members"]), M_CLU):
            errors.append(f"{f['id']}: (c) cluster {c['id']} arrow leaves the map box")
    
    for c in f["clusters"]:
        if c["child"] not in byid:
            errors.append(f"{f['id']}: (d) cluster {c['id']} has no child frame")
            continue
        miss = set(c["members"]) - shown_individually(c["child"])
        if miss:
            errors.append(f"{f['id']}: (d) child {c['child']} misses {[M.NAME[m] for m in miss]}")
        if not set(c["members"]) <= set(byid[c["child"]]["members"]):
            errors.append(f"{f['id']}: (d) child {c['child']} members do not include cluster {c['id']}")
    
    rows.append((f, dmin))


import geopandas as gpd, shapely   
land = gpd.read_file(os.path.join(M.GEO, "ridings_land.gpkg"), layer="ridings").set_index("code").geometry
cov = set()
for f in frames:
    for i in f["individuals"]:
        cov.add(i["code"])
        if not land[i["code"]].contains(shapely.Point(i["x"], i["y"])):
            errors.append(f"{f['id']}: anchor of {M.NAME[i['code']]} outside its land")
if cov != set(M.CODES):
    errors.append(f"(e) never shown individually: {[M.NAME[c] for c in set(M.CODES) - cov]}")


NF = len(frames)
order = [f["id"] for f in frames]          
slide_of = {fid: 3 + j for j, fid in enumerate(order)}   

name = lambda fid: cfg["frames"][fid]["name"]
md = ["# Frame plan", "", f"{NF} frames per set; 6 sets (WINNER, PQ, PLQ, CAQ, QS, PCQ) → {1 + 6 * (NF + 1)} slides "
      "(1 index + 6 × (divider + frames)).", "",
      "Slide numbers are given for the WINNER set; add k × " + str(NF + 1) + " for set k (PQ = 1, PLQ = 2, CAQ = 3, "
      "QS = 4, PCQ = 5).", "", "## Tree", ""]
for f in frames:
    md.append(f"{'  ' * f['depth']}- **{name(f['id'])}** (`{f['id']}`, slide {slide_of[f['id']]}) – "
              f"{len(f['members'])} ridings, {f['km_per_in']:.1f} km/in")
md += ["", "## Frames", "", "| Slide | Frame | Name | Scale (km/in) | Members | Individual (members + context) | Clusters | "
       "Min spacing (in) | Nudged anchors |", "|---|---|---|---|---|---|---|---|---|"]
for f, dmin in rows:
    nm = sum(not i["context"] for i in f["individuals"])
    nc = sum(i["context"] for i in f["individuals"])
    nud = ", ".join(M.NAME[i["code"]] for i in f["individuals"] if i["nudged"]) or "–"
    cl = "; ".join(f"{c['id']}→{c['child']} ({len(c['members'])})" for c in f["clusters"]) or "–"
    md.append(f"| {slide_of[f['id']]} | `{f['id']}` | {name(f['id'])} | {f['km_per_in']:.1f} | {len(f['members'])} | "
              f"{nm} + {nc} | {cl} | {dmin / EMU_PER_IN:.3f} | {nud} |")
md += ["", "## Validator", "", "Checks (a) each member exactly once, (b) min spacing ≥ S_MIN, (c) all arrows of all 6 modes inside "
       "the map box with margin, (d) every cluster has a breakout showing all members, (e) all 127 ridings shown "
       "individually somewhere, plus every anchor inside its riding's land.", "",
       ("**PASS**" if not errors else "**FAIL**\n\n" + "\n".join("- " + e for e in errors)), ""]
for f in frames:
    if f["log"]:
        md.append(f"- `{f['id']}` planner log: " + "; ".join(f["log"]))
open(os.path.join(PLAN, "frames_plan.md"), "w", encoding="utf-8").write("\n".join(md) + "\n")
print("\n".join(md))
if errors:
    sys.exit("PLAN VALIDATION FAILED")
print("PLAN OK")
