pass
import os, unicodedata
import pandas as pd
from mapstyle import PARTIES, MODES, arrow_ends, arrow_colour, DOT_BELOW

MAPS = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.dirname(MAPS)
DATA = os.path.join(OUT, "data")
GEO = os.path.join(MAPS, "geo")
EPSG = 3798   

nfc = lambda s: unicodedata.normalize("NFC", s)

sw = pd.read_csv(os.path.join(DATA, "riding_swings.csv"))
sw["riding"] = sw.riding.map(nfc)
sw = sw.set_index("code", drop=False)
r26 = pd.read_csv(os.path.join(DATA, "qc2026_by_riding.csv")).set_index("code", drop=False)
t22 = pd.read_csv(os.path.join(DATA, "qc2022_transposed_2026map.csv")).set_index("code", drop=False)
CODES = sorted(sw.code.tolist())
NAME = dict(zip(sw.code, sw.riding))
assert len(CODES) == 127


def flag(code, party=None):
    pass
    r = sw.loc[code]
    if party and (not r[party + "_ran_2022"] or not r[party + "_ran_2026"]):
        return "*"
    if r.notional_baseline_flag:
        return "**"
    return ""


def riding_arrow(code, mode):
    pass
    r = sw.loc[code]
    party = r.winner_2026 if mode == "WINNER" else mode
    s = float(r[party + "_swing"])
    return party, s, arrow_colour(mode, party, s)


def agg(codes):
    pass
    codes = list(codes)
    a26, a22 = r26.loc[codes], t22.loc[codes]
    v26, v22 = a26.valid.sum(), a22.valid.sum()
    out = {"n": len(codes), "valid_2026": int(v26), "valid_2022": float(v22), "share_2022": {}, "share_2026": {},
           "swing": {}, "votes_2026": {}}
    for p in PARTIES:
        out["share_2026"][p] = 100 * a26[p + "_votes"].sum() / v26
        out["share_2022"][p] = 100 * a22[p + "_votes"].sum() / v22
        out["swing"][p] = out["share_2026"][p] - out["share_2022"][p]
        out["votes_2026"][p] = int(a26[p + "_votes"].sum())
    out["top_party"] = max(PARTIES, key=lambda p: out["votes_2026"][p])
    seats = sw.loc[codes].winner_2026.value_counts()
    out["seats"] = {p: int(seats.get(p, 0)) for p in PARTIES}
    return out


def cluster_arrow(codes, mode):
    a = agg(codes)
    party = a["top_party"] if mode == "WINNER" else mode
    s = a["swing"][party]
    return party, s, arrow_colour(mode, party, s), a


def arrow_spec(kind, ident, mode):
    pass
    if kind == "riding":
        return riding_arrow(ident, mode)
    p, s, c, _ = cluster_arrow(ident, mode)
    return p, s, c


def offsets(kind, ident):
    pass
    out = {}
    for m in MODES:
        p, s, _ = arrow_spec(kind, ident, m)
        out[m] = None if abs(s) < DOT_BELOW else arrow_ends(0, 0, p, s)
    return out



for c in CODES[::9]:
    a = agg([c])
    for p in PARTIES:
        assert abs(a["swing"][p] - sw.loc[c, p + "_swing"]) < 1e-3, (c, p)   
