#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""seg2 / seg5 / seg10 编辑器 —— 家园资源、宝箱、魔窟。

以前 ``give_resources.py`` 管钻石/肉/进化石/草丛、``unlock_progress.py`` 管关卡，
seg2/5/10 里的字段从来没做过编辑器。这个脚本补上。

【上限从哪来 —— 这是本脚本最重要的设计决定】

    所有「满级」数值都**从官方模板现读**，不在代码里写常量。

    原因：2026-10-30 第一版把 ``HOME_LEVEL_MAX`` 猜成 5、``魔窟难度`` 猜成 10，
    结果比模板里的真实值（240~299 / 20~26）低了一到两个数量级 ——
    「拉满」反而把玩家的进度改**小**了。

    三个官方模板（``evidence/templates/playerDate_0{1,2,3}.bin``）是游戏自带
    资源，代表 36/56/60 级时的合法状态，把它们逐字段取 max 就是上限的可靠上界。

字段全景（2026-10-30 从 SaveFile_device_orig.es3 实测，见 docs/20 §七）

    seg2 家园 / 伐木场 / 矿石场（19 字段）
        JiaYuanLevel / JiaYuanRenKou            家园等级 / 人口
        FaMuChangLevel / FaMuChangRenKou        伐木场等级 / 人口
        MuCaiShuLiang / MuCaiShuLiang_LiXianKu  木材库存 / 离线累计
        KuangShiChangLevel / KuangShiChangRenKou
        KuangShiShuLiang / KuangShiShuLiang_LiXianKu
        ZiYuanLiXianTime                        离线结算时间戳
        PaiQianZongCiShu / PaiQianZhuangTai / PaiQianOverTime
        PaiQianGuanKaID / PaiQianNanDu / PaiQianCiShu
        ZiDongDuanZaoID                         自动锻造槽，空槽是 -1（不是 0！）

    seg5 宝箱（6 字段）
        DaoZhiYaoShi / KaiXiangCiShu / BaoXiangIsOpen[9] / BaoXiangLeiXingInt[9] / ChongZhiTime

    seg10 魔窟 / 魔物碎片（10 字段）
        MoGaoLevel / MoShiShuLiang / MoKuNanDuDangQian / MoKuNanDuBest
        TongGuanTimeBest  {cengJiTimes:[{cengJi, bestTime}]}  ← 嵌套结构
        MoWuSuiPian / MoKuTiLi / TiLiShopKuCun / ChongZhiTime

【离线收益的坑】

    seg2 的 ``*_LiXianKu`` 是「离线收益库」，**不受 UI 库存上限约束**
    （顶端库存栏显示 ``MuCaiShuLiang/1500``，那才是主库存）。
    想刷木材/矿石，改 ``*_LiXianKu`` 比改 ``MuCaiShuLiang`` 隐蔽得多。

用法
====
    # 家园三场按官方满级档取上限 + 离线库给满
    python scripts/edit_seg2510.py --in cur.es3 --out new.es3 --home-max

    # 只列字段，并显示每个字段的模板上限
    python scripts/edit_seg2510.py --in cur.es3 --list --show-limits

    # 魔窟全拉满（难度/层级/碎片都取模板最大值）
    python scripts/edit_seg2510.py --in cur.es3 --out new.es3 --moku

    # 单项微调
    python scripts/edit_seg2510.py --in cur.es3 --out new.es3 \\
        --set 2.MuCaiShuLiang_LiXianKu=9999999
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import savedit  # noqa: E402
import es3save as E  # noqa: E402
from paths import TEMPLATES  # noqa: E402
from unlock_progress import find_slot, rebuild_bucket, split_l1  # noqa: E402

#: 三份官方模板，按 TapLevel 从低到高
TEMPLATE_FILES = ("playerDate_01.bin", "playerDate_02.bin", "playerDate_03.bin")

SEG_NAMES = {2: "家园/伐木场/矿石场", 5: "盗贼宝藏", 10: "魔窟/魔物碎片"}

#: ulong 字段的安全上限。取 2^53，而不是 2^64-1 —— JSON 数字在别的语言里
#: 常被解析成 double，超过 2^53 会悄悄丢精度，改出来的档就不是我们想的值。
ULONG_SAFE_MAX = 1 << 53


def _load_template_segs():
    out = []
    for name in TEMPLATE_FILES:
        p = os.path.join(TEMPLATES, name)
        if not os.path.exists(p):
            continue
        raw = open(p, "rb").read().decode("utf-8")
        out.append((name, [json.loads(x) for x in raw.split("$")]))
    if not out:
        raise SystemExit("找不到官方模板，检查 evidence/templates/ "
                         + str(TEMPLATES))
    return out


def template_max(seg_idx, field, signed=False):
    """取三份模板里该字段的最大值。非数值字段返回 None。"""
    best = None
    for _name, segs in _load_template_segs():
        v = segs[seg_idx].get(field)
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            continue
        if best is None or v > best:
            best = v
    if best is None:
        return None
    return int(best) if not signed or best >= 0 else best


def limits_map(seg_idx, fields):
    return {f: template_max(seg_idx, f) for f in fields}


def edit_home(seg):
    """seg2：三场等级/人口按模板上限拉满，离线库给到模板最大值的 10 倍。"""
    logs = []
    for prefix in ("JiaYuan", "FaMuChang", "KuangShiChang"):
        for suffix in ("Level", "RenKou"):
            k = prefix + suffix
            if k not in seg:
                continue
            cap = template_max(2, k)
            if cap is None:
                continue
            old = seg[k]
            seg[k] = cap
            logs.append("%-24s %r -> %d  (模板上限)" % (k, old, cap))
    for k in ("MuCaiShuLiang_LiXianKu", "KuangShiShuLiang_LiXianKu"):
        if k not in seg:
            continue
        cap = template_max(2, k)
        if cap is None:
            continue
        old = seg[k]
        # Date_ZiYuan 里这两个字段是 **ulong**（docs/20 §七），
        # 所以不必保守 —— 直接给一个远超正常玩法量级的值。
        # 用 2^53 而不是 2^64-1：JSON 数字在别的语言里可能被解析成 double，
        # 超过 2^53 会丢精度。
        seg[k] = ULONG_SAFE_MAX
        logs.append("%-24s %r -> %d  (ulong，模板参考 %d)"
                    % (k, old, seg[k], cap))
    if "ZiYuanLiXianTime" in seg:
        seg["ZiYuanLiXianTime"] = 0
        logs.append("%-24s -> 0  (离线收益立刻结算)" % "ZiYuanLiXianTime")
    # ZiDongDuanZaoID 的空槽是 -1，不动它，避免触发自动锻造
    return logs


def edit_chests(seg):
    """seg5：钥匙按模板最大给，9 个宝箱全开，重置时间清零。"""
    logs = []
    if "DaoZeiYaoShi" in seg:
        cap = template_max(5, "DaoZeiYaoShi") or 60
        key_max = max(cap, 60) * 10
        old = seg["DaoZeiYaoShi"]
        seg["DaoZeiYaoShi"] = key_max
        logs.append("%-24s %r -> %d" % ("DaoZeiYaoShi", old, key_max))
    if "KaiXiangCiShu" in seg:
        logs.append("%-24s %r (不改，纯统计)" % ("KaiXiangCiShu",
                                                 seg["KaiXiangCiShu"]))
    arr = seg.get("BaoXiangIsOpen") or [0] * 9
    seg["BaoXiangIsOpen"] = [1] * len(arr)
    logs.append("%-24s %r -> %r" % ("BaoXiangIsOpen", arr, seg["BaoXiangIsOpen"]))
    if "ChongZhiTime" in seg:
        seg["ChongZhiTime"] = 0
        logs.append("%-24s -> 0" % "ChongZhiTime")
    return logs


def edit_moku(seg):
    """seg10：魔窟各上限按模板取最大，碎片/体力给满。"""
    logs = []
    for k in ("MoGaoLevel", "MoShiShuLiang", "MoKuNanDuDangQian", "MoKuNanDuBest"):
        if k not in seg:
            continue
        cap = template_max(10, k)
        if cap is None:
            continue
        old = seg[k]
        seg[k] = cap
        logs.append("%-24s %r -> %d  (模板上限)" % (k, old, cap))
    for k in ("MoWuSuiPian", "MoKuTiLi", "TiLiShopKuCun"):
        if k not in seg:
            continue
        old = seg[k]
        seg[k] = 9999
        logs.append("%-24s %r -> 9999" % (k, old))
    if "ChongZhiTime" in seg:
        seg["ChongZhiTime"] = 0
        logs.append("%-24s -> 0" % "ChongZhiTime")
    # TongGuanTimeBest 是嵌套结构。保持形状不变，只把 bestTime 清零
    # （清零 = 本次通关必破纪录，不会因为「打不过自己的记录」而卡住）
    tgb = seg.get("TongGuanTimeBest")
    if isinstance(tgb, dict) and isinstance(tgb.get("cengJiTimes"), list):
        n = 0
        for row in tgb["cengJiTimes"]:
            if isinstance(row, dict) and "bestTime" in row:
                row["bestTime"] = 0.0
                n += 1
        if n:
            logs.append("%-24s %d 条 bestTime -> 0.0" % ("TongGuanTimeBest", n))
    return logs


def apply_sets(segs, assigns):
    for item in assigns:
        if "=" not in item:
            raise SystemExit("--set 需要 SEG.FIELD=VALUE，收到 %r" % item)
        lhs, rhs = item.split("=", 1)
        seg_s, field = lhs.split(".", 1)
        idx = int(seg_s)
        if idx not in SEG_NAMES:
            raise SystemExit("本脚本只管 seg%s，收到 seg%d"
                             % ("/".join(str(k) for k in SEG_NAMES), idx))
        if field not in segs[idx]:
            raise SystemExit("seg%d 里没有字段 %r\n可用: %s"
                             % (idx, field, ", ".join(sorted(segs[idx]))))
        try:
            val = json.loads(rhs)
        except json.JSONDecodeError:
            val = rhs
        print("  set seg%d.%s %r -> %r" % (idx, field, segs[idx][field], val))
        segs[idx][field] = val


def list_fields(segs, show_limits=False):
    for idx in sorted(SEG_NAMES):
        d = segs[idx]
        print()
        print("=== seg%d  %s  (%d fields) ===" % (idx, SEG_NAMES[idx], len(d)))
        for k, v in d.items():
            sv = repr(v)
            if len(sv) > 60:
                sv = sv[:57] + "..."
            extra = ""
            if show_limits:
                cap = template_max(idx, k)
                if cap is not None:
                    extra = "   [模板上限 %d]" % cap
            print("  %-32s %s%s" % (k, sv, extra))


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="编辑 seg2/5/10：家园资源、宝箱、魔窟（上限取自官方模板）")
    ap.add_argument("--in", dest="inp", required=True, help="基准 .es3")
    ap.add_argument("--out", dest="out", default=None, help="输出 .es3")
    ap.add_argument("--home-max", action="store_true",
                    help="seg2：三场等级/人口按模板上限 + 离线库 x10 + 离线时间清零")
    ap.add_argument("--chests", action="store_true",
                    help="seg5：钥匙给满 + 9 个宝箱全开 + 重置时间清零")
    ap.add_argument("--moku", action="store_true",
                    help="seg10：魔窟各上限按模板取最大 + 碎片/体力给满")
    ap.add_argument("--set", action="append", default=[], metavar="SEG.FIELD=VALUE",
                    help="单项改写，可重复")
    ap.add_argument("--list", action="store_true", help="只列出三段字段")
    ap.add_argument("--show-limits", action="store_true",
                    help="与 --list 合用，同时显示模板里的最大合法值")
    a = ap.parse_args(argv)

    if not os.path.exists(a.inp):
        print("错误：找不到 %s" % a.inp, file=sys.stderr)
        return 2

    segs = savedit.load(E.read_save(a.inp).decode("utf-8"))

    if a.list:
        list_fields(segs, a.show_limits)
        return 0

    logs = []
    if a.home_max:
        logs += edit_home(segs[2])
    if a.chests:
        logs += edit_chests(segs[5])
    if a.moku:
        logs += edit_moku(segs[10])
    if a.set:
        apply_sets(segs, a.set)

    if not (a.home_max or a.chests or a.moku or a.set):
        print("没有指定编辑动作。用 --list --show-limits 看字段与上限，"
              "或加 --home-max/--chests/--moku。", file=sys.stderr)
        return 2
    if not a.out:
        print("错误：有编辑动作时必须给 --out", file=sys.stderr)
        return 2

    for ln in logs:
        print("  " + ln)

    blob = open(a.inp, "rb").read()
    salt, iv, layer1 = split_l1(blob)
    slot, counter, obj = find_slot(layer1)
    if slot is None:
        print("错误：桶里找不到 string 槽", file=sys.stderr)
        return 1

    plain = savedit.dump(segs).encode("utf-8")
    hexstr = E.des_encrypt(plain)
    inner = rebuild_bucket(hexstr, obj)
    key = E.PBKDF2(E.PASSWORD.encode("utf-8"), salt, dkLen=E.KEY_LEN,
                   count=E.ITERATIONS, hmac_hash_module=E.SHA1)
    new_blob = salt + iv + E.AES.new(key, E.AES.MODE_CBC, iv).encrypt(
        E.pad(inner, 16))
    outdir = os.path.dirname(os.path.abspath(a.out))
    if outdir and not os.path.isdir(outdir):
        os.makedirs(outdir, exist_ok=True)
    with open(a.out, "wb") as f:
        f.write(new_blob)
    print("输出 %s (%d 字节)" % (a.out, len(new_blob)))

    back = savedit.load(E.read_save(a.out).decode("utf-8"))
    ok = (len(back) == 14
          and all(back[i]["DateID"] == i for i in range(14)))
    print("回读自检: %s" % ("通过" if ok else "失败"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
