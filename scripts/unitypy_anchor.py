"""手工解析 ES3Defaults MonoBehaviour 原始字节。

Unity 序列化字符串（对齐版本，m_EditorFormat 为 false 时）：
    int32 length      (包含结尾 \\0)
    byte[length]      字符串内容 + \\0
    (若 align 且 (4 - (length+4)%4) 有填充则补齐) —— 实际上直接按 length 跳过即可

从 dump 出的字节看：
    00ead7a6: 0b 00 00 00 "ES3Defaults" 27
        -> 长度 0x0b = 11, "ES3Defaults" 正好 11 字符，但后面跟 0x27 而不是 \0
        说明这块不是 m_Name，而是 m_Script 里打包的 PPtr 引用表 / 或其他结构

真实情况：0x27 0x00 0xf1 0x01 是 MonoBehaviour 的大小头（size = 0x27=39 后续）
    然后 0c 00 00 00 "SaveFile.es3" + 0x15 0x00  等是 AssetBundle 内部的 PPtr 表

换思路：从 0xead7a6 往回找该对象真正的起点，按 AssetFileInfo 结构走。
更稳妥的做法：用 UnityPy 遍历全部对象，把 byte_size 与 offset 落在该区域的找出来。
"""
from paths import APK

import io
import zipfile

import UnityPy
z = zipfile.ZipFile(APK)
raw = z.read("assets/bin/Data/data.unity3d")
env = UnityPy.load(io.BytesIO(raw))

ANCHOR = 0xEAD7A6
hits = []
for o in env.objects:
    try:
        off = o.byte_offset
        size = o.byte_size
    except Exception:
        continue
    if off <= ANCHOR < off + size:
        hits.append(o)

print("objects covering anchor:", len(hits))
for o in hits:
    print(f"  type={o.type.name} path_id={o.path_id} off=0x{o.byte_offset:x} size={o.byte_size}")
    body = bytes(o.get_raw_data()) if o.byte_size else b""
    print("  raw len:", len(body))
    # 打印可见 ASCII 串
    import re
    for m in re.finditer(rb"[\x20-\x7e]{4,}", body):
        print(f"    @{m.start()}: {m.group()!r}")
