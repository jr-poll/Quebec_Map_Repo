pass
import json, math, os, subprocess, sys
import geopandas as gpd
import shapely
import yaml
from pyproj import Transformer

HERE = os.path.dirname(os.path.abspath(__file__))   
FINAL = os.path.dirname(HERE)
sys.path.insert(0, FINAL)
import paths   
from mapstyle import (PARTIES, MODES, COL, NAME, HEADING, LOSS_COL, ARROW_ALPHA, EMU_PER_POINT, MIN_ARROW_EMU,   
                      DOT_BELOW, ACCENT, INK, SHADE, SHADE_LABEL)
import mapdata as M   
import colour_check   
import mapstyle as _MS   
assert _MS.__file__.startswith(FINAL + os.sep) and M.__file__.startswith(FINAL + os.sep)

SIMPLIFY = os.environ.get("QC_SIMPLIFY", "8%")
SEP_PX = 26
TMP = os.path.join(paths.TMP, "html_geo")
os.makedirs(paths.writable(os.path.join(TMP, "x")).rsplit(os.sep, 1)[0], exist_ok=True)
OUT = paths.HTML_OUT
MAPSHAPER = paths.MAPSHAPER
to_ll = Transformer.from_crs(M.EPSG, 4326, always_xy=True)


gw = os.path.join(M.GEO, "ridings_land_wgs84.gpkg")
rid = gpd.read_file(gw, layer="ridings")[["code", "region", "geometry"]]
rid["code"] = rid.code.astype(int)
nei = gpd.read_file(gw, layer="neighbours")
clipbox = shapely.box(-83.5, 40.5, -52.0, 63.8)
nei = gpd.GeoDataFrame(geometry=nei.geometry.intersection(clipbox), crs=4326)
nei = nei[~nei.is_empty]
rid.to_file(paths.writable(os.path.join(TMP, "ridings.geojson")), driver="GeoJSON", COORDINATE_PRECISION=6)
nei.to_file(paths.writable(os.path.join(TMP, "neighbours.geojson")), driver="GeoJSON", COORDINATE_PRECISION=5)
topo_p = paths.writable(os.path.join(TMP, "qc.topojson"))
cmd = [MAPSHAPER, "-i", os.path.join(TMP, "ridings.geojson"), os.path.join(TMP, "neighbours.geojson"),
       "combine-files", "-simplify", SIMPLIFY, "keep-shapes", "-o", "format=topojson", "quantization=100000",
       topo_p]
subprocess.run(cmd, check=True, capture_output=True)
topo = json.load(open(topo_p))
assert set(topo["objects"]) == {"ridings", "neighbours"}, topo["objects"].keys()
assert len(topo["objects"]["ridings"]["geometries"]) == 127


plan = json.load(open(os.path.join(paths.PLAN, "frames_plan.json")))["frames"]
cfg = yaml.safe_load(open(os.path.join(paths.PLAN, "frames_config.yaml"), encoding="utf-8"))
anc = M.pd.read_csv(os.path.join(M.GEO, "anchors.csv")).set_index("code")


def ll(x, y):
    lon, lat = to_ll.transform(x, y)
    return [round(lon, 6), round(lat, 6)]


sw = M.sw
ridings = []
for c in M.CODES:
    r = sw.loc[c]
    ridings.append({
        "code": int(c), "name": M.NAME[c], "region": r.region, "ll": [float(anc.loc[c, "lon"]), float(anc.loc[c, "lat"])],
        "winner": r.winner_2026, "cand": str(M.r26.loc[c, "winner_candidate"]), "w22": r.winner_2022_notional,
        "flip": bool(r.flip), "status": r.boundary_status,
        "base22": bool(r.notional_baseline_flag),
        "seat": {p: M.seat_cat(c, p) for p in PARTIES},
        "noCand": {p: (not bool(r[p + "_ran_2022"])) or (not bool(r[p + "_ran_2026"])) for p in PARTIES},
        "p22": {p: float(r[p + "_2022"]) for p in PARTIES},
        "p26": {p: float(r[p + "_2026"]) for p in PARTIES},
        "sw": {p: float(r[p + "_swing"]) for p in PARTIES},
    })

frames, clusters = [], []
for f in plan:
    x0, y0, x1, y1 = f["extent"]
    corners = [ll(x, y) for x, y in [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]]
    lons, lats = [p[0] for p in corners], [p[1] for p in corners]
    frames.append({
        "id": f["id"], "parent": f["parent"], "name": cfg["frames"][f["id"]]["name"],
        "short": cfg["frames"][f["id"]]["short"], "members": f["members"], "km_per_in": f["km_per_in"],
        "bbox": [[min(lons), min(lats)], [max(lons), max(lats)]],
        "ind": [{"code": i["code"], "ll": ll(i["x"], i["y"]), "xy": [i["x"], i["y"]]}
                for i in f["individuals"] if not i["context"]],
        "clusters": [c["id"] for c in f["clusters"]],
    })
    for c in f["clusters"]:
        a = M.agg(c["members"])
        clusters.append({
            "id": c["id"], "frame": f["id"], "child": c["child"], "members": c["members"], "ll": ll(c["x"], c["y"]),
            "xy": [c["x"], c["y"]], "name": cfg["frames"][c["child"]]["short"],
            "share22": a["share_2022"], "share26": a["share_2026"], "swing": a["swing"], "seats": a["seats"],
            "top": a["top_party"], "n": a["n"],
        })
FRM = {f["id"]: f for f in frames}
CLU = {c["id"]: c for c in clusters}


def expand(cid):
    pass
    c = CLU[cid]
    ch = FRM[c["child"]]
    mem = set(c["members"])
    out = [("r", i["code"], i["xy"]) for i in ch["ind"] if i["code"] in mem]
    out += [("c", k, CLU[k]["xy"]) for k in ch["clusters"] if set(CLU[k]["members"]) & mem]
    return out


def parent_items(cid):
    f = FRM[CLU[cid]["frame"]]
    return [("r", i["code"], i["xy"]) for i in f["ind"]] + \
           [("c", k, CLU[k]["xy"]) for k in f["clusters"] if k != cid]



for c in clusters:
    ex = expand(c["id"])
    pts = [p for *_, p in ex]
    others = [p for *_, p in parent_items(c["id"])]
    d = [(math.dist(pts[i], pts[j]), pts[i], pts[j]) for i in range(len(pts)) for j in range(i + 1, len(pts))]
    d += [(math.dist(p, q), p, q) for p in pts for q in others]
    dm, p, q = min(d)
    c["sep_m"] = round(dm, 1)
    c["sep_ll"] = [ll(*p), ll(*q)]   
    c["expand"] = [[k, v] for k, v, _ in ex]
for c in clusters:
    del c["xy"]
for f in frames:
    for i in f["ind"]:
        del i["xy"]

payload = {
    "parties": PARTIES, "modes": MODES, "col": COL, "name": NAME, "heading": HEADING, "lossCol": LOSS_COL,
    "alpha": ARROW_ALPHA, "pxPerPoint": round(EMU_PER_POINT / 914400 * 96 * 1.25, 4),
    "minPx": round(MIN_ARROW_EMU / 914400 * 96 * 1.25, 3), "dotBelow": DOT_BELOW, "sepPx": SEP_PX,
    "accent": ACCENT, "ridings": ridings, "frames": frames, "clusters": clusters,
    "seatParties": [p for p in PARTIES if (sw.winner_2026 == p).any()],
    "reversed": sorted([M.NAME[c] for c in M.CODES if float(sw.loc[c, sw.loc[c, "winner_2026"] + "_swing"]) < 0]),
    "source": ("Change in vote share (percentage points), 2022 results transposed to 2026 boundaries → 2026 general "
               "election. Source: Élections Québec. 2022 transposition: calculation from official "
               "polling-division results."),
    
    "ink": INK, "shade": SHADE,
    "shadeLabel": {("none" if k is None else k): v for k, v in SHADE_LABEL.items()},
    "seatCounts": {p: M.seat_counts(p) for p in PARTIES},
    "simplify": SIMPLIFY,
}

tpl = open(os.path.join(HERE, "html_template.html"), encoding="utf-8").read()
d3js = open(os.path.join(paths.RAW_JS, "d3.min.js"), encoding="utf-8").read()
tjs = open(os.path.join(paths.RAW_JS, "topojson-client.min.js"), encoding="utf-8").read()
safe = lambda s: s.replace("</", "<\\/")
html = (tpl.replace("/*__D3__*/", d3js).replace("/*__TOPOJSON__*/", tjs)
        .replace("__TOPO__", safe(json.dumps(topo, separators=(",", ":"))))
        .replace("__DATA__", safe(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))))
open(paths.writable(OUT), "w", encoding="utf-8").write(html)
mb = os.path.getsize(OUT) / 1e6
print(f"wrote {OUT}: {mb:.2f} MB (topojson {os.path.getsize(topo_p) / 1e6:.2f} MB, simplify {SIMPLIFY})")
print("sep_m:", {c["id"]: c["sep_m"] for c in clusters})
assert mb <= 4.0, mb
