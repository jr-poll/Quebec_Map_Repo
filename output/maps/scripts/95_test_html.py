pass
import json, os, random, sys
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
MAPS = os.path.dirname(HERE)
sys.path.insert(0, MAPS)
import mapdata as M   
from mapstyle import MODES, PARTIES   

HTML = os.path.join(MAPS, "Quebec_2026_Swing_Map.html")
SHOTS = os.path.join(MAPS, "html_screens")
os.makedirs(SHOTS, exist_ok=True)
for f in os.listdir(SHOTS):
    if f.endswith(".png"):
        os.remove(os.path.join(SHOTS, f))
URL = "file://" + HTML
plan = json.load(open(os.path.join(MAPS, "plan/frames_plan.json")))["frames"]
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
        pg.screenshot(path=os.path.join(SHOTS, f"initial_{m}.png"))
        if pg.evaluate("location.hash") != f"#mode={m}":
            err(f"hash not updated for {m}")
    
    for m in ("WINNER", "PLQ"):
        pg.evaluate(f"__map.setMode('{m}')")
        for f in plan:
            pg.evaluate(f"__map.zoomToFrame('{f['id']}')")
            pg.wait_for_timeout(250)
            vis = set(pg.evaluate("__map.visibleRidingCodes()"))
            ind = {i["code"] for i in f["individuals"] if not i["context"]}
            if not ind <= vis:
                err(f"{m} frame {f['id']}: members not individual: {[M.NAME[c] for c in ind - vis]}")
            pg.screenshot(path=os.path.join(SHOTS, f"frame_{f['id']}_{m}.png"))
    
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
        pg.screenshot(path=os.path.join(SHOTS, f"hover_{c}.png"))
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
    pg.screenshot(path=os.path.join(SHOTS, "search_megantic.png"))
    
    pg.evaluate("__map.zoomToFrame('F')")
    pg.wait_for_timeout(900)
    res["checks"]["initial_labels"] = pg.evaluate("__map.labelled().length")
    
    pg.set_viewport_size({"width": 1280, "height": 720})
    pg.wait_for_timeout(500)
    pg.screenshot(path=os.path.join(SHOTS, "initial_1280x720.png"))
    if pg.evaluate("__map.visibleArrowCount()") != want_plan:
        err("1280x720 initial arrow count differs")
    
    ph = br.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
    ph.on("console", lambda m: m.type == "error" and res["console_errors"].append("phone: " + m.text))
    ph.goto(URL + "#mode=PLQ")
    ph.wait_for_function("window.__map !== undefined")
    ph.wait_for_timeout(800)
    ph.screenshot(path=os.path.join(SHOTS, "phone_initial.png"))
    small = ph.evaluate("""() => [...document.querySelectorAll('button')].filter(b => b.offsetParent)
        .map(b => b.getBoundingClientRect().height).filter(h => h < 40).length""")
    res["checks"]["phone_buttons_lt_40px"] = small
    if small:
        err(f"{small} phone buttons shorter than 40 px")
    ph.click("#legendToggle")
    ph.wait_for_timeout(400)
    ph.screenshot(path=os.path.join(SHOTS, "phone_legend.png"))
    sw_ = ph.evaluate("document.documentElement.scrollWidth")
    if sw_ > 390:
        err(f"phone horizontal overflow {sw_}")
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
json.dump(res, open(os.path.join(MAPS, "build/html_test_results.json"), "w"), ensure_ascii=False, indent=1)
print(json.dumps(res["checks"], ensure_ascii=False, indent=1)[:3000])
print("ERRORS:", len(res["errors"]))
for e in res["errors"]:
    print("  ", e)
sys.exit(1 if res["errors"] else 0)
