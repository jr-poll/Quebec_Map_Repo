pass
import glob, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import mpaths   
import numpy as np   
from PIL import Image   


def frac(p):
    a = np.asarray(Image.open(p).convert("RGB")).astype(float)
    a = a[int(a.shape[0] * 0.06):].reshape(-1, 3)
    p0, d = np.array([255., 255., 255.]), np.array([-22., -27., -8.])
    t = np.clip(((a - p0) @ d) / (d @ d), 0, 1.4)
    return float((np.linalg.norm(a - (p0 + t[:, None] * d), axis=1) > 10).mean())


res = {}
for tag in ("final", "mobile"):
    g = glob.glob(os.path.join(mpaths.SCREENS, f"ql_{tag}", "*.png"))
    res[tag] = {"thumbnail": os.path.relpath(g[0], mpaths.MOBILE) if g else None, "content_frac": round(frac(g[0]), 4) if g else None}
ok = bool(res["mobile"]["content_frac"] and res["mobile"]["content_frac"] >= 0.01)
res["ok"] = ok
json.dump(res, open(mpaths.writable(os.path.join(mpaths.BUILD, "quicklook.json")), "w"), indent=1)
print("QUICK LOOK:", res)
sys.exit(0 if ok else 1)
