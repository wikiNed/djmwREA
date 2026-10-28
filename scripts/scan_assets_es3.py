"""从 APK 里提取 Unity Assets，搜 ES3 口令痕迹。

关注：
  1. TextAsset 里有没有 ES3 相关配置（ES3Defaults 序列化后的 JSON）
  2. 有没有可疑的十六进制/base64 长串（可能是口令）
  3. 是否有 Resources/ES3Defaults 之类的资产
"""
import io
import os
import re
import zipfile

import UnityPy

APK = r"E:\DSH\game\.rea-study\apk\TapDemons_v5.9.2.apk"
OUT = r"E:\DSH\game\.rea-study\assets"
os.makedirs(OUT, exist_ok=True)

z = zipfile.ZipFile(APK)
names = z.namelist()
print("apk entries:", len(names))

# 1) 找 .assets / bundle / .resS
data_names = [n for n in names if n.startswith("assets/") and n.endswith((".assets", ".resource", ".resS", ".bundle"))]
print("unity data files:", len(data_names))
for n in data_names[:40]:
    print("  ", n, z.getinfo(n).file_size)

# 2) 用 UnityPy 加载内置 assets/bin/Data
bin_data = [n for n in names if re.match(r"assets/bin/Data/[0-9a-f]{32}(\.assets)?$", n)]
print("\nbin/Data level files:", len(bin_data))

hits = []
texts = 0
for n in bin_data:
    try:
        raw = z.read(n)
        env = UnityPy.load(io.BytesIO(raw))
    except Exception as e:
        print("skip", n, e)
        continue
    for obj in env.objects:
        if obj.type.name != "TextAsset":
            continue
        texts += 1
        try:
            d = obj.read()
            name = getattr(d, "m_Name", "")
            script = d.m_Script
            if isinstance(script, bytes):
                body = script.decode("utf-8", "replace")
            else:
                body = str(script)
        except Exception:
            continue
        low = body.lower()
        if "es3" in low or "encryption" in low or "savefile" in low:
            hits.append((n, name, len(body)))
            print(f"\n=== HIT {n} :: {name} ({len(body)} chars) ===")
            print(body[:1500])
            out = os.path.join(OUT, re.sub(r"[^\w.-]", "_", name) + ".txt")
            open(out, "w", encoding="utf-8").write(body)
            print("saved ->", out)

print(f"\nscanned textassets: {texts}, hits: {len(hits)}")
