pass
import json, glob, os, re, unicodedata
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, "raw")
DATA = os.path.join(ROOT, "data")
INT = os.path.join(DATA, "intermediate")
os.makedirs(INT, exist_ok=True)


PARTY_BY_NUM = {8: "PQ", 6: "PLQ", 27: "CAQ", 40: "QS", 22: "PCQ"}
PARTIES = ["PQ", "PLQ", "CAQ", "QS", "PCQ"]


def nfc(s):
    return unicodedata.normalize("NFC", s) if isinstance(s, str) else s


def official_names(year):
    import geopandas as gpd
    f = {"2026": "geo/circonscriptions_electorales_2026_shapefile/circonscriptions_électorales_2026_shapefile/Circonscription_electorales_2026_shapefile.shp",
         "2022": "geo/circonscriptions_electorales_2022_shapefile/Circonscription_electorale_2022_shapefile.shp"}[year]
    g = gpd.read_file(os.path.join(RAW, f), ignore_geometry=True)
    return {int(c): nfc(n) for c, n in zip(g.CO_CEP, g.NM_CEP)}


def parse_json(year_dir):
    d = json.load(open(os.path.join(RAW, year_dir, "resultats.json"), encoding="utf-8"))
    rows, wide = [], []
    names = official_names(year_dir[3:7])
    for c in d["circonscriptions"]:
        code = c["numeroCirconscription"]
        name = names[code]
        assert name.replace("–", "-").replace("—", "-") == nfc(c["nomCirconscription"]).replace("–", "-").replace("—", "-"), (name, c["nomCirconscription"])
        w = {"code": code, "riding": name, "final": c["isResultatsFinaux"],
             "valid": c["nbVoteValide"], "rejected": c["nbVoteRejete"],
             "cast": c["nbVoteExerce"], "electors": c["nbElecteurInscrit"],
             "turnout_pct": float(str(c["tauxParticipation"]).replace(",", "."))}
        for p in PARTIES + ["OTH"]:
            w[f"{p}_votes"] = 0
        best = None
        for k in c["candidats"]:
            num = k["numeroPartiPolitique"]
            p = PARTY_BY_NUM.get(num, "OTH")
            v = k["nbVoteTotal"]
            rows.append({"code": code, "riding": name, "party_num": num,
                         "party_abbr": nfc(k["abreviationPartiPolitique"]), "party": p,
                         "candidate": nfc(f'{k["prenom"]} {k["nom"]}'), "votes": v,
                         "pct": k["tauxVote"]})
            w[f"{p}_votes"] += v
            if best is None or v > best[1]:
                best = (p if p != "OTH" else nfc(k["abreviationPartiPolitique"]), v,
                        nfc(f'{k["prenom"]} {k["nom"]}'))
        for p in PARTIES:
            w[f"{p}_ran"] = any(r["party"] == p for r in rows if r["code"] == code)
            w[f"{p}_pct"] = 100 * w[f"{p}_votes"] / w["valid"]
        w["OTH_pct"] = 100 * w["OTH_votes"] / w["valid"]
        w["winner"], w["winner_candidate"] = best[0], best[2]
        wide.append(w)
    return d["statistiques"], pd.DataFrame(wide), pd.DataFrame(rows)


def parse_bv_2022():
    pass
    cand = pd.read_csv(os.path.join(RAW, "gen2022-10-03", "candidats.csv"), sep=";",
                       encoding="latin1", dtype=str)
    cand.columns = ["code", "cand_num", "nom", "prenom", "party_num", "abbr", "votes", "pct", "adv"]
    out = []
    for f in sorted(glob.glob(os.path.join(RAW, "gen2022-10-03", "bv", "*.csv"))):
        lines = open(f, encoding="latin1").read().splitlines()
        header = lines[0].split(";")
        body = [l.split(";") for l in lines[1:] if l.strip()]
        code = int(body[0][0])
        cc = cand[cand.code == str(code)]
        
        i0, i1 = header.index("É.I.") + 1, header.index("B.V.")
        colparty = {}
        for j in range(i0, i1):
            h = nfc(header[j])
            
            m = None
            for _, r in cc.iterrows():
                if h.endswith(" " + nfc(r.abbr)) and h.startswith(nfc(r.nom)):
                    m = r; break
            if m is None:
                for _, r in cc.iterrows():
                    if h.endswith(" " + nfc(r.abbr)):
                        m = r; break
            if m is None:
                raise ValueError(f"no party for column {h} in {f}")
            colparty[j] = PARTY_BY_NUM.get(int(m.party_num), "OTH")
        for r in body:
            if len(r) < i1 + 2:
                continue  
            label, secteur, regr, sv = nfc(r[4]), r[5], nfc(r[6]), r[7].strip()
            try:
                votes = {j: int(r[j] or 0) for j in range(i0, i1)}
                valid, rej = int(r[i1] or 0), int(r[i1 + 1] or 0)
                el = int(r[8] or 0)
            except ValueError:
                continue
            if label.startswith("Total de la circonscription"):
                kind = "TOTAL"
            elif sv:
                kind = "SV"
            elif re.match(r"^BVA\d+", label):
                kind = "BVA"
            else:
                kind = "SPECIAL"
            agg = {p: 0 for p in PARTIES + ["OTH"]}
            for j, v in votes.items():
                agg[colparty[j]] += v
            out.append({"code22": code, "riding22": nfc(r[1]), "kind": kind, "label": label,
                        "regr": regr, "sv": sv, "electors": el, "valid": valid,
                        "rejected": rej, **agg})
    return pd.DataFrame(out)


if __name__ == "__main__":
    s26, w26, l26 = parse_json("gen2026-10-05")
    s22, w22, l22 = parse_json("gen2022-10-03")
    w26.to_csv(os.path.join(DATA, "qc2026_by_riding.csv"), index=False, encoding="utf-8")
    l26.to_csv(os.path.join(DATA, "qc2026_by_riding_long.csv"), index=False, encoding="utf-8")
    w22.to_csv(os.path.join(INT, "qc2022_by_riding_2022map.csv"), index=False, encoding="utf-8")
    l22.to_csv(os.path.join(INT, "qc2022_by_riding_2022map_long.csv"), index=False, encoding="utf-8")
    json.dump({"2026": {k: v for k, v in s26.items() if k != "partisPolitiques"},
               "2022": {k: v for k, v in s22.items() if k != "partisPolitiques"}},
              open(os.path.join(INT, "official_province_stats.json"), "w"), indent=1)
    pd.DataFrame([{"year": y, "party_num": p["numeroPartiPolitique"],
                   "party": PARTY_BY_NUM.get(p["numeroPartiPolitique"], "OTH"),
                   "name": nfc(p["nomPartiPolitique"]), "abbr": nfc(p["abreviationPartiPolitique"]),
                   "votes": p["nbVoteTotal"], "pct": p["tauxVoteTotal"],
                   "seats": p["nbCirconscriptionsEnAvance"]}
                  for y, s in (("2026", s26), ("2022", s22)) for p in s["partisPolitiques"]]
                 ).to_csv(os.path.join(INT, "official_province_parties.csv"), index=False)
    bv = parse_bv_2022()
    bv.to_csv(os.path.join(INT, "qc2022_bv_long.csv"), index=False, encoding="utf-8")
    print(len(w26), len(w22), len(bv), bv.kind.value_counts().to_dict())
    print(w26.winner.value_counts().to_dict(), w22.winner.value_counts().to_dict())
