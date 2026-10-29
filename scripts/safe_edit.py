#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""安全改档 —— 按官方满级模板 `playerDate_03` 的可达上限约束每一项改动。

为什么需要它
============
2026-10-29 14:47 推入 ``SaveFile_pets_all.es3``（85 只宠物全部
Lv60 / JinHua4 / JinJie10 / HP≈158万~193万）后触发封号红屏
「你的作弊行为触动了魔王的底线」。静态逆向结论（见
docs/09-反作弊机制逆向.md）：

  * 客户端**没有**任何数值检测。ZuoBi.JiaRuHeiMingDan
    （rva 0x18B3904）与 XianShiNiCheng.HeiMingDan（rva 0x17FB4F8）
    只是把 (qingQiuID, playerID) POST 到
    http://www.hqgames2013.com/heiMingDan.asp，判定与执行都在服务端。
  * 服务端在收到 beiFen.asp 云存档上传后做合法性检查。

那条路径已不可用。本脚本改走「**让每一项都不超出官方模板可达范围**」
的路线：所有上界都直接从 data.unity3d 里的 TextAsset
``playerDate_03``（path_id=161，104886 字节，TapLevel=60 满级存档）
读出来，而不是凭感觉定数字。

实测模板可达值（2026-10-29 抓取）
================================
    TapLevel              60           TapZongShu       602076
    GuanKaLevel           62           BaoShiSuiPian    303978
    ZuanShi               34680        JinYan           4875401982240
    JiaYuanLevel          240          FaMuChangLevel   299
    KuangShiChangLevel    245          MuCaiShuLiang    5364060
    MoGaoLevel            200          MoKuNanDuBest    26
    ChongWuLevel          max 60       ChongWuJinHua    0..4
    ChongWuJinJie         0..10        HP max 1755000   Dmg max 1599750

宠物是重点
==========
宠物属性直接计入战斗力（XianShiNiCheng.SetZhanDouLi 上报的
ZhanDouLi），是最容易被服务端比值检查抓到的字段。所以：

  * **默认 ``--pets template``**：直接用模板 85 条**原样**（连
    HP/Damage 都不动），只把 ``IsMaoXian`` 设为 -1（已拥有）。
  * ``--pets keep``：保留基准档现有条目，不做任何改动。
  * ``--pets cap``：保留现有条目，但把每条的 Level/JinHua/JinJie/
    HP/Damage 夹到「同 ID 在模板里的值」——绝不超过官方。

安全边界（``--mode``）
=====================
    gentle（默认）  货币/资源只提到模板值的 60%，宠物原样
    template        货币/资源提到模板值 100%，宠物原样
    custom          完全按参数写，``--force`` 才放行超模板值

所有上界默认是「模板值」，任何参数超过它会**拒绝执行**（除非 ``--force``）。

用法
====
    # 预览（不写文件）
    python scripts/safe_edit.py --in work/live/SaveFile_after_catch.es3 \\
                               --out work/live/SaveFile_safe.es3 --dry-run

    # 实际生成
    python scripts/safe_edit.py --in work/live/SaveFile_after_catch.es3 \\
                               --out work/live/SaveFile_safe.es3

    # 只看宠物会变成什么
    python scripts/safe_edit.py --in ... --out ... --dry-run --pets cap
"""
import argparse
import json
import sys
from pathlib import Path

from Crypto.Util.Padding import pad

import paths
import savedit
from es3save import (
    AES, ITERATIONS, KEY_LEN, PASSWORD, PBKDF2, SHA1,
    des_encrypt, read_save,
)
from unlock_progress import find_slot, rebuild_bucket, split_l1

TEMPLATE = paths.REPO / "work" / "textassets" / "ta_161_104886.bin"

# 模板实测上限（读不到模板时的兜底；正常路径一律从模板现算）
FALLBACK_CAPS = {
    "TapLevel": 60,
    "TapZongShu": 602076,
    "GuanKaLevel": 62,
    "BaoShiSuiPian": 303978,
    "ZuanShi": 34680,
    "JingYan": 4875401982240,
    "JiaYuanLevel": 240,
    "FaMuChangLevel": 299,
    "KuangShiChangLevel": 245,
    "MuCaiShuLiang": 5364060,
    "KuangShiShuLiang": 3601500,
    "MoGaoLevel": 200,
    "MoShiShuLiang": 10000,
    "MoWuSuiPian": 982,
    "ChongWuSiLiao": 9949,
}

# 资源键 -> (seg 索引, 字段名)
RESOURCE_SLOTS = {
    "zhuanshi": (13, "ZuanShi"),
    "baoshi": (9, "BaoShiSuiPian"),
    "mucai": (2, "MuCaiShuLiang"),
    "kuangshi": (2, "KuangShiShuLiang"),
    "siliao": (6, "ChongWuSiLiao"),
    "jingyan": (13, "JingYan"),
}

JINHUA_KEYS = ("JinHuaShi_Feng", "JinHuaShi_Huo", "JinHuaShi_Shui",
               "JinHuaShi_Di", "JinHuaShi_Guang", "JinHuaShi_An")


def load_segs_blob(path):
    """读 .es3 -> 14 段 dict。"""
    raw = read_save(str(path))
    if isinstance(raw, (list, tuple)):
        text = "$".join(p.decode("utf-8") if isinstance(p, bytes) else p for p in raw)
    else:
        text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
    return savedit.load(text)


def load_template(caps):
    """读官方满级模板；失败则返回 None 并沿用 FALLBACK_CAPS。"""
    if not TEMPLATE.exists():
        print("警告：找不到模板 %s，使用内置上限" % TEMPLATE, file=sys.stderr)
        return None
    tpl = savedit.load(TEMPLATE.read_text(encoding="utf-8", errors="replace"))
    # 用模板实测值覆盖兜底
    caps["TapLevel"] = tpl[0].get("TapLevel", caps["TapLevel"])
    caps["TapZongShu"] = max(caps["TapZongShu"], tpl[0].get("TapZongShu", 0))
    caps["GuanKaLevel"] = tpl[8].get("GuanKaLevel", caps["GuanKaLevel"])
    caps["BaoShiSuiPian"] = tpl[9].get("BaoShiSuiPian", caps["BaoShiSuiPian"])
    caps["ZuanShi"] = tpl[13].get("ZuanShi", caps["ZuanShi"])
    caps["JingYan"] = tpl[13].get("JingYan", caps["JingYan"])
    caps["JiaYuanLevel"] = tpl[2].get("JiaYuanLevel", caps["JiaYuanLevel"])
    caps["FaMuChangLevel"] = tpl[2].get("FaMuChangLevel", caps["FaMuChangLevel"])
    caps["KuangShiChangLevel"] = tpl[2].get("KuangShiChangLevel", caps["KuangShiChangLevel"])
    caps["MuCaiShuLiang"] = tpl[2].get("MuCaiShuLiang", caps["MuCaiShuLiang"])
    caps["KuangShiShuLiang"] = tpl[2].get("KuangShiShuLiang", caps["KuangShiShuLiang"])
    caps["MoGaoLevel"] = tpl[10].get("MoGaoLevel", caps["MoGaoLevel"])
    caps["MoShiShuLiang"] = tpl[10].get("MoShiShuLiang", caps["MoShiShuLiang"])
    caps["MoWuSuiPian"] = tpl[10].get("MoWuSuiPian", caps["MoWuSuiPian"])
    # 饲料上限取「模板值」与「基准档现值」的较大者：模板是满级存档，
    # 饲料剩得少不代表上限低，把玩家手里已有的肉改小没有意义。
    caps["ChongWuSiLiao"] = tpl[6].get("ChongWuSiLiao", caps["ChongWuSiLiao"])
    return tpl


def template_pet_map(tpl):
    """ChongWuID -> 模板条目。"""
    if not tpl:
        return {}
    return {p["ChongWuID"]: p for p in (tpl[6].get("SuoYouChongWuDate") or [])}


def plan_resources(a, caps, mode):
    """算出每一项的目标值，并返回 (targets, refusals, notes)。"""
    ratio = 0.60 if mode == "gentle" else 1.00
    wanted = {
        "zhuanshi": a.zhuanshi,
        "baoshi": a.baoshi,
        "mucai": a.mucai,
        "kuangshi": a.kuangshi,
        "siliao": a.siliao,
        "jingyan": a.jingyan,
    }
    capkey = {
        "zhuanshi": "ZuanShi",
        "baoshi": "BaoShiSuiPian",
        "mucai": "MuCaiShuLiang",
        "kuangshi": "KuangShiShuLiang",
        "siliao": "ChongWuSiLiao",
        "jingyan": "JingYan",
    }
    # --fill：没给数值的项直接顶到该 mode 的上限
    if a.fill:
        for k in wanted:
            if wanted[k] is None:
                wanted[k] = caps[capkey[k]]

    targets, refusals, notes = {}, [], []
    # 只增不减：资源类改动的目的是「补足」，把玩家已有的量改小毫无意义，
    # 而且下降的数值在服务端看同样是异常。
    cur = {
        "zhuanshi": (13, "ZuanShi"),
        "baoshi": (9, "BaoShiSuiPian"),
        "mucai": (2, "MuCaiShuLiang"),
        "kuangshi": (2, "KuangShiShuLiang"),
        "siliao": (6, "ChongWuSiLiao"),
        "jingyan": (13, "JingYan"),
    }
    for k, v in wanted.items():
        if v is None:
            continue
        cap = caps[capkey[k]]
        if mode == "custom":
            if v > cap and not a.force:
                refusals.append("%s=%d 超过模板上限 %d（加 --force 放行）" % (k, v, cap))
                continue
            targets[k] = v
            if v > cap:
                notes.append("%s=%d 已超模板上限 %d（--force）" % (k, v, cap))
            continue
        ceiling = int(cap * ratio)
        goal = min(v, ceiling)
        si, fld = cur[k]
        old = a._segs[si].get(fld, 0) if getattr(a, "_segs", None) else None
        if old is not None and isinstance(old, (int, float)) and old >= goal:
            notes.append("%s 现值 %r 已不低于目标 %d，保持不动" % (k, old, goal))
            continue
        if v > ceiling:
            notes.append("%s 请求 %d，按 %s 上限夹到 %d（模板 %d × %.0f%%）"
                         % (k, v, mode, ceiling, cap, ratio * 100))
        targets[k] = goal
    return targets, refusals, notes


def plan_pets(a, segs, tpl, caps):
    """返回 (new_pets or None, notes)。None 表示不动宠物段。"""
    notes = []
    cur = segs[6].get("SuoYouChongWuDate") or []
    mode = a.pets

    if mode == "keep":
        notes.append("宠物：保持基准档原样（%d 条）" % len(cur))
        return None, notes

    tpl_pets = (tpl[6].get("SuoYouChongWuDate") or []) if tpl else []
    tmap = {p["ChongWuID"]: p for p in tpl_pets}

    if mode == "template":
        if not tpl_pets:
            notes.append("宠物：模板不可用，退回 keep")
            return None, notes
        out = []
        for p in tpl_pets:
            e = dict(p)
            e["IsMaoXian"] = a.maoxian
            e["IsXieDai"] = 1 if e["ChongWuID"] == a.equip else 0
            out.append(e)
        notes.append("宠物：整段替换为模板 %d 条原样（Level/JinHua/JinJie/HP/Dmg 全不动）"
                     % len(out))
        return out, notes

    # mode == "cap"：保留现有条目，逐项夹到同 ID 的模板值
    #
    # 注意：模板的 ChongWuID 是 0..84，而基准档（游戏自己写的）是 1..90，
    # 两套编号不同。模板里查不到的 ID 说明该 ID 不在官方表里，游戏 UI 会
    # 显示「未知型」——直接把这类条目丢掉，而不是造一个空壳。
    out, capped, dropped = [], 0, []
    for p in cur:
        e = dict(p)
        e["IsMaoXian"] = a.maoxian
        t = tmap.get(e.get("ChongWuID"))
        if t is None:
            dropped.append(e.get("ChongWuID"))
            continue
        for f in ("ChongWuLevel", "ChongWuJinHua", "ChongWuJinJie",
                  "ChongWuYongJiu_HP", "ChongWuYongJiu_Damage"):
            tv = t.get(f, 0)
            if e.get(f, 0) > tv:
                capped += 1
                e[f] = tv
        e["IsXieDai"] = 1 if e.get("ChongWuID") == a.equip else 0
        out.append(e)
    notes.append("宠物：保留 %d 条，%d 个字段被夹到模板值" % (len(out), capped))
    if dropped:
        notes.append("宠物：丢弃 %d 条模板里不存在的 ID（%s）"
                     % (len(dropped), dropped[:10]))
    return out, notes


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="安全改档：每一项都不超出官方满级模板的可达值")
    ap.add_argument("--in", dest="inp", required=True, help="基准 .es3")
    ap.add_argument("--out", dest="out", required=True, help="输出 .es3")
    ap.add_argument("--mode", choices=("gentle", "template", "custom"),
                    default="gentle",
                    help="gentle=货币按模板60%%（默认）；template=100%%；custom=按参数")
    ap.add_argument("--pets", choices=("template", "cap", "keep"),
                    default="template",
                    help="template=用模板85条原样（默认）；cap=夹到模板值；keep=不动")
    ap.add_argument("--equip", type=int, default=0, help="出战宠物 ID（默认 0）")
    ap.add_argument("--maoxian", type=int, default=-1,
                    help="IsMaoXian 值，-1=已拥有（默认）")
    ap.add_argument("--zhuanshi", type=int, default=None,
                    help="钻石（gentle/template 会自动夹到上限；默认不动）")
    ap.add_argument("--baoshi", type=int, default=None, help="宝石碎片")
    ap.add_argument("--mucai", type=int, default=None, help="木材")
    ap.add_argument("--kuangshi", type=int, default=None, help="矿石")
    ap.add_argument("--siliao", type=int, default=None, help="宠物饲料（肉）")
    ap.add_argument("--jingyan", type=int, default=None, help="经验")
    ap.add_argument("--fill", action="store_true",
                    help="不给具体数值时，按 mode 一次性把常用资源提到上限")
    ap.add_argument("--guan-ka", type=int, default=None,
                    help="GuanKaLevel（宠物解锁需 >20，模板已到 62）")
    ap.add_argument("--jinhua-shi", type=int, default=None,
                    help="六种进化石统一数量（模板最大 553）")
    ap.add_argument("--force", action="store_true",
                    help="允许 custom 模式写入超过模板上限的值（危险）")
    ap.add_argument("--dry-run", action="store_true", help="只打印，不写文件")
    a = ap.parse_args(argv)

    caps = dict(FALLBACK_CAPS)
    tpl = load_template(caps)

    print("=" * 68)
    print("官方模板可达上限（playerDate_03）")
    print("=" * 68)
    for k in ("TapLevel", "TapZongShu", "GuanKaLevel", "BaoShiSuiPian",
              "ZuanShi", "JingYan", "MuCaiShuLiang", "KuangShiShuLiang",
              "MoGaoLevel", "ChongWuSiLiao"):
        print("  %-20s %d" % (k, caps[k]))

    blob = Path(a.inp).read_bytes()
    salt, iv, layer1 = split_l1(blob)
    slot, counter, obj = find_slot(layer1)
    if slot is None:
        print("错误：桶里找不到 string 槽", file=sys.stderr)
        return 1
    print("\n基准 %s  (%d 字节)" % (a.inp, len(blob)))
    print("  slot=%s  _Key=%r  桶条目=%s"
          % (slot, counter, ", ".join(obj.keys())))

    segs = load_segs_blob(a.inp)
    if len(segs) < 14:
        print("错误：段数 %d < 14，不是有效存档" % len(segs), file=sys.stderr)
        return 1
    a._segs = segs  # plan_resources 需要读现值做「只增不减」判断

    # ---- 资源 ----
    targets, refusals, notes = plan_resources(a, caps, a.mode)
    if refusals:
        print("\n拒绝执行：")
        for r in refusals:
            print("  - " + r)
        return 2

    print("\n" + "=" * 68)
    print("改动清单")
    print("=" * 68)
    for k, v in targets.items():
        si, fld = RESOURCE_SLOTS[k]
        old = segs[si].get(fld)
        segs[si][fld] = v
        print("  %-10s seg%-2d %-16s %r -> %d  (上限 %d)"
              % (k, si, fld, old, v, caps[{
                  "zhuanshi": "ZuanShi", "baoshi": "BaoShiSuiPian",
                  "mucai": "MuCaiShuLiang", "kuangshi": "KuangShiShuLiang",
                  "siliao": "ChongWuSiLiao", "jingyan": "JingYan"}[k]]))
    for n in notes:
        print("  ! " + n)

    # ---- 关卡 ----
    if a.guan_ka is not None:
        if a.guan_ka > caps["GuanKaLevel"] and not a.force:
            print("\n拒绝执行：guan-ka=%d 超过模板上限 %d"
                  % (a.guan_ka, caps["GuanKaLevel"]))
            return 2
        old = segs[8].get("GuanKaLevel")
        segs[8]["GuanKaLevel"] = a.guan_ka
        print("  %-10s seg%-2d %-16s %r -> %d  (上限 %d)"
              % ("guanka", 8, "GuanKaLevel", old, a.guan_ka, caps["GuanKaLevel"]))

    # ---- 进化石 ----
    if a.jinhua_shi is not None:
        cap = 553  # 模板里最大的一项
        v = a.jinhua_shi
        if v > cap and not a.force:
            print("  ! jinhua-shi=%d 超过模板最大 %d，夹到 %d" % (v, cap, cap))
            v = cap
        for k in JINHUA_KEYS:
            segs[6][k] = v
        print("  进化石 x6               -> %d  (模板最大 553)" % v)

    # ---- 宠物 ----
    new_pets, pet_notes = plan_pets(a, segs, tpl, caps)
    for n in pet_notes:
        print("  " + n)
    if new_pets is not None:
        # 顺带把宠物段几个「一看就知道改过」的计数器拉回模板值
        if tpl:
            for k in ("ZhuaChongZongShu", "ZhuaChongShiBaiShu",
                      "HeChengChongWuCiShu", "ChongWuIsZiDongJiNeng"):
                if k in tpl[6]:
                    segs[6][k] = tpl[6][k]
        segs[6]["SuoYouChongWuDate"] = new_pets

    # ---- 预览 ----
    if new_pets:
        print("\n  宠物样例：")
        print("  %-4s %-4s %-7s %-6s %-12s %-12s %-4s"
              % ("ID", "Lv", "JinHua", "JinJie", "HP", "Dmg", "携带"))
        for e in new_pets[:4] + new_pets[-2:]:
            print("  %-4d %-4d %-7d %-6d %-12d %-12d %-4d" % (
                e["ChongWuID"], e["ChongWuLevel"], e["ChongWuJinHua"],
                e["ChongWuJinJie"], e["ChongWuYongJiu_HP"],
                e["ChongWuYongJiu_Damage"], e["IsXieDai"]))
        print("  ... 共 %d 只" % len(new_pets))

    if a.dry_run:
        print("\n--dry-run：不写文件")
        return 0

    # ---- 写盘 ----
    plain = savedit.dump(segs).encode("utf-8")
    hexstr = des_encrypt(plain)
    inner = rebuild_bucket(hexstr, obj)
    key = PBKDF2(PASSWORD.encode("utf-8"), salt, dkLen=KEY_LEN,
                 count=ITERATIONS, hmac_hash_module=SHA1)
    new_blob = salt + iv + AES.new(key, AES.MODE_CBC, iv).encrypt(pad(inner, 16))
    Path(a.out).write_bytes(new_blob)
    print("\n输出 %s (%d 字节)" % (a.out, len(new_blob)))

    # ---- 自检 ----
    back = load_segs_blob(a.out)
    ok = True
    for k, v in targets.items():
        si, fld = RESOURCE_SLOTS[k]
        if back[si].get(fld) != v:
            print("  自检失败：%s = %r，期望 %d" % (fld, back[si].get(fld), v))
            ok = False
    bp = back[6].get("SuoYouChongWuDate") or []
    if new_pets is not None and len(bp) != len(new_pets):
        print("  自检失败：宠物 %d 条，期望 %d" % (len(bp), len(new_pets)))
        ok = False
    # 超模板检查
    over = []
    for k, capk in (("baoshi", "BaoShiSuiPian"), ("zhuanshi", "ZuanShi")):
        if k in targets and targets[k] > caps[capk]:
            over.append("%s=%d > 模板 %d" % (k, targets[k], caps[capk]))
    for e in bp:
        if e.get("ChongWuYongJiu_HP", 0) > 1755000:
            over.append("宠物 %d HP=%d > 模板 1755000"
                        % (e.get("ChongWuID"), e["ChongWuYongJiu_HP"]))
            break
    if over:
        print("  警告：以下项超出模板上限")
        for o in over:
            print("    - " + o)
    print("回读自检: %s" % ("通过" if ok else "失败"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
