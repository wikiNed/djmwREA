#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用旧版 v5.5.7 模板批量修改存档。

与 TapTap 版 new_save.py 的区别：
  - 加密层用 v557save（单层 DES + hex），不需要 salt/iv
  - 模板来自旧版 data.unity3d 解出的 playerDate_03_v557.bin

用法::

    python scripts/v557_edit.py --in save.es3 --out new.es3 \
        --tree --gem 88888 --pets
"""
import argparse
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import v557save  # noqa: E402

TEMPLATE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "evidence", "templates")
TEMPLATE_03 = os.path.join(TEMPLATE_DIR, "playerDate_03_v557.bin")


def load_template():
    with open(TEMPLATE_03, encoding="utf-8") as f:
        txt = f.read()
    segs = txt.split("$")
    if len(segs) != v557save.NUM_SEGMENTS:
        raise SystemExit("模板段数 %d != 14" % len(segs))
    return segs


def jload(b):
    if isinstance(b, bytes):
        b = b.decode("utf-8")
    return json.loads(b)


def jdump(o):
    return json.dumps(o, ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8")


def report(segs, title):
    print("--- %s ---" % title)
    j11 = jload(segs[11])
    j9 = jload(segs[9])
    j6 = jload(segs[6])
    pets = j6.get("SuoYouChongWuDate") or []
    print("  seg11 (生命树) IsJiHuo=%s IsHuangJin=%s GuoQiTime=%s"
          % (j11.get("IsJiHuo"), j11.get("IsHuangJin"), j11.get("GuoQiTime")))
    print("  seg9  (宝石洞) BaoShiSuiPian=%s" % j9.get("BaoShiSuiPian"))
    print("  seg6  (宠物)   数量=%d" % len(pets))
    if pets:
        p = pets[0]
        print("        首只 ID=%s Lv=%s JinHua=%s JinJie=%s IsMaoXian=%s"
              % (p.get("ChongWuID"), p.get("ChongWuLevel"),
                 p.get("ChongWuJinHua"), p.get("ChongWuJinJie"),
                 p.get("IsMaoXian")))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="src", required=True)
    ap.add_argument("--out", dest="dst", required=True)
    ap.add_argument("--tree", action="store_true", help="解锁黄金树")
    ap.add_argument("--gem", type=int, default=None, help="宝石碎片数量")
    ap.add_argument("--pets", action="store_true", help="从模板补全宠物")
    ap.add_argument("--pets-level", type=int, default=60)
    ap.add_argument("--pet-food", type=int, default=None,
                    help="ChongWuSiLiao 数量")
    ap.add_argument("--evolve-stone", type=int, default=None,
                    help="六种 JinHuaShi_* 各设多少")
    ap.add_argument("--grass-reset", action="store_true",
                    help="草丛刷新时间归零（立即刷新）")
    ap.add_argument("--auto-skill", action="store_true",
                    help="ChongWuIsZiDongJiNeng=1")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    header, segs = v557save.read_segments(a.src)
    segs = list(segs)
    report(segs, "修改前")

    changed = []

    if a.pets or a.pet_food is not None or a.evolve_stone is not None \
            or a.grass_reset or a.auto_skill:
        j6 = jload(segs[6])
        touched = []

        if a.pets:
            tpl = load_template()
            tpets = jload(tpl[6]).get("SuoYouChongWuDate") or []
            cur = j6.get("SuoYouChongWuDate") or []
            by_id = {p.get("ChongWuID"): dict(p) for p in tpets}
            out = []
            for p in cur:
                pid = p.get("ChongWuID")
                src = by_id.get(pid)
                if src:
                    np = dict(src)
                    np["ChongWuLevel"] = a.pets_level
                    np["IsMaoXian"] = -1
                    np["IsXieDai"] = 0
                    out.append(np)
                else:
                    out.append(p)
            have = {p.get("ChongWuID") for p in out}
            for pid, src in by_id.items():
                if pid not in have:
                    np = dict(src)
                    np["ChongWuLevel"] = a.pets_level
                    np["IsMaoXian"] = -1
                    np["IsXieDai"] = 0
                    out.append(np)
            j6["SuoYouChongWuDate"] = out
            if "DianIsOpen" in j6:
                j6["DianIsOpen"] = [1] * len(j6["DianIsOpen"])
            touched.append("宠物 %d -> %d 只（等级 %d）"
                           % (len(cur), len(out), a.pets_level))

        if a.pet_food is not None:
            old = j6.get("ChongWuSiLiao")
            j6["ChongWuSiLiao"] = a.pet_food
            touched.append("肉 %s -> %d" % (old, a.pet_food))

        if a.evolve_stone is not None:
            for k in ("JinHuaShi_An", "JinHuaShi_Di", "JinHuaShi_Feng",
                      "JinHuaShi_Guang", "JinHuaShi_Huo", "JinHuaShi_Shui"):
                if k in j6:
                    j6[k] = a.evolve_stone
            touched.append("六种进化石 -> %d" % a.evolve_stone)

        if a.grass_reset:
            old = j6.get("CaoCongChongZhiTime")
            j6["CaoCongChongZhiTime"] = 0
            touched.append("草丛刷新 %s -> 0" % old)

        if a.auto_skill:
            j6["ChongWuIsZiDongJiNeng"] = 1
            touched.append("自动技能 = 1")

        segs[6] = jdump(j6)
        for t in touched:
            changed.append("seg6 " + t)

    if a.tree:
        j11 = jload(segs[11])
        j11["IsJiHuo"] = 1
        j11["IsHuangJin"] = 1
        j11["GuoQiTime"] = 4102416000000
        segs[11] = jdump(j11)
        changed.append("seg11 黄金树解锁")

    if a.gem is not None:
        j9 = jload(segs[9])
        j9["BaoShiSuiPian"] = a.gem
        segs[9] = jdump(j9)
        changed.append("seg9 BaoShiSuiPian=%d" % a.gem)

    if not changed:
        print("\n没有任何修改，退出")
        return 1

    print("\n修改项:")
    for c in changed:
        print("  -", c)

    report(segs, "修改后")

    if a.dry_run:
        print("\n[dry-run] 不写出")
        return 0

    size = v557save.write_segments(a.dst, header, segs)
    print("\n写出 %s : %d 字节" % (a.dst, size))
    v557save.verify(a.dst)
    return 0


if __name__ == "__main__":
    sys.exit(main())
