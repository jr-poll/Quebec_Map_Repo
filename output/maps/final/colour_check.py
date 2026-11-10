pass
import os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mapstyle import PARTIES, INK, LOSS_COL, SHADE, SHADE_ALPHA, LAND_QC, COL   

MIN_CONTRAST, MIN_DE = 3.0, 8.0


def _rgb(h):
    return [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]


def _lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def luminance(h):
    r, g, b = (_lin(c) for c in _rgb(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(h1, h2):
    l1, l2 = sorted((luminance(h1), luminance(h2)), reverse=True)
    return (l1 + 0.05) / (l2 + 0.05)


def lab(h):
    r, g, b = (_lin(c) for c in _rgb(h))
    X = 0.4124564 * r + 0.3575761 * g + 0.1804375 * b
    Y = 0.2126729 * r + 0.7151522 * g + 0.0721750 * b
    Z = 0.0193339 * r + 0.1191920 * g + 0.9503041 * b
    Xn, Yn, Zn = 0.95047, 1.0, 1.08883
    f = lambda t: t ** (1 / 3) if t > (6 / 29) ** 3 else t / (3 * (6 / 29) ** 2) + 4 / 29
    fx, fy, fz = f(X / Xn), f(Y / Yn), f(Z / Zn)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def delta_e(h1, h2):
    return sum((a - b) ** 2 for a, b in zip(lab(h1), lab(h2))) ** 0.5


def table():
    rows = []
    for p in PARTIES:
        t = SHADE[p]
        rows.append({
            "party": p, "col": COL[p], "ink": INK[p], "both": t["both"], "gain26": t["gain26"], "lost22": t["lost22"],
            "ink_vs": {k: contrast(INK[p], v) for k, v in (("both", t["both"]), ("gain26", t["gain26"]),
                                                            ("lost22", t["lost22"]), ("base", LAND_QC))},
            "loss_vs": {k: contrast(LOSS_COL, t[k]) for k in ("both", "gain26", "lost22")},
            "dE": {"base-lost22": delta_e(LAND_QC, t["lost22"]), "lost22-gain26": delta_e(t["lost22"], t["gain26"]),
                   "gain26-both": delta_e(t["gain26"], t["both"])},
        })
    return rows


def check():
    rows = table()
    fails = []
    for r in rows:
        for k, v in r["ink_vs"].items():
            if v < MIN_CONTRAST:
                fails.append(f"{r['party']} ink vs {k} {v:.2f}")
        for k, v in r["loss_vs"].items():
            if v < MIN_CONTRAST:
                fails.append(f"{r['party']} loss vs {k} {v:.2f}")
        for k, v in r["dE"].items():
            if v < MIN_DE:
                fails.append(f"{r['party']} dE {k} {v:.2f}")
    assert not fails, "colour check failed: " + "; ".join(fails)
    return rows


def markdown(rows):
    out = [f"Alphas: both {SHADE_ALPHA['both']}, gain26 {SHADE_ALPHA['gain26']}, lost22 {SHADE_ALPHA['lost22']} "
           f"(mixed with `{LAND_QC}`); loss colour `{LOSS_COL}`.", "",
           "| Party | Colour | Ink | Both | 2026 only | 2022 only | Ink vs both / 2026 / 2022 / base | "
           "Loss vs both / 2026 / 2022 | ΔE base↔2022 / 2022↔2026 / 2026↔both |",
           "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        iv, lv, de = r["ink_vs"], r["loss_vs"], r["dE"]
        out.append(f"| {r['party']} | `{r['col']}` | `{r['ink']}` | `{r['both']}` | `{r['gain26']}` | `{r['lost22']}` | "
                   f"{iv['both']:.2f} / {iv['gain26']:.2f} / {iv['lost22']:.2f} / {iv['base']:.2f} | "
                   f"{lv['both']:.2f} / {lv['gain26']:.2f} / {lv['lost22']:.2f} | "
                   f"{de['base-lost22']:.1f} / {de['lost22-gain26']:.1f} / {de['gain26-both']:.1f} |")
    allc = [v for r in rows for v in r["ink_vs"].values()]
    allL = [v for r in rows for v in r["loss_vs"].values()]
    allD = [v for r in rows for v in r["dE"].values()]
    out += ["", f"Minimums: ink contrast {min(allc):.2f}:1, loss contrast {min(allL):.2f}:1, ΔE {min(allD):.2f} "
                f"(thresholds 3.0, 3.0, 8)."]
    return "\n".join(out)


ROWS = check()   

if __name__ == "__main__":
    import paths
    md = markdown(ROWS)
    print(md)
    open(paths.writable(os.path.join(paths.BUILD, "colour_table.md")), "w", encoding="utf-8").write(md + "\n")
    print("COLOUR CHECK: PASS")
