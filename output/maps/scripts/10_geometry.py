pass
import glob, json, os, sys, unicodedata
import geopandas as gpd
import pandas as pd
import shapely
from shapely.ops import polylabel
from pyproj import CRS

HERE = os.path.dirname(os.path.abspath(__file__))
MAPS = os.path.dirname(HERE)
OUT = os.path.dirname(MAPS)
GEO = os.path.join(MAPS, "geo")
RAW = os.path.join(MAPS, "raw")
os.makedirs(GEO, exist_ok=True)

EPSG = 3798
log = {}


shp = glob.glob(os.path.join(OUT, "raw/geo/**/Circonscription_electorales_2026_shapefile.shp"), recursive=True)
assert len(shp) == 1, shp
r = gpd.read_file(shp[0])

from pyproj import Transformer
_t1 = Transformer.from_crs(4326, r.crs, always_xy=True); _t2 = Transformer.from_crs(4326, EPSG, always_xy=True)
for lon, lat in [(-73.6, 45.5), (-61.8, 47.4), (-77, 62)]:
    a1, a2 = _t1.transform(lon, lat), _t2.transform(lon, lat)
    assert abs(a1[0] - a2[0]) < 1 and abs(a1[1] - a2[1]) < 1, (a1, a2)
r = r.set_crs(EPSG, allow_override=True)
r["code"] = r["CO_CEP"].astype(int)
sw = pd.read_csv(os.path.join(OUT, "data/riding_swings.csv"))
rmap = pd.read_csv(os.path.join(OUT, "data/region_map.csv"))
assert set(r.code) == set(sw.code) and len(r) == 127
nfc = lambda s: unicodedata.normalize("NFC", s)
names = dict(zip(sw.code, sw.riding.map(nfc)))
mism = [(c, n, names[c]) for c, n in zip(r.code, r.NM_CEP.map(nfc)) if n != names[c]]
log["name_mismatches"] = mism
print("name mismatches:", mism)
r["riding"] = r.code.map(names)
inv = int((~r.is_valid).sum())
log["invalid_fixed"] = inv
if inv:
    r["geometry"] = shapely.make_valid(r.geometry.values)
r = r.merge(rmap[["code", "region"]], on="code")
r["legal_km2"] = r.area / 1e6


statcan = glob.glob(os.path.join(RAW, "lpr_000b21a_e/*.shp"))
ne = gpd.read_file(os.path.join(RAW, "ne_10m_admin_1_states_provinces/ne_10m_admin_1_states_provinces.shp"))
if statcan:
    pr = gpd.read_file(statcan[0]).to_crs(EPSG)
    qc = pr[pr.PRUID == "24"].union_all()
    neigh = pr[pr.PRUID.isin(["35", "13", "10", "12", "11"])][["geometry"]]
    log["land_source"] = "StatCan 2021 cartographic boundary file lpr_000b21a_e"
elif os.path.exists(os.path.join(RAW, "gadm/gadm41_CAN_1.json")):
    gd = gpd.read_file(os.path.join(RAW, "gadm/gadm41_CAN_1.json")).to_crs(EPSG)
    qc = shapely.make_valid(gd[gd.NAME_1 == "Québec"].union_all())
    neigh = gd[gd.NAME_1.isin(["Ontario", "NewBrunswick", "New Brunswick", "NewfoundlandandLabrador",
                                "Newfoundland and Labrador", "NovaScotia", "Nova Scotia",
                                "PrinceEdwardIsland", "Prince Edward Island"])][["geometry"]]
    assert len(neigh) == 5, gd.NAME_1.tolist()
    log["land_source"] = ("GADM 4.1 Canada level-1 (Québec); StatCan download returned a bot-check page (403), "
                          "GADM preferred over the coarser Natural Earth fallback")
else:
    can = ne[ne.adm0_a3 == "CAN"].to_crs(EPSG)
    qc = shapely.make_valid(can[can.iso_3166_2 == "CA-QC"].union_all())
    neigh = can[can.iso_3166_2.isin(["CA-ON", "CA-NB", "CA-NL", "CA-NS", "CA-PE"])][["geometry"]]
    log["land_source"] = "FALLBACK Natural Earth 10m admin-1 (CA-QC); StatCan download returned a bot-check page (403)"
usa = ne[(ne.adm0_a3 == "USA") & ne.iso_3166_2.isin(
    ["US-ME", "US-NH", "US-VT", "US-NY", "US-MA", "US-CT", "US-RI", "US-PA", "US-MI", "US-OH", "US-NJ"])].to_crs(EPSG)
neigh = pd.concat([neigh, usa[["geometry"]]], ignore_index=True)


lakes = gpd.read_file(os.path.join(RAW, "ne_10m_lakes/ne_10m_lakes.shp")).to_crs(EPSG)
lakes = lakes[lakes.intersects(qc)]
lakes = lakes[lakes.area > 300e6]
log["lakes_removed"] = sorted(str(n) for n in lakes.name.fillna("(unnamed)"))
lake_u = lakes.union_all()
land_mask = qc.difference(lake_u)

geoms, loss = [], []
for _, row in r.iterrows():
    g = row.geometry.intersection(land_mask)
    if g.is_empty or g.area < 0.02 * row.geometry.intersection(qc).area:   
        g = row.geometry.intersection(qc)
    g = shapely.make_valid(g)
    g = shapely.get_parts(g)
    from shapely.geometry import MultiPolygon
    g = MultiPolygon([p for p in g if p.geom_type == "Polygon" and p.area > 1e4])
    geoms.append(g)
r["geometry"] = geoms
r["land_km2"] = r.area / 1e6
assert (r.land_km2 > 0).all()

neigh_u = neigh.union_all()
r_legal = gpd.read_file(shp[0]).set_crs(EPSG, allow_override=True)
r_legal["code"] = r_legal.CO_CEP.astype(int)
bl = []
for _, row in r_legal.iterrows():
    out = row.geometry.intersection(neigh_u).area
    if out > 0.02 * row.geometry.area:
        bl.append((int(row.code), names[int(row.code)], round(100 * out / row.geometry.area, 1)))
log["border_loss_gt2pct"] = bl
print("border loss >2%:", bl)
idm = r[r.riding == "Îles-de-la-Madeleine"].iloc[0]
assert 50 < idm.land_km2 < 600, idm.land_km2
dup = r[r.riding == "Duplessis"].iloc[0]
anticosti = shapely.Point(-63.0, 49.45)
anticosti = gpd.GeoSeries([anticosti], crs=4326).to_crs(EPSG).iloc[0]
assert dup.geometry.contains(anticosti), "Duplessis lost Anticosti"
log["iles_de_la_madeleine_land_km2"] = round(idm.land_km2, 1)
log["duplessis_parts"] = len(dup.geometry.geoms)
log["area_km2"] = {"min": [names[int(r.loc[r.land_km2.idxmin(), "code"])], round(r.land_km2.min(), 2)],
                   "max": [names[int(r.loc[r.land_km2.idxmax(), "code"])], round(r.land_km2.max(), 0)]}
big_loss = r.assign(pct=100 * (1 - r.land_km2 / r.legal_km2)).sort_values("pct", ascending=False)
log["largest_water_share"] = [(n, round(p, 1)) for n, p in zip(big_loss.riding.head(12), big_loss.pct.head(12))]

regions = r.dissolve("region")[["geometry"]].reset_index()
province = gpd.GeoDataFrame({"name": ["Québec"]}, geometry=[r.union_all()], crs=EPSG)
neigh = gpd.GeoDataFrame(geometry=[neigh_u.difference(province.geometry.iloc[0].buffer(0))], crs=EPSG)
neigh = neigh.explode(index_parts=False).reset_index(drop=True)
rid = r[["code", "riding", "region", "legal_km2", "land_km2", "geometry"]]

gp = os.path.join(GEO, "ridings_land.gpkg")
if os.path.exists(gp):
    os.remove(gp)
for name, df in [("ridings", rid), ("regions", regions), ("province", province), ("neighbours", neigh)]:
    df.to_file(gp, layer=name, driver="GPKG")
gw = os.path.join(GEO, "ridings_land_wgs84.gpkg")
if os.path.exists(gw):
    os.remove(gw)
for name, df in [("ridings", rid), ("regions", regions), ("province", province), ("neighbours", neigh)]:
    df.to_crs(4326).to_file(gw, layer=name, driver="GPKG")


rows = []
for _, row in rid.iterrows():
    part = max(row.geometry.geoms, key=lambda q: q.area)
    pt = polylabel(part, tolerance=50)
    rows.append((row.code, pt.x, pt.y))
anc = pd.DataFrame(rows, columns=["code", "x", "y"])
ll = gpd.GeoSeries(gpd.points_from_xy(anc.x, anc.y), crs=EPSG).to_crs(4326)
anc["lon"], anc["lat"] = ll.x.round(6), ll.y.round(6)
anc.to_csv(os.path.join(GEO, "anchors.csv"), index=False)
for c, x, y in rows:
    assert rid.set_index("code").geometry[c].contains(shapely.Point(x, y))
json.dump(log, open(os.path.join(GEO, "geometry_log.json"), "w"), ensure_ascii=False, indent=1)
print(json.dumps(log, ensure_ascii=False, indent=1))
