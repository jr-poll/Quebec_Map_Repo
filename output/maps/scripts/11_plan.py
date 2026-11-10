pass
import json, math, os, sys
import numpy as np
import geopandas as gpd
import shapely
import shapely.ops
from shapely.ops import polylabel, unary_union

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from mapstyle import MAP_X, MAP_Y, MAP_W, MAP_H, S_MIN_EMU, EMU_PER_IN, MODES   
import mapdata as M   

PLAN = os.path.join(M.MAPS, "plan")
os.makedirs(PLAN, exist_ok=True)
rid = gpd.read_file(os.path.join(M.GEO, "ridings_land.gpkg"), layer="ridings").set_index("code")
prov = gpd.read_file(os.path.join(M.GEO, "ridings_land.gpkg"), layer="province").geometry.iloc[0]
LAND = {int(c): g for c, g in rid.geometry.items()}
AREA = {c: g.area for c, g in LAND.items()}
anc = __import__("pandas").read_csv(os.path.join(M.GEO, "anchors.csv")).set_index("code")
ANCHOR = {int(c): (r.x, r.y) for c, r in anc.iterrows()}

M_RID = 36576 + 36000       
M_CLU = 36576 + 60000       
FINEST = 2.5 * 1000 / EMU_PER_IN     
FINEST_ABS = 2.0 * 1000 / EMU_PER_IN  
MAX_DEPTH = 5
ZOOM_OUT_MAX = 1.25
_cfgp = os.path.join(PLAN, "frames_config.yaml")
CONFIG = __import__("yaml").safe_load(open(_cfgp, encoding="utf-8")) if os.path.exists(_cfgp) else {}
SHARED = [list(g) for g in (CONFIG.get("shared_breakouts") or [])]
FEEDBACK = {}   
OFF_R = {c: M.offsets("riding", c) for c in M.CODES}
_off_c = {}


def off_cluster(codes):
    k = tuple(sorted(codes))
    if k not in _off_c:
        _off_c[k] = M.offsets("cluster", list(k))
    return _off_c[k]



class Frame:
    def __init__(self, cx, cy, mpe):
        self.mpe = mpe   
        w, h = MAP_W * mpe, MAP_H * mpe
        self.x0, self.x1, self.y0, self.y1 = cx - w / 2, cx + w / 2, cy - h / 2, cy + h / 2

    @classmethod
    def from_bbox(cls, x0, y0, x1, y1, pad=0.10, finest=FINEST):
        w, h = (x1 - x0) * (1 + 2 * pad), (y1 - y0) * (1 + 2 * pad)
        mpe = max(w / MAP_W, h / MAP_H, finest)
        return cls((x0 + x1) / 2, (y0 + y1) / 2, mpe)

    def to_slide(self, x, y):
        return MAP_X + (x - self.x0) / self.mpe, MAP_Y + (self.y1 - y) / self.mpe

    def ext(self):
        return [self.x0, self.y0, self.x1, self.y1]

    def km_per_in(self):
        return self.mpe * EMU_PER_IN / 1000

    def fits(self, x, y, offs, margin):
        X, Y = self.to_slide(x, y)
        for m in MODES:
            o = offs[m]
            pts = [(0, 0)] if o is None else [o[0], o[1]]
            for dx, dy in pts:
                if not (MAP_X + margin <= X + dx <= MAP_X + MAP_W - margin and
                        MAP_Y + margin <= Y + dy <= MAP_Y + MAP_H - margin):
                    return False
        return True

    def scaled(self, f):
        return Frame((self.x0 + self.x1) / 2, (self.y0 + self.y1) / 2, self.mpe * f)


def sample_points(geom, n=300):
    x0, y0, x1, y1 = geom.bounds
    k = 24
    while True:
        xs, ys = np.meshgrid(np.linspace(x0, x1, k), np.linspace(y0, y1, k))
        xs, ys = xs.ravel(), ys.ravel()
        inside = shapely.contains_xy(geom, xs, ys)
        if inside.sum() >= n or k > 400:
            pts = np.column_stack([xs[inside], ys[inside]])
            if len(pts) > n:
                pts = pts[np.linspace(0, len(pts) - 1, n).astype(int)]
            return pts
        k = int(k * 1.6)


def try_nudge(fr, code, placed_xy, smin, margin=M_RID):
    pass
    g = LAND[code]
    ge = g.buffer(-0.03 * EMU_PER_IN * fr.mpe)
    if ge.is_empty:
        ge = g
    vis = shapely.box(*fr.ext())
    ge = ge.intersection(vis)
    if ge.is_empty:
        return None
    pts = sample_points(ge)
    if not len(pts):
        return None
    S = np.column_stack(fr.to_slide(pts[:, 0], pts[:, 1]))
    if placed_xy:
        P = np.array(placed_xy)
        d = np.sqrt(((S[:, None, :] - P[None, :, :]) ** 2).sum(-1)).min(1)
    else:
        d = np.full(len(S), np.inf)
    ok = d >= smin
    ok &= np.array([fr.fits(x, y, OFF_R[code], margin) for x, y in pts])
    if not ok.any():
        return None
    ax, ay = ANCHOR[code]
    cand = pts[ok]
    j = np.argmin((cand[:, 0] - ax) ** 2 + (cand[:, 1] - ay) ** 2)
    return float(cand[j, 0]), float(cand[j, 1])


def dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def greedy(fr, codes, smin, placed=None, forced=()):
    pass
    placed = list(placed or [])
    ind, unres = {}, [c for c in codes if c in forced]
    for c in sorted([c for c in codes if c not in forced], key=lambda c: -AREA[c]):
        x, y = ANCHOR[c]
        X, Y = fr.to_slide(x, y)
        if fr.fits(x, y, OFF_R[c], M_RID) and all(dist((X, Y), p) >= smin for p in placed):
            ind[c] = (x, y, False)
            placed.append((X, Y))
            continue
        nz = try_nudge(fr, c, placed, smin)
        if nz:
            ind[c] = (nz[0], nz[1], True)
            placed.append(fr.to_slide(*nz))
        else:
            unres.append(c)
    return ind, unres


_ca = {}


def cluster_anchor(codes):
    pass
    k = tuple(sorted(codes))
    if k in _ca:
        return _ca[k]
    u = unary_union([LAND[c] for c in codes])
    w = np.array([float(M.r26.loc[c, "valid"]) for c in k])
    xy = np.array([ANCHOR[c] for c in k])
    cx, cy = (xy * w[:, None]).sum(0) / w.sum()
    pt = shapely.Point(cx, cy)
    if not u.contains(pt):
        inner = u.buffer(-1500)
        tgt = inner if not inner.is_empty else u
        pt = shapely.ops.nearest_points(tgt, pt)[0]
        if not u.contains(pt):
            parts = list(u.geoms) if hasattr(u, "geoms") else [u]
            pt = polylabel(max(parts, key=lambda q: q.area), tolerance=50)
    _ca[k] = (pt.x, pt.y)
    return _ca[k]


def uf_groups(fr, codes, link):
    codes = list(codes)
    par = {c: c for c in codes}

    def find(c):
        while par[c] != c:
            par[c] = par[par[c]]
            c = par[c]
        return c
    pos = {c: fr.to_slide(*ANCHOR[c]) for c in codes}
    for i, a in enumerate(codes):
        for b in codes[i + 1:]:
            if dist(pos[a], pos[b]) < link:
                par[find(a)] = find(b)
    groups = {}
    for c in codes:
        groups.setdefault(find(c), []).append(c)
    return [sorted(g) for g in groups.values()]


def layout(fr, members, smin, log, forced=()):
    pass
    ind, unres = greedy(fr, members, smin, forced=forced)
    if forced:
        log.append("label feedback: forced into breakout: " + ", ".join(M.NAME[c] for c in sorted(forced)))
    groups = uf_groups(fr, unres, 1.5 * smin) if unres else []
    for _ in range(200):
        changed = False
        clusters = [(g, cluster_anchor(g)) for g in groups]
        
        for i in range(len(clusters)):
            for j in range(i + 1, len(clusters)):
                if dist(fr.to_slide(*clusters[i][1]), fr.to_slide(*clusters[j][1])) < smin:
                    groups = [g for k, g in enumerate(groups) if k not in (i, j)] + \
                             [sorted(clusters[i][0] + clusters[j][0])]
                    changed = True
                    break
            if changed:
                break
        if changed:
            continue
        
        for gi, (g, (cx, cy)) in enumerate(clusters):
            C = fr.to_slide(cx, cy)
            hit = [c for c, (x, y, _) in ind.items() if dist(C, fr.to_slide(x, y)) < smin]
            if hit:
                for c in hit:
                    del ind[c]
                groups[gi] = sorted(g + hit)
                changed = True
                break
        if changed:
            continue
        
        for gi, g in enumerate(groups):
            if len(g) == 1:
                c = g[0]
                pts = [fr.to_slide(x, y) for x, y, _ in ind.values()] + \
                      [fr.to_slide(*a) for k, (gg, a) in enumerate(clusters) if k != gi]
                nz = try_nudge(fr, c, pts, smin)
                if nz:
                    ind[c] = (nz[0], nz[1], True)
                    groups.pop(gi)
                    log.append(f"singleton {M.NAME[c]} resolved by nudge")
                else:
                    P = fr.to_slide(*ANCHOR[c])
                    near = min(ind, key=lambda k: dist(P, fr.to_slide(*ind[k][:2])))
                    del ind[near]
                    groups[gi] = sorted([c, near])
                    log.append(f"singleton {M.NAME[c]} paired with {M.NAME[near]}")
                changed = True
                break
        if not changed:
            break
    else:
        raise RuntimeError("layout did not converge")
    clusters = [{"members": g, "x": cluster_anchor(g)[0], "y": cluster_anchor(g)[1]} for g in groups]
    return ind, clusters


def ensure_fit(fr, members, ind_only=False):
    pass
    for _ in range(60):
        if all(fr.fits(*ANCHOR[c], OFF_R[c], M_RID) for c in members):
            return fr
        fr = fr.scaled(1.05)
    raise RuntimeError("cannot fit members")


def sep_ok(fr, members, smin):
    ind, unres = greedy(fr, members, smin)
    return not unres


def child_frame(group, parent_mpe):
    pass
    x0, y0, x1, y1 = unary_union([LAND[c] for c in group]).bounds
    fr = ensure_fit(Frame.from_bbox(x0, y0, x1, y1), group)
    smin = 1.15 * S_MIN_EMU
    if sep_ok(fr, group, smin):
        lo, hi = fr.mpe, min(parent_mpe / 2.0, max(fr.mpe * ZOOM_OUT_MAX, parent_mpe / 5.0))   
        if hi > lo:
            for _ in range(14):
                mid = math.sqrt(lo * hi)
                if sep_ok(Frame((fr.x0 + fr.x1) / 2, (fr.y0 + fr.y1) / 2, mid), group, smin):
                    lo = mid
                else:
                    hi = mid
            fr = Frame((fr.x0 + fr.x1) / 2, (fr.y0 + fr.y1) / 2, lo)
    return fr


def frame_bounds_ok(fr, codes):
    return [c for c in codes if fr.fits(*ANCHOR[c], OFF_R[c], M_RID)]


def plan(fr, members, fid, parent, depth, out):
    log = []
    smin = S_MIN_EMU
    try:
        ind, clusters = layout(fr, members, smin, log, forced=FEEDBACK.get(fid, set()) & set(members))
    except RuntimeError:
        raise
    if depth >= MAX_DEPTH and clusters:
        for f in (0.9, 0.8):
            smin = max(0.24 * EMU_PER_IN, S_MIN_EMU * f)
            ind, clusters = layout(fr, members, smin, log, forced=FEEDBACK.get(fid, set()) & set(members))
            log.append(f"depth cap: S_MIN lowered to {smin / EMU_PER_IN:.2f} in")
            if not clusters:
                break
    
    others = [c for c in M.CODES if c not in members]
    vis = shapely.box(*fr.ext())
    others = [c for c in others if LAND[c].intersects(vis)]
    pts = [fr.to_slide(x, y) for x, y, _ in ind.values()] + [fr.to_slide(k["x"], k["y"]) for k in clusters]
    ctx_fit = frame_bounds_ok(fr, others) if parent is not None else []
    ctx, _ = greedy(fr, ctx_fit, smin, placed=pts)
    outline_only = sorted(set(others) - set(ctx))
    node = {"id": fid, "parent": parent, "depth": depth, "extent": fr.ext(), "mpe": fr.mpe,
            "km_per_in": round(fr.km_per_in(), 3), "s_min_emu": smin, "members": sorted(members),
            "individuals": [{"code": c, "x": x, "y": y, "nudged": n, "context": False} for c, (x, y, n) in
                            sorted(ind.items())] +
                           [{"code": c, "x": x, "y": y, "nudged": n, "context": True} for c, (x, y, n) in
                            sorted(ctx.items())],
            "clusters": [], "outline_only": outline_only, "log": log}
    out.append(node)
    cl_sorted = sorted(clusters, key=lambda k: -len(k["members"]))
    ids = [f"{fid}.{i + 1}" for i in range(len(cl_sorted))]
    child_of = {cid: cid for cid in ids}
    for grp in SHARED:   
        if all(g in ids for g in grp):
            for g in grp:
                child_of[g] = grp[0]
            log.append(f"override: clusters {grp} share breakout {grp[0]}")
    for cid, cl in zip(ids, cl_sorted):
        node["clusters"].append({"id": cid, "child": child_of[cid], "members": cl["members"], "x": cl["x"], "y": cl["y"]})
    for cid in ids:
        if child_of[cid] != cid:
            continue
        mem = sorted(sum((c["members"] for c in node["clusters"] if c["child"] == cid), []))
        cfr = child_frame(mem, fr.mpe)
        if cfr.mpe < FINEST_ABS:
            cfr = cfr.scaled(FINEST_ABS / cfr.mpe)
        plan(cfr, mem, cid, fid, depth + 1, out)


if __name__ == "__main__":
    x0, y0, x1, y1 = prov.bounds
    root = ensure_fit(Frame.from_bbox(x0, y0, x1, y1, pad=0.03), M.CODES)
    out = []
    plan(root, list(M.CODES), "F", None, 0, out)
    json.dump({"frames": out}, open(os.path.join(PLAN, "frames_plan.json"), "w"), ensure_ascii=False, indent=1)
    for n in out:
        nctx = sum(i["context"] for i in n["individuals"])
        print(f"{'  ' * n['depth']}{n['id']}: {len(n['members'])} members, {len(n['individuals']) - nctx} ind "
              f"(+{nctx} ctx), {len(n['clusters'])} clusters, {n['km_per_in']:.1f} km/in  "
              f"e.g. {', '.join(M.NAME[c] for c in n['members'][:3])}  {n['log']}")
