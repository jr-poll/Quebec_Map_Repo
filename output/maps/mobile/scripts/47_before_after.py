pass
import json, os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import mpaths   

rep = {lab: json.load(open(os.path.join(mpaths.SCREENS, lab, "report.json")))["runs"] for lab in ("final", "mobile")}
idx = {lab: {(r["device"], r["scenario"]): r for r in runs} for lab, runs in rep.items()}
devices = list(dict.fromkeys(r["device"] for r in rep["mobile"]))
f0 = lambda v: "–" if v is None else f"{v:.0f}"


def cell(lab, dev):
    g = lambda s: idx[lab].get((dev, s), {})
    s1, s2, s4, s6, s8 = g("S1-http"), g("S2"), g("S4"), g("S6"), g("S8")
    wh = s1.get("wrap", [0, 0, 0, None])[3] if s1.get("wrap") else None
    s8d = s8.get("s8") or {}
    errs = sum(len(g(s).get("page_errors", [])) for s in ("S1-file", "S1-http", "S3", "S4", "S5", "S6", "S7", "S8", "S9", "S10"))
    nf = sum(bool(r["failures"]) for (d, s), r in idx[lab].items() if d == dev)
    return [f0(s1.get("header")), f0(wh), f0(s1.get("minTarget")), f0(s1.get("searchFont")),
            f"{100 * s2.get('nonbg', 0):.0f}%", f0(s4.get("t127_s4")),
            f0(s6.get("wrap", [0, 0, 0, None])[3] if s6.get("wrap") else None),
            "–" if not s8d else f"{s8d['before']['k']:.1f}→{s8d['after']['k']:.1f}", str(errs), str(nf)]


hdr = ["Header px", "Map h px", "Min target", "Search px", "No-JS map", "Map visible, slow fonts (ms)", "Map h in 320px iframe",
       "Zoom k after URL-bar resize", "Page errors", "Failing runs"]
lines = ["| Device | File | " + " | ".join(hdr) + " |", "|---|---|" + "---|" * len(hdr)]
for d in devices:
    for lab in ("final", "mobile"):
        lines.append(f"| {d} | {'FINAL' if lab == 'final' else 'mobile'} | " + " | ".join(cell(lab, d)) + " |")
tot = {lab: (len(rep[lab]), sum(bool(r["failures"]) for r in rep[lab])) for lab in rep}
lines += ["", f"Runs: FINAL {tot['final'][0]} ({tot['final'][1]} failing), mobile {tot['mobile'][0]} ({tot['mobile'][1]} failing)."]
md = "\n".join(lines) + "\n"
open(mpaths.writable(os.path.join(mpaths.BUILD, "before_after.md")), "w", encoding="utf-8").write(md)
print(md)
