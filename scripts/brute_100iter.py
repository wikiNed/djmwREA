"""深挖 AESEncryptionAlgorithm 的流式 Encrypt/Decrypt，找 100 轮 key 派生。

关键假设：ES3_FILE 的 GetKey 实现大致为
    byte[] key = Encoding.UTF8.GetBytes(password);
    for (int i = 0; i < pwIterations; i++) key = MD5(key);   // 或 SHA256
    // 截取 keySize(16)

验证方法：静态反汇编找循环 + MD5/SHA 调用；
另一条更快的路：直接**运行时穷举 100 轮派生**，用已知口令候选打。

本脚本同时做后者：对每个候选口令做 100 轮 MD5/SHA256/SHA1 迭代，试解。
"""
from paths import EMU, ES3_FILE

import hashlib

from Crypto.Cipher import AES
blob = open(ES3_FILE, "rb").read()
iv, ct = blob[:16], blob[16:]

PW = ["password", "Password", "PASSWORD", "SaveFile.es3", "es3", "ES3",
      "TapDemons", "taptap", "HQGAMES", "game.taptap.HQGAMES.TapDemons",
      "dianji", "DianJi", "mowang", "MoWang"]


def ok_plain(body: bytes) -> bool:
    head = body[:200]
    if len(head) < 2:
        return False
    pr = sum(1 for b in head if 32 <= b < 127 or b in (9, 10, 13))
    return pr / len(head) >= 0.90 and head[:1] in (b"{", b"[")


def test(key: bytes, label: str):
    if len(key) not in (16, 24, 32):
        return False
    try:
        pt = AES.new(key, AES.MODE_CBC, iv).decrypt(ct)
    except Exception:
        return False
    pad = pt[-1]
    if not (1 <= pad <= 16 and pt[-pad:] == bytes([pad]) * pad):
        return False
    body = pt[:-pad]
    if ok_plain(body):
        print(f"\n*** MATCH {label}")
        print(body[:800])
        return True
    return False


HASHES = {
    "md5": lambda b: hashlib.md5(b).digest(),
    "sha1": lambda b: hashlib.sha1(b).digest(),
    "sha256": lambda b: hashlib.sha256(b).digest(),
}

found = False
for pw in PW:
    ub = pw.encode("utf-8")
    # 0 轮：直接用
    if test(ub, f"{pw} raw"):
        found = True
        break
    # 1..100 轮迭代
    for hname, hf in HASHES.items():
        cur = ub
        for it in range(1, 101):
            cur = hf(cur)
            if it in (1, 10, 99, 100):
                if test(cur[:16], f"{pw} {hname} x{it} [:16]"):
                    found = True
                    break
                if len(cur) >= 32 and test(cur[:32], f"{pw} {hname} x{it} [:32]"):
                    found = True
                    break
        if found:
            break
    if found:
        break

print("found" if found else "no match with 100-iteration hash chain")
