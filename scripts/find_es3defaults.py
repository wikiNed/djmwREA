"""找 ES3Defaults 这个 ScriptableObject（resources.resource 里）。

ES3Settings.defaultSettingsPath = "ES3/ES3Defaults"
ES3Defaults 序列化后含 encryptionPassword 字段。
UnityPy 解析 MonoBehaviour 需要 TypeTree；IL2CPP 构建通常剥离了 TypeTree，
因此改用原始字符串搜索：直接在 resource 的原始字节里找 "ES3" / 可疑长串。
"""
from paths import APK

import os
import re
import zipfile
z = zipfile.ZipFile(APK)

targets = [
    "assets/bin/Data/resources.resource",
    "assets/bin/Data/data.unity3d",
] + [f"assets/bin/Data/sharedassets{i}.resource" for i in (2, 3, 4, 5, 6, 7, 8, 10)]

for t in targets:
    try:
        raw = z.read(t)
    except KeyError:
        continue
    # 1) 找 "ES3" 附近的可打印上下文
    for m in re.finditer(rb"ES3[A-Za-z/]{0,24}", raw):
        s = max(0, m.start() - 60)
        ctx = raw[s : m.end() + 60]
        pr = "".join(chr(b) if 32 <= b < 127 else "." for b in ctx)
        print(f"[{t}] @{m.start()} {pr}")
    # 2) 直接找 ES3Defaults 名字
    for m in re.finditer(rb"ES3Defaults", raw):
        print(f"[{t}] ES3Defaults @{m.start()}")
print("done")
