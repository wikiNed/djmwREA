# -*- coding: utf-8 -*-
"""列出魔石窟怪物表全部条目，并标出 TapTap 版新增的两只。"""
import json
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(p):
    with open(p, "rb") as f:
        raw = f.read()
    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    return json.loads(raw.decode("utf-8"))


new = load(os.path.join(BASE, "evidence", "templates", "MoShiKuGuaiDate.bin"))
old_ids = {o["ID"] for o in load(os.path.join(BASE, "evidence", "templates", "MoShiKuGuaiDate_v557.bin"))["shengWu"]}


def flat(v):
    """HP/Damage 有时是 int，有时是 list（按难度分档）。统一成字符串。"""
    if isinstance(v, list):
        return "/".join(str(x) for x in v)
    return str(v)


print("%-6s %-14s %-28s %-24s %s" % ("ID", "Name", "HP", "Damage", "标记"))
print("-" * 96)
for o in new["shengWu"]:
    mark = "★ 新增" if o["ID"] not in old_ids else ""
    print("%-6s %-14s %-28s %-24s %s" % (
        o["ID"], o.get("Name", "?"), flat(o.get("HP")), flat(o.get("Damage")), mark))
print()
print("共 %d 只，其中新增 %d 只" % (len(new["shengWu"]), len(new["shengWu"]) - len(old_ids)))
