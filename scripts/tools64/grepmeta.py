# -*- coding: utf-8 -*-
"""在 global-metadata.dat 里搜 UTF-8 字符串，打印命中位置及邻近字符串。"""
import re
import sys


def main():
    path = sys.argv[1]
    words = sys.argv[2:]
    data = open(path, "rb").read()
    for w in words:
        needle = w.encode("utf-8")
        print("=== %s ===" % w)
        start = 0
        n = 0
        while True:
            i = data.find(needle, start)
            if i < 0:
                break
            s = i
            while s > 0 and 32 <= data[s - 1] < 127:
                s -= 1
            e = i + len(needle)
            while e < len(data) and 32 <= data[e] < 127:
                e += 1
            try:
                txt = data[s:e].decode("utf-8")
            except Exception:
                txt = repr(data[max(0, i - 24): i + 48])
            print("  0x%08x  %s" % (i, txt))
            n += 1
            start = i + 1
            if n > 12:
                break


if __name__ == "__main__":
    main()
