import struct, os, sys
from pathlib import Path

p = str(Path(__file__).resolve().parent.parent / 'emu' / 'SaveFile.es3')
data = open(p, "rb").read()
print("size:", len(data), "first16:", data[:16].hex())

# ES3 默认文件格式：
#   [4字节 版本格式] 或直接是 AES 加密的 key 表
# ES3 File 格式（未加密）：先 4 字节的 key 数？实际是：
#   byte[4] "ES3 " magic? 不，ES3 文件是没有 magic 的 JSON
# 加密时：头部是 IV(16B) + 密文，整体长度应为 16 的倍数
print("len % 16 =", len(data) % 16)
iv = data[:16]
ct = data[16:]
print("IV:", iv.hex())
print("ciphertext len:", len(ct), "mod16:", len(ct) % 16)

# 尝试常见 ES3 AES 头：前 4 字节可能是格式标记
print("\n--- 按 ES3 官方 AES 格式尝试 ---")
# ES3 加密文件结构：IV(16) + AES-128-CBC(payload)
# 解密后应为 JSON，形如 { "key1" : {...}, "key2": ... }
