pass
import json, os, random, sys
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import mpaths   
FINAL = mpaths.FINAL
sys.path.insert(0, FINAL)
import paths   
import mapdata as M   
from mapstyle import MODES, PARTIES, SHADE, INK, LOSS_COL, COL, SHADE_LABEL   

HTML = os.path.abspath(sys.argv[1]) if len(sys.argv) > 1 else mpaths.MOBILE_HTML
SHOTS = mpaths.mkdir(os.path.join(mpaths.SCREENS, "desktop95"))
for f in os.listdir(SHOTS):
    if f.endswith(".png"):
        os.remove(mpaths.writable(os.path.join(SHOTS, f)))
URL = "file://" + HTML
plan = json.load(open(os.path.join(paths.PLAN, "frames_plan.json")))["frames"]
res = {"errors": [], "console_errors": [], "requests": [], "checks": {}}
err = res["errors"].append
ALLOWED = ("fonts.googleapis.com", "fonts.gstatic.com")


def f1(v):
    r = round(v * 10) / 10
    return ("−" if r < 0 else "") + f"{abs(r):.1f}"


def sgn(v):
    r = round(v * 10) / 10
    return ("+" if r > 0 else "−" if r < 0 else "") + f"{abs(r):.1f}"


with sync_playwright() as pw:
    br = pw.chromium.launch()
    pg = br.new_page(viewport={"width": 1440, "height": 900})
    pg.on("console", lambda m: m.type == "error" and res["console_errors"].append(m.text))
    pg.on("pageerror", lambda e: res["console_errors"].append(str(e)))
    pg.on("request", lambda r: (not r.url.startswith("file://") and not r.url.startswith("data:"))
          and res["requests"].append(r.url))
    pg.goto(URL)
    pg.wait_for_function("window.__map !== undefined")
    pg.wait_for_timeout(800)
    
    n0 = pg.evaluate("__map.visibleArrowCount()")
    want0 = pg.evaluate("__map.frameCount('F')")
    root = next(f for f in plan if f["id"] == "F")
    want_plan = sum(not i["context"] for i in root["individuals"]) + len(root["clusters"])
    res["checks"]["initial_arrows"] = [n0, want0, want_plan]
    if not (n0 == want0 == want_plan):
        err(f"initial arrows {n0} vs province frame {want_plan}")
    res["checks"]["k_split"] = pg.evaluate("__map.kSplit()")
    
    for m in MODES:
        pg.evaluate(f"__map.setMode('{m}')")
        pg.wait_for_timeout(450)
        pg.screenshot(path=mpaths.writable(os.path.join(SHOTS, f"initial_{m}.png")))
        if pg.evaluate("location.hash") != f"#mode={m}":
            err(f"hash not updated for {m}")
    
    for m in ("WINNER", "PLQ", "CAQ", "QS"):
        pg.evaluate(f"__map.setMode('{m}')")
        for f in plan:
            pg.evaluate(f"__map.zoomToFrame('{f['id']}')")
            pg.wait_for_timeout(250)
            vis = set(pg.evaluate("__map.visibleRidingCodes()"))
            ind = {i["code"] for i in f["individuals"] if not i["context"]}
            if not ind <= vis:
                err(f"{m} frame {f['id']}: members not individual: {[M.NAME[c] for c in ind - vis]}")
            pg.screenshot(path=mpaths.writable(os.path.join(SHOTS, f"frame_{f['id']}_{m}.png")))
    
    pg.evaluate("__map.setZoom(80)")
    allv = pg.evaluate("__map.visibleRidingCodes()")
    res["checks"]["max_zoom_ridings"] = len(allv)
    if len(allv) != 127:
        err(f"max zoom shows {len(allv)} ridings")
    prev, mono = set(), True
    k = 1.0
    while k <= 80:
        pg.evaluate(f"__map.setZoom({k})")
        cur = set(pg.evaluate("__map.visibleRidingCodes()"))
        if not prev <= cur:
            mono = False
            err(f"LOD not monotone at k={k:.2f}")
        prev = cur
        k *= 1.15
    res["checks"]["lod_monotone"] = mono
    
    for f in plan:
        pg.evaluate(f"__map.zoomToFrame('{f['id']}')")
        pg.wait_for_timeout(100)
        pg.evaluate("__map.setZoom(80)")
        vis = set(pg.evaluate("__map.visibleRidingCodes()"))
        if not set(f["members"]) <= vis:
            err(f"max zoom over {f['id']}: missing members")
    
    random.seed(7)
    hov = []
    pg.evaluate("__map.setMode('WINNER')")
    for c in random.sample(M.CODES, 5):
        pg.evaluate(f"__map.zoomToRiding({c})")
        pg.wait_for_timeout(200)
        xy = pg.evaluate(f"__map.itemXY({c})")
        box = pg.locator("#mapwrap").bounding_box()
        pg.mouse.move(box["x"] + xy[0], box["y"] + xy[1])
        pg.wait_for_timeout(120)
        rows = pg.evaluate("""() => [...document.querySelectorAll('#tip tr[data-party]')].map(tr =>
            [tr.dataset.party, ...[...tr.querySelectorAll('td')].slice(1).map(td => td.textContent)])""")
        title = pg.evaluate("document.querySelector('#tip b') && document.querySelector('#tip b').textContent")
        r = M.sw.loc[c]
        ok = title.startswith(M.NAME[c]) and len(rows) == 5
        for p, a, b, s in rows:
            exp = [f1(r[p + "_2022"]) + "%", f1(r[p + "_2026"]) + "%", sgn(r[p + "_swing"])]
            if [a, b, s] != exp:
                ok = False
                err(f"tooltip {M.NAME[c]} {p}: {[a, b, s]} != {exp}")
        hov.append({"riding": M.NAME[c], "ok": ok, "rows": rows})
        pg.screenshot(path=mpaths.writable(os.path.join(SHOTS, f"hover_{c}.png")))
        pg.mouse.move(5, 5)
    res["checks"]["hover"] = hov
    
    pg.evaluate("__map.zoomToFrame('F')")
    pg.wait_for_timeout(900)
    pg.focus("#search")
    for _ in range(3):
        pg.keyboard.press("Tab")
    pg.wait_for_timeout(150)
    kb = pg.evaluate("document.activeElement.classList.contains('item') && getComputedStyle(document.querySelector('#tip')).display")
    res["checks"]["keyboard_tooltip"] = kb
    if kb != "block":
        err(f"keyboard tab to arrow did not show tooltip ({kb})")
    
    pg.fill("#search", "megantic")
    pg.wait_for_timeout(100)
    opts = pg.evaluate("[...document.querySelectorAll('#results li')].map(l => l.textContent)")
    res["checks"]["search_megantic"] = opts
    if "Mégantic" not in opts:
        err("accent-insensitive search failed")
    pg.keyboard.press("Enter")
    pg.wait_for_timeout(1000)
    pg.screenshot(path=mpaths.writable(os.path.join(SHOTS, "search_megantic.png")))
    
    pg.evaluate("__map.zoomToFrame('F')")
    pg.wait_for_timeout(900)
    res["checks"]["initial_labels"] = pg.evaluate("__map.labelled().length")
    
    pg.set_viewport_size({"width": 1280, "height": 720})
    pg.wait_for_timeout(500)
    pg.screenshot(path=mpaths.writable(os.path.join(SHOTS, "initial_1280x720.png")))
    if pg.evaluate("__map.visibleArrowCount()") != want_plan:
        err("1280x720 initial arrow count differs")
    
    pg.set_viewport_size({"width": 1440, "height": 900})
    pg.wait_for_timeout(500)
    pg.mouse.move(2, 2)
    rgb = lambda h: f"rgb({int(h[0:2], 16)}, {int(h[2:4], 16)}, {int(h[4:6], 16)})"
    UNSH = "rgb(252, 251, 255)"
    FILLS_JS = "() => [...document.querySelectorAll('path.riding')].map(p => [p.__data__.properties.code, getComputedStyle(p).fill])"

    def check_fills(m, tag):
        pg.evaluate(f"__map.setMode('{m}')")
        pg.wait_for_timeout(500)
        got = pg.evaluate(FILLS_JS)
        bad_ = []
        for c, fill in got:
            cat = None if m == "WINNER" else M.seat_cat(c, m)
            want = rgb(SHADE[m][cat]) if cat else UNSH
            if fill != want:
                bad_.append((c, fill, want))
        res["checks"].setdefault("fills", []).append({"mode": m, "tag": tag, "paths": len(got), "mismatches": len(bad_)})
        if len(got) != 127 or bad_:
            err(f"fills {tag} {m}: {len(got)} paths, {len(bad_)} mismatches {bad_[:3]}")
    for m in MODES:
        check_fills(m, "initial")
    for m in ("WINNER", "PLQ", "CAQ", "WINNER"):
        check_fills(m, "sequence")
    
    H2_PARTY = ["Gain or loss", "Arrow length = size of change", "Where ridings are too dense",
                "Seats won (riding shading)", "Notes"]
    for m in MODES:
        pg.evaluate(f"__map.setMode('{m}')")
        pg.wait_for_timeout(450)
        h2 = pg.evaluate("[...document.querySelectorAll('#panel h2')].map(h => h.textContent)")
        if m == "WINNER":
            if "Seats won (riding shading)" in h2:
                err("WINNER legend has a Seats won section")
            sub_ = pg.evaluate("document.querySelector('#subtitle').textContent")
            want_sub = "Change in winner\u2019s vote share 2022 \u2192 2026"
            res["checks"]["subtitle_codepoints"] = [hex(ord(ch)) for ch in sub_ if ord(ch) > 127]
            if [ord(ch) for ch in sub_] != [ord(ch) for ch in want_sub]:
                err(f"WINNER subtitle {sub_!r}")
        else:
            if h2 != H2_PARTY:
                err(f"{m} legend h2 sequence {h2}")
            rows = pg.evaluate("""() => [...document.querySelectorAll('.shade-key .row')].map(r => [r.dataset.cat,
                r.querySelector('.n').textContent, getComputedStyle(r.querySelector('.ssw')).backgroundColor,
                r.classList.contains('zero'), r.textContent])""")
            cnt = M.seat_counts(m)
            for cat, n_txt, bg, zero, text in rows:
                want_bg = rgb(SHADE[m][cat]) if cat != "none" else UNSH
                lab = SHADE_LABEL[None if cat == "none" else cat]
                if n_txt != f"({cnt[cat]})" or bg != want_bg or zero != (cnt[cat] == 0) or lab not in text:
                    err(f"{m} shade key row {cat}: {n_txt} {bg} zero={zero} vs {cnt[cat]} {want_bg}")
            if len(rows) != 4:
                err(f"{m}: {len(rows)} shade key rows")
            note = pg.evaluate("document.querySelector('.shade-key').nextElementSibling.textContent")
            if f"Shading uses the {m}'s colour." not in note:
                err(f"{m} shade note {note!r}")
            res["checks"].setdefault("shade_key", {})[m] = [[r_[0], r_[1]] for r_ in rows]
            
            arr = pg.evaluate("""() => [...document.querySelectorAll('#map g.item line.main')].filter(l => l.style.display !== 'none')
                .map(l => { const id = (l.getAttribute('marker-end') || '').slice(5, -1);
                  const mk = document.getElementById(id); const p = mk && mk.querySelector('path');
                  return [getComputedStyle(l).stroke, id, p ? getComputedStyle(p).fill : null]; })""")
            okc = {rgb(INK[m]): INK[m], rgb(LOSS_COL): LOSS_COL}
            badarr = [a_ for a_ in arr if a_[0] not in okc or a_[2] != a_[0] or a_[1][1:] != okc[a_[0]]]
            dots = pg.evaluate("""() => [...document.querySelectorAll('#map g.item circle.dot')].filter(c => c.style.display !== 'none')
                .map(c => getComputedStyle(c).fill)""")
            baddot = [d_ for d_ in dots if d_ not in okc]
            res["checks"].setdefault("arrows", {})[m] = {"lines": len(arr), "dots": len(dots), "bad": len(badarr) + len(baddot)}
            if badarr or baddot or not arr:
                err(f"{m} arrows: {len(badarr)} bad lines {badarr[:3]}, {len(baddot)} bad dots")
            foot = pg.evaluate("[...document.querySelectorAll('path.foot')].map(p => getComputedStyle(p).fillOpacity)")
            if any(float(v) != 0 for v in foot):
                err(f"{m} footprint fill-opacity {foot}")
    pg.evaluate("__map.setMode('WINNER')")
    pg.wait_for_timeout(450)
    foot = pg.evaluate("[...document.querySelectorAll('path.foot')].map(p => getComputedStyle(p).fillOpacity)")
    if not foot or any(abs(float(v) - 0.07) > 1e-6 for v in foot):
        err(f"WINNER footprint fill-opacity {foot}")
    
    pg.evaluate("__map.setMode('PLQ')")
    pg.wait_for_timeout(450)
    random.seed(11)
    hv = []
    for c in random.sample(M.CODES, 5):
        pg.evaluate(f"__map.zoomToRiding({c})")
        pg.wait_for_timeout(250)
        xy = pg.evaluate(f"__map.itemXY({c})")
        box = pg.locator("#mapwrap").bounding_box()
        pg.mouse.move(box["x"] + xy[0], box["y"] + xy[1])
        pg.wait_for_timeout(150)
        tiptxt = pg.evaluate("document.querySelector('#tip').textContent")
        want_line = f"PLQ: {SHADE_LABEL[M.seat_cat(c, 'PLQ')]}"
        ok = f"2022 winner: {M.sw.loc[c, 'winner_2022_notional']}" in tiptxt and want_line in tiptxt and \
            "notional" not in tiptxt.lower()
        hv.append({"riding": M.NAME[c], "ok": ok, "line": want_line})
        if not ok:
            err(f"PLQ tooltip {M.NAME[c]}: {tiptxt[:200]!r}")
        pg.mouse.move(2, 2)
    res["checks"]["hover_plq"] = hv
    
    pin = next(c for c in M.CODES if M.seat_cat(c, "PLQ") == "both")
    pg.evaluate(f"__map.zoomToFrame('F')")
    pg.wait_for_timeout(900)
    pg.fill("#search", M.NAME[pin])
    pg.wait_for_timeout(150)
    pg.keyboard.press("Enter")
    pg.wait_for_timeout(1300)
    pinned = pg.evaluate("document.querySelector('#tip').classList.contains('pinned')")
    res["checks"]["pinned_tooltip"] = [M.NAME[pin], pinned]
    if not pinned:
        err("pinned tooltip did not pin")
    pg.screenshot(path=mpaths.writable(os.path.join(SHOTS, "pinned_tooltip_PLQ.png")))
    pg.keyboard.press("Escape")
    
    pg.evaluate("__map.zoomToFrame('F')")
    pg.wait_for_timeout(900)
    pan = pg.evaluate("""() => { const p = document.querySelector('#panel'); const hs = [...p.querySelectorAll('h2')];
        const i = hs.findIndex(h => h.textContent === 'Notes'); const src = p.querySelector('.src');
        return {scrollH: p.scrollHeight, clientH: p.clientHeight, overflowY: getComputedStyle(p).overflowY,
                before_notes: i > 0 ? hs[i - 1].textContent : null, srcBottom: src.offsetTop + src.offsetHeight}; }""")
    pg.screenshot(path=mpaths.writable(os.path.join(SHOTS, "panel_PLQ_top.png")))
    pg.evaluate("document.querySelector('#panel').scrollTop = 1e6")
    pg.wait_for_timeout(150)
    src_vis = pg.evaluate("""() => { const p = document.querySelector('#panel').getBoundingClientRect();
        const s = document.querySelector('#panel .src').getBoundingClientRect(); return s.bottom <= p.bottom + 1 && s.top >= p.top; }""")
    pg.screenshot(path=mpaths.writable(os.path.join(SHOTS, "panel_PLQ_scrolled.png")))
    pan["src_visible_after_scroll"] = src_vis
    res["checks"]["panel_1440"] = pan
    if pan["before_notes"] != "Seats won (riding shading)" or not src_vis or pan["overflowY"] not in ("auto", "scroll"):
        err(f"panel layout {pan}")
    pg.evaluate("document.querySelector('#panel').scrollTop = 0")
    
    br.close()

bad_req = [u for u in res["requests"] if not any(a in u for a in ALLOWED)]
res["checks"]["external_requests"] = res["requests"]
if bad_req:
    err(f"network requests: {bad_req}")
if res["console_errors"]:
    err(f"console errors: {res['console_errors']}")
mb = os.path.getsize(HTML) / 1e6
res["checks"]["file_mb"] = round(mb, 2)
if mb > 4:
    err(f"file {mb:.2f} MB > 4")
json.dump(res, open(mpaths.writable(os.path.join(mpaths.BUILD, "html_test_results_desktop.json")), "w"), ensure_ascii=False, indent=1)
print(json.dumps(res["checks"], ensure_ascii=False, indent=1)[:3000])
print("ERRORS:", len(res["errors"]))
for e in res["errors"]:
    print("  ", e)
sys.exit(1 if res["errors"] else 0)
