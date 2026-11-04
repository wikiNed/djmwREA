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
import struct
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from Crypto.Cipher import DES  # noqa: E402
from Crypto.Util.Padding import pad, unpad  # noqa: E402

#: ShuJuDate.MIMA —— 内层 DES 的 key 与 iv（同为这 8 字节）
KEY = b"PJSQJ678"
#: 文件尾标记
FOOTER = b"{"
#: 段分隔符
SEP = "$"
#: 段数
NUM_SEGMENTS = 14

# ----------------------------------------------------------------- header
#
# 2026-11 完全解出。header 是 Easy Save 2 的记录头，长度可变：
#
#     header = 7e 00 | uint32 LE (文件总长 - 6) | ff ee f1 e9 fd | varint(hex 长度)
#
#   * 第 1、2 字节固定 `7e 00`
#   * 偏移 2..5 是**小端 uint32**，等于「文件总长 − 6」
#     （即从偏移 6 到文件末尾的字节数）
#   * 偏移 6..10 是 5 字节固定常量 `ff ee f1 e9 fd`
#   * 偏移 11.. 是 .NET 的 7-bit varint，值为 hex 字符串的字符数
#     （= 密文字节数 × 2 = 文件总长 − header 长度 − 1）
#
# 因此 header 长度 = 11 + varint 长度，通常 3 字节 varint → 14 字节 header。
# 旧的 `h[11:14] = 0xCB90 + delta` 只在 delta ≤ 96 时碰巧成立，是错的。
HDR_PREFIX = bytes([0x7E, 0x00])
HDR_MAGIC = bytes.fromhex("ffeef1e9fd")
#: 兼容旧名：基线档（75167 字节）的天然头
BASE_HEADER = bytes.fromhex("7e0099250100ffeef1e9fd90cb04")
BASE_TOTAL = 75167
HEADER_LEN = len(BASE_HEADER)


def es2_varint(n):
    """写出 .NET ``Write7BitEncodedInt`` 的 7-bit varint。"""
    if n < 0:
        raise ValueError("varint 不能为负: %d" % n)
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out.append(b | 0x80)
        else:
            out.append(b)
            return bytes(out)


def read_es2_varint(buf, pos):
    """读回 7-bit varint，返回 (值, 占用字节数)。"""
    val = 0
    shift = 0
    for n in range(5):
        b = buf[pos + n]
        val |= (b & 0x7F) << shift
        if not (b & 0x80):
            return val, n + 1
        shift += 7
    raise ValueError("varint 超过 5 字节")


def make_header(hexlen):
    """按 hex 字符串长度生成合法 header。"""
    v = es2_varint(hexlen)
    total = len(HDR_PREFIX) + 4 + len(HDR_MAGIC) + len(v) + hexlen + len(FOOTER)
    return (HDR_PREFIX + struct.pack("<I", total - 6) + HDR_MAGIC + v)


def header_len_of(blob):
    """从文件字节推算出 header 的实际长度。"""
    _, n = read_es2_varint(blob, 11)
    return 11 + n


# ----------------------------------------------------------------- 解析

def split_parts(blob):
    """拆出 (header, des_body) 。"""
    if len(blob) < 15 + 8:
        raise ValueError("文件太短: %d 字节" % len(blob))
    hlen = header_len_of(blob)
    header = blob[:hlen]
    rest = blob[hlen:]
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


def un_fix_header_length(header):
    """已废弃：保留仅为兼容旧调用。header 现在由 ``make_header`` 整份重建。"""
    return BASE_HEADER


def build(header, plain):
    """由 header + 明文拼出完整文件字节。

    ``header`` 参数已不再被使用（长度字段由 ES2 结构唯一决定），
    保留是为了兼容既有调用点。真正写入的 header 由 ``make_header`` 按新
    明文长度重新生成。
    """
    body = encrypt_body(plain)
    hextext = binascii.hexlify(body).upper()
    hdr = make_header(len(hextext))
    return hdr + hextext + FOOTER


def fix_header_length(header, total_len):
    """按文件总长度重建 header（旧的「累加器」模型已被推翻）。"""
    hexlen = total_len - len(HDR_PREFIX) - 4 - len(HDR_MAGIC) - len(FOOTER)
    for _ in range(4):
        hdr = make_header(hexlen)
        real = len(hdr) + hexlen + len(FOOTER)
        if real == total_len:
            return hdr
        hexlen += total_len - real
    raise ValueError("无法为总长 %d 解出 header" % total_len)


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
    """读回自检：解出来再重新加密，应与原文件逐字节一致。

    注意不能直接 ``build(header, pt)`` —— 文件里的 header 已经带长度累加，
    再走一遍 ``fix_header_length`` 会二次累加。先用基线头重算。
    """
    blob = open(path, "rb").read()
    header, body = split_parts(blob)
    pt = decrypt_body(body)
    again = build(BASE_HEADER, pt)
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
