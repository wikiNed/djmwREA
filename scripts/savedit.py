#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
点击魔王 (TapDemons) v5.9.2 存档读写工具

存档格式（实测确认）:
    {json0}${json1}$...${json13}
    - 14 个独立 JSON 对象, 用 '$' 拼接
    - 每段自带 DateID 字段 (0~13)
    - UTF-8, 无 BOM, 无加密, 无签名

用法:
    python savedit.py info      <archive>
    python savedit.py roundtrip <archive>          # 无损往返自测
    python savedit.py get       <archive> <path>
    python savedit.py libao     <archive> <LiBaoID ...> [--out FILE]  # 删除已兑码
    python savedit.py baoshi    <archive> <数量>   [--out FILE]       # 宝石碎片
    python savedit.py baoshiall <archive> [--level N --pinjie N
                                          --xiyoudu N --zhuan N] [--out FILE]
                                                                     # 宝石实体强化
    python savedit.py pets      <archive> [--level N --jinhua N --jinjie N
                                          --hp N --dmg N] [--out FILE] # 宠物属性强化
    python savedit.py tree      <archive> [--jihuo N --huangjin N --year N]
                                                                     # 黄金树永久
    python savedit.py set       <archive> <path> <json值> [--out FILE]

path 语法: 段号.字段[.子字段][.数组下标], 例如
    9.BaoShiSuiPian
    6.SuoYouChongWuDate.0.ChongWuLevel
    11.GuoQiTime
    13.LiBaoIDs
"""

import json
import sys
import os
import shutil
import math
import re
import time
from decimal import Decimal, ROUND_HALF_UP

SEP = "$"
NUM_SEGMENTS = 14


# ---------------------------------------------------------------- 解析/序列化

def load(text):
    """把存档文本拆成 14 段 dict。容忍 BOM 与段尾空白。"""
    if isinstance(text, bytes):
        text = text.decode("utf-8-sig")
    text = text.lstrip("\ufeff")
    parts = text.split(SEP)
    segs = []
    for i, p in enumerate(parts):
        p = p.strip()
        if not p:
            continue
        segs.append(json.loads(p))
    return segs


# ---- C# 兼容的 double 格式化（实测结论，2026-10 复核）------------------
#
# 规则：十进制 ROUND_HALF_UP 保留 17 位有效数字 + 整数值补 ".0" + 无科学计数法。
#
# 【实测数据】3 个官方演示存档，共 372 个带小数点的 token：
#   - 数值等价：372/372 = 100%      <- 这是真正重要的
#   - 文本完全一致：90+97+95 = 282/372 ≈ 75.8%
#   - 文本末位不同的 90 处，形如
#       游戏值 2.4295361042022707   重存得 2.4295361042022705
#       游戏值 0.031873904168605807 重存得 0.031873904168605804
#     经 float() 解析后是同一个 double，游戏读档数值完全相同。
#
# 【已试过但不成立的假设】（不必重复踩坑）
#   1. Python 内置 repr() / .NET shortest round-trip -> 只能还原 66~75%
#   2. double 的精确十进制展开 Decimal(float)        -> 游戏值明显更短，不是
#   3. ROUND_DOWN（向零）@17 位                      -> 6/123，错得离谱
#   4. ROUND_CEILING @17 位                          -> 82/123，比 HALF_UP 更差
#   5. 按 15->17 位逐级试探（.NET ToString 行为）     -> 90/123，同上
#   => 反推游戏确切浮点算法的边际收益极低：文本差异不影响数值，不影响游戏运行。
#      除非有证据表明游戏校验存档文本，否则不值得继续追。
#
# 【结论】写回存档是安全的。存档无校验和/无签名/无 HMAC，游戏不比对文本。

import math
import re
from decimal import Decimal, ROUND_HALF_UP

_NUM_RE = re.compile(r"-?\d+(?:\.\d+)?")


def _fmt_double(x):
    """按游戏规则格式化一个 double。"""
    if x != x:
        return "NaN"
    if math.isinf(x):
        return "Infinity" if x > 0 else "-Infinity"
    if x == 0:
        return "0.0"
    d = Decimal(repr(float(x)))
    e = d.adjusted()                       # 最高有效位的十进制指数
    q = Decimal(1).scaleb(e - 17 + 1)
    r = d.quantize(q, rounding=ROUND_HALF_UP)
    s = format(r, "f")
    if "." in s:
        s = s.rstrip("0")
        if s.endswith("."):
            s += "0"
    else:
        s += ".0"                          # 整数值也带 .0
    return s


def dump(segs):
    """序列化为存档文本。compact 风格，与游戏原格式一致（无空格缩进）。

    浮点格式化：标准 json 已经把 float 写成 "abc.def" 形式，
    这里只把**带小数点**的数字 token 重写为游戏的 17 位有效数字形式；
    纯整数 token 原样保留（游戏里 int 与 double 字段的序列化本就不同）。
    """
    out = SEP.join(
        json.dumps(s, ensure_ascii=False, separators=(",", ":"),
                   sort_keys=False)
        for s in segs
    )
    return _NUM_RE.sub(
        lambda m: _fmt_double(float(m.group())) if "." in m.group() else m.group(),
        out,
    )


def roundtrip(src_text):
    """解析后立刻序列化，返回 (out_text, verdict, detail)。

    verdict:
        'IDENTICAL'  文本逐字节相同
        'NUMERIC'    文本有差异，但所有数字 token 数值等价、字段结构完全相同
                     => 可以安全写回（游戏读档后数值一致）
        'STRUCTURED' 字段结构有增减 => 危险，不可写回
    """
    segs = load(src_text)
    out = dump(segs)

    if out == src_text:
        return out, "IDENTICAL", "文本逐字节相同"

    # 1) 结构比对：重新解析输出，与原结构深度比较
    try:
        segs2 = load(out)
        struct_same = json.dumps(segs2, sort_keys=True) == json.dumps(segs, sort_keys=True)
    except Exception:
        struct_same = False

    # 2) 数字 token 逐个数值比对
    ta = _NUM_RE.findall(src_text)
    tb = _NUM_RE.findall(out)
    n_text_diff = 0
    n_val_diff = 0
    examples = []
    if len(ta) == len(tb):
        for x, y in zip(ta, tb):
            if x != y:
                n_text_diff += 1
                try:
                    if float(x) != float(y):
                        n_val_diff += 1
                        if len(examples) < 3:
                            examples.append((x, y))
                except ValueError:
                    n_val_diff += 1
    else:
        n_val_diff = -1   # token 数量都不同，视为结构性差异

    if not struct_same:
        n = min(len(out), len(src_text))
        i = 0
        while i < n and out[i] == src_text[i]:
            i += 1
        return out, "STRUCTURED", (
            f"字段结构变化！首处差异 @{i}: "
            f"原文{src_text[i:i+40]!r} 新文{out[i:i+40]!r}"
        )

    if n_val_diff == 0:
        return out, "NUMERIC", (
            f"{n_text_diff} 个数字 token 文本末位不同，但数值全部等价"
            f"（共 {len(ta)} 个 token）"
        )

    return out, "STRUCTURED", (
        f"数值不等价：{n_val_diff} 处，例 {examples}"
    )


# ---------------------------------------------------------------- 路径访问

def parse_path(path):
    """'9.BaoShiSuiPian' -> ['9','BaoShiSuiPian']"""
    return path.split(".")


def _walk(segs, keys, create=False):
    cur = segs
    for k in keys[:-1]:
        if isinstance(cur, list):
            cur = cur[int(k)]
        else:
            if k not in cur:
                raise KeyError(f"字段不存在: {k}")
            cur = cur[k]
    return cur


def get_path(segs, path):
    keys = parse_path(path)
    parent = _walk(segs, keys)
    last = keys[-1]
    if isinstance(parent, list):
        return parent[int(last)]
    return parent[last]


def set_path(segs, path, value):
    keys = parse_path(path)
    parent = _walk(segs, keys)
    last = keys[-1]
    if isinstance(parent, list):
        parent[int(last)] = value
    else:
        parent[last] = value
    return segs


# ---------------------------------------------------------------- 业务操作

def op_libao(segs, ids):
    """从 LiBaoIDs 中删除指定礼包 ID（可重复兑换）。"""
    seg13 = None
    for s in segs:
        if s.get("DateID") == 13:
            seg13 = s
            break
    if seg13 is None:
        raise RuntimeError("找不到 DateID=13 的段")
    before = list(seg13.get("LiBaoIDs", []))
    removed = []
    for i in ids:
        i = int(i)
        if i in seg13["LiBaoIDs"]:
            seg13["LiBaoIDs"].remove(i)
            removed.append(i)
    return seg13, before, seg13["LiBaoIDs"], removed


def op_baoshi(segs, value):
    """设置宝石碎片 BaoShiSuiPian（段9）。"""
    seg9 = None
    for s in segs:
        if s.get("DateID") == 9:
            seg9 = s
            break
    if seg9 is None:
        raise RuntimeError("找不到 DateID=9 的段")
    before = seg9.get("BaoShiSuiPian")
    seg9["BaoShiSuiPian"] = int(value)
    return seg9, before, seg9["BaoShiSuiPian"]


def op_tree(segs, is_jihuo=1, is_huangjin=1, year=2100):
    """黄金树永久：段11 / Date_ShengMingShu (TypeDefIndex 3075)。

    字段语义实证（三份官方存档横向对比）：
        IsJiHuo          激活标志        (uint，0/1)
        IsHuangJin       **黄金等级标志**  (uint，0/1) —— 独立于到期时间！
        GuoQiTime        到期时间戳(毫秒)  (ulong)
        JiHuoCiShu       累计激活次数      (uint)
        GuoShiIsLingQu   果实是否已领      (uint)
        GuoShiChongZhiTime 果实重置时间戳  (ulong)

    关键证据：playerDate_01/02 的 GuoQiTime 已于 2020-07 过期，
    但 IsHuangJin 仍为 1 —— 所以"黄金"由 IsHuangJin 决定，不是由到期时间推导。
    把 IsHuangJin 置 1 且 GuoQiTime 推到远期，即可同时满足两个条件。

    注意 GuoQiTime 是 ulong（不是 long），4092444800000 这类值完全合法。
    """
    seg11 = None
    for s in segs:
        if s.get("DateID") == 11:
            seg11 = s
            break
    if seg11 is None:
        raise RuntimeError("找不到 DateID=11 的段")

    before = dict(seg11)
    # 2100-01-01T00:00:00Z 的毫秒时间戳，留足余量
    far = int(time.mktime(time.strptime("%d-01-01" % year, "%Y-%m-%d"))) * 1000
    seg11["IsJiHuo"] = int(is_jihuo)
    seg11["IsHuangJin"] = int(is_huangjin)
    seg11["GuoQiTime"] = far
    return seg11, before


def op_baoshiall(segs, level=99, pinjie=6, xiyoudu=5, zhuan_shu=None,
                 recount=True):
    """宝石全面强化：段1 各英雄 HeroBaoShis 内每颗宝石的属性。

    结构（dump.cs:263021 ShenQiBaoShiClass TypeDefIndex 3057）：
        ulong baoShiID;           // 0x10  ID 编码：颜色*? + 段位，如 3667
        uint  baoShiLevel;        // 0x18  等级 1~99（实测上限 99）
        uint  baoShiZhuanShuID;   // 0x1C  专精 0~5
        uint  baoShiPinJie;       // 0x20  品阶 0~6
        BaoShiXiYouDu baoShiXiYouDu; // 0x24 稀有度 0~5
        bool  isZhuangBei;        // 0x28  是否已镶在装备上
        int[] zhuangBeiID;        // 0x30  镶在哪件装备 [26,1] = 英雄装备格

    枚举 BaoShiXiYouDu (dump.cs:257244)：
        0 普通 PuTong / 1 精致 JingZhi / 2 稀有 XiYou
        3 史诗 ShiShi / 4 传说 ChuanShuo / 5 远古 YuanGu

    对 HeroBaoShis 的处理：**只改属性，不增删数组**。
    新增宝石元素风险高 —— baoShiID 的编码规则未知，
    而且 isZhuangBei / zhuangBeiID 必须与 HeroZhuangBeis[].XiangQianBaoShiID 保持一致，
    随意插入会造成"宝石说自己镶在 X，但装备 X 的孔位里没有它"的不一致状态。
    """
    seg1 = None
    for s in segs:
        if s.get("DateID") == 1:
            seg1 = s
            break
    if seg1 is None:
        raise RuntimeError("找不到 DateID=1 的段")

    touched = 0
    per_hero = []
    for h in seg1.get("HerosDates") or []:
        lst = h.get("HeroBaoShis") or []
        for b in lst:
            b["baoShiLevel"] = max(b.get("baoShiLevel", 0), int(level))
            b["baoShiPinJie"] = max(b.get("baoShiPinJie", 0), int(pinjie))
            b["baoShiXiYouDu"] = max(b.get("baoShiXiYouDu", 0), int(xiyoudu))
            if zhuan_shu is not None:
                b["baoShiZhuanShuID"] = max(b.get("baoShiZhuanShuID", 0),
                                            int(zhuan_shu))
            touched += 1
        per_hero.append((h.get("HeroID"), h.get("HeroName"), len(lst)))

    peak = 0
    if recount:
        peak = op_baoshi_recount(segs)
    return per_hero, touched, peak


def op_baoshi_recount(segs):
    """重算段9 的 SuoYouBaoShiTongJi 统计，使其与段1 的实际宝石一致。

    统计口径（实测反推，基于 3 份官方存档 556 颗宝石）：
        baoShiZongShu        **历史累计**获得总数（远大于当前持有，如 23812 vs 497）
        baoShiShuJie_01..07  按品阶(baoShiPinJie)计数，Jie_0N = PinJie N-1
        baoShiShu_PuTong..   按稀有度(BaoShiXiYouDu 0~5)计数，与枚举同名
        baoShiShu_FenJie     历史累计分解数（无法从当前状态推导，保持原值）

    这里只重算**能确定的 13 项**（总阶 7 + 品质 6），把它们设为与当前
    宝石数组完全一致的值；ZongShu 与 FenJie 属于历史累计量，保持不动。

    忠实度证据：playerDate_03 当前 497 颗，其中 XiYouDu=4 的有 494、
    =5 的有 3，与统计里的 ChuanShuo=776 / YuanGu=3 在 YuanGu 一项完全吻合，
    说明统计确实是按同一口径累加的。

    返回：更新后的品质计数中最大的值（供调用方参考）。
    """
    seg1 = None
    seg9 = None
    for s in segs:
        if s.get("DateID") == 1:
            seg1 = s
        elif s.get("DateID") == 9:
            seg9 = s
    if seg1 is None or seg9 is None:
        raise RuntimeError("找不到段 1 或段 9")

    pin = [0] * 7
    xy = [0] * 6
    for h in seg1.get("HerosDates") or []:
        for b in h.get("HeroBaoShis") or []:
            p = int(b.get("baoShiPinJie", 0))
            x = int(b.get("baoShiXiYouDu", 0))
            if 0 <= p < 7:
                pin[p] += 1
            if 0 <= x < 6:
                xy[x] += 1

    st = seg9.get("SuoYouBaoShiTongJi")
    if st is None:
        return 0
    for i in range(7):
        st["baoShiShuJie_%02d" % (i + 1)] = pin[i]
    names = ["PuTong", "JingZhi", "XiYou", "ShiShi", "ChuanShuo", "YuanGu"]
    for i, n in enumerate(names):
        st["baoShiShu_" + n] = xy[i]
    # 严格对应：总和应等于当前持有数
    total_now = sum(pin)
    if total_now > int(st.get("baoShiZongShu", 0)):
        st["baoShiZongShu"] = total_now
    return max(xy) if xy else 0


def op_pets(segs, level=60, jinhua=4, jinjie=10, hp=9999, dmg=9999):
    """宠物强化：提升段6 全部槽位的属性。

    【重要认知 — 2026-10 实测修正】
    `SuoYouChongWuDate` **不是**"已获得宠物列表"，而是**全部 85 种宠物的属性表**。
    三份官方演示存档里 85 个槽位全部有值（ChongWuLevel 均 > 0）。
    dump.cs:263195 的 ChongWuDate 只有 8 个字段，**没有任何"是否拥有"标志**：

        public uint  ChongWuID;              // 0x10
        public uint  ChongWuLevel;           // 0x14
        public uint  ChongWuJinHua;          // 0x18   进化阶段 0~4
        public uint  ChongWuJinJie;          // 0x1C   阶级
        public ulong ChongWuYongJiu_HP;      // 0x20   永久生命
        public ulong ChongWuYongJiu_Damage;  // 0x28   永久攻击
        public uint  IsXieDai;               // 0x30   是否携带(同时只能 1 只 = 1)
        public int   IsMaoXian;             // 0x34   是否冒险

    => 所以"宠物获取"在存档层无法实现；宠物本就全在表里。
       能改的是**属性**：等级 / 进化 / 阶级 / 永久HP / 永久攻击。
       真正的"开放"是解锁宠物**玩法**，见 ChongWuPool.OpenAllChongWu() (dump.cs:256215)。

    这里只上调、不下调（取 max），避免把已培养的宠物改低。
    """
    seg6 = None
    for s in segs:
        if s.get("DateID") == 6:
            seg6 = s
            break
    if seg6 is None:
        raise RuntimeError("找不到 DateID=6 的段")
    lst = seg6["SuoYouChongWuDate"]
    changed = []
    for it in lst:
        old = (it.get("ChongWuLevel", 0), it.get("ChongWuJinHua", 0),
               it.get("ChongWuJinJie", 0), it.get("ChongWuYongJiu_HP", 0),
               it.get("ChongWuYongJiu_Damage", 0))
        it["ChongWuLevel"] = max(it.get("ChongWuLevel", 0), level)
        it["ChongWuJinHua"] = max(it.get("ChongWuJinHua", 0), jinhua)
        it["ChongWuJinJie"] = max(it.get("ChongWuJinJie", 0), jinjie)
        it["ChongWuYongJiu_HP"] = max(it.get("ChongWuYongJiu_HP", 0), hp)
        it["ChongWuYongJiu_Damage"] = max(it.get("ChongWuYongJiu_Damage", 0), dmg)
        new = (it["ChongWuLevel"], it["ChongWuJinHua"], it["ChongWuJinJie"],
               it["ChongWuYongJiu_HP"], it["ChongWuYongJiu_Damage"])
        if new != old:
            changed.append(it.get("ChongWuID"))
    return seg6, len(lst), changed


# ---------------------------------------------------------------- CLI

def read_file(p):
    with open(p, "rb") as f:
        return f.read()


def write_file(p, text, bak=True):
    if bak and os.path.exists(p):
        shutil.copy2(p, p + ".bak")
    with open(p, "w", encoding="utf-8", newline="") as f:
        f.write(text)
    return p


def cmd_info(archive):
    raw = read_file(archive)
    segs = load(raw)
    print(f"文件: {archive}")
    print(f"大小: {len(raw)} 字节, {len(segs)} 段")
    for i, s in enumerate(segs):
        keys = [k for k in s.keys() if k != "DateID"]
        print(f"  seg[{s.get('DateID', i)}] {len(keys)} 字段: {keys[:8]}")


def cmd_roundtrip(archive):
    raw = read_file(archive)
    text = raw.decode("utf-8-sig")
    out, verdict, detail = roundtrip(text)
    print(f"原文 {len(text)} 字符 -> 重存 {len(out)} 字符")
    if verdict == "IDENTICAL":
        print("RESULT: IDENTICAL —— 文本逐字节相同，完美无损")
        return 0
    if verdict == "NUMERIC":
        print(f"RESULT: NUMERIC-SAFE —— {detail}")
        print("  说明: 仅浮点末位文本表示不同，double 值完全一致。")
        print("        存档无校验和/签名，游戏不比对文本 => 安全写回。")
        return 0
    print(f"RESULT: STRUCTURED-DIFF —— {detail}")
    print("  !! 字段结构发生变化，不要直接写回，需人工核对。")
    return 1


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    cmd, archive = argv[1], argv[2]
    args = argv[3:]
    out = None
    if "--out" in args:
        i = args.index("--out")
        out = args[i + 1]
        args = args[:i] + args[i + 2:]

    if cmd == "info":
        cmd_info(archive)
        return 0
    if cmd == "roundtrip":
        return cmd_roundtrip(archive)

    raw = read_file(archive)
    segs = load(raw)

    if cmd == "get":
        print(json.dumps(get_path(segs, args[0]), ensure_ascii=False))
        return 0

    if cmd == "set":
        val = json.loads(args[1])
        set_path(segs, args[0], val)
        print(f"已设置 {args[0]} = {val}")

    elif cmd == "libao":
        seg, before, after, removed = op_libao(segs, args)
        print(f"LiBaoIDs 前: {before}")
        print(f"LiBaoIDs 后: {after}")
        print(f"移除: {removed}")

    elif cmd == "baoshi":
        seg, before, after = op_baoshi(segs, args[0])
        print(f"BaoShiSuiPian: {before} -> {after}")

    elif cmd == "pets":
        # 可选参数: --level N --jinhua N --jinjie N --hp N --dmg N
        opts = {"level": 60, "jinhua": 4, "jinjie": 10, "hp": 9999, "dmg": 9999}
        rest = []
        i = 0
        while i < len(args):
            a = args[i]
            if a.startswith("--") and a[2:] in opts:
                opts[a[2:]] = int(args[i + 1])
                i += 2
            else:
                rest.append(a)
                i += 1
        seg, total, changed = op_pets(segs, **opts)
        print("宠物槽位总数 %d, 本次上调 %d 个" % (total, len(changed)))
        print("  参数: %s" % opts)
        print("  变更ID: %s%s" % (changed[:20], " ..." if len(changed) > 20 else ""))

    elif cmd == "tree":
        # 可选参数: --jihuo N --huangjin N --year N
        opts = {"jihuo": 1, "huangjin": 1, "year": 2100}
        i = 0
        while i < len(args):
            a = args[i]
            if a.startswith("--") and a[2:] in opts:
                opts[a[2:]] = int(args[i + 1])
                i += 2
            else:
                i += 1
        seg, before = op_tree(segs, opts["jihuo"], opts["huangjin"], opts["year"])
        print("段11 前: %s" % before)
        print("段11 后: %s" % dict(seg))

    elif cmd == "baoshiall":
        # 可选参数: --level N --pinjie N --xiyoudu N --zhuan N
        opts = {"level": 99, "pinjie": 6, "xiyoudu": 5, "zhuan": None}
        i = 0
        while i < len(args):
            a = args[i]
            if a.startswith("--") and a[2:] in opts:
                opts[a[2:]] = int(args[i + 1])
                i += 2
            else:
                i += 1
        per_hero, touched, peak = op_baoshiall(
            segs, opts["level"], opts["pinjie"], opts["xiyoudu"], opts["zhuan"])
        print("各英雄宝石数 (HeroID, 名字, 颗数):")
        for hid, name, n in per_hero:
            print("   %-3s %-8s %d" % (hid, name, n))
        print("本次强化宝石总数: %d" % touched)
        print("段9 统计已重算 (品阶 7 项 + 品质 6 项)，最大品质计数: %d" % peak)

    else:
        print(f"未知命令: {cmd}")
        return 2

    new_text = dump(segs)
    dest = out or archive
    write_file(dest, new_text)
    print(f"已写入: {dest}  ({len(new_text)} 字符)")
    if dest == archive:
        print(f"原文件已备份: {archive}.bak")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
