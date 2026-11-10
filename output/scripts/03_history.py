pass
import json, os, re, html, glob, unicodedata
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW, DATA = os.path.join(ROOT, "raw"), os.path.join(ROOT, "data")
YEARS = {"2003": "gen2003-04-14", "2007": "gen2007-03-26", "2008": "gen2008-12-08",
         "2012": "gen2012-09-04", "2014": "gen2014-04-07", "2018": "gen2018-10-01",
         "2022": "gen2022-10-03", "2026": "gen2026-10-05"}


def party_key(name):
    n = unicodedata.normalize("NFC", name).lower()
    if n.startswith("parti libéral du québec"): return "PLQ"
    if n.startswith("parti québécois"): return "PQ"
    if "action démocratique" in n: return "ADQ"
    if "coalition avenir" in n: return "CAQ"
    if "québec solidaire" in n: return "QS"
    if "parti conservateur du québec" in n: return "PCQ"
    if "union des forces progressistes" in n: return "UFP"
    return None



t = open(os.path.join(RAW, "web", "stats1867.html"), encoding="utf-8").read()
tb = re.findall(r"<table.*?</table>", t, re.S)[1]
ref = {}
for r in re.findall(r"<tr.*?</tr>", tb, re.S):
    c = [html.unescape(re.sub(r"<[^>]+>", "", x)).strip().replace("\xa0", "").replace(" ", "")
         for x in re.findall(r"<t[hd].*?</t[hd]>", r, re.S)]
    if c and c[0] in YEARS:
        ref[c[0]] = dict(electors=int(c[1]), valid=int(c[2]), rejected=int(c[3]),
                         turnout=float(c[4].replace(",", ".")))

rows, checks = [], []
for y, d in YEARS.items():
    s = json.load(open(os.path.join(RAW, d, "resultats.json"), encoding="utf-8"))["statistiques"]
    valid, electors, rej = s["nbVoteValide"], s["nbElecteurInscrit"], s["nbVoteRejete"]
    turnout = round(100 * (valid + rej) / electors, 4)  
    checks.append(dict(year=y, json_valid=valid, ref_valid=ref[y]["valid"], json_electors=electors,
                       ref_electors=ref[y]["electors"], json_rejected=rej, ref_rejected=ref[y]["rejected"],
                       json_turnout=turnout, ref_turnout=ref[y]["turnout"]))
    seen = {}
    oth_v = oth_s = 0
    for p in s["partisPolitiques"]:
        k = party_key(p["nomPartiPolitique"])
        if k is None or k in seen:
            oth_v += p["nbVoteTotal"]; oth_s += p["nbCirconscriptionsEnAvance"]; continue
        seen[k] = 1
        rows.append(dict(year=int(y), party=k, party_name=unicodedata.normalize("NFC", p["nomPartiPolitique"]).strip(),
                         votes=p["nbVoteTotal"], vote_pct=round(100 * p["nbVoteTotal"] / valid, 4),
                         seats=p["nbCirconscriptionsEnAvance"], candidates=p.get("nbCandidat"),
                         total_valid=valid, rejected=rej, electors=electors, turnout_pct=turnout,
                         total_seats=s["nbCirconscription"]))
    rows.append(dict(year=int(y), party="OTH", party_name="All other parties and independents",
                     votes=oth_v, vote_pct=round(100 * oth_v / valid, 4), seats=oth_s, candidates=None,
                     total_valid=valid, rejected=rej, electors=electors, turnout_pct=turnout,
                     total_seats=s["nbCirconscription"]))

h = pd.DataFrame(rows)

h["series"] = h.party.replace({"ADQ": "ADQ/CAQ", "CAQ": "ADQ/CAQ"})
h.to_csv(os.path.join(DATA, "qc_provincial_history_2003_2026.csv"), index=False, encoding="utf-8")
c = pd.DataFrame(checks)
c.to_csv(os.path.join(DATA, "intermediate", "history_crosscheck.csv"), index=False)
print(c.to_string())
print(h.pivot_table(index="year", columns="party", values="vote_pct").round(1).to_string())
print(h.pivot_table(index="year", columns="party", values="seats").to_string())
chk = h.groupby("year").agg(v=("votes", "sum"), t=("total_valid", "first"), s=("seats", "sum"), ts=("total_seats", "first"))
print("vote sums match:", (chk.v == chk.t).all(), "| seat sums match:", (chk.s == chk.ts).all())
