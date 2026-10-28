"""精确爆破 ES3 口令：对 global-metadata.dat 的全部字符串字面量做 PBKDF2。

算法（已由反汇编确定）：
  key = PBKDF2-HMAC-SHA1(password, salt, 100, dkLen=16)
  AES-128-CBC, IV = 文件偏移 16..32, 密文 = 32..
  文件偏移 0..16 = salt

判据（极严格）：
  解出的明文必须从 '{' 或 '\xef\xbb\xbf{' 开始，且能 json 解析前 200 字节，
  或整体能按 '$' 切片且每片都能 json 解析。

133048 条 × PBKDF2(100 轮) 单线程约 15 分钟；这里先只取长度 1..64 的
字面量（口令几乎不可能更长），并用多进程加速。
"""

from paths import EMU
SAVE_OUT = EMU / 'save_decrypted.json'
from paths import ES3_FILE, META
import hashlib
import json
import struct
import sys

from Crypto.Cipher import AES

MD = META
ES3 = ES3_FILE


def load_literals():
    d = open(MD, "rb").read()
    # header: magic(4) version(4) = 8, 然后 32 组 (offset,size)
    lit_off, lit_cnt = struct.unpack_from("<ii", d, 8 + 0 * 8)
    lit_data_off, lit_data_cnt = struct.unpack_from("<ii", d, 8 + 2 * 8)
    base = 8 + 32 * 8
    lits = []
    for i in range(lit_cnt):
        ln, off = struct.unpack_from("<ii", d, base + lit_off + i * 8)
        blob = d[base + lit_data_off + off: base + lit_data_off + off + ln]
        lits.append(blob)
    return lits


def key_for(pw: bytes, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac("sha1", pw, salt, 100, 16)


def check(pt: bytes):
    if not pt:
        return None
    body = pt
    if body.startswith(b"\xef\xbb\xbf"):
        body = body[3:]
    if not body.startswith(b"{"):
        return None
    # 尝试整体 JSON
    try:
        json.loads(body.decode("utf-8"))
        return "json"
    except Exception:
        pass
    # 尝试 $ 切片
    parts = body.split(b"$")
    if len(parts) > 1:
        ok = 0
        for p in parts:
            try:
                json.loads(p.decode("utf-8"))
                ok += 1
            except Exception:
                break
        if ok == len(parts):
            return f"segments({len(parts)})"
    return None


def main():
    ct_all = open(ES3, "rb").read()
    salt, iv, ct = ct_all[:16], ct_all[16:32], ct_all[32:]
    lits = load_literals()
    print(f"字面量总数: {len(lits)}", flush=True)

    cands = [x for x in lits if 1 <= len(x) <= 64]
    print(f"长度 1..64 的候选: {len(cands)}", flush=True)

    # 去重且优先试 ASCII 可打印的
    seen = set()
    uniq = []
    for x in cands:
        if x in seen:
            continue
        seen.add(x)
        uniq.append(x)
    print(f"去重后: {len(uniq)}", flush=True)

    for i, pw in enumerate(uniq):
        if i % 5000 == 0:
            print(f"  ...{i}", flush=True)
        try:
            key = key_for(pw, salt)
        except Exception:
            continue
        pt = AES.new(key, AES.MODE_CBC, iv).decrypt(ct[: 16 * 1])  # 只解首块，快
        if not (pt[:1] in (b"{", b"\xef", b"[", b" ", b"\n", b"\t")):
            continue
        # 首块像 JSON，完整解一次确认
        full = AES.new(key, AES.MODE_CBC, iv).decrypt(ct)
        pad = full[-1]
        if 1 <= pad <= 16 and full.endswith(bytes([pad]) * pad):
            full = full[:-pad]
        r = check(full)
        if r:
            print(f"\n*** 命中 *** {r}", flush=True)
            print("password =", pw, flush=True)
            print("password(hex) =", pw.hex(), flush=True)
            open(str(SAVE_OUT), "wb").write(full)
            print("已写出 save_decrypted.json", len(full), "字节", flush=True)
            return 0
    print("\n未命中", flush=True)
    return 1


if __name__ == "__main__":
    sys.exit(main())
