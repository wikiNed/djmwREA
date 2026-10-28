import UnityPy, os, sys

APK = r"E:\DSH\game\.rea-study\apk\TapDemons_v5.9.2.apk"
OUT = r"E:\DSH\game\.rea-study\saves"
os.makedirs(OUT, exist_ok=True)
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
    p = os.path.join(OUT, n + ".json")
    with open(p, "wb") as f:
        f.write(raw)
    print("wrote", p, len(raw))
