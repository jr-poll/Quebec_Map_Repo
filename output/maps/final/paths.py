pass
import os

FINAL = os.path.dirname(os.path.abspath(__file__))          
SRC_MAPS = os.path.dirname(FINAL)                            
OUT_ROOT = os.path.dirname(SRC_MAPS)                         
PROJECT = os.path.dirname(OUT_ROOT)                          
DATA = os.path.join(OUT_ROOT, "data")
GEO = os.path.join(SRC_MAPS, "geo")
PLAN = os.path.join(SRC_MAPS, "plan")
RAW_JS = os.path.join(SRC_MAPS, "raw", "js")
MAPSHAPER = os.path.join(SRC_MAPS, "tmp", "node", "node_modules", ".bin", "mapshaper")
SCRIPTS = os.path.join(FINAL, "scripts")
BUILD = os.path.join(FINAL, "build")
TMP = os.path.join(FINAL, "tmp")
PREVIEWS = os.path.join(FINAL, "previews")
SCREENS = os.path.join(FINAL, "html_screens")
COMPARE = os.path.join(FINAL, "compare")
REPRO = os.environ.get("QC_REPRO") == "1"
HTML_OUT = os.path.join(TMP, "repro.html") if REPRO else os.path.join(SRC_MAPS, "Quebec_2026_Swing_Map_FINAL.html")
ORIG_HTML = os.path.join(SRC_MAPS, "Quebec_2026_Swing_Map.html")

BUILD_RUN = os.path.join(BUILD, "repro") if REPRO else BUILD


def writable(p):
    pass
    p = os.path.abspath(p)
    finals = (os.path.join(SRC_MAPS, "Quebec_2026_Swing_Map_FINAL.html"),)
    assert p.startswith(FINAL + os.sep) or p in finals, f"refusing to write {p}"
    return p


for _d in (BUILD, BUILD_RUN, TMP, PREVIEWS, SCREENS, COMPARE):
    os.makedirs(writable(os.path.join(_d, "x")).rsplit(os.sep, 1)[0], exist_ok=True)
