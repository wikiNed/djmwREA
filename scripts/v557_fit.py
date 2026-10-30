#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""旧版 v5.5.7 存档变长改档：按「密文长度保持不变」约束自动补齐。

核心约束（实测得出）
------------------
旧版存档 = header(14) || hex_upper(DES-CBC-PKCS7(明文)) || b"{"
游戏侧 DesDecrypt 逐 2 字符 Convert.ToByte，CBC 解密后必须能 unpad。
因此 **密文长度（明文长度向上取整到 8 的倍数）必须与原档一致**。

实测：
    明文 37568 -> 密文 37576  ✅ 原档
    明文 37571 -> 密文 37576  ✅ z5000（+3）
    明文 37578 -> 密文 37584  ❌ pad8
    明文 37582 -> 密文 37584  ❌ tree

也就是说，明文可以在 [密文长 - 8 + 1, 密文长 - 1] 区间内自由浮动，
超出就要么缩别的字段、要么整体升一个密文块。

本脚本的做法
-----------
修改目标字段后，若明文长度越过当前密文块上限，就在**同一段内**删除
若干「可安全删除」的次要字段来抵消；若实在不够，再在整档尾部追加/
裁掉 JSON 允许的空白（空格），把长度调回目标密文块。

用法::

    python scripts/v557_fit.py --in a.es3 --out b.es3 --tree --gem 88888 ...
"""
import argparse
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import v557save  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TPL03 = os.path.join(ROOT, "evidence", "templates", "playerDate_03_v557.bin")

#: 可以在空间不足时安全删除的字段（游戏会填默认值）
DROPPABLE = {
    11: ["GuoShiChongZhiTime", "GuoShiIsLingQu", "JiHuoCiShu"],
    12: [],
    13: [],
}


def jload(b):
    if isinstance(b, bytes):
        b = b.decode("utf-8")
    return json.loads(b)


def jdump(o):
    return json.dumps(o, ensure_ascii=False, separators=(",", ":")).encode()


def ct_len_of(plain_len):
    """明文长度 -> 密文长度（向上取整到 8）。"""
    return ((plain_len + 7) // 8) * 8


def fit(segs, target_ct=None):
    """长度对齐。

    target_ct 为 None 时不做任何对齐 —— 因为 v557save.build() 会自动
    改写 header 里的长度字节，密文块变化是安全的。
    保留 target_ct 参数用于需要严格等长的场景。
    """
    if target_ct is None:
        return segs, ["跳过对齐（build 会自动修正 header 长度字节）"]

    notes = []

    def cur():
        return ct_len_of(len(v557save.SEP.encode().join(
            s if isinstance(s, bytes) else s.encode() for s in segs)))

    if cur() == target_ct:
        return segs, ["长度已匹配，无需调整"]

    # 太长 -> 删窗内可删字段
    guard = 0
    while cur() > target_ct and guard < 40:
        guard += 1
        dropped = False
        for si, fields in DROPPABLE.items():
            if not fields:
                continue
            obj = jload(segs[si])
            for f in fields:
                if f in obj:
                    old_len = len(segs[si])
                    del obj[f]
                    segs[si] = jdump(obj)
                    notes.append("删除 seg%d.%s（%d -> %d 字节）"
                                 % (si, f, old_len, len(segs[si])))
                    dropped = True
                    break
            if dropped:
                break
        if not dropped:
            break

    # 还是太长 -> 交给调用方（这里只报告）
    if cur() > target_ct:
        notes.append("警告：删除可删字段后仍超长（当前密文 %d > 目标 %d）"
                     % (cur(), target_ct))
        return segs, notes

    # 太短 -> 用尾部空白补（JSON 尾部空白合法）
    short = target_ct - cur()
    total = 0
    while cur() < target_ct and total < 64:
        total += 1
        segs = list(segs)
        segs[-1] = (segs[-1] if isinstance(segs[-1], bytes)
                    else segs[-1].encode()) + b" "
    if total:
        notes.append("尾部追加 %d 个空格对齐密文块" % total)
    return segs, notes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="src", required=True)
    ap.add_argument("--out", dest="dst", required=True)
    ap.add_argument("--tree", action="store_true")
    ap.add_argument("--gem", type=int, default=None)
    ap.add_argument("--pets", action="store_true")
    ap.add_argument("--pets-level", type=int, default=60)
    ap.add_argument("--pet-food", type=int, default=None)
    ap.add_argument("--evolve-stone", type=int, default=None)
    ap.add_argument("--zhuanshi", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    blob = open(a.src, "rb").read()
    header = blob[:14]
    body = blob[14:]
    if body.endswith(b"{"):
        body = body[:-1]
    target_ct = len(body) // 2
    print("原档密文长度 = %d 字节；明文可浮动到 %d..%d"
          % (target_ct, target_ct - 7, target_ct))

    _, segs = v557save.read_segments(a.src)
    segs = list(segs)
    plain0 = v557save.SEP.encode().join(segs)
    print("原明文长度 = %d（密文 %d）" % (len(plain0), ct_len_of(len(plain0))))

    changed = []

    if a.tree:
        j = jload(segs[11])
        j["IsJiHuo"] = 1
        j["IsHuangJin"] = 1
        j["GuoQiTime"] = 4102416000000
        segs[11] = jdump(j)
        changed.append("seg11 黄金树解锁 + GuoQiTime=4102416000000")

    if a.gem is not None:
        j = jload(segs[9])
        j["BaoShiSuiPian"] = a.gem
        segs[9] = jdump(j)
        changed.append("seg9 BaoShiSuiPian=%d" % a.gem)

    if a.zhuanshi is not None:
        j = jload(segs[13])
        j["ZuanShi"] = a.zhuanshi
        segs[13] = jdump(j)
        changed.append("seg13 ZuanShi=%d" % a.zhuanshi)

    if a.pets or a.pet_food is not None or a.evolve_stone is not None:
        j6 = jload(segs[6])
        if a.pets:
            with open(TPL03, encoding="utf-8") as f:
                tpl = f.read().split("$")
            tpets = jload(tpl[6]).get("SuoYouChongWuDate") or []
            cur = j6.get("SuoYouChongWuDate") or []
            by_id = {p.get("ChongWuID"): dict(p) for p in tpets}
            out = []
            for p in cur:
                src = by_id.get(p.get("ChongWuID"))
                if src:
                    np = dict(src)
                    np["ChongWuLevel"] = a.pets_level
                    np["IsMaoXian"] = -1
                    np["IsXieDai"] = 0
                    out.append(np)
                else:
                    out.append(p)
            j6["SuoYouChongWuDate"] = out
            changed.append("宠物 %d 只 -> 等级 %d" % (len(out), a.pets_level))
        if a.pet_food is not None:
            j6["ChongWuSiLiao"] = a.pet_food
            changed.append("肉 = %d" % a.pet_food)
        if a.evolve_stone is not None:
            for k in ("JinHuaShi_An", "JinHuaShi_Di", "JinHuaShi_Feng",
                      "JinHuaShi_Guang", "JinHuaShi_Huo", "JinHuaShi_Shui"):
                if k in j6:
                    j6[k] = a.evolve_stone
            changed.append("六种进化石 = %d" % a.evolve_stone)
        segs[6] = jdump(j6)

    if not changed:
        print("没有修改项")
        return 1
    print("\n修改项:")
    for c in changed:
        print("  -", c)

    plain1 = v557save.SEP.encode().join(
        s if isinstance(s, bytes) else s.encode() for s in segs)
    print("\n改后明文 %d -> 密文 %d" % (len(plain1), ct_len_of(len(plain1))))

    segs, notes = fit(segs, None)
    print("\n长度处理:")
    for n in notes:
        print("  -", n)

    plain2 = v557save.SEP.encode().join(
        s if isinstance(s, bytes) else s.encode() for s in segs)
    print("最终明文 %d -> 密文 %d" % (len(plain2), ct_len_of(len(plain2))))

    if a.dry_run:
        print("\n[dry-run] 不写出")
        return 0

    size = v557save.write_save(a.dst, header, plain2)
    print("\n写出 %s : %d 字节" % (a.dst, size))
    v557save.verify(a.dst)
    return 0


if __name__ == "__main__":
    sys.exit(main())
