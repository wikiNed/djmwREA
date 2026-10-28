#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一次性探查：把存档 14 段的结构、关键数值、以及"可改面"打印出来。

用法:
    python scripts/probe_save.py saves/playerDate_01.json
    python scripts/probe_save.py saves/playerDate_01.json --seg 9
"""
import json
import sys


def load(p):
    t = open(p, encoding="utf-8-sig").read()
    return [json.loads(x) for x in t.split("$") if x.strip()]


def shape(v, depth=0):
    if isinstance(v, dict):
        return "{%d keys}" % len(v) if depth > 2 else {
            k: shape(x, depth + 1) for k, x in list(v.items())[:12]
        }
    if isinstance(v, list):
        return "[%d]" % len(v) if depth > 2 else [shape(v[0], depth + 1)] if v else []
    return v


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    path = argv[0]
    only = None
    if "--seg" in argv:
        only = int(argv[argv.index("--seg") + 1])

    segs = load(path)
    for s in segs:
        d = s.get("DateID")
        if only is not None and d != only:
            continue
        print("=" * 70)
        print("seg %s  (%d fields)" % (d, len(s)))
        for k, v in s.items():
            if k == "DateID":
                continue
            t = type(v).__name__
            if isinstance(v, list):
                head = shape(v[0]) if v else None
                print("  %-28s list[%-4d] first=%s" % (k, len(v), json.dumps(head, ensure_ascii=False)[:150]))
            elif isinstance(v, dict):
                print("  %-28s dict[%d] %s" % (k, len(v), json.dumps(shape(v), ensure_ascii=False)[:200]))
            else:
                print("  %-28s %-8s %s" % (k, t, json.dumps(v, ensure_ascii=False)[:100]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
