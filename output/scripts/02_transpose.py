pass
import os, re
import numpy as np
import pandas as pd
import geopandas as gpd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW, DATA = os.path.join(ROOT, "raw"), os.path.join(ROOT, "data")
INT = os.path.join(DATA, "intermediate")
P = ["PQ", "PLQ", "CAQ", "QS", "PCQ", "OTH"]
COLS = P + ["valid", "rejected", "electors"]
SLIVER = 0.01

bv = pd.read_csv(os.path.join(INT, "qc2022_bv_long.csv"), dtype={"sv": str})
bv["regr"] = bv["regr"].fillna("")


sv = bv[bv.kind == "SV"].copy()
sv["base"] = sv.sv.str.extract(r"^(\d+)")[0].astype(int)
lead = {}
for r in sv.itertuples():
    m = re.match(r"Regr\. BVO-(\d+)", r.regr)
    lead[(r.code22, r.base)] = int(m.group(1)) if m else r.base


def resolve(code, n, depth=0):
    nxt = lead.get((code, n), n)
    return n if nxt == n or depth > 10 else resolve(code, nxt, depth + 1)


sv["unit"] = [resolve(c, b) for c, b in zip(sv.code22, sv.base)]

units = sv.groupby(["code22", "unit"])[COLS].sum().reset_index()

g22 = gpd.read_file(os.path.join(RAW, "geo/sections_vote_2022_shapefile/Section_de_vote.shp"))
g22 = g22[g22.NO_SV_VG != 999].copy()
g22["base"] = g22.NO_SV_VG.astype(int)
g22["unit"] = [resolve(c, b) for c, b in zip(g22.CO_CEP_VG, g22.base)]
g22 = g22.rename(columns={"CO_CEP_VG": "code22"})
gu = g22.dissolve(by=["code22", "unit"]).reset_index()[["code22", "unit", "geometry"]]
gu["geometry"] = gu.geometry.buffer(0)

g26sv = gpd.read_file(os.path.join(RAW, "geo/sections_vote_2026_shapefile/sections_de_vote_15_07_2026_shapefile.shp"))
g26sv = g26sv.to_crs(gu.crs)[["CO_CEP", "ELEC_2026", "geometry"]].copy()
g26sv["geometry"] = g26sv.geometry.buffer(0)
g26sv["a26"] = g26sv.geometry.area
g26sv["ELEC_2026"] = g26sv["ELEC_2026"].fillna(0).astype(float)


ov = gpd.overlay(gu, g26sv, how="intersection", keep_geom_type=True)
ov["area"] = ov.geometry.area
ov["w_el"] = ov.ELEC_2026 * ov.area / ov.a26
w = ov.groupby(["code22", "unit", "CO_CEP"]).agg(area=("area", "sum"), w_el=("w_el", "sum")).reset_index()
tot = w.groupby(["code22", "unit"])[["area", "w_el"]].transform("sum")
w["f_area"] = w.area / tot.area
w["f_el"] = np.where(tot.w_el > 0, w.w_el / tot.w_el.replace(0, np.nan), np.nan)
w["f"] = w.f_el.fillna(w.f_area)
w = w[(w.f >= SLIVER) & (w.f_area >= 0.001)].copy()   
w["f"] = w.f / w.groupby(["code22", "unit"]).f.transform("sum")
w = w[["code22", "unit", "CO_CEP", "f"]].rename(columns={"CO_CEP": "code26"})


r22 = gpd.read_file(os.path.join(RAW, "geo/circonscriptions_electorales_2022_shapefile/Circonscription_electorale_2022_shapefile.shp"))
r26 = gpd.read_file(os.path.join(RAW, "geo/circonscriptions_electorales_2026_shapefile/circonscriptions_électorales_2026_shapefile/Circonscription_electorales_2026_shapefile.shp")).to_crs(r22.crs)
r22["geometry"], r26["geometry"] = r22.buffer(0), r26.buffer(0)
inter = gpd.overlay(r22[["CO_CEP", "geometry"]].rename(columns={"CO_CEP": "c22"}),
                    r26[["CO_CEP", "geometry"]].rename(columns={"CO_CEP": "c26"}), how="intersection")
inter["ia"] = inter.area
a22, a26 = r22.set_index("CO_CEP").area, r26.set_index("CO_CEP").area
inter["iou"] = inter.ia / (inter.c22.map(a22) + inter.c26.map(a26) - inter.ia)
same = inter[inter.iou >= 0.995][["c22", "c26", "iou"]]
same.to_csv(os.path.join(INT, "unchanged_ridings_geometry.csv"), index=False)
pin = dict(zip(same.c22, same.c26))
w = w[~w.code22.isin(pin)]

w = w[~w.code26.isin(list(pin.values()))].copy()
w["f"] = w.f / w.groupby(["code22", "unit"]).f.transform("sum")
pinned = units[units.code22.isin(pin)][["code22", "unit"]].copy()
pinned["code26"], pinned["f"] = pinned.code22.map(pin), 1.0
w = pd.concat([w, pinned], ignore_index=True)
print("geometrically unchanged ridings:", len(pin))

missing = units.merge(w[["code22", "unit"]].drop_duplicates(), how="left", indicator=True)
missing = missing[missing._merge == "left_only"]
if len(missing):
   
    print("WARNING units without geometry:", len(missing), missing.valid.sum())

alloc = units.merge(w, on=["code22", "unit"])
for c in COLS:
    alloc[c] = alloc[c] * alloc.f
ord26 = alloc.groupby(["code22", "code26"])[COLS].sum()  


def parse_svlist(label):
    m = re.search(r"SV no (.*)$", label)
    if not m:
        return None
    out = []
    for part in m.group(1).split(","):
        part = part.strip()
        r = re.match(r"^(\d+)\w?\s*à\s*(\d+)\w?$", part)
        if r:
            out += list(range(int(r.group(1)), int(r.group(2)) + 1))
        elif re.match(r"^\d+\w?$", part):
            out.append(int(re.match(r"^(\d+)", part).group(1)))
        else:
            return None
    return out


unit_alloc = alloc.set_index(["code22", "unit"])
adv_rows, adv_fallback = [], 0
for r in bv[bv.kind == "BVA"].itertuples():
    svs = parse_svlist(r.label)
    sub = None
    if svs:
        us = sorted({resolve(r.code22, s) for s in svs})
        keys = [(r.code22, u) for u in us if (r.code22, u) in unit_alloc.index]
        if keys:
            sub = unit_alloc.loc[keys].groupby("code26")[P + ["valid"]].sum()
    if sub is None or sub.valid.sum() == 0:
        adv_fallback += 1
        sub = ord26.loc[r.code22][P + ["valid"]]
    for code26, row in sub.iterrows():
        rec = {"code22": r.code22, "code26": code26}
        for p in P:
            share = row[p] / sub[p].sum() if sub[p].sum() > 0 else row.valid / sub.valid.sum()
            rec[p] = getattr(r, p) * share
        rec["rejected"] = r.rejected * row.valid / sub.valid.sum()
        adv_rows.append(rec)
adv = pd.DataFrame(adv_rows)
adv["valid"] = adv[P].sum(axis=1)
adv["electors"] = 0.0
adv26 = adv.groupby(["code22", "code26"])[COLS].sum()


base = ord26.add(adv26, fill_value=0)
spec = bv[bv.kind == "SPECIAL"].groupby("code22")[COLS].sum()
sp_rows = []
for code22, row in spec.iterrows():
    b = base.loc[code22]
    for code26, br in b.iterrows():
        rec = {"code22": code22, "code26": code26}
        for p in P:
            rec[p] = row[p] * (br[p] / b[p].sum() if b[p].sum() > 0 else br.valid / b.valid.sum())
        rec["rejected"] = row.rejected * br.valid / b.valid.sum()
        rec["electors"] = row.electors * br.electors / b.electors.sum() if b.electors.sum() else 0
        sp_rows.append(rec)
sp = pd.DataFrame(sp_rows)
sp["valid"] = sp[P].sum(axis=1)
sp26 = sp.groupby(["code22", "code26"])[COLS].sum()

portion = base.add(sp26, fill_value=0).reset_index()
portion.to_csv(os.path.join(INT, "transposition_portions_2022to2026.csv"), index=False)


names26 = pd.read_csv(os.path.join(DATA, "qc2026_by_riding.csv"))[["code", "riding"]]
off22 = pd.read_csv(os.path.join(INT, "qc2022_by_riding_2022map.csv"))
names22 = off22.set_index("code").riding
t = portion.groupby("code26")[COLS].sum()

portion["share_of_26"] = portion.valid / portion.groupby("code26").valid.transform("sum")
portion["share_of_22"] = portion.valid / portion.groupby("code22").valid.transform("sum")
main = portion.sort_values("share_of_26", ascending=False).groupby("code26").head(1).set_index("code26")
t["main_pred_code22"] = main.code22
t["main_pred_riding22"] = main.code22.map(names22)
t["main_pred_share"] = main.share_of_26
t["main_pred_share_of_22"] = main.share_of_22
t["n_pred"] = portion[portion.share_of_26 >= 0.005].groupby("code26").size()
t["unchanged"] = t.index.isin(list(pin.values()))
t = t.reset_index().rename(columns={"code26": "code"}).merge(names26, on="code")
for p in P:
    t[f"{p}_votes"] = t.pop(p)
    t[f"{p}_pct"] = 100 * t[f"{p}_votes"] / t.valid
t["turnout_pct_notional"] = 100 * (t.valid + t.rejected) / t.electors
t["winner_notional"] = t[[f"{p}_votes" for p in P[:-1]]].idxmax(axis=1).str.replace("_votes", "")
t["method"] = "own calculation (2022 polling-division results x 2026 boundaries, elector-weighted)"
cols = ["code", "riding", "valid", "rejected", "electors", "turnout_pct_notional"] + \
       [f"{p}_votes" for p in P] + [f"{p}_pct" for p in P] + \
       ["winner_notional", "main_pred_code22", "main_pred_riding22", "main_pred_share",
        "main_pred_share_of_22", "n_pred", "unchanged", "method"]
t = t[cols].sort_values("riding")
t.to_csv(os.path.join(DATA, "qc2022_transposed_2026map.csv"), index=False, encoding="utf-8")
print("ridings:", len(t), "| advance-poll fallbacks:", adv_fallback,
      "| unchanged:", int(t.unchanged.sum()))
print(t.winner_notional.value_counts().to_dict())
