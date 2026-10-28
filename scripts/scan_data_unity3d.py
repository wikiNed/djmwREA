"""扫 data.unity3d 里的 TextAsset，找 ES3 口令痕迹。"""
import io
import os
import re
import zipfile

import UnityPy

APK = r"E:\DSH\game\.rea-study\apk\TapDemons_v5.9.2.apk"
OUT = r"E:\DSH\game\.rea-study\assets"
os.makedirs(OUT, exist_ok=True)
ENTRY = "assets/bin/Data/data.unity3d"

z = zipfile.ZipFile(APK)
raw = z.read(ENTRY)
print("data.unity3d:", len(raw), "bytes, head=", raw[:8])

env = UnityPy.load(io.BytesIO(raw))
objs = list(env.objects)
print("objects:", len(objs))

from collections import Counter

print("types:", Counter(o.type.name for o in objs).most_common(15))

texts = 0
hits = []
for o in objs:
    if o.type.name != "TextAsset":
        continue
    texts += 1
    try:
        d = o.read()
        name = d.m_Name
        s = d.m_Script
        body = s.decode("utf-8", "replace") if isinstance(s, bytes) else str(s)
    except Exception:
        continue
    low = body.lower()
    if any(k in low for k in ("es3", "encryption", "savefile", "password", "aes")):
        hits.append((name, len(body)))
        print(f"\n=== HIT {name} ({len(body)}) ===")
        print(body[:1200])
        open(os.path.join(OUT, re.sub(r"[^\w.-]", "_", name) + ".txt"), "w", encoding="utf-8").write(body)

print(f"\ntextassets={texts} hits={len(hits)}")
print("all textasset names:", sorted({n for n, _ in hits})[:40])
