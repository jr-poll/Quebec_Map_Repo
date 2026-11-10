pass
import glob, os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import mpaths   
from PIL import Image, ImageDraw   

label = sys.argv[1]
pat = sys.argv[2] if len(sys.argv) > 2 else "*.png"
files = sorted(f for f in glob.glob(os.path.join(mpaths.SCREENS, label, pat)) if "_full" not in f and "_ref" not in f)
TH, COLS, PER = 520, 6, 18
for n in range(0, len(files), PER):
    tiles = []
    for f in files[n:n + PER]:
        im = Image.open(f).convert("RGB")
        s = TH / im.height
        im = im.resize((max(1, int(im.width * s)), TH))
        if im.width > 700:
            s2 = 700 / im.width
            im = im.resize((700, int(TH * s2)))
        tiles.append((os.path.basename(f)[:-4], im))
    cw = max(t[1].width for t in tiles) + 10
    rows = (len(tiles) + COLS - 1) // COLS
    sheet = Image.new("RGB", (cw * COLS, (TH + 26) * rows), "#888")
    for i, (cap, im) in enumerate(tiles):
        x, y = (i % COLS) * cw, (i // COLS) * (TH + 26)
        sheet.paste(im, (x + 5, y + 22))
        ImageDraw.Draw(sheet).text((x + 5, y + 5), cap[:60], fill="white")
    out = os.path.join(mpaths.COMPARE, f"qa_{label}_{n // PER + 1:02d}.png")
    sheet.save(mpaths.writable(out))
    print(out)
