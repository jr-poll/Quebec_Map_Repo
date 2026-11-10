pass
import os
import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt   
import shapely   
from shapely.ops import unary_union   
from mapstyle import MAP_W, MAP_H, EMU_PER_IN, LAND_NEIGH, LAND_QC, RIDING_EDGE, REGION_EDGE, COAST, ACCENT   
import mapdata as M   

GP = os.path.join(M.GEO, "ridings_land.gpkg")
RID = gpd.read_file(GP, layer="ridings")
REG = gpd.read_file(GP, layer="regions")
PROV = gpd.read_file(GP, layer="province")
NEI = gpd.read_file(GP, layer="neighbours")
LAND = dict(zip(RID.code.astype(int), RID.geometry))
DPI = 300


def _h(c):
    return "#" + c


def _prep(gdf, box, tol):
    g = gdf[gdf.intersects(box)].copy()
    g["geometry"] = shapely.simplify(g.geometry.values, tol, preserve_topology=True)
    return g


def footprint(codes):
    return unary_union([LAND[c] for c in codes])


def render_basemap(extent, footprints, path, dpi=DPI):
    pass
    x0, y0, x1, y1 = extent
    wi, hi = MAP_W / EMU_PER_IN, MAP_H / EMU_PER_IN
    m_per_px = (x1 - x0) / (wi * dpi)
    tol = 0.4 * m_per_px
    pad = (x1 - x0) * 0.05
    box = shapely.box(x0 - pad, y0 - pad, x1 + pad, y1 + pad)
    fig = plt.figure(figsize=(wi, hi), dpi=dpi)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    ax.set_aspect("equal")
    ax.axis("off")
    _prep(NEI, box, tol).plot(ax=ax, color=_h(LAND_NEIGH), linewidth=0)
    _prep(RID, box, tol).plot(ax=ax, facecolor=_h(LAND_QC), edgecolor=_h(RIDING_EDGE), linewidth=0.35)
    _prep(REG, box, tol).boundary.plot(ax=ax, color=_h(REGION_EDGE), linewidth=0.8)
    _prep(PROV, box, tol).boundary.plot(ax=ax, color=_h(COAST), linewidth=0.8)
    for fp in footprints:
        fp = shapely.simplify(fp, tol, preserve_topology=True)
        gpd.GeoSeries([fp]).plot(ax=ax, facecolor=_h(ACCENT), alpha=0.07, linewidth=0)
        gpd.GeoSeries([fp]).boundary.plot(ax=ax, color=_h(ACCENT), linewidth=1.1, linestyle=(0, (3, 2)))
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    fig.savefig(path, dpi=dpi, transparent=True)
    plt.close(fig)
    return path


def render_locator(extent, rect, path, w_emu, h_emu, dpi=200):
    pass
    x0, y0, x1, y1 = extent
    wi, hi = w_emu / EMU_PER_IN, h_emu / EMU_PER_IN
    m_per_px = max((x1 - x0) / (wi * dpi), (y1 - y0) / (hi * dpi))
    box = shapely.box(x0, y0, x1, y1)
    fig = plt.figure(figsize=(wi, hi), dpi=dpi)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.axis("off")
    _prep(NEI, box, m_per_px).plot(ax=ax, color=_h(LAND_NEIGH), linewidth=0)
    _prep(PROV, box, m_per_px).plot(ax=ax, color="#E9E6F2", edgecolor=_h(COAST), linewidth=0.4)
    ax.set_xlim(x0, x1)
    ax.set_ylim(y0, y1)
    ax.set_aspect("equal")
    fig.savefig(path, dpi=dpi, transparent=True)
    plt.close(fig)
    return path
