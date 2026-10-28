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
    python savedit.py equip     <archive> [--level N] [--max N]      # 装备等级+LvMax
    python savedit.py heroes    <archive> [--level N --shenqi N --moshu N
                                          --autoskill N]              # 英雄/神器/魔石
    python savedit.py currency  <archive> [--zuanshi N --jinyan N
                                          --baoshi N --mowu N]        # 钻石/经验/碎片
    python savedit.py resources <archive> [--mucai N --kuangshi N --jinhua N
                                          --yaoshi N --siliao N]      # 木材/矿石/进化石
    python savedit.py level     <archive> [--guanka N --taplevel N
                                          --jianyuan N --famuchang N
                                          --kuangshichang N]          # 各类关卡等级
    python savedit.py chengjiu  <archive> [--level N]                 # 成就等级

path 语法: 段号.字段[.子字段][.数组下标], 例如
    9.BaoShiSuiPian
    6.SuoYouChongWuDate.0.ChongWuLevel
    11.GuoQiTime
    13.LiBaoIDs

密文存档: 本工具只吃解密后的 14 段明文 JSON。要处理 .es3 请先
    python scripts/es3save.py unpack saves/SaveFile.es3 out.json
改完再
    python scripts/es3save.py pack out.json saves/SaveFile.es3
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


def op_zhuangbei(segs, level=None, maxlevel=None, only_below=False):
    """装备等级强化：段1 每个英雄的 HeroZhuangBeis。

    结构（dump.cs:263040 ZhuangBeiDate TypeDefIndex 3058）：
        uint   ZhuangBeiID;         // 0x10
        uint   ZhuangBeiLevel;      // 0x14  当前等级
        uint   ZhuangBeiLevelMax;   // 0x18  等级上限
        ulong[] XiangQianBaoShiID;  // 0x20  已镶嵌的宝石 ID（5 个孔）

    【实证】三份官方存档里 Level 与 LevelMax **恒相等**（playerDate_02/03 全量比对），
    唯一例外是 _01 里 Zero 英雄的 200/230（培养中途的状态）。
    所以只抬 Level 不抬 LevelMax，会造出"超过上限"的非法态 —— 两个必须一起抬。

    返回 (总件数, 改动件数, 涉及英雄数)。
    """
    seg1 = _seg(segs, 1)
    total = 0
    changed = 0
    heroes = set()
    for h in seg1.get("HerosDates") or []:
        hit = False
        for z in h.get("HeroZhuangBeis") or []:
            total += 1
            cur = int(z.get("ZhuangBeiLevel", 0))
            cmax = int(z.get("ZhuangBeiLevelMax", 0))
            if only_below and cur >= maxlevel:
                continue
            new = cur if level is None else max(cur, int(level))
            newmax = cmax if maxlevel is None else max(cmax, int(maxlevel))
            if new != cur or newmax != cmax:
                z["ZhuangBeiLevel"] = new
                z["ZhuangBeiLevelMax"] = newmax
                changed += 1
                hit = True
        if hit:
            heroes.add(h.get("HeroID"))
    return total, changed, len(heroes)


def op_heroes(segs, level=None, shenqi=None, moshu=None, auto_skill=None):
    """英雄本体强化：段1 每个 HeroDate。

    结构（dump.cs:262999 HeroDate TypeDefIndex 3056）：
        uint   HeroID;             // 0x10
        string HeroName;           // 0x18
        uint   HeroLevel;          // 0x20  ★ 只能上调
        uint[] HeroPiFus;          // 0x28  已解锁皮肤
        uint   HeroPiFuXuanZeID;   // 0x30
        ZhuangBeiDate[] HeroZhuangBeis;  // 0x38
        ShenQiBaoShiClass[] HeroBaoShis; // 0x40
        uint   HeroShenQiLevel;    // 0x48  神器等级
        MoShiJiNengDate[] MoShiJiNengs;  // 0x50
        uint   ZiDongJiNengID;     // 0x58

    【重要】**不要下调 HeroLevel**。
    三份官方存档的最高英雄等级是 33 / 51 / 60，但游戏里还卡着
    `JingYan`（经验）这条腿；单改等级不会补经验，可能被读档逻辑判为
    "等级超出经验可解释范围" 而回退。保持 max() 语义最稳。
    """
    seg1 = _seg(segs, 1)
    rows = []
    for h in seg1.get("HerosDates") or []:
        old = h.get("HeroLevel", 0)
        if level is not None:
            h["HeroLevel"] = max(int(old), int(level))
        if shenqi is not None:
            h["HeroShenQiLevel"] = max(int(h.get("HeroShenQiLevel", 0)), int(shenqi))
        if moshu is not None:
            for m in h.get("MoShiJiNengs") or []:
                m["MoShiJiNengLevel"] = max(
                    int(m.get("MoShiJiNengLevel", 0)), int(moshu))
        if auto_skill is not None:
            h["ZiDongJiNengID"] = int(auto_skill)
        rows.append((h.get("HeroID"), h.get("HeroName"), old,
                     h.get("HeroLevel"), h.get("HeroShenQiLevel")))
    return rows


def op_currency(segs, zuanshi=None, jinyan=None, baoshi=None, mowu=None):
    """货币/经验：段13（钻石、经验）、段9（宝石碎片）、段10（魔物碎片）。"""
    seg13 = _seg(segs, 13)
    before = {k: seg13.get(k) for k in ("ZuanShi", "JingYan")}
    if zuanshi is not None:
        seg13["ZuanShi"] = int(zuanshi)
    if jinyan is not None:
        seg13["JingYan"] = int(jinyan)
    if baoshi is not None:
        _seg(segs, 9)["BaoShiSuiPian"] = int(baoshi)
    if mowu is not None:
        _seg(segs, 10)["MoWuSuiPian"] = int(mowu)
    after = {k: seg13.get(k) for k in ("ZuanShi", "JingYan")}
    return before, after


def op_resources(segs, mucai=None, kuangshi=None, jinhua=None,
                 yaoshi=None, siliao=None):
    """资源：段2（木材/矿石）、段6（六种进化石/宠物饲料）、段5（盗贼钥匙）。

    Date_ZiYuan（dump.cs:263070）的 MuCaiShuLiang / KuangShiShuLiang 是 ulong，
    另有 *_LiXianKu 是离线累积池 —— 这里**同步抬离线池**，否则一读档
    "离线收益"会把主数值覆盖回去。
    """
    seg2 = _seg(segs, 2)
    out = {}
    if mucai is not None:
        v = int(mucai)
        out["MuCaiShuLiang"] = (seg2.get("MuCaiShuLiang"), v)
        seg2["MuCaiShuLiang"] = v
        seg2["MuCaiShuLiang_LiXianKu"] = v
    if kuangshi is not None:
        v = int(kuangshi)
        out["KuangShiShuLiang"] = (seg2.get("KuangShiShuLiang"), v)
        seg2["KuangShiShuLiang"] = v
        seg2["KuangShiShuLiang_LiXianKu"] = v
    if jinhua is not None:
        seg6 = _seg(segs, 6)
        for k in ("JinHuaShi_Feng", "JinHuaShi_Huo", "JinHuaShi_Shui",
                  "JinHuaShi_Di", "JinHuaShi_Guang", "JinHuaShi_An"):
            out[k] = (seg6.get(k), int(jinhua))
            seg6[k] = int(jinhua)
    if siliao is not None:
        seg6 = _seg(segs, 6)
        out["ChongWuSiLiao"] = (seg6.get("ChongWuSiLiao"), int(siliao))
        seg6["ChongWuSiLiao"] = int(siliao)
    if yaoshi is not None:
        seg5 = _seg(segs, 5)
        out["DaoZeiYaoShi"] = (seg5.get("DaoZeiYaoShi"), int(yaoshi))
        seg5["DaoZeiYaoShi"] = int(yaoshi)
    return out


def op_level(segs, guanka=None, taplevel=None, jianyuan=None, famuchang=None,
             kuangshichang=None):
    """关卡/家园/伐木场/矿石场等级：段8、段0、段2。"""
    out = {}
    if guanka is not None:
        s8 = _seg(segs, 8)
        out["GuanKaLevel"] = (s8.get("GuanKaLevel"), int(guanka))
        s8["GuanKaLevel"] = int(guanka)
    if taplevel is not None:
        s0 = _seg(segs, 0)
        out["TapLevel"] = (s0.get("TapLevel"), int(taplevel))
        s0["TapLevel"] = int(taplevel)
    s2 = _seg(segs, 2)
    for key, val in (("JiaYuanLevel", jianyuan),
                     ("FaMuChangLevel", famuchang),
                     ("KuangShiChangLevel", kuangshichang)):
        if val is not None:
            out[key] = (s2.get(key), int(val))
            s2[key] = int(val)
    return out


def op_chengjiu(segs, level=99):
    """成就等级：段4 SuoYouChengJiu（Date_ChengJiu 3062）。"""
    seg4 = _seg(segs, 4)
    lst = seg4.get("SuoYouChengJiu") or []
    changed = 0
    for it in lst:
        if int(it.get("ChengJiuLevel", 0)) < int(level):
            it["ChengJiuLevel"] = int(level)
            changed += 1
    return len(lst), changed


def _seg(segs, did):
    for s in segs:
        if int(s.get("DateID", -1)) == did:
            return s
    raise RuntimeError("找不到 DateID=%d 的段" % did)


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
    """读存档。命中 .es3 就自动走两层解密（docs/10 + docs/11），
    返回 14 段明文 UTF-8。这样所有子命令对 .es3 与 .json 一视同仁。
    """
    with open(p, "rb") as f:
        raw = f.read()
    if p.lower().endswith(".es3") or is_es3_blob(raw):
        try:
            from es3save import read_save
        except ImportError:  # 脚本被拷到别处单独跑
            print("!! 这是 ES3 密文，需要同目录的 es3save.py 才能解密")
            raise
        return read_save(p)
    return raw


def is_es3_blob(raw):
    """粗判是否为 ES3 密文：长度 = 32 + 16n，且第 17..32 字节像 IV（非全零）。"""
    if len(raw) < 48 or (len(raw) - 32) % 16:
        return False
    head = raw[:8]
    # 明文存档一定以 '{' 或 '$' 分隔的对象开头，密文则完全随机
    if head.lstrip().startswith(b"{") or head.lstrip()[:1] in (b"0", b"1"):
        return False
    return True


def write_file(p, text, bak=True):
    """写存档。目标后缀是 .es3 就重新走两层加密（新随机 salt/iv）。"""
    if bak and os.path.exists(p):
        shutil.copy2(p, p + ".bak")
    if p.lower().endswith(".es3"):
        from es3save import write_save
        write_save(p, text.encode("utf-8"), bak=False)
        return p
    with open(p, "wb") as f:
        f.write(text.encode("utf-8"))
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


def verify_archive(text):
    """写回前自检：必须是 14 段、每段可独立解析、DateID 齐全且唯一。

    返回 None 表示通过，否则返回一句人类可读的失败原因。
    这个检查比 roundtrip 更严格 —— roundtrip 只能保证"我解析再序列化"
    这一步没走样，而 verify_archive 保证"产出物本身是合法存档"。
    """
    parts = [p for p in text.split(SEP) if p.strip()]
    if len(parts) != NUM_SEGMENTS:
        return "段数 %d != %d" % (len(parts), NUM_SEGMENTS)
    ids = []
    for i, p in enumerate(parts):
        try:
            obj = json.loads(p)
        except Exception as e:  # noqa: BLE001
            return "第 %d 段 JSON 解析失败: %s" % (i, e)
        if not isinstance(obj, dict):
            return "第 %d 段不是对象: %s" % (i, type(obj).__name__)
        if "DateID" not in obj:
            return "第 %d 段缺 DateID" % i
        ids.append(int(obj["DateID"]))
    if ids != list(range(NUM_SEGMENTS)):
        return "DateID 序列异常: %s" % ids
    return None


def _parse_opts(args, opts):
    """把 `--key N` 形式的参数就地填进 opts（键必须是 opts 已有的）。"""
    i = 0
    while i < len(args):
        a = args[i]
        if a.startswith("--") and a[2:] in opts:
            opts[a[2:]] = int(args[i + 1])
            i += 2
        else:
            i += 1
    return opts


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
    dry_run = "--dry-run" in args
    if dry_run:
        args = [a for a in args if a != "--dry-run"]

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

    elif cmd == "equip":
        opts = {"level": None, "max": None}
        _parse_opts(args, opts)
        total, changed, nhero = op_zhuangbei(
            segs, opts["level"], opts["max"] or opts["level"])
        print("装备总件数 %d，本次改动 %d 件（涉及 %d 个英雄）" % (total, changed, nhero))
        print("  参数: Level=%s LevelMax=%s" % (opts["level"], opts["max"] or opts["level"]))

    elif cmd == "heroes":
        opts = {"level": None, "shenqi": None, "moshu": None, "autoskill": None}
        _parse_opts(args, opts)
        rows = op_heroes(segs, opts["level"], opts["shenqi"],
                         opts["moshu"], opts["autoskill"])
        print("英雄 (ID, 名字, 旧Lv, 新Lv, 神器Lv):")
        for r in rows:
            print("   %-3s %-8s %3s -> %-3s  神器%s" % r)

    elif cmd == "currency":
        opts = {"zuanshi": None, "jinyan": None, "baoshi": None, "mowu": None}
        _parse_opts(args, opts)
        before, after = op_currency(segs, **opts)
        print("段13 前: %s" % before)
        print("段13 后: %s" % after)
        if opts["baoshi"] is not None:
            print("段9 BaoShiSuiPian -> %s" % opts["baoshi"])
        if opts["mowu"] is not None:
            print("段10 MoWuSuiPian -> %s" % opts["mowu"])

    elif cmd == "resources":
        opts = {"mucai": None, "kuangshi": None, "jinhua": None,
                "yaoshi": None, "siliao": None}
        _parse_opts(args, opts)
        res = op_resources(segs, **opts)
        for k, (a, b) in res.items():
            print("   %-24s %s -> %s" % (k, a, b))

    elif cmd == "level":
        opts = {"guanka": None, "taplevel": None, "jianyuan": None,
                "famuchang": None, "kuangshichang": None}
        _parse_opts(args, opts)
        res = op_level(segs, **opts)
        for k, (a, b) in res.items():
            print("   %-20s %s -> %s" % (k, a, b))

    elif cmd == "chengjiu":
        opts = {"level": 99}
        _parse_opts(args, opts)
        total, changed = op_chengjiu(segs, opts["level"])
        print("成就总数 %d，本次上调 %d 条" % (total, changed))

    else:
        print(f"未知命令: {cmd}")
        return 2

    new_text = dump(segs)

    # ---- 写回前自检：新存档必须仍是 14 段、且每段能独立 json 解析 ----
    bad = verify_archive(new_text)
    if bad:
        print("!! 自检失败，拒绝写回: %s" % bad)
        return 1

    if dry_run:
        print("[--dry-run] 未写盘。生成 %d 字符" % len(new_text))
        return 0

    dest = out or archive
    write_file(dest, new_text)
    print(f"已写入: {dest}  ({len(new_text)} 字符)")
    if dest == archive:
        print(f"原文件已备份: {archive}.bak")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
