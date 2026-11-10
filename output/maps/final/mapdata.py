pass
import os, unicodedata
import pandas as pd
from mapstyle import PARTIES, MODES, arrow_ends, arrow_colour, DOT_BELOW

import paths
MAPS = paths.SRC_MAPS          
OUT = paths.OUT_ROOT
DATA = paths.DATA
GEO = paths.GEO
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



def seat_cat(code, party):
    pass
    r = sw.loc[code]
    w22, w26 = r.winner_2022_notional == party, r.winner_2026 == party
    if w22 and w26:
        return "both"
    if w26:
        return "gain26"
    if w22:
        return "lost22"
    return None


def seat_counts(party, codes=None):
    pass
    out = {"both": 0, "gain26": 0, "lost22": 0, "none": 0}
    for c in (CODES if codes is None else codes):
        out[seat_cat(c, party) or "none"] += 1
    return out


_EXPECT = {"PQ": (3, 57, 0, 67), "PLQ": (21, 18, 0, 88), "CAQ": (0, 0, 92, 35), "QS": (9, 0, 2, 116),
           "PCQ": (0, 19, 0, 108)}
for _p, _e in _EXPECT.items():
    _c = seat_counts(_p)
    assert (_c["both"], _c["gain26"], _c["lost22"], _c["none"]) == _e, (_p, _c, _e)
assert sw.winner_2022_notional.value_counts().to_dict() == {"CAQ": 92, "PLQ": 21, "QS": 11, "PQ": 3}
assert sw.winner_2026.value_counts().to_dict() == {"PQ": 60, "PLQ": 39, "PCQ": 19, "QS": 9}
