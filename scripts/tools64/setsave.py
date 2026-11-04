# -*- coding: utf-8 -*-
"""按段改存档里的 JSON 字段（二进制段原样保留）。

    python setsave.py <src> <out> "13.ZuanShi=50000" ["13.JingYan=123" ...]
"""
import json
import sys

sys.path.insert(0, r"E:\DSH\game\djmwREA\scripts")
import v557save as V


def main():
    src, out = sys.argv[1], sys.argv[2]
    header, segs = V.read_segments(src)
    segs = list(segs)
    for spec in sys.argv[3:]:
        path, _, raw = spec.partition("=")
        sidx, _, key = path.partition(".")
        i = int(sidx)
        obj = json.loads(segs[i].decode("utf-8"))
        try:
            val = json.loads(raw)
        except Exception:
            val = raw
        old = obj.get(key)
        obj[key] = val
        segs[i] = json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        print("seg%-2d %-16s %r -> %r" % (i, key, old, val))
    V.write_segments(out, header, segs)
    print("写出 %s" % out)


if __name__ == "__main__":
    main()
