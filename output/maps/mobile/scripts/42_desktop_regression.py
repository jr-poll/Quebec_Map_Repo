pass
import json, os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import mpaths   
from mserve import Server   
import numpy as np   
from PIL import Image, ImageDraw   
from playwright.sync_api import sync_playwright   

OUT = mpaths.mkdir(os.path.join(mpaths.COMPARE, "desktop"))
LIMIT = 0.005
SIZES = [(1440, 900), (1280, 720)]
MODES = ["WINNER", "PQ", "PLQ", "CAQ", "QS", "PCQ"]
STYLE_SEL = ["header", "#modes button", "#search", "#panel", "#zoom", ".zbtn", "#tip", ".riding"]
STYLE_PROPS = ["font-size", "height", "width", "padding", "position"]
STYLES_JS = """(args) => { const [sels, props] = args; const out = {};
  for (const s of sels) { const el = document.querySelector(s); if (!el) { out[s] = null; continue; }
    const cs = getComputedStyle(el); out[s] = Object.fromEntries(props.map(p => [p, cs.getPropertyValue(p)])); }
  return out; }"""
PIN_RIDING = "Westmount–Saint-Louis"


def scenes(pg, tag, size_dir, res):
    shots = {}
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.wait_for_function("window.__map !== undefined")
    pg.evaluate("document.fonts ? document.fonts.ready.then(() => 1) : 1")
    pg.wait_for_timeout(500)
    pg.mouse.move(2, 2)

    def shot(name):
        p = os.path.join(size_dir, f"{name}_{tag}.png")
        pg.screenshot(path=mpaths.writable(p))
        shots[name] = p
    res["styles"][tag] = pg.evaluate(STYLES_JS, [STYLE_SEL, STYLE_PROPS])
    res["labels"].setdefault(tag, {})
    for m in MODES:
        pg.evaluate(f"__map.setMode('{m}')")
        pg.wait_for_timeout(500)
        shot(f"initial_{m}")
        res["labels"][tag][f"initial_{m}"] = pg.evaluate("__map.labelled()")
    for m in ("WINNER", "PLQ"):
        pg.evaluate(f"__map.setMode('{m}')")
        for f in ("F.1.1.1", "F.1.1.2"):
            pg.evaluate(f"__map.zoomToFrame('{f}')")
            pg.wait_for_timeout(500)
            shot(f"frame_{f}_{m}")
            res["labels"][tag][f"frame_{f}_{m}"] = pg.evaluate("__map.labelled()")
    pg.evaluate("__map.setMode('PLQ')")
    pg.evaluate("__map.zoomToFrame('F')")
    pg.wait_for_timeout(900)
    pg.fill("#search", PIN_RIDING)
    pg.wait_for_timeout(150)
    pg.keyboard.press("Enter")
    pg.wait_for_timeout(1400)
    pg.mouse.move(2, 2)
    shot("pinned_tooltip_PLQ")
    res["pinned"][tag] = pg.evaluate("[document.getElementById('tip').classList.contains('pinned'), document.getElementById('tip').dataset.code]")
    res["errors"][tag] = errs
    return shots


def diff(a, b):
    A = np.asarray(Image.open(a).convert("RGB")).astype(int)
    B = np.asarray(Image.open(b).convert("RGB")).astype(int)
    if A.shape != B.shape:
        return 1.0, None
    d = np.abs(A - B).max(axis=2) > 0
    return float(d.mean()), d


def montage(a, b, d, out):
    A, B = Image.open(a).convert("RGB"), Image.open(b).convert("RGB")
    D = Image.fromarray(np.where(d[..., None], np.array([210, 0, 42]), np.array([255, 255, 255])).astype("uint8"))
    w, h = A.size
    M = Image.new("RGB", (w * 3 + 20, h + 30), "white")
    for i, (im, t) in enumerate(((A, "FINAL"), (B, "mobile"), (D, "differing pixels"))):
        M.paste(im, (i * (w + 10), 30))
        ImageDraw.Draw(M).text((i * (w + 10) + 8, 8), t, fill="black")
    M.save(mpaths.writable(out))


CONDITIONS = {
    
    "fonts-blocked": True,
    
    
    "fonts-network": False,
}
report = {"limit": LIMIT, "conditions": {}, "failures": [], "notes": []}
with Server() as srv, sync_playwright() as pw:
    br = pw.chromium.launch()
    for cond, block in CONDITIONS.items():
        report["conditions"][cond] = {}
        for (w, h) in SIZES:
            sd = mpaths.mkdir(os.path.join(OUT, cond, f"{w}x{h}"))
            res = {"styles": {}, "labels": {}, "pinned": {}, "errors": {}, "pairs": {}, "geometry": {}}
            shots = {}
            runs = [("final", mpaths.FINAL_HTML), ("mobile", mpaths.MOBILE_HTML)]
            if not block:
                runs.append(("final2", mpaths.FINAL_HTML))
            for tag, path in runs:
                ctx = br.new_context(viewport={"width": w, "height": h})
                if block:
                    ctx.route("**/fonts.googleapis.com/**", lambda rt: rt.abort())
                    ctx.route("**/fonts.gstatic.com/**", lambda rt: rt.abort())
                pg = ctx.new_page()
                pg.goto(srv.url(path))
                shots[tag] = scenes(pg, tag, sd, res)
                res["geometry"][tag] = pg.evaluate("[document.getElementById('map').getAttribute('viewBox'), "
                                                   "document.getElementById('mapwrap').getBoundingClientRect().height]")
                ctx.close()
            for name in shots["final"]:
                frac, d = diff(shots["final"][name], shots["mobile"][name])
                same_labels = res["labels"]["final"].get(name) == res["labels"]["mobile"].get(name)
                pr = {"diff_frac": round(frac, 6), "same_labels": same_labels if name in res["labels"]["final"] else None}
                if "final2" in shots:
                    pr["final_vs_final"] = round(diff(shots["final"][name], shots["final2"][name])[0], 6)
                if frac > LIMIT and d is not None:
                    mp = os.path.join(sd, f"montage_{name}.png")
                    montage(shots["final"][name], shots["mobile"][name], d, mp)
                    pr["montage"] = os.path.relpath(mp, mpaths.MOBILE)
                res["pairs"][name] = pr
                if block and frac > LIMIT:
                    report["failures"].append(f"{cond} {w}x{h} {name}: {100 * frac:.2f}% pixels differ")
                if pr["same_labels"] is False:
                    report["failures"].append(f"{cond} {w}x{h} {name}: label set differs")
            for sel in STYLE_SEL:
                a, b = res["styles"]["final"][sel], res["styles"]["mobile"][sel]
                if a != b:
                    report["failures"].append(f"{cond} {w}x{h} computed style {sel}: {a} != {b}")
            if res["pinned"]["final"] != res["pinned"]["mobile"] or not res["pinned"]["mobile"][0]:
                report["failures"].append(f"{cond} {w}x{h} pinned tooltip {res['pinned']}")
            for tag in res["errors"]:
                if res["errors"][tag]:
                    report["failures"].append(f"{cond} {w}x{h} {tag} page errors {res['errors'][tag]}")
            report["conditions"][cond][f"{w}x{h}"] = res
            worst = max(v["diff_frac"] for v in res["pairs"].values())
            print(f"[{cond}] {w}x{h}: {len(res['pairs'])} pairs, worst {100 * worst:.3f}% differing pixels; styles equal: "
                  f"{all(res['styles']['final'][s] == res['styles']['mobile'][s] for s in STYLE_SEL)}; geometry {res['geometry']}")
            for n, v in res["pairs"].items():
                print(f"   {n:28s} FINAL vs mobile {100 * v['diff_frac']:.3f}%"
                      + (f"  (FINAL vs FINAL {100 * v['final_vs_final']:.3f}%)" if "final_vs_final" in v else "")
                      + f"  labels same: {v['same_labels']}")
    br.close()
json.dump(report, open(mpaths.writable(os.path.join(mpaths.BUILD, "desktop_regression.json")), "w"), ensure_ascii=False, indent=1)
print("FAILURES:", len(report["failures"]))
for f in report["failures"]:
    print("  ", f)
sys.exit(1 if report["failures"] else 0)
