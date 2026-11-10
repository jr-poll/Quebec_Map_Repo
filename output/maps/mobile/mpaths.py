pass
import os

MOBILE = os.path.dirname(os.path.abspath(__file__))        
SRC_MAPS = os.path.dirname(MOBILE)                           
OUT_ROOT = os.path.dirname(SRC_MAPS)                         
FINAL = os.path.join(SRC_MAPS, "final")                      
FINAL_HTML = os.path.join(SRC_MAPS, "Quebec_2026_Swing_Map_FINAL.html")
MOBILE_HTML = os.path.join(SRC_MAPS, "Quebec_2026_Swing_Map_FINAL_mobile.html")
SCRIPTS = os.path.join(MOBILE, "scripts")
TMP = os.path.join(MOBILE, "tmp")
BUILD = os.path.join(MOBILE, "build")
SCREENS = os.path.join(MOBILE, "screens")
COMPARE = os.path.join(MOBILE, "compare")
REPRO = os.environ.get("QC_REPRO") == "1"
HTML_OUT = os.path.join(TMP, "repro.html") if REPRO else MOBILE_HTML
PASS1 = os.path.join(TMP, "pass1.html")
FALLBACK = os.path.join(BUILD, "fallback.json")   


def writable(p):
    pass
    p = os.path.abspath(p)
    assert p.startswith(MOBILE + os.sep) or p == MOBILE_HTML, f"refusing to write {p}"
    return p


def mkdir(d):
    os.makedirs(writable(os.path.join(d, "x")).rsplit(os.sep, 1)[0], exist_ok=True)
    return d


for _d in (TMP, BUILD, SCREENS, COMPARE):
    mkdir(_d)
