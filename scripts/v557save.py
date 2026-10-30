#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""旧版 v5.5.7（com.HQGAMES.TopDemons）存档读写。

格式（实测确认）::

    file = header(14 字节) || hex_upper( DES-CBC-PKCS7(明文) ) || b"{"

    key = iv = b"PJSQJ678"      # == ShuJuDate.MIMA
    明文   = 14 段 JSON，用 "$" 连接

与 TapTap 版（game.taptap.HQGAMES.TapDemons）的区别：
    旧版：单层 DES + hex 明文可读
    TapTap 版：外层 AES-128-CBC(PBKDF2 hqgames@2013) + 内层 DES

用法::

    python scripts/v557save.py info  save.es3
    python scripts/v557save.py dump  save.es3  out_dir
    python scripts/v557save.py verify save.es3
"""
import argparse
import binascii
import hashlib
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from Crypto.Cipher import DES  # noqa: E402
from Crypto.Util.Padding import pad, unpad  # noqa: E402

#: ShuJuDate.MIMA —— 内层 DES 的 key 与 iv（同为这 8 字节）
KEY = b"PJSQJ678"
#: 文件头长度（内容未解析，读档保留、写档原样回填）
HEADER_LEN = 14
#: 文件尾标记
FOOTER = b"{"
#: 段分隔符
SEP = "$"
#: 段数
NUM_SEGMENTS = 14


# ----------------------------------------------------------------- 解析

def split_parts(blob):
    """拆出 (header, des_body) 。"""
    if len(blob) < HEADER_LEN + 2:
        raise ValueError("文件太短: %d 字节" % len(blob))
    header = blob[:HEADER_LEN]
    rest = blob[HEADER_LEN:]
    if rest.endswith(FOOTER):
        rest = rest[:-len(FOOTER)]
    try:
        text = rest.decode("ascii")
    except UnicodeDecodeError as exc:
        raise ValueError("hex 段不是纯 ASCII：%s" % exc) from exc
    if len(text) % 2:
        raise ValueError("hex 字符数为奇数: %d" % len(text))
    body = binascii.unhexlify(text)
    return header, body


def decrypt_body(body):
    """DES-CBC-PKCS7 解密，返回明文字节串。"""
    if len(body) % 8:
        raise ValueError("密文长度 %d 不是 8 的倍数" % len(body))
    pt = DES.new(KEY, DES.MODE_CBC, KEY).decrypt(body)
    return unpad(pt, 8)


def read_save(path):
    """返回 (header, plaintext_bytes)。"""
    blob = open(path, "rb").read()
    header, body = split_parts(blob)
    return header, decrypt_body(body)


def read_segments(path):
    """返回 (header, [seg bytes] * 14)。"""
    header, pt = read_save(path)
    segs = pt.split(SEP.encode())
    if len(segs) != NUM_SEGMENTS:
        raise ValueError("段数 %d != %d" % (len(segs), NUM_SEGMENTS))
    return header, segs


# ----------------------------------------------------------------- 生成

def encrypt_body(plain):
    ct = DES.new(KEY, DES.MODE_CBC, KEY).encrypt(pad(plain, 8))
    return ct


def build(header, plain):
    """由 header + 明文拼出完整文件字节。

    header 里第 2、11 字节编码了文件总长度（相对基线 75167 的偏移）。
    这里会自动按实际长度重新计算这两个字节。
    """
    if len(header) != HEADER_LEN:
        raise ValueError("header 必须 %d 字节" % HEADER_LEN)
    body = encrypt_body(plain)
    total = HEADER_LEN + len(body) * 2 + len(FOOTER)
    hdr = fix_header_length(header, total)
    return hdr + binascii.hexlify(body).upper() + FOOTER


#: 头部中随长度线性变化的两个小端 16 位累加器 (低字节位置)
HDR_LEN_POS = (2, 11)
#: 长度编码基线（原档 75167 字节对应的天然头部）
BASE_TOTAL = 75167


def fix_header_length(header, total_len):
    """按文件总长度修正 header 里的长度累加器。

    实测：
        总长 75167 -> header[2..3]=0x2599  header[11..12]=0x0490
        总长 75231 -> header[2..3]=0x25D9  header[11..12]=0x04D0  (delta 0x40)
        总长 75183 -> header[2..3]=0x25A9  header[11..12]=0x04A0  (delta 0x10)

    两处都是**小端 16 位**，按 delta 直接相加（会进位到高字节）。
    早期只把低字节 +delta 并 &0xFF，delta 超过 255 时回绕导致解密失败。
    """
    hdr = bytearray(header)
    delta = total_len - BASE_TOTAL
    if delta == 0:
        return bytes(hdr)
    for p in HDR_LEN_POS:
        v = (hdr[p] | (hdr[p + 1] << 8)) + delta
        v &= 0xFFFF
        hdr[p] = v & 0xFF
        hdr[p + 1] = (v >> 8) & 0xFF
    return bytes(hdr)


def write_save(path, header, plain):
    data = build(header, plain)
    with open(path, "wb") as f:
        f.write(data)
    return len(data)


def write_segments(path, header, segs):
    if len(segs) != NUM_SEGMENTS:
        raise ValueError("段数 %d != %d" % (len(segs), NUM_SEGMENTS))
    plain = SEP.encode().join(s if isinstance(s, bytes) else s.encode()
                              for s in segs)
    return write_save(path, header, plain)


# ----------------------------------------------------------------- 自检

def verify(path):
    """读回自检：解出来再重新加密，应与原文件逐字节一致。"""
    blob = open(path, "rb").read()
    header, body = split_parts(blob)
    pt = decrypt_body(body)
    again = build(header, pt)
    ok = again == blob
    print("文件      : %s" % path)
    print("总长      : %d" % len(blob))
    print("header    : %s" % header.hex())
    print("密文      : %d 字节" % len(body))
    print("明文      : %d 字节" % len(pt))
    print("段数      : %d" % len(pt.split(b"$")))
    print("重加密一致: %s" % ok)
    if not ok:
        print("  !! 差异 %d 字节" % sum(1 for a, b in zip(again, blob) if a != b))
    return ok


def main():
    ap = argparse.ArgumentParser(description="旧版 v5.5.7 存档读写")
    ap.add_argument("cmd", choices=("info", "verify", "dump", "hex"))
    ap.add_argument("path")
    ap.add_argument("out", nargs="?", help="dump 的输出目录")
    a = ap.parse_args()

    if a.cmd == "verify":
        sys.exit(0 if verify(a.path) else 1)

    header, segs = read_segments(a.path)
    print("header : %s" % header.hex())
    if a.cmd == "hex":
        for i, s in enumerate(segs):
            print("seg%-2d %6d  %s" % (i, len(s),
                                       s[:70].decode("utf-8", "replace")))
        return
    if a.cmd == "info":
        for i, s in enumerate(segs):
            print("seg%-2d %6d 字节  %s"
                  % (i, len(s), s[:60].decode("utf-8", "replace")))
        return
    if a.cmd == "dump":
        out = a.out or "."
        os.makedirs(out, exist_ok=True)
        for i, s in enumerate(segs):
            p = os.path.join(out, "seg%02d.json" % i)
            with open(p, "wb") as f:
                f.write(s)
        print("已写出 %d 段到 %s" % (len(segs), out))


if __name__ == "__main__":
    main()
