# -*- coding: utf-8 -*-
"""按 methodPointers 索引直接读 64 位方法指针。

    python ptr64.py <lib> <idx> ...
"""
import struct
import sys

ARR = 0x146E848  # 64 位 lib 里 methodPointers 的文件偏移（= VA 0x147e848 - 0x10000）
COUNT = 4933


def main():
    path = sys.argv[1]
    d = open(path, "rb").read()
    for a in sys.argv[2:]:
        i = int(a, 0)
        if not (0 <= i < COUNT):
            print("idx %d 越界" % i)
            continue
        va = struct.unpack_from("<Q", d, ARR + i * 8)[0]
        print("idx %-6d 0x%x" % (i, va))


if __name__ == "__main__":
    main()
