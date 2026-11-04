# -*- coding: utf-8 -*-
"""在模拟器存档（v5.5.7 DES 格式）上改字段并重新封装。

用法：
    python fix_account.py <src.save> <out.save> [k=v ...]
k 可以是 "seg13.ZhangHao=1007421637@qq.com" 这种形式，v 按 JSON 解析（失败则当字符串）。
"""
import json
import os
import sys

sys.path.insert(0, r"E:\DSH\game\djmwREA\scripts")
import v557save as V


def main():
    src, out = sys.argv[1], sys.argv[2]
    segs = [s if isinstance(s, str) else s.decode("utf-8") for s in V.read_segments(src)]
    segs = list(segs)
    for spec in sys.argv[3:]:
        key, val = spec.split("=", 1)
        segname, field = key.split(".", 1)
        idx = int(segname[3:])
        obj = json.loads(segs[idx])
        try:
            parsed = json.loads(val)
        except Exception:
            parsed = val
        old = obj.get(field, "<missing>")
        obj[field] = parsed
        segs[idx] = json.dumps(obj, ensure_ascii=False, separators=(",", ":"))
        print("seg%d.%s: %r -> %r" % (idx, field, old, parsed))
    n = V.write_segments(out, None, segs)
    print("wrote %s  %d bytes" % (out, n))


if __name__ == "__main__":
    main()
