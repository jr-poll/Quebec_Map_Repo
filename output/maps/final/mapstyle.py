pass
import math

PARTIES = ["PQ", "PLQ", "CAQ", "QS", "PCQ"]
COL = {"PLQ": "D2002A", "PQ": "2F6FD0", "CAQ": "00B5C8", "QS": "F99D1C", "PCQ": "0B2A55"}   
NAME = {"PQ": "PQ", "PLQ": "Liberal", "CAQ": "CAQ", "QS": "QS", "PCQ": "Conservative"}

HEADING = {"QS": 160, "PQ": 125, "PLQ": 90, "CAQ": 55, "PCQ": 20}
LOSS_COL = "4D4D4D"            

INK = {"PQ": "1D4C9E", "PLQ": "9E0020", "CAQ": "007C8A", "QS": "B35A00", "PCQ": "0B2A55"}
ARROW_ALPHA = 0.90
EMU_PER_POINT = 16459          
MIN_ARROW_EMU = 54864          
DOT_BELOW = 0.5                
S_MIN_EMU = 274320             
EMU_PER_IN = 914400


SLIDE_W, SLIDE_H = 9144000, 5143500
MAP_X, MAP_Y, MAP_W, MAP_H = 1690000, 905000, 7300000, 3790000
PANEL_X, PANEL_W, PANEL_Y = 300000, 1300000, 905000
MODES = ["WINNER"] + PARTIES


W_RIDING, W_CLUSTER, W_HALO = 22225, 34925, 60325
DOT_D = 45720
HEAD_SMALL_BELOW = int(0.14 * EMU_PER_IN)


LAND_NEIGH, LAND_QC, RIDING_EDGE = "ECE9F4", "FCFBFF", "CBC5DF"
REGION_EDGE, COAST = "A69ECB", "8C84B6"
ACCENT = "6657D1"


SHADE_CATS = ["both", "gain26", "lost22"]
SHADE_ALPHA = {"both": 0.40, "gain26": 0.24, "lost22": 0.11}
SHADE_LABEL = {"both": "Won in 2022 and 2026", "gain26": "Won in 2026 only", "lost22": "Won in 2022 only",
               None: "Not won in either year"}
FOOT_ALPHA = {"WINNER": 0.07, "PARTY": 0.0}     


def _mix(c, base, a):
    c1 = [int(c[i:i + 2], 16) for i in (0, 2, 4)]
    c0 = [int(base[i:i + 2], 16) for i in (0, 2, 4)]
    return "".join(f"{int(round(a * x + (1 - a) * y)):02X}" for x, y in zip(c1, c0))


def tint(party, cat):
    pass
    if cat is None:
        return LAND_QC
    return _mix(COL[party], LAND_QC, SHADE_ALPHA[cat])


SHADE = {p: {c: tint(p, c) for c in SHADE_CATS} for p in PARTIES}


def arrow_len(swing):
    return max(MIN_ARROW_EMU, abs(swing) * EMU_PER_POINT)


def arrow_angle(party, swing):
    pass
    return HEADING[party] + (180 if swing < 0 else 0)


def arrow_ends(ax, ay, party, swing):
    pass
    L = arrow_len(swing)
    th = math.radians(arrow_angle(party, swing))
    ux, uy = math.cos(th), -math.sin(th)
    return (ax - L / 2 * ux, ay - L / 2 * uy), (ax + L / 2 * ux, ay + L / 2 * uy)


def arrow_colour(mode, party, swing):
    pass
    if mode == "WINNER":
        return COL[party]
    return INK[party] if swing >= 0 else LOSS_COL
