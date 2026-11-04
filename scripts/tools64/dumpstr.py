# -*- coding: utf-8 -*-
"""打印 global-metadata.dat 某区间里的可读字符串。

    python dumpstr.py <meta> <start_hex> <end_hex>
"""
import re
import sys


def main():
    data = open(sys.argv[1], "rb").read()
    s = int(sys.argv[2], 0)
    e = int(sys.argv[3], 0)
    chunk = data[s:e]
    for m in re.finditer(rb"[\x20-\x7e\xe0-\xef\x80-\xbf]{4,}", chunk):
        try:
            t = m.group().decode("utf-8")
        except Exception:
            continue
        print("0x%08x  %s" % (s + m.start(), t))


if __name__ == "__main__":
    main()
