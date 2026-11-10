pass
import json, math, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import mpaths   
from mserve import Server   
from playwright.sync_api import sync_playwright   

CLONE_JS = r"""() => {
  const [W, H] = __map.size();
  const svg = document.getElementById("map").cloneNode(true);
  svg.querySelectorAll(".hit").forEach(n => n.remove());
  const all = [svg, ...svg.querySelectorAll("*")];
  for (const el of all) {
    if (el !== svg) {
      el.removeAttribute("tabindex"); el.removeAttribute("role");
      [...el.attributes].filter(a => a.name.startsWith("aria-")).forEach(a => el.removeAttribute(a.name));
    }
    if (el.style && el.style.opacity === "1") el.style.removeProperty("opacity");
    if (el.getAttribute("style") === "") el.removeAttribute("style");
  }
  [...svg.attributes].filter(a => a.name.startsWith("aria-")).forEach(a => svg.removeAttribute(a.name));
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  svg.setAttribute("preserveAspectRatio", "xMidYMid meet");
  svg.removeAttribute("width"); svg.removeAttribute("height");
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", "Static map: 2026 winner's change, province view");
  for (const el of all) {
    if (el.id) el.id = "fb-" + el.id;
    for (const a of [...el.attributes]) if (a.value.includes("url(#")) el.setAttribute(a.name, a.value.replace(/url\(#/g, "url(#fb-"));
  }
  // legend: rewrite its marker references to "fbl-" copies kept in a hidden <defs> (separate prefix: no duplicate ids)
  const panel = document.getElementById("panel");
  let legend = panel.innerHTML;
  const need = new Set([...legend.matchAll(/url\(#([^)]+)\)/g)].map(m => m[1]));
  legend = legend.replace(/url\(#/g, "url(#fbl-");
  const marks = [...need].map(id => { const m = document.getElementById(id).cloneNode(true); m.id = "fbl-" + id; return m.outerHTML; });
  legend += `<svg width="0" height="0" aria-hidden="true" focusable="false" style="position:absolute"><defs>${marks.join("")}</defs></svg>`;
  return {svg: svg.outerHTML, legend, subtitle: document.getElementById("subtitle").textContent,
          W, H, mode: __map.mode(), k: __map.zoomK(), arrows: __map.visibleArrowCount(), frameF: __map.frameCount("F"),
          labels: __map.labelled().length, fonts: document.fonts ? document.fonts.status : "n/a",
          openSans: document.fonts ? document.fonts.check('11px "Open Sans"') : null};
}"""

NUM_ATTRS = ("d", "transform", "x", "y", "x1", "y1", "x2", "y2", "r", "viewBox")
num = re.compile(r"-?\d*\.\d+(?:e[-+]?\d+)?|-?\d+e[-+]?\d+")


def r1(m):
    v = round(float(m.group(0)), 1)
    s = f"{v:.1f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


THIN_PX = 0.5   


def thin(d, tol=THIN_PX):
    pass
    out = []
    for sub in re.findall(r"M[^M]*", d):
        closed = sub.rstrip().endswith(("z", "Z"))
        pts = [tuple(map(float, q.split(","))) for q in
               re.findall(r"-?[\d.]+(?:e[-+]?\d+)?,-?[\d.]+(?:e[-+]?\d+)?", sub)]
        if not pts:
            continue
        keep = [pts[0]]
        for q in pts[1:-1]:
            if math.dist(q, keep[-1]) >= tol:
                keep.append(q)
        if len(pts) > 1:
            keep.append(pts[-1])
        xs, ys = [q[0] for q in keep], [q[1] for q in keep]
        if closed and max(xs) - min(xs) < 0.8 and max(ys) - min(ys) < 0.8:
            continue
        out.append("M" + "L".join(f"{x},{y}" for x, y in keep) + ("Z" if closed else ""))
    return "".join(out)


def round_attrs(svg):
    svg = re.sub(r' d="([^"]*)"', lambda m: ' d="%s"' % thin(m.group(1)), svg)
    pat = re.compile(r'\b(%s)="([^"]*)"' % "|".join(NUM_ATTRS))
    return pat.sub(lambda m: f'{m.group(1)}="{num.sub(r1, m.group(2))}"', svg)


with Server() as srv, sync_playwright() as pw:
    br = pw.chromium.launch()
    ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=1, is_mobile=True, has_touch=True)
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(srv.url(mpaths.PASS1))
    pg.wait_for_function("window.__map !== undefined && __map.booted()")
    pg.evaluate("document.fonts ? document.fonts.ready.then(() => 1) : 1")
    pg.evaluate("new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")
    pg.wait_for_timeout(600)   
    assert pg.evaluate("__map.mode()") == "WINNER" and abs(pg.evaluate("__map.zoomK()") - 1) < 1e-9
    snap = pg.evaluate(CLONE_JS)
    pg.screenshot(path=mpaths.writable(os.path.join(mpaths.BUILD, "fallback_snapshot.png")))
    br.close()
assert not errs, errs
raw = len(snap["svg"])
snap["svg"] = round_attrs(snap["svg"])
n_rid = len(re.findall(r'<path[^>]*class="riding[" ]', snap["svg"]))
n_it = len(re.findall(r'<g[^>]*class="item[" ]', snap["svg"]))
assert n_rid == 127 and n_it == snap["frameF"] == snap["arrows"], (n_rid, n_it, snap["frameF"], snap["arrows"])
assert 'id="map"' not in snap["svg"] and "url(#m" not in snap["svg"]
out = {k: snap[k] for k in ("svg", "legend", "subtitle")}
meta = {k: v for k, v in snap.items() if k not in out}
meta.update(svg_bytes_raw=raw, svg_bytes=len(snap["svg"].encode()), legend_bytes=len(snap["legend"].encode()),
            ridings=n_rid, arrows=n_it)
out["meta"] = meta
json.dump(out, open(mpaths.writable(mpaths.FALLBACK), "w", encoding="utf-8"), ensure_ascii=False)
print("fallback snapshot:", json.dumps(meta, ensure_ascii=False))
