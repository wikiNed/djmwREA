"""手工解析 ES3Defaults。

UnityPy 在这个 bundle 上不提供 byte_offset（压缩块），
所以回到原始字节手工处理。

从 hexdump 看，0xead7a6 处的 0b 00 00 00 "ES3Defaults" 后紧跟 0x27，
说明 0x27 是**下一个**结构的起点，即：
    0xead7a6: len=0x0b, "ES3Defaults" (11 bytes, 无 \\0 填充到 0x...b1 = 0xead7b5)
    0xead7b6: 27 00 f1 01 0c 00 00 00 "SaveFile.es3" 15 00 ...
              ^^ 0x27 是某个 PPtr/长度标记

真正的 ES3Defaults m_Script 布局（POJO，无 typetree 时就是裸字节）：
    ES3Defaults:
        m_GameObject : PPtr (8 bytes: fileID int32, pathID int64) = 12 bytes
        m_Enabled    : 1 byte + align3
        m_Script     : PPtr (12 bytes)
        m_Name       : string
        settings(path string, encryptionType int, compressionType int,
                 encryptionPassword string, directory int, format int,
                 prettyPrint bool, bufferSize int, encoding int,
                 saveChildren bool, postprocessRawCachedData bool,
                 typeChecking bool, safeReflection bool,
                 memberReferenceMode int, referenceMode int,
                 serializationDepthLimit int, assemblyNames string[])
        addMgrToSceneAutomatically bool
        autoUpdateReferences bool
        addAllPrefabsToManager bool
        serializationDepthLimit int

"ES3Defaults" 是 m_Name，则它之前 12+4+12 = 28 字节是 GameObject/Enabled/Script 头。
字符串之后应是 settings.path = "SaveFile.es3"。

从 hexdump：ES3Defaults 后是 0x27 (39)，再 0x00 0xf1 0x01，再 0c 00 00 00 "SaveFile.es3"。
所以 m_Name 之后先有一个 39 字节长的块（0x27），然后才是 path。

不合理 —— 更可能是 0x27 是 "SaveFile.es3" 前面的对齐噪声。

直接做法：从 "SaveFile.es3" 结尾处按 4 字节对齐继续解析整数与字符串，
把沿途每个可疑 ASCII 串都当作 AES 口令试一遍。
"""

from paths import ES3_FILE, unity_data_asset
import struct

from Crypto.Cipher import AES

UNITY = unity_data_asset()
ES3 = ES3_FILE

raw = open(UNITY, "rb").read()
blob = open(ES3, "rb").read()
iv, ct = blob[:16], blob[16:]


def ok_plain(body: bytes) -> bool:
    head = body[:200]
    if len(head) < 2:
        return False
    pr = sum(1 for b in head if 32 <= b < 127 or b in (9, 10, 13))
    return pr / len(head) >= 0.92 and head[:1] in (b"{", b"[")


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


base = 0xEAD7A6
region = raw[base : base + 900]

print("=== region ASCII 串（含偏移） ===")
import re

cands = []
for m in re.finditer(rb"[\x20-\x7e]{4,}", region):
    s = m.group().decode("ascii")
    print(f"  +0x{m.start():03x}  {s!r}")
    cands.append(s)

print("\n=== 全部当口令试 ===")
for s in cands:
    b = s.encode()
    variants = {
        "raw": b,
        "pad0_16": (b + b"\x00" * 16)[:16] if len(b) < 16 else None,
        "pad0_32": (b + b"\x00" * 32)[:32] if len(b) < 32 else None,
    }
    for label, k in variants.items():
        if not k:
            continue
        r = try_decrypt(k)
        if r:
            print(f"*** MATCH {s!r} variant={label}")
            print(r[:600])
            raise SystemExit(0)
print("no match")
