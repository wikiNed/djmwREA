"""在内存里找 Il2CppString 实例并提取候选口令。

Il2CppString (IL2CPP 标准布局):
  [0x00] Il2CppClass* klass
  [0x08] void*       monitor
  [0x10] int32_t     length
  [0x14] uint16_t    chars[length]
"""

from paths import EMU
import struct
import sys

path = sys.argv[1] if len(sys.argv) > 1 else str(EMU / 'mem2.bin')
data = open(path, "rb").read()
print("dump:", path, len(data))


def find_strings(name):
    u16 = name.encode("utf-16-le")
    hits = []
    start = 0
    while True:
        i = data.find(u16, start)
        if i < 0:
            break
        hits.append(i)
        start = i + 1
    return hits


for name in ("SaveFile.es3", "AutoSave.es3"):
    hits = find_strings(name)
    print(f"\n=== {name!r}: {len(hits)} hits ===")
    for h in hits[:10]:
        ln = struct.unpack_from("<i", data, h - 4)[0]
        print(f"  off {h:#x}  len@-4={ln}  expect {len(name)}")

# 通用扫描：所有可能的 Il2CppString（有合理 length 且 UTF-16 可打印）
print("\n=== 扫描短 ASCII Il2CppString（8..48 字符，纯可打印）===")
found = []
n = len(data)
i = 0
# 以 4 字节对齐步长扫描 length 字段
while i < n - 64:
    ln = struct.unpack_from("<i", data, i)[0]
    if 8 <= ln <= 48:
        start = i + 4
        end = start + ln * 2
        if end <= n:
            raw = data[start:end]
            # UTF-16LE 且每个高字节为 0
            ok = True
            buf = []
            for k in range(ln):
                lo = raw[k * 2]
                hi = raw[k * 2 + 1]
                if hi != 0 or not (32 <= lo < 127):
                    ok = False
                    break
                buf.append(chr(lo))
            if ok:
                s = "".join(buf)
                found.append((i, ln, s))
    i += 4

print(f"total candidate strings: {len(found)}")
# 只打印像口令的：无明显空格、含混合大小写+数字+符号
import re

pat = re.compile(r"^[A-Za-z0-9_!@#$%^&*\-+=~]{8,48}$")
cands = [(o, ln, s) for o, ln, s in found if pat.match(s)]
print(f"token-like: {len(cands)}")
for o, ln, s in cands[:80]:
    print(f"  {o:#010x} len={ln:<3} {s!r}")
