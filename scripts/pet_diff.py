#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""对比满级模板 playerDate_03 与当前存档的宠物条目，找出「未知型」成因。

用法
====
    python scripts/pet_diff.py work/live/SaveFile_rich.es3
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import es3save  # noqa: E402
import savedit  # noqa: E402
import paths  # noqa: E402


def load_segs(path):
    """读 .es3 -> 14 段 dict。read_save 返回 14 个 bytes，段间用 '$' 拼接。"""
    parts = es3save.read_save(str(path))
    if isinstance(parts, (list, tuple)):
        text = "$".join(p.decode("utf-8") if isinstance(p, bytes) else p for p in parts)
    else:
        text = parts.decode("utf-8") if isinstance(parts, bytes) else parts
    return savedit.load(text)


def main():
    save = sys.argv[1] if len(sys.argv) > 1 else "work/live/SaveFile_rich.es3"

    # 满级模板
    tpl_path = paths.REPO / "work" / "textassets" / "ta_161_104886.bin"
    if not tpl_path.exists():
        print("缺少模板 %s（先跑 UnityPy 导出 TextAsset）" % tpl_path)
        return 1
    tpl_segs = savedit.load(tpl_path.read_text(encoding="utf-8", errors="replace"))
    tpl_pets = tpl_segs[6]["SuoYouChongWuDate"]

    segs = load_segs(save)
    cur_pets = segs[6]["SuoYouChongWuDate"]

    print("模板宠物数 = %d  (ID %d..%d)" % (
        len(tpl_pets), min(p["ChongWuID"] for p in tpl_pets),
        max(p["ChongWuID"] for p in tpl_pets)))
    print("当前宠物数 = %d  (ID %d..%d)" % (
        len(cur_pets), min(p["ChongWuID"] for p in cur_pets),
        max(p["ChongWuID"] for p in cur_pets)))
    print()

    tby = {p["ChongWuID"]: p for p in tpl_pets}
    print("%-4s %-6s %-6s %-6s %-8s %-10s %-10s" % (
        "ID", "Lv(模)", "Lv(我)", "JinHua", "JinJie", "HP", "Dmg"))
    for pid in (0, 1, 6, 10, 45, 75, 84):
        t = tby.get(pid)
        c = cur_pets[pid] if pid < len(cur_pets) else None
        if not t or not c:
            print("%-4d 缺失" % pid)
            continue
        print("%-4d %-6s %-6s %-6s %-8s %-10s %-10s" % (
            pid,
            t["ChongWuLevel"], c.get("ChongWuLevel"),
            "%s/%s" % (t["ChongWuJinHua"], c.get("ChongWuJinHua")),
            "%s/%s" % (t["ChongWuJinJie"], c.get("ChongWuJinJie")),
            "%s/%s" % (t["ChongWuYongJiu_HP"], c.get("ChongWuYongJiu_HP")),
            "%s/%s" % (t["ChongWuYongJiu_Damage"], c.get("ChongWuYongJiu_Damage")),
        ))
    print()

    print("模板 seg6 其他字段：")
    for k, v in tpl_segs[6].items():
        if k == "SuoYouChongWuDate":
            continue
        print("  %-24s = %r" % (k, v))
    print()
    print("当前 seg6 其他字段：")
    for k, v in segs[6].items():
        if k == "SuoYouChongWuDate":
            continue
        print("  %-24s = %r" % (k, v))
    return 0


if __name__ == "__main__":
    sys.exit(main())
