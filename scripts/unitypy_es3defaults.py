"""用 UnityPy 直接解析 data.unity3d 中 ES3Defaults 那个 MonoBehaviour。

172,961 个对象里有一个 m_Name == "ES3Defaults" 的 MonoBehaviour。
UnityPy 能拿到它的 raw_data（不含 TypeTree 时是原始字节流），
并且 read() 在 typetree 存在时能直接给出 m_Script。

先试读，若失败则退回 raw_data 手工解析。
"""
import io
import zipfile

import UnityPy

APK = r"E:\DSH\game\.rea-study\apk\TapDemons_v5.9.2.apk"
z = zipfile.ZipFile(APK)
raw = z.read("assets/bin/Data/data.unity3d")
env = UnityPy.load(io.BytesIO(raw))

targets = []
for o in env.objects:
    if o.type.name != "MonoBehaviour":
        continue
    try:
        d = o.read()
    except Exception:
        continue
    nm = getattr(d, "m_Name", "") or ""
    if nm in ("ES3Defaults",) or "ES3" in nm:
        targets.append((o, d, nm))

print("matched:", [(n) for _, _, n in targets])
for o, d, nm in targets:
    print(f"\n=== {nm} pathID={o.path_id} size={o.byte_size} ===")
    print("type-tree present:", getattr(d, "m_TypeTree", None) is not None)
    # 打印所有可读属性
    try:
        tree = d.read_typetree()
        print("typetree:", tree)
    except Exception as e:
        print("read_typetree failed:", type(e).__name__, e)
    rd = d.m_Script if hasattr(d, "m_Script") else None
    if rd is not None:
        b = rd.encode("utf-8") if isinstance(rd, str) else rd
        print("m_Script len:", len(b))
        print("head:", b[:200])
