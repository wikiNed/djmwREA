"""在内存 dump 里找 Il2CppString 对象（C# string 布局：16 字节头 + UTF-16 数据）。

Il2CppString:
  +0x00 klass*
  +0x08 monitor
  +0x10 int32 length
  +0x14 wchar_t[length]
找到 'SaveFile.es3' 和 'AutoSave.es3' 的 Il2CppString 实例，
再找附近（同一 object pool 区域）的短 ASCII 字符串，可能是口令。
"""
from paths import EMU, MEMDUMP

import re
import struct
data = open(MEMDUMP, "rb").read()
print("size:", len(data))

for name in ("SaveFile.es3", "AutoSave.es3"):
    u16 = name.encode("utf-16-le")
    hits = []
    start = 0
    while True:
        i = data.find(u16, start)
        if i < 0:
            break
        hits.append(i)
        start = i + 1
    print(f"\n=== {name!r}: {len(hits)} UTF-16 hits ===")
    for h in hits[:20]:
        ln_off = h - 4
        ln = struct.unpack_from("<i", data, ln_off)[0] if ln_off >= 0 else -1
        print(f"  offset {h:#x}  len@-4={ln}  (expected {len(name)})")
