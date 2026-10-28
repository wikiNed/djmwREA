"""从 global-metadata.dat 提取 string literal，搜索口令候选。"""
from paths import META

import re
import struct
data = open(META, "rb").read()

SL_OFF, SL_CNT = 256, 133048
SLD_OFF = 133304
N = SL_CNT // 8
print("string literal entries:", N)

lits = []
for i in range(N):
    ln, di = struct.unpack_from("<ii", data, SL_OFF + i * 8)
    if 1 <= ln <= 96:
        raw = data[SLD_OFF + di : SLD_OFF + di + ln]
        try:
            s = raw.decode("utf-8")
        except UnicodeDecodeError:
            continue
        lits.append((i, di, ln, s))

print("decoded:", len(lits))

pat = re.compile(r"(?i)pass|encrypt|secret|es3|savefile|\.es3")
hits = [(i, di, ln, s) for i, di, ln, s in lits if pat.search(s)]
print(f"\n=== keyword hits: {len(hits)} ===")
for i, di, ln, s in hits:
    print(f"  idx={i:<7} dataIdx={di:<7} len={ln:<3} {s!r}")

print("\n=== 32-64 字符、无空格的纯 token 型字符串（可能的口令）===")
cand = [
    (i, di, ln, s)
    for i, di, ln, s in lits
    if 16 <= ln <= 64 and " " not in s and "\n" not in s and s.isprintable()
]
print(f"total {len(cand)}")
for i, di, ln, s in cand[:120]:
    print(f"  idx={i:<7} len={ln:<3} {s!r}")
