pass
import glob, json, os, random, unicodedata
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D, RAW = os.path.join(ROOT, "data"), os.path.join(ROOT, "raw")
P = ["PQ", "PLQ", "CAQ", "QS", "PCQ", "OTH"]
out = []
def chk(name, ok, detail=""):
    out.append(f"| {name} | {'PASS' if ok else 'FAIL'} | {detail} |")

r26 = pd.read_csv(os.path.join(D, "qc2026_by_riding.csv"))
t22 = pd.read_csv(os.path.join(D, "qc2022_transposed_2026map.csv"))
o22 = pd.read_csv(os.path.join(D, "intermediate", "qc2022_by_riding_2022map.csv"))
prov = pd.read_csv(os.path.join(D, "intermediate", "official_province_parties.csv"))
hist = pd.read_csv(os.path.join(D, "qc_provincial_history_2003_2026.csv"))
sw = pd.read_csv(os.path.join(D, "riding_swings.csv"))

chk("2026: 127 ridings, unique codes", len(r26) == 127 and r26.code.is_unique, f"{len(r26)} rows")
chk("2022 transposed: 127 ridings, unique codes, same codes as 2026",
    len(t22) == 127 and t22.code.is_unique and set(t22.code) == set(r26.code), f"{len(t22)} rows")
chk("2026: all ridings final (résultats officiels)", r26["final"].all(), "isResultatsFinaux = true for all 127")
for y, df, col in (("2026", r26, "_votes"), ("2022 (2022 map)", o22, "_votes")):
    pp = prov[prov.year == int(y[:4])].groupby("party").votes.sum()
    diffs = {p: int(df[p + col].sum() - pp.get(p, 0)) for p in P}
    chk(f"{y}: riding sums = official province totals", all(v == 0 for v in diffs.values()), str(diffs))
pp22 = prov[prov.year == 2022].groupby("party").votes.sum()
rel = {p: round(100 * (t22[p + "_votes"].sum() / pp22[p] - 1), 6) for p in P}
chk("2022 transposed: province totals preserved (±0.1%)", all(abs(v) <= 0.1 for v in rel.values()), f"% diff {rel}")
unch = t22[t22.unchanged]
o22i = o22.set_index("code")
maxd = max(abs(r[p + "_votes"] - o22i.loc[r.main_pred_code22, p + "_votes"]) for _, r in unch.iterrows() for p in P)
chk("Unchanged ridings: transposed = official 2022 exactly", maxd < 1e-6, f"{len(unch)} unchanged ridings, max abs diff {maxd:.2e} votes")
s26 = r26[[p + "_pct" for p in P]].sum(axis=1); s22 = t22[[p + "_pct" for p in P]].sum(axis=1)
chk("Riding party % sum to ~100", ((s26 - 100).abs() < 1e-6).all() and ((s22 - 100).abs() < 1e-6).all(),
    f"max dev 2026 {abs(s26-100).max():.1e}, 2022 {abs(s22-100).max():.1e}")
seats = r26.winner.value_counts().to_dict()
off = prov[(prov.year == 2026) & (prov.seats > 0)].set_index("party").seats.to_dict()
chk("2026 winners/seat totals = official seat count", seats == off, f"computed {seats}; official {off}")
h26 = hist[hist.year == 2026].set_index("party")
chk("History 2026 row = riding file", all(h26.loc[p, "votes"] == r26[p + "_votes"].sum() for p in P[:-1]), "")
out_hdr = ["| Check | Result | Detail |", "|---|---|---|"]


random.seed(2026)
codes = random.sample(sorted(r26.code), 5)
spot = ["", "| Riding (code) | Party votes in resultats.json | Polling-station file total row | Match |", "|---|---|---|---|"]
files = {}
for f in glob.glob(os.path.join(RAW, "gen2026-10-05", "bv", "*.csv")):
    first = open(f, encoding="latin1").read().splitlines()[1].split(";")
    files[int(first[0])] = f
long26 = pd.read_csv(os.path.join(D, "qc2026_by_riding_long.csv"))
for c in codes:
    lines = open(files[c], encoding="latin1").read().splitlines()
    hdr = lines[0].split(";")
    tot = next(l.split(";") for l in lines if "Total de la circonscription" in l)
    i0, i1 = hdr.index("Électeurs inscrits") + 1, hdr.index("Bulletins valides")
    bv = sorted(int(tot[j]) for j in range(i0, i1))
    js = sorted(long26[long26.code == c].votes.tolist())
    rr = r26[r26.code == c].iloc[0]
    ok = bv == js and int(tot[i1]) == rr.valid and int(tot[i1 + 1]) == rr.rejected
    spot.append(f"| {rr.riding} ({c}) | {js[::-1]} valid={rr.valid} rej={rr.rejected} | {bv[::-1]} valid={tot[i1]} rej={tot[i1+1]} | {'yes' if ok else 'NO'} |")
print("\n".join(out_hdr + out + spot))
