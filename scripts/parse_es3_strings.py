"""精确解析 ES3Defaults 的 ES3SerializableSettings 序列化块。

发现：UnityType 树被剥离（IL2CPP），但 MonoBehaviour 数据仍是标准序列化：
每个字段前有 4 字节对齐长度（含 \\0 的字符串）。

已知锚点（data.unity3d 偏移，十六进制）：
  0xead7a6: len=11 "ES3Defaults"        <- m_Name
  0xead7b6: 00 f1 01 0c 00 00 00 "SaveFile.es3"   <- path = "SaveFile.es3"
  0xead7ca: 15 00 f1 00 00 00 00 08 00 00 00 "password"  <- 可能是 assemblyNames 或字段名残留

注意 0xf1 是标志字节（Unity 对象内的 alignment/marker），不是数据。

策略：从 "SaveFile.es3" 之后开始，按 [len][bytes][pad] 扫描连续字符串，
        并尝试把每个"看起来是口令"的字符串当作 AES key。
"""

from paths import ES3_FILE, unity_data_asset
import struct

from Crypto.Cipher import AES

UNITY = unity_data_asset()
ES3 = unity_data_asset()
import os
if not os.path.exists(ES3):
    ES3 = ES3_FILE

raw = open(UNITY, "rb").read()
blob = open(ES3, "rb").read()
iv, ct = blob[:16], blob[16:]


def ok_plain(body: bytes) -> bool:
    head = body[:200]
    if len(head) < 2:
        return False
    printable = sum(1 for b in head if 32 <= b < 127 or b in (9, 10, 13))
    if printable / len(head) < 0.92:
        return False
    return head[:1] in (b"{", b"[")


def try_decrypt(key: bytes):
    if len(key) not in (16, 24, 32):
        return None
    try:
        pt = AES.new(key, AES.MODE_CBC, iv).decrypt(ct)
    except Exception:
        return None
    pad = pt[-1]
    if not (1 <= pad <= 16 and pt[-pad:] == bytes([pad]) * pad):
        return None
    body = pt[:-pad]
    return body if ok_plain(body) else None


# 1) 先把 anchor 区域所有 [len][ascii] 字符串揪出来
ANCHOR = 0xEAD7A6
region = raw[ANCHOR - 64 : ANCHOR + 800]
found = []
i = 0
while i < len(region) - 4:
    (ln,) = struct.unpack_from("<I", region, i)
    if 1 <= ln <= 64 and i + 4 + ln <= len(region):
        cand = region[i + 4 : i + 4 + ln]
        if all(32 <= b < 127 for b in cand[:-1]) and cand[-1] == 0:
            found.append((ANCHOR - 64 + i, cand[:-1].decode("ascii")))
            i += 4 + ln + ((4 - ln % 4) % 4)
            continue
    i += 1

print(f"=== 字符串候选 ({len(found)}) ===")
for off, s in found:
    print(f"  0x{off:x}  {s!r}")

# 2) 逐个当口令试
print("\n=== 当作 AES 口令试解 ===")
for off, s in found:
    b = s.encode("utf-8")
    for variant, key in (("raw", b), ("pad0", b + b"\x00" * (16 - len(b)) if len(b) < 16 else b)):
        r = try_decrypt(key)
        if r:
            print(f"*** MATCH 0x{off:x} {s!r} ({variant})")
            print(r[:600])
            raise SystemExit(0)
print("no match")
