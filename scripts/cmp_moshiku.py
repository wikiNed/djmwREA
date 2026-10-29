# -*- coding: utf-8 -*-
"""对比旧版与 TapTap 版 MoShiKuGuaiDate 魔石窟怪物表。

第一眼看到字节数 87282 vs 39005 会以为内容砍掉一半，
但两份文件开头就不同：TapTap 版是紧凑排版（`"shengWu": [`），
旧版是展开排版（`"shengWu":\n    [`）。所以先按 JSON 解析再比，
不能拿文件大小当内容差异的证据。
"""
import json
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NEW = os.path.join(BASE, "evidence", "templates", "MoShiKuGuaiDate.bin")
OLD = os.path.join(BASE, "evidence", "templates", "MoShiKuGuaiDate_v557.bin")


def load(p):
    with open(p, "rb") as f:
        raw = f.read()
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    return json.loads(raw.decode("utf-8")), raw


def shape_keys(objs):
    """统计对象列表里出现过的所有字段名。"""
    keys = {}
    for o in objs:
        if isinstance(o, dict):
            for k in o:
                keys[k] = keys.get(k, 0) + 1
    return keys


def main():
    new, new_raw = load(NEW)
    old, old_raw = load(OLD)

    print("=== 顶层 ===")
    print("新版 top keys:", list(new.keys()) if isinstance(new, dict) else type(new))
    print("旧版 top keys:", list(old.keys()) if isinstance(old, dict) else type(old))
    print()

    for label, d, raw in (("新版(TapTap v5.9.2)", new, new_raw), ("旧版(v5.5.7)", old, old_raw)):
        sw = d.get("shengWu", [])
        print("%s: %d B, %d 只怪物" % (label, len(raw), len(sw)))
        ks = shape_keys(sw)
        print("   字段 %d 个: %s" % (len(ks), ", ".join(sorted(ks))))
        if sw:
            print("   ID 范围: %s .. %s" % (sw[0].get("ID"), sw[-1].get("ID")))
        # 其他顶层数组
        for k, v in d.items():
            if k == "shengWu":
                continue
            if isinstance(v, list):
                print("   顶层数组 %s: %d 项" % (k, len(v)))
            else:
                print("   顶层字段 %s: %r" % (k, v if not isinstance(v, (dict,)) else "<dict>"))
        print()

    a = {o["ID"]: o for o in new.get("shengWu", [])}
    b = {o["ID"]: o for o in old.get("shengWu", [])}
    only_new = sorted(set(a) - set(b))
    only_old = sorted(set(b) - set(a))
    both = sorted(set(a) & set(b))
    print("=== ID 集合 ===")
    print("共有 %d, 仅新版 %d, 仅旧版 %d" % (len(both), len(only_new), len(only_old)))
    if only_new:
        print("  仅新版 ID:", only_new[:20], "…" if len(only_new) > 20 else "")
    if only_old:
        print("  仅旧版 ID:", only_old[:20], "…" if len(only_old) > 20 else "")
    print()

    ka, kb = shape_keys(a.values()), shape_keys(b.values())
    print("=== 字段差异 ===")
    print("仅新版字段:", sorted(set(ka) - set(kb)) or "无")
    print("仅旧版字段:", sorted(set(kb) - set(ka)) or "无")
    print()

    changed = []
    for i in both:
        if a[i] != b[i]:
            changed.append(i)
    print("=== 同 ID 但内容不同: %d 个 ===" % len(changed))
    if changed:
        i = changed[0]
        print("例 ID=%s" % i)
        for k in sorted(set(a[i]) | set(b[i])):
            va, vb = a[i].get(k), b[i].get(k)
            if va != vb:
                print("   %-24s 新=%-24r 旧=%r" % (k, va, vb))
    return 0


if __name__ == "__main__":
    sys.exit(main())
