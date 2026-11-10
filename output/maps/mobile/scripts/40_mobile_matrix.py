pass
import argparse, json, math, os, re, sys, time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import mpaths   
from mserve import Server   
import numpy as np   
from PIL import Image   
from playwright.sync_api import sync_playwright   

ap = argparse.ArgumentParser()
ap.add_argument("--target", required=True)
ap.add_argument("--label", required=True)
ap.add_argument("--devices", default="")
ap.add_argument("--scenarios", default="")
ap.add_argument("--merge", action="store_true", help="replace matching runs in an existing report.json")
A = ap.parse_args()
TARGET = os.path.abspath(A.target)
OUT = mpaths.mkdir(os.path.join(mpaths.SCREENS, A.label))
if not A.merge:
    for f in os.listdir(OUT):
        if f.endswith(".png"):
            os.remove(mpaths.writable(os.path.join(OUT, f)))



DEVICES = [
    ("iPhone SE", "webkit", "phone-portrait", "iPhone SE"),
    ("iPhone 13", "webkit", "phone-portrait", "iPhone 13"),
    ("iPhone 15 Pro Max", "webkit", "phone-portrait", "iPhone 15 Pro Max"),
    ("iPhone 13 landscape", "webkit", "phone-landscape", "iPhone 13 landscape"),
    
    ("Phone 844x390 landscape", "webkit", "phone-landscape",
     {"viewport": {"width": 844, "height": 390}, "device_scale_factor": 3, "is_mobile": True, "has_touch": True,
      "user_agent": None}),
    ("Pixel 7", "chromium", "phone-portrait", "Pixel 7"),
    ("Galaxy S9+", "chromium", "phone-portrait", "Galaxy S9+"),
    ("Pixel 7 landscape", "chromium", "phone-landscape", "Pixel 7 landscape"),
    ("iPad Mini", "webkit", "tablet", "iPad Mini"),
    ("iPad Mini landscape", "webkit", "tablet", "iPad Mini landscape"),
    ("Desktop Chromium 1440x900", "chromium", "desktop", {"viewport": {"width": 1440, "height": 900}}),
    ("Desktop Firefox 1280x720", "firefox", "desktop", {"viewport": {"width": 1280, "height": 720}}),
]
MOBILE_SCEN = ["S1-file", "S1-http", "S2", "S3", "S4", "S5", "S6", "S7", "S8", "S9", "S10"]
DESKTOP_SCEN = ["S1-file", "S1-http", "S2", "S3", "S5"]
if A.devices:
    keep = [d.strip() for d in A.devices.split(",")]
    DEVICES = [d for d in DEVICES if d[0] in keep]

INIT_JS = r"""
window.__errs = [];
window.addEventListener('error', e => window.__errs.push(String(e.message || e)));
window.addEventListener('unhandledrejection', e => window.__errs.push('unhandled rejection: ' + String(e.reason && e.reason.message || e.reason)));
(function poll() {
  try { if (document.querySelectorAll('#map path.riding').length >= 127) { window.__t127 = performance.now(); return; } } catch (e) {}
  requestAnimationFrame(poll);
})();
"""

METRICS_JS = r"""() => {
  const q = s => document.querySelector(s);
  const R = el => { if (!el) return null; const b = el.getBoundingClientRect(); return [b.left, b.top, b.width, b.height]; };
  const rid = document.querySelectorAll('#map path.riding');
  const wrap = R(q('#mapwrap')), map = R(q('#map')), g = rid.length ? R(rid[0].parentNode) : null;
  let fill = null, inside = null;
  if (wrap && g && wrap[2] > 0 && wrap[3] > 0) {
    fill = Math.max(g[2] / wrap[2], g[3] / wrap[3]);
    inside = g[0] >= wrap[0] - 1 && g[1] >= wrap[1] - 1 && g[0] + g[2] <= wrap[0] + wrap[2] + 1 && g[1] + g[3] <= wrap[1] + wrap[3] + 1;
  }
  const vis = el => { const cs = getComputedStyle(el); if (cs.display === 'none' || cs.visibility === 'hidden') return false;
    const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
  const btns = [...document.querySelectorAll('button')].filter(vis).filter(b => !b.closest('#panel:not(.open)') || getComputedStyle(q('#panel')).position === 'static');
  const targets = btns.map(b => { const r = b.getBoundingClientRect();
    return [b.id || b.dataset.mode || b.className, Math.round(r.width * 10) / 10, Math.round(r.height * 10) / 10]; });
  const s = q('#search');
  const app = R(q('#app'));
  return {
    ridings: rid.length, t127: window.__t127 === undefined ? null : Math.round(window.__t127), errs: window.__errs || [],
    inner: [innerWidth, innerHeight], header: q('header') ? q('header').getBoundingClientRect().height : null,
    wrap, map, ridingBox: g, fill, inside, app,
    overflowX: document.documentElement.scrollWidth > innerWidth + 0.5, scrollW: document.documentElement.scrollWidth,
    scrollable: document.scrollingElement.scrollHeight > innerHeight + 1 && getComputedStyle(document.body).overflowY !== 'hidden',
    minTarget: targets.length ? Math.min(...targets.map(t => Math.min(t[1], t[2]))) : null, targets,
    searchFont: s ? parseFloat(getComputedStyle(s).fontSize) : null,
    coarse: matchMedia('(pointer:coarse)').matches, hoverNone: matchMedia('(hover:none)').matches,
    sheet: window.__map && window.__map.isSheet ? window.__map.isSheet() : null,
    fallback: !!document.getElementById('fallback'), k: window.__map ? window.__map.zoomK() : null,
    fontsOK: document.fonts ? document.fonts.check('11px "Open Sans"') : null,
    subtitle: q('#subtitle') ? q('#subtitle').textContent : null,
  };
}"""

LABEL_OVERLAP_JS = r"""() => {
  // placement boxes (__map.labelRects, mobile file only) must not overlap at all; rendered glyph boxes may graze by
  // up to 2 px (text ascent/descent exceeds the 13.5 px placement line box; FINAL behaves the same)
  const ov = (rs, tol) => { let n = 0; for (let i = 0; i < rs.length; i++) for (let j = i + 1; j < rs.length; j++) {
    const a = rs[i], b = rs[j];
    if (Math.min(a[2], b[2]) - Math.max(a[0], b[0]) > tol && Math.min(a[3], b[3]) - Math.max(a[1], b[1]) > tol) n++; } return n; };
  const rendered = [...document.querySelectorAll('#map .labels text')].map(t => { const b = t.getBoundingClientRect(); return [b.left, b.top, b.right, b.bottom]; });
  const placed = window.__map && window.__map.labelRects ? window.__map.labelRects() : null;
  const g = ov(rendered, 2), p = placed ? ov(placed, 0) : null;
  return {labels: rendered.length, rendered_overlaps_gt2px: g, placement_overlaps: p, overlaps: g + (p || 0)};
}"""


def slug(s):
    return re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_")


def host_page(kind, w="100%", h="700px", sandbox=False, hidden=False):
    rel = os.path.relpath(TARGET, mpaths.TMP).replace(os.sep, "/")
    sb = ' sandbox="allow-scripts"' if sandbox else ""
    style = f"width:{w};height:{h};border:0;display:{'none' if hidden else 'block'}"
    show = "<script>setTimeout(function(){document.getElementById('f').style.display='block';},1000);</script>" if hidden else ""
    html = (f"<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'>"
            f"<title>host {kind}</title><style>body{{margin:0;font:14px sans-serif}} p{{margin:8px}}</style></head><body>"
            f"<p>Host page ({kind})</p><iframe id='f' src='{rel}'{sb} style='{style}' title='map'></iframe>{show}</body></html>")
    p = mpaths.writable(os.path.join(mpaths.TMP, f"host_{A.label}_{kind}.html"))
    open(p, "w", encoding="utf-8").write(html)
    return p


def nonbg_fraction(png, ref_png, box):
    pass
    im = np.asarray(Image.open(png).convert("RGB")).astype(int)
    ref = np.asarray(Image.open(ref_png).convert("RGB")).astype(int)
    sx = im.shape[1] / box["vw"]
    x0, y0, x1, y1 = [int(round(v * sx)) for v in (box["x"], box["y"], box["x"] + box["w"], box["y"] + box["h"])]
    sl = (slice(max(0, y0), max(0, y1)), slice(max(0, x0), max(0, x1)))
    a, b = im[sl], ref[sl]
    if not a.size or a.shape != b.shape:
        return 0.0
    return float((np.abs(a - b).max(axis=2) >= 2).mean())


def app_frame(pg, timeout=20):
    name = os.path.basename(TARGET)
    t0 = time.time()
    while time.time() - t0 < timeout:
        for fr in pg.frames:
            if fr != pg.main_frame and name in fr.url:
                return fr
        pg.wait_for_timeout(100)
    raise RuntimeError("iframe not found")


def wait_render(fr, pg, timeout=20):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            if fr.evaluate("document.querySelectorAll('#map path.riding').length") >= 127:
                return True
        except Exception:
            pass
        pg.wait_for_timeout(100)
    return False


def run_one(pw, br, dev, scen, srv, res):
    name, engine, kind, opt = dev
    o = dict(pw.devices[opt]) if isinstance(opt, str) else dict(opt)
    o.pop("default_browser_type", None)
    if o.get("user_agent") is None:
        o.pop("user_agent", None)
        if kind.startswith("phone") and engine == "webkit":
            o["user_agent"] = pw.devices["iPhone 13"]["user_agent"]
    if scen == "S2":
        o["java_script_enabled"] = False
    ctx = br.new_context(**o)
    if scen != "S2":
        ctx.add_init_script(INIT_JS)
    pg = ctx.new_page()
    r = {"device": name, "engine": engine, "kind": kind, "scenario": scen, "page_errors": [], "console_errors": [], "notes": []}
    pg.on("pageerror", lambda e: r["page_errors"].append(str(e)[:300]))
    pg.on("console", lambda m: m.type == "error" and r["console_errors"].append(m.text[:200]))
    shot = lambda tag="": pg.screenshot(path=mpaths.writable(os.path.join(OUT, f"{slug(name)}__{scen}{tag}.png")))
    fr = pg.main_frame
    t_start = time.time()
    try:
        if scen in ("S3",):
            ctx.route("**/fonts.googleapis.com/**", lambda rt: rt.abort())
            ctx.route("**/fonts.gstatic.com/**", lambda rt: rt.abort())
        if scen == "S1-file":
            pg.goto("file://" + TARGET)
        elif scen in ("S1-http", "S3", "S8", "S10"):
            pg.goto(srv.url(TARGET))
        elif scen == "S2":
            pg.goto(srv.url(TARGET))
            pg.wait_for_timeout(1500)
            
            ref_png = os.path.join(OUT, f"{slug(name)}__S2_ref.png")
            body = open(TARGET, encoding="utf-8").read().replace(
                "</style>", "#fallback,#map,.fb-note{visibility:hidden!important}</style>", 1)
            pg2 = ctx.new_page()
            pg2.route("**/" + os.path.basename(TARGET).replace(" ", "%20"),
                      lambda rt: rt.fulfill(status=200, content_type="text/html; charset=utf-8", body=body))
            pg2.goto(srv.url(TARGET))
            pg2.wait_for_timeout(1500)
            pg2.screenshot(path=mpaths.writable(ref_png))
            pg2.close()
        elif scen == "S4":
            pending = []
            ctx.route("**/fonts.googleapis.com/**", lambda rt: pending.append((time.time(), rt)))
            ctx.route("**/fonts.gstatic.com/**", lambda rt: pending.append((time.time(), rt)))
            pg.goto(srv.url(TARGET), wait_until="commit")
            seen = None
            while time.time() - t_start < 30:
                for item in list(pending):
                    if time.time() - item[0] >= 8:
                        try:
                            item[1].continue_()
                        except Exception as e:
                            r["notes"].append(f"continue failed {e}")
                        pending.remove(item)
                try:
                    n = pg.evaluate("document.querySelectorAll('#map path.riding').length")
                except Exception:
                    n = 0
                if n >= 127 and seen is None:
                    seen = pg.evaluate("window.__t127")
                    r["t127_s4"] = seen
                    try:   
                        pg.screenshot(path=mpaths.writable(os.path.join(OUT, f"{slug(name)}__{scen}_before_fonts.png")), timeout=2500)
                    except Exception:
                        r["notes"].append("before-fonts screenshot skipped (engine waits for fonts)")
                    r["labels_before_fonts"] = pg.evaluate(LABEL_OVERLAP_JS)
                try:
                    done = pg.evaluate("document.fonts && document.fonts.check('11px \"Open Sans\"') && document.fonts.status === 'loaded'")
                except Exception:
                    done = False
                if seen is not None and done and not pending and time.time() - t_start > 9:
                    break
                pg.wait_for_timeout(100)
            pg.wait_for_timeout(700)
            r["labels_after_fonts"] = pg.evaluate(LABEL_OVERLAP_JS)
            r["fonts_loaded_s4"] = pg.evaluate("document.fonts ? document.fonts.check('11px \"Open Sans\"') : null")
        elif scen in ("S5", "S6", "S7", "S9"):
            hp = {"S5": lambda: host_page("tall"), "S6": lambda: host_page("short", h="320px"),
                  "S7": lambda: host_page("sandbox", w="min(390px,100%)", sandbox=True),
                  "S9": lambda: host_page("hidden", hidden=True)}[scen]()
            pg.goto(srv.url(hp))
            fr = app_frame(pg)
        if scen != "S2" and scen != "S4":
            if not wait_render(fr, pg):
                r["notes"].append("map did not render 127 ridings within 20 s")
            pg.wait_for_timeout(1500 if scen == "S9" else 900)
        if scen == "S2":
            try:
                m = {"inner": pg.evaluate("[innerWidth, innerHeight]")}
            except Exception:
                m = {"inner": [o["viewport"]["width"], o["viewport"]["height"]]}
            loc = lambda s: pg.locator(s).first
            box = loc("#mapwrap").bounding_box()
            m["wrap"] = box and [box["x"], box["y"], box["width"], box["height"]]
            p = os.path.join(OUT, f"{slug(name)}__{scen}.png")
            pg.screenshot(path=mpaths.writable(p))
            if box and box["height"] > 0:
                m["nonbg"] = round(nonbg_fraction(p, ref_png, {"x": box["x"], "y": box["y"], "w": box["width"],
                                                      "h": min(box["height"], m["inner"][1] - box["y"]), "vw": m["inner"][0]}), 4)
            else:
                m["nonbg"] = 0.0
            m["note_visible"] = loc(".fb-note").is_visible() if pg.locator(".fb-note").count() else False
            m["legend_h2_visible"] = pg.locator("#panel h2").count() > 0 and loc("#panel h2").is_visible()
            m["live_controls_visible"] = [s for s in ("#zoom", "#modes", "#legendToggle", "#searchToggle", "#search")
                                          if pg.locator(s).count() and loc(s).is_visible()]
            pg.screenshot(path=mpaths.writable(os.path.join(OUT, f"{slug(name)}__{scen}_full.png")), full_page=True)
            r.update(m)
        else:
            r.update(fr.evaluate(METRICS_JS))
            if scen != "S4":
                shot()
        if scen == "S6":
            
            fr.evaluate("window.scrollTo(0, 1e6)")
            pg.wait_for_timeout(300)
            shot("_scrolled")
        if scen == "S7":
            sub0 = fr.evaluate("document.querySelector('#subtitle').textContent")
            b = fr.locator('#modes button[data-mode="PLQ"]')
            (b.tap() if o.get("has_touch") else b.click())
            pg.wait_for_timeout(600)
            sub1 = fr.evaluate("document.querySelector('#subtitle').textContent")
            r["s7_mode_switch"] = {"before": sub0, "after": sub1, "ok": sub1 != sub0 and "PLQ" in sub1,
                                   "errs": fr.evaluate("window.__errs || []")}
            shot("_plq")
        if scen == "S8":
            fr.evaluate("__map.zoomToFrame('F.1.1.1')")
            pg.wait_for_timeout(1000)
            ref = pg.evaluate("""() => { const w = document.getElementById('mapwrap').getBoundingClientRect();
                const it = (window.__lastItems || []).filter(d => d.kind === 'r').map(d => [Math.hypot(d.x - w.width / 2, d.y - w.height / 2), d.code]);
                it.sort((a, b) => a[0] - b[0]); return it.length ? it[0][1] : null; }""")
            before = {"k": pg.evaluate("__map.zoomK()"), "xy": pg.evaluate(f"__map.itemXY({ref})"), "code": ref}
            shot("_before")
            vw, vh = o["viewport"]["width"], o["viewport"]["height"]
            pg.set_viewport_size({"width": vw, "height": vh - 80})
            pg.wait_for_timeout(400)
            mid = {"k": pg.evaluate("__map.zoomK()"), "xy": pg.evaluate(f"__map.itemXY({ref})")}
            pg.set_viewport_size({"width": vw, "height": vh})
            pg.wait_for_timeout(700)
            after = {"k": pg.evaluate("__map.zoomK()"), "xy": pg.evaluate(f"__map.itemXY({ref})")}
            shot("_after")
            shift = math.dist(before["xy"], after["xy"]) if before["xy"] and after["xy"] else None
            r["s8"] = {"before": before, "mid": mid, "after": after,
                       "k_ratio": after["k"] / before["k"] if before["k"] else None, "shift_px": shift}
        if scen == "S10":
            s10(pg, ctx, engine, kind, r, shot)
        r["page_errors"] += [e for e in (fr.evaluate("window.__errs || []") if scen != "S2" else []) if e not in r["page_errors"]]
    except Exception as e:
        r["notes"].append(f"EXCEPTION {type(e).__name__}: {str(e)[:300]}")
        try:
            shot("_exception")
        except Exception:
            pass
    r["seconds"] = round(time.time() - t_start, 1)
    try:
        ctx.unroute_all(behavior="ignoreErrors")
    except Exception:
        pass
    ctx.close()
    res.append(r)
    fl = failures(r)
    print(f"{name:28s} {scen:8s} {r['seconds']:5.1f}s  {'OK' if not fl else 'FAIL: ' + '; '.join(fl)}", flush=True)


def tap(pg, sel):
    pg.locator(sel).first.tap()


def s10(pg, ctx, engine, kind, r, shot):
    out = r.setdefault("s10", {})
    D = pg.evaluate("JSON.parse(document.getElementById('mapdata').textContent)")
    rgb = lambda h: f"rgb({int(h[0:2], 16)}, {int(h[2:4], 16)}, {int(h[4:6], 16)})"
    
    modes = []
    prev = pg.evaluate("document.querySelector('#subtitle').textContent")
    for m in ["PQ", "PLQ", "CAQ", "QS", "PCQ", "WINNER"]:
        tap(pg, f'#modes button[data-mode="{m}"]')
        pg.wait_for_timeout(500)
        sub = pg.evaluate("document.querySelector('#subtitle').textContent")
        strokes = set(pg.evaluate("""() => [...document.querySelectorAll('#map g.item line.main')]
            .filter(l => l.style.display !== 'none').map(l => getComputedStyle(l).stroke)"""))
        ok_col = {rgb(D["ink"][m]), rgb(D["lossCol"])} if m != "WINNER" else {rgb(c) for c in D["col"].values()}
        ok = sub != prev and bool(strokes) and strokes <= ok_col and (m in sub if m != "WINNER" else "winner" in sub)
        modes.append({"mode": m, "subtitle": sub, "ok": ok, "strokes": sorted(strokes)})
        prev = sub
    out["modes"] = modes
    shot("_modes")
    
    pick = pg.evaluate("""() => { const w = document.getElementById('mapwrap').getBoundingClientRect();
        const its = (window.__lastItems || []).filter(d => d.kind === 'r' && d.x > 70 && d.x < w.width - 70 && d.y > 70 && d.y < w.height - 150);
        return its.length ? {code: its[0].code, x: w.left + its[0].x, y: w.top + its[0].y} : null; }""")
    tapres = {"picked": pick}
    if pick:
        pg.touchscreen.tap(pick["x"], pick["y"])
        pg.wait_for_timeout(1700)
        st = pg.evaluate(f"""() => {{ const t = document.getElementById('tip'); const cs = getComputedStyle(t);
            const b = t.getBoundingClientRect(); const c = t.querySelector('.tipclose');
            const g = [...document.querySelectorAll('#map g.item')].find(g => g.__data__ && g.__data__.kind === 'r' && g.__data__.code === {pick['code']});
            const a = g ? (g.querySelector('line.main').style.display === 'none' ? g.querySelector('circle.dot') : g.querySelector('line.main')).getBoundingClientRect() : null;
            const inter = a && Math.min(a.right, b.right) - Math.max(a.left, b.left) > 0 && Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top) > 0;
            return {{shown: cs.display !== 'none', code: t.dataset.code, rect: [b.left, b.top, b.right, b.bottom],
              onscreen: b.left >= -0.5 && b.top >= -0.5 && b.right <= innerWidth + 0.5 && b.bottom <= innerHeight + 0.5,
              close: !!c && c.getBoundingClientRect().width >= 44 && c.getBoundingClientRect().height >= 44,
              arrow: a && [a.left, a.top, a.right, a.bottom], covered: !!inter, sheet: t.classList.contains('sheet')}}; }}""")
        tapres.update(st)
        shot("_tap_card")
        if st["close"]:
            tap(pg, "#tip .tipclose")
            pg.wait_for_timeout(300)
            tapres["closed"] = pg.evaluate("getComputedStyle(document.getElementById('tip')).display === 'none'")
        else:
            tapres["closed"] = False
        tapres["ok"] = bool(st["shown"] and str(st["code"]) == str(pick["code"]) and st["onscreen"] and st["close"]
                            and not st["covered"] and tapres["closed"])
    else:
        tapres["ok"] = False
    out["tap"] = tapres
    
    lg = {}
    if not pg.locator("#legendToggle").is_visible():
        side = pg.evaluate("""() => { const b = document.getElementById('panel').getBoundingClientRect();
            return {rect: [b.left, b.top, b.right, b.bottom], iw: innerWidth, ih: innerHeight}; }""")
        lg.update(side_panel=True, open=side, visible=side["rect"][2] - side["rect"][0] > 100 and side["rect"][0] >= -1,
                  closed=True, drawer=False)
        lg["ok"] = kind == "tablet" and lg["visible"]
        out["legend"] = lg
    else:
        legend_toggle(pg, kind, lg, shot)
        out["legend"] = lg
    search_and_pinch(pg, ctx, engine, kind, out, shot, D)


def legend_toggle(pg, kind, lg, shot):
    tap(pg, "#legendToggle")
    pg.wait_for_timeout(450)
    lg["open"] = pg.evaluate("""() => { const p = document.getElementById('panel'), b = p.getBoundingClientRect(),
        w = document.getElementById('mapwrap').getBoundingClientRect();
        return {cls: p.classList.contains('open'), rect: [b.left, b.top, b.right, b.bottom], iw: innerWidth, ih: innerHeight,
          wrapH: w.height, wrapTop: w.top}; }""")
    shot("_legend")
    o_ = lg["open"]
    rr = o_["rect"]
    lg["visible"] = o_["cls"] and rr[0] >= -1 and rr[2] <= o_["iw"] + 1 and rr[3] <= o_["ih"] + 1 and rr[1] >= o_["wrapTop"] - 1
    lg["drawer"] = abs(rr[2] - o_["iw"]) < 2 and (rr[2] - rr[0]) < 0.6 * o_["iw"] and (rr[3] - rr[1]) > 0.8 * o_["wrapH"]
    tap(pg, "#legendToggle")
    pg.wait_for_timeout(450)
    c_ = pg.evaluate("""() => { const p = document.getElementById('panel'), b = p.getBoundingClientRect();
        return {cls: p.classList.contains('open'), rect: [b.left, b.top, b.right, b.bottom]}; }""")
    lg["closed"] = (not c_["cls"]) and (c_["rect"][1] >= o_["ih"] - 1 or c_["rect"][0] >= o_["iw"] - 1)
    lg["ok"] = lg["visible"] and lg["closed"] and (lg["drawer"] if kind == "phone-landscape" else True)


def search_and_pinch(pg, ctx, engine, kind, out, shot, D):
    
    sr = {}
    if pg.locator("#searchToggle").count() and pg.locator("#searchToggle").is_visible():
        tap(pg, "#searchToggle")
        sr["via_toggle"] = True
    else:
        tap(pg, "#search")
        sr["via_toggle"] = False
    pg.wait_for_timeout(250)
    sr["search_visible"] = pg.locator("#search").is_visible()
    pg.keyboard.type("Mégantic", delay=20)
    pg.wait_for_timeout(300)
    opts = pg.evaluate("[...document.querySelectorAll('#results li')].map(l => l.textContent)")
    sr["options"] = opts
    shot("_search")
    code = next(rr_["code"] for rr_ in D["ridings"] if rr_["name"] == "Mégantic")
    if "Mégantic" in opts:
        pg.locator("#results li", has_text=re.compile(r"^Mégantic$")).first.tap()
        pg.wait_for_timeout(1900)
    st = pg.evaluate("""() => { const t = document.getElementById('tip'); const b = t.getBoundingClientRect();
        return {pinned: t.classList.contains('pinned'), code: t.dataset.code, shown: getComputedStyle(t).display !== 'none',
          onscreen: b.left >= -0.5 && b.top >= -0.5 && b.right <= innerWidth + 0.5 && b.bottom <= innerHeight + 0.5,
          active: document.activeElement && document.activeElement.id}; }""")
    sr.update(st)
    sr["ok"] = bool(st["pinned"] and str(st["code"]) == str(code) and st["shown"] and st["onscreen"])
    shot("_search_pinned")
    out["search"] = sr
    
    if engine == "chromium":
        pg.keyboard.press("Escape")
        tap(pg, "#zreset")
        pg.wait_for_timeout(800)
        k0 = pg.evaluate("__map.zoomK()")
        b = pg.locator("#mapwrap").bounding_box()
        cx, cy = b["x"] + b["width"] / 2, b["y"] + b["height"] / 2
        cdp = ctx.new_cdp_session(pg)
        pts = lambda d: [{"x": cx - d, "y": cy, "id": 1}, {"x": cx + d, "y": cy, "id": 2}]
        cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": pts(30)})
        for i in range(1, 13):
            cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": pts(30 + i * 9)})
            pg.wait_for_timeout(16)
        cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
        pg.wait_for_timeout(600)
        k1 = pg.evaluate("__map.zoomK()")
        out["pinch"] = {"k0": k0, "k1": k1, "ok": k1 > k0 * 1.2,
                        "labels_after": pg.evaluate("document.querySelectorAll('#map .labels text').length")}
        shot("_pinch")



def failures(r):
    f = []
    s, kind, dev = r["scenario"], r["kind"], r["device"]
    errs = r["page_errors"]
    if any(n.startswith("EXCEPTION") or "did not render" in n for n in r["notes"]):
        f += [n for n in r["notes"] if n.startswith("EXCEPTION") or "did not render" in n]
    if s == "S2":
        if r.get("nonbg", 0) < 0.08:
            f.append(f"no-JS map area {100 * r.get('nonbg', 0):.1f}% non-background (< 8%)")
        if not r.get("note_visible"):
            f.append("no-JS note not visible")
        if not r.get("legend_h2_visible"):
            f.append("no-JS legend not visible")
        if r.get("live_controls_visible"):
            f.append(f"no-JS live controls shown {r['live_controls_visible']}")
        return f
    if errs:
        f.append(f"{len(errs)} page errors: {errs[0][:120]}")
    if s in ("S1-file", "S1-http", "S3", "S4", "S5", "S7", "S9", "S6", "S8", "S10"):
        if r.get("ridings") != 127:
            f.append(f"{r.get('ridings')} riding paths")
        if s not in ("S6", "S8", "S10"):
            if r.get("fill") is None or r["fill"] < 0.85:
                f.append(f"province fills {r.get('fill') and round(r['fill'], 3)} (< 0.85)")
            if not r.get("inside"):
                f.append("province not fully inside the map area")
        if r.get("overflowX"):
            f.append(f"horizontal overflow {r.get('scrollW')} > {r['inner'][0]}")
    if s == "S4":
        t = r.get("t127_s4")
        if t is None or t > 1500:
            f.append(f"map visible after {t} ms with slow fonts (> 1500)")
        la = r.get("labels_after_fonts") or {}
        if la.get("overlaps", 1):
            f.append(f"{la.get('overlaps')} overlapping labels after fonts load")
    if s in ("S1-file", "S1-http") and kind != "desktop":
        vw, vh = r["inner"]
        wh = r["wrap"][3] if r.get("wrap") else 0
        if kind == "phone-portrait":
            lim = 160 if vw <= 320 else 150
            if r["header"] > lim:
                f.append(f"header {r['header']:.0f} px (> {lim})")
            if wh < 0.6 * vh:
                f.append(f"map {wh:.0f} px tall (< 60% of {vh})")
        if kind == "phone-landscape":
            if r["header"] > 52:
                f.append(f"header {r['header']:.0f} px (> 52)")
            if (vw, vh) == (844, 390) and wh < 330:
                f.append(f"map {wh:.0f} px tall on 844x390 (< 330)")
        if r.get("coarse") and (r.get("minTarget") or 0) < 44:
            small = [t for t in r["targets"] if min(t[1], t[2]) < 44]
            f.append(f"touch targets < 44 px: {small[:4]}")
        if kind.startswith("phone") and (r.get("searchFont") or 0) < 16:
            f.append(f"#search font-size {r.get('searchFont')} px (< 16)")
    if s == "S6":
        app_h = r["app"][3] if r.get("app") else 0
        wh = r["wrap"][3] if r.get("wrap") else 0
        if app_h < 420 - 0.5:
            f.append(f"app {app_h:.0f} px tall in a 320 px iframe (min-height 420 not applied)")
        if not r.get("scrollable"):
            f.append("embedded page does not scroll")
        if wh < 300:
            f.append(f"map {wh:.0f} px tall (< 300)")
    if s == "S7":
        ms = r.get("s7_mode_switch") or {}
        if not ms.get("ok") or ms.get("errs"):
            f.append(f"mode switch in sandboxed iframe failed {ms.get('after', '')[:40]!r} errs={ms.get('errs')}")
    if s == "S8":
        s8 = r.get("s8") or {}
        kr, sh = s8.get("k_ratio"), s8.get("shift_px")
        if kr is None or abs(kr - 1) > 0.01:
            f.append(f"zoom k {s8.get('before', {}).get('k')} -> {s8.get('after', {}).get('k')} after URL-bar resize")
        if sh is None or sh >= 4:
            f.append(f"view centre moved {sh if sh is None else round(sh, 1)} px")
    if s == "S10":
        t = r.get("s10") or {}
        bad = [m["mode"] for m in t.get("modes", []) if not m["ok"]]
        if bad:
            f.append(f"mode taps failed {bad}")
        tp = t.get("tap") or {}
        if not tp.get("ok"):
            f.append("riding tap card: " + ", ".join(k for k in ("shown", "onscreen", "close", "closed") if not tp.get(k)) +
                     (" covered" if tp.get("covered") else ""))
        lg = t.get("legend") or {}
        if not lg.get("ok"):
            f.append(f"legend open/close visible={lg.get('visible')} closed={lg.get('closed')} drawer={lg.get('drawer')}")
        sr = t.get("search") or {}
        if not sr.get("ok"):
            f.append(f"search Mégantic options={sr.get('options')} pinned={sr.get('pinned')} code={sr.get('code')}")
        if "pinch" in t and not t["pinch"]["ok"]:
            f.append(f"pinch k {t['pinch']['k0']} -> {t['pinch']['k1']}")
    return f



res = []
with Server() as srv, sync_playwright() as pw:
    browsers = {}
    for dev in DEVICES:
        eng = dev[1]
        if eng not in browsers:
            browsers[eng] = getattr(pw, eng).launch()
        scen = DESKTOP_SCEN if dev[2] == "desktop" else MOBILE_SCEN
        if A.scenarios:
            scen = [s for s in scen if s in A.scenarios.split(",") or s.split("-")[0] in A.scenarios.split(",")]
        for s in scen:
            run_one(pw, browsers[eng], dev, s, srv, res)
    for b in browsers.values():
        b.close()

if A.merge and os.path.exists(os.path.join(OUT, "report.json")):
    new_keys = {(r["device"], r["scenario"]) for r in res}
    old = json.load(open(os.path.join(OUT, "report.json")))["runs"]
    order = [(r["device"], r["scenario"]) for r in old]
    merged = {(r["device"], r["scenario"]): r for r in old}
    merged.update({(r["device"], r["scenario"]): r for r in res})
    res = [merged[k] for k in order] + [r for r in res if (r["device"], r["scenario"]) not in set(order)]
for r in res:
    r["failures"] = failures(r)
nfail = sum(bool(r["failures"]) for r in res)
json.dump({"target": os.path.relpath(TARGET, mpaths.OUT_ROOT), "label": A.label, "runs": res, "failed_runs": nfail},
          open(mpaths.writable(os.path.join(OUT, "report.json")), "w"), ensure_ascii=False, indent=1)

fmt = lambda v, n=0: "–" if v is None else (f"{v:.{n}f}" if isinstance(v, float) else str(v))
lines = [f"# Mobile matrix: `{os.path.relpath(TARGET, mpaths.OUT_ROOT)}` ({A.label})", "",
         f"{len(res)} runs, {nfail} with failures. Engines: iOS/iPadOS descriptors on Playwright WebKit, Android on Chromium.", "",
         "| Device | Scenario | Errors | 127 at (ms) | Header px | Map h px | Fill | Overflow | Min target | Search px | Result |",
         "|---|---|---|---|---|---|---|---|---|---|---|"]
for r in res:
    wh = r["wrap"][3] if r.get("wrap") else None
    t = r.get("t127_s4", r.get("t127"))
    extra = ""
    if r["scenario"] == "S2":
        extra = f"non-bg {100 * r.get('nonbg', 0):.1f}%; "
    if r["scenario"] == "S8" and r.get("s8"):
        extra = f"k {fmt(r['s8']['before']['k'], 2)}→{fmt(r['s8']['after']['k'], 2)}, shift {fmt(r['s8']['shift_px'], 1)} px; "
    lines.append(f"| {r['device']} | {r['scenario']} | {len(r['page_errors'])} | {fmt(t)} | {fmt(r.get('header'), 0)} | "
                 f"{fmt(wh, 0)} | {fmt(r.get('fill'), 2)} | {'yes' if r.get('overflowX') else 'no'} | {fmt(r.get('minTarget'), 0)} | "
                 f"{fmt(r.get('searchFont'), 0)} | {extra}{'OK' if not r['failures'] else 'FAIL: ' + '; '.join(r['failures'])} |")
open(mpaths.writable(os.path.join(OUT, "report.md")), "w", encoding="utf-8").write("\n".join(lines) + "\n")
print(f"\n{len(res)} runs, {nfail} with failures -> {os.path.relpath(OUT, mpaths.OUT_ROOT)}/report.md")
sys.exit(1 if (nfail and A.label != "final") else 0)
