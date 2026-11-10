import zipfile, sys, os, unicodedata
src, dst = sys.argv[1], sys.argv[2]
os.makedirs(dst, exist_ok=True)
with zipfile.ZipFile(src, metadata_encoding='latin1') as z:
    for info in z.infolist():
        name = unicodedata.normalize('NFC', info.filename)
        out = os.path.join(dst, name)
        if name.endswith('/'): os.makedirs(out, exist_ok=True); continue
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, 'wb') as f: f.write(z.read(info))
print(src, 'ok')
