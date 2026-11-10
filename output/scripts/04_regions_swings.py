pass
import os
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
INT = os.path.join(DATA, "intermediate")
PARTIES = ["PQ", "PLQ", "CAQ", "QS", "PCQ"]

ADMIN = {"01": "Bas-Saint-Laurent", "02": "Saguenay–Lac-Saint-Jean", "03": "Capitale-Nationale",
         "04": "Mauricie", "05": "Estrie", "06": "Montréal", "07": "Outaouais",
         "08": "Abitibi-Témiscamingue", "09": "Côte-Nord", "10": "Nord-du-Québec",
         "11": "Gaspésie–Îles-de-la-Madeleine", "12": "Chaudière-Appalaches", "13": "Laval",
         "14": "Lanaudière", "15": "Laurentides", "16": "Montérégie", "17": "Centre-du-Québec"}


def cd_to_admin(cd):
    if 1 <= cd <= 6: return "11"
    if 7 <= cd <= 14: return "01"
    if cd in (15, 16, 20, 21, 22, 23, 34): return "03"
    if cd in (17, 18, 19, 25, 26, 27, 28, 29, 31, 33): return "12"
    if cd in (30, 40, 41, 42, 43, 44, 45, 46, 47): return "05"   
    if cd in (32, 38, 39, 49, 50): return "17"
    if cd in (35, 36, 37, 51, 90): return "04"
    if cd in (48, 53, 54, 55, 56, 57, 58, 59, 67, 68, 69, 70, 71): return "16"
    if cd in (52, 60, 61, 62, 63, 64): return "14"
    if cd == 65: return "13"
    if cd == 66: return "06"
    if 72 <= cd <= 79: return "15"
    if 80 <= cd <= 84: return "07"
    if 85 <= cd <= 89: return "08"
    if 91 <= cd <= 94: return "02"
    if 95 <= cd <= 98: return "09"
    if cd == 99: return "10"
    raise ValueError(cd)


MTL_WEST = {"Acadie", "Bourassa-Sauvé", "D'Arcy-McGee", "Jacques-Cartier", "Jeanne-Mance–Viger",
            "LaFontaine", "Marguerite-Bourgeoys", "Marquette", "Mont-Royal–Outremont", "Nelligan",
            "Notre-Dame-de-Grâce", "Robert-Baldwin", "Saint-Laurent", "Saint-Henri–Sainte-Anne",
            "Viau", "Westmount–Saint-Louis"}

GROUP = {"Montréal": None, "Laval": "Laval", "Laurentides": "Laurentides–Lanaudière",
         "Lanaudière": "Laurentides–Lanaudière", "Montérégie": "Montérégie (South Shore)",
         "Capitale-Nationale": "Capitale-Nationale (Québec City)",
         "Chaudière-Appalaches": "Chaudière-Appalaches", "Outaouais": "Outaouais", "Estrie": "Estrie",
         "Mauricie": "Mauricie–Centre-du-Québec", "Centre-du-Québec": "Mauricie–Centre-du-Québec",
         "Saguenay–Lac-Saint-Jean": "Saguenay–Lac-Saint-Jean",
         "Bas-Saint-Laurent": "Eastern Quebec", "Côte-Nord": "Eastern Quebec",
         "Gaspésie–Îles-de-la-Madeleine": "Eastern Quebec",
         "Abitibi-Témiscamingue": "Abitibi / Nord-du-Québec", "Nord-du-Québec": "Abitibi / Nord-du-Québec"}
ORDER = ["Montréal – anglophone/allophone", "Montréal – francophone", "Laval", "Laurentides–Lanaudière",
         "Montérégie (South Shore)", "Capitale-Nationale (Québec City)", "Chaudière-Appalaches",
         "Outaouais", "Estrie", "Mauricie–Centre-du-Québec", "Saguenay–Lac-Saint-Jean",
         "Eastern Quebec", "Abitibi / Nord-du-Québec"]

x = pd.read_csv(os.path.join(INT, "riding_cd_electors.csv"))
x["admin_code"] = x.cd.map(cd_to_admin)
a = x.groupby(["CO_CEP", "admin_code"]).ELEC_2026.sum().reset_index()
a["share"] = a.ELEC_2026 / a.groupby("CO_CEP").ELEC_2026.transform("sum")
top = a.sort_values("share", ascending=False).groupby("CO_CEP").head(1).set_index("CO_CEP")

r26 = pd.read_csv(os.path.join(DATA, "qc2026_by_riding.csv"))
rm = r26[["code", "riding", "electors"]].copy()
rm["admin_region_code"] = rm.code.map(top.admin_code)
rm["admin_region"] = rm.admin_region_code.map(ADMIN)
rm["admin_share_of_electors"] = rm.code.map(top.share).round(4)
rm["region"] = rm.admin_region.map(GROUP)
mtl = rm.admin_region == "Montréal"
rm.loc[mtl, "region"] = ["Montréal – anglophone/allophone" if n in MTL_WEST else "Montréal – francophone"
                         for n in rm.loc[mtl, "riding"]]
assert set(MTL_WEST) <= set(rm.riding), set(MTL_WEST) - set(rm.riding)
rm["region_order"] = rm.region.map({r: i + 1 for i, r in enumerate(ORDER)})
rm.drop(columns="electors").sort_values(["region_order", "riding"]).to_csv(
    os.path.join(DATA, "region_map.csv"), index=False, encoding="utf-8")


off = pd.read_csv(os.path.join(ROOT, "raw/geo/electeur_region-adm.csv"), sep=";", encoding="latin1").dropna()
off["NOMBRE_ELECTEUR"] = off.NOMBRE_ELECTEUR.astype(str).str.replace(r"\s", "", regex=True).astype(int)
off["admin_region_code"] = off.CODE.astype(int).map(lambda c: f"{c:02d}")
mine = rm.groupby("admin_region_code").electors.sum()
off["by_riding_majority"] = off.admin_region_code.map(mine)
off["diff_pct"] = (100 * (off.by_riding_majority / off.NOMBRE_ELECTEUR - 1)).round(1)
off.to_csv(os.path.join(INT, "region_check.csv"), index=False)
print(off[["NOM", "NOMBRE_ELECTEUR", "by_riding_majority", "diff_pct"]].to_string())


t22 = pd.read_csv(os.path.join(DATA, "qc2022_transposed_2026map.csv"))
s = r26.merge(t22, on="code", suffixes=("_26", "_22"))
s = s.merge(rm[["code", "region", "admin_region"]], on="code")
out = s[["code", "riding_26", "region", "admin_region"]].rename(columns={"riding_26": "riding"})
for p in PARTIES:
    out[f"{p}_2022"] = s[f"{p}_pct_22"].round(4)
    out[f"{p}_2026"] = s[f"{p}_pct_26"].round(4)
    out[f"{p}_swing"] = (s[f"{p}_pct_26"] - s[f"{p}_pct_22"]).round(4)
    out[f"{p}_ran_2026"] = s[f"{p}_ran"]
    out[f"{p}_ran_2022"] = s[f"{p}_votes_22"] > 0
out["winner_2026"] = s.winner
out["winner_2022_notional"] = s.winner_notional
out["flip"] = out.winner_2026 != out.winner_2022_notional
NEW_2026 = {"Bellefeuille", "Marie-Lacoste-Gérin-Lajoie"}   
out["boundary_status"] = ["new riding" if r.riding_26 in NEW_2026 else
                          ("unchanged" if r.unchanged else
                           ("substantially redrawn" if r.main_pred_share < 0.85 else "minor changes"))
                          for r in s.itertuples()]
out["notional_baseline_flag"] = out.boundary_status.isin(["new riding", "substantially redrawn"])
out["main_predecessor_2022"] = s.main_pred_riding22
out["main_predecessor_share"] = s.main_pred_share.round(4)
out.sort_values("riding").to_csv(os.path.join(DATA, "riding_swings.csv"), index=False, encoding="utf-8")
print(out.boundary_status.value_counts().to_dict())
print(out.groupby("region").size().reindex(ORDER).to_string())
