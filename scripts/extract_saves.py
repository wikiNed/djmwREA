from paths import APK, SAVES

import UnityPy, os, sys
os.makedirs(SAVES, exist_ok=True)
UnityPy.config.FALLBACK_UNITY_VERSION = "2022.3.62f1"
env = UnityPy.load(APK)
for o in env.objects:
    if o.type.name != "TextAsset":
        continue
    d = o.read()
    n = getattr(d, "m_Name", "")
    if not n.startswith("playerDate"):
        continue
    raw = d.m_Script
    if isinstance(raw, str):
        raw = raw.encode()
    p = os.path.join(SAVES, n + ".json")
    with open(p, "wb") as f:
        f.write(raw)
    print("wrote", p, len(raw))
