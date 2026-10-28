"""从 ES3 文件反推口径，验证 '\\nError: ' 这个 16 字节口令是不是真的。

刚才 try_key 给了个假阳性匹配：只要 key 长度恰好 16、解出来的尾字节碰巧符合 PKCS7
就会被判为命中。13726 个候选 × 3 种 keylen，总会撞上。

正确做法：
  1. 只把 key 长度 == len(password bytes) 的候选当作“真的用了这个口令”
  2. 更严格的验证：解出的明文必须是可读 UTF-8 / 可解析 JSON
  3. ES3 实际格式：文件头 16 字节 IV + 密文，且明文是 ES3 的 ASCII 标签流
     （ES3 非 JSON 模式：tag 字节 + 变量名 + 值），或者 Games/Prefabs 序列化流。

先看真实存档的前 64 字节密文解密后长什么样 —— 用严格判据重扫。
"""
import json
import struct

from Crypto.Cipher import AES

META = r"E:\DSH\game\.rea-study\lib\global-metadata.dat"
ES3 = r"E:\DSH\game\.rea-study\emu\SaveFile.es3"

meta = open(META, "rb").read()
SL_OFF, SL_CNT, SLD_OFF = 256, 133048, 133304


def lit(i):
    ln, di = struct.unpack_from("<ii", meta, SL_OFF + i * 8)
    return meta[SLD_OFF + di : SLD_OFF + di + ln].decode("utf-8", "replace")


blob = open(ES3, "rb").read()
iv, ct = blob[:16], blob[16:]


def looks_like_es3(body: bytes) -> bool:
    """严格判据：ES3 明文开头应是可读文本（JSON 或 ES3 标签流）。"""
    head = body[:256]
    if not head:
        return False
    # 全部是可打印 ASCII / 制表换行
    printable = sum(1 for b in head if 32 <= b < 127 or b in (9, 10, 13))
    if printable / len(head) < 0.95:
        return False
    # 进一步：应包含这些 ES3 常见关键字之一
    try:
        txt = head.decode("ascii", "replace")
    except Exception:
        return False
    return txt.startswith("{") or txt.startswith("[")


def try_key_strict(pw: str):
    kb = pw.encode("utf-8")
    if len(kb) not in (16, 24, 32):
        return None
    try:
        pt = AES.new(kb, AES.MODE_CBC, iv).decrypt(ct)
    except Exception:
        return None
    pad = pt[-1]
    if not (1 <= pad <= 16 and pt[-pad:] == bytes([pad]) * pad):
        return None
    body = pt[:-pad]
    if looks_like_es3(body):
        return body
    return None


hits = []
for i in range(SL_CNT // 8):
    try:
        s = lit(i)
    except Exception:
        continue
    if len(s) in (16, 24, 32):
        r = try_key_strict(s)
        if r:
            hits.append((i, s, r[:100]))
            print(f"*** HIT literal#{i} {s!r}")
            print(r[:300])

print(f"\nstrict hits: {len(hits)}")
if not hits:
    print("no strict hit —— 口令不是 metadata 里长度恰为 16/24/32 的字面量")
