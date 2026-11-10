pass
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from PIL import Image
import basemap as B, mapdata as M
from mapstyle import MAP_W, MAP_H, EMU_PER_IN
mode = sys.argv[1] if len(sys.argv) > 1 else "WINNER"
plan = json.load(open(os.path.join(M.MAPS, "plan/frames_plan.json")))["frames"]
D = os.path.join(M.MAPS, "debug"); os.makedirs(D, exist_ok=True)
for f in plan:
    p = B.render_basemap(f["extent"], [B.footprint(c["members"]) for c in f["clusters"]], os.path.join(D, "bm.png"), dpi=110)
    im = plt.imread(p); x0, y0, x1, y1 = f["extent"]; mpe = f["mpe"]
    fig = plt.figure(figsize=(MAP_W / EMU_PER_IN, MAP_H / EMU_PER_IN), dpi=110); ax = fig.add_axes([0, 0, 1, 1])
    ax.set_facecolor("#ECE7F7"); fig.patch.set_facecolor("#ECE7F7")
    ax.imshow(im, extent=[x0, x1, y0, y1]); ax.set_xlim(x0, x1); ax.set_ylim(y0, y1); ax.axis("off")
    items = [("riding", i["code"], i["x"], i["y"], 1.75, M.NAME[i["code"]]) for i in f["individuals"]] + \
            [("cluster", c["members"], c["x"], c["y"], 2.75, f"[{c['id']}] {len(c['members'])}") for c in f["clusters"]]
    for kind, ident, x, y, lw, lab in items:
        par, s, col = M.arrow_spec(kind, ident, mode)
        from mapstyle import arrow_ends
        (tx, ty), (hx, hy) = arrow_ends(0, 0, par, s)
        ax.annotate("", xy=(x + hx * mpe, y - hy * mpe), xytext=(x + tx * mpe, y - ty * mpe),
                    arrowprops=dict(arrowstyle="-|>", color="#" + col, lw=lw, mutation_scale=8))
        ax.plot([x], [y], "r.", ms=3)
        ax.text(x, y, lab, fontsize=4, color="#333")
    fig.savefig(os.path.join(D, f"plan_{f['id']}_{mode}.png")); plt.close(fig)
    print(f["id"])
