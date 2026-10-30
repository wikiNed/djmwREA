#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从零构造一个游戏可读的 SaveFile.es3 —— 不需要任何现存存档文件。

【为什么可行（docs/20）】

    槽名 = PlayerData.GetID() = ShuJuDate.playerZhangHao
         = PlayerPrefs["UJHJKOikhS"] = 账号名

    `PlayerData.GetID @ 0x1896030` 是纯转发，没有哈希也没有随机数，
    所以只要知道账号名，槽名就是确定的。

【三层输入】

    1. 骨架：官方模板 playerDate_03（evidence/templates/playerDate_03.bin）
       104886 字节的满级存档（TapLevel=60 / TapZongShu=602076），
       14 段齐全。这是游戏自带的资源，不是我们造的，所以字段集合、
       类型、顺序全都合法。

    2. 外层参数：salt / iv / _Key
       同一工作区里找一份真机原档当“随机源”：
         - salt / iv 直接从原档读（复用它们是 docs/19 的硬性要求）
         - _Key 默认照抄原档（真机为 2640）

    3. 账号名：决定桶里 string 槽的名字

【派生还是照抄】

    没有原档时 salt/iv 只能随机，此时 ``--allow-random-outer`` 必须显式
    打开。random outer 在真机上的表现没有验证过（docs/19 记录的反例是
    “换 salt/iv → 黑屏”），所以默认拒绝，而不是默默生成一个可能读不出的文件。

用法:
    # 用工作区里现成的原档当 salt 源
    python scripts/new_save.py --account "o2D+pAPsvrXCo74JUkh9jw==" \\
        --base work/live/SaveFile_device_orig.es3 --out new.es3

    # 从模板起，改几个值
    python scripts/new_save.py --account "abc==" --out new.es3 \\
        --set 13.ZuanShi=9999999 --set 0.PlayerName=wikined

    # 自检：解析回来校验段数与槽名
    python scripts/new_save.py --account x --out new.es3 --verify
"""
import argparse
import base64
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import es3save as E  # noqa: E402
from paths import REPO, TEMPLATES  # noqa: E402

NUM_SEGMENTS = 14

#: 官方满级模板（UnityPy 从 data.unity3d 的 TextAsset path_id=161 导出）
DEFAULT_TEMPLATE = os.path.join(TEMPLATES, "playerDate_03.bin")

#: 找 salt 源时按顺序尝试的真机存档
BASELINE_CANDIDATES = (
    os.path.join(REPO, "work", "live", "SaveFile_device_orig.es3"),
    os.path.join(REPO, "evidence", "saves", "SaveFile_device_orig.es3"),
)

#: 字段补全的参考档（游戏自己写过、必定能读）。按顺序取第一份存在的。
#:
#: 为什么需要补全（docs/22）：唯一一份自带的满级模板 playerDate_03 缺字段。
#:     seg12 缺 TanPai_{IOP,ZCS,DTCS,CZT}  —— 游戏实跑后写的档里有
#:     （seg2 / seg13 的差异见 templates/template_diff.py 的输出）
#: 缺字段会让「从零构造」与「真机档」形状不一致，所以默认从参考档补齐。
SHAPE_REFERENCE_CANDIDATES = (
    os.path.join(REPO, "evidence", "saves", "SaveFile_device_orig.es3"),
    os.path.join(REPO, "evidence", "saves", "SaveFile_after_orig.es3"),
)


class NewSaveError(RuntimeError):
    pass


def load_baseline(explicit=None):
    """找一份真机存档当 salt/iv 源，返回 (salt, iv, key_counter) 或 None。"""
    cands = ([explicit] if explicit else []) + list(BASELINE_CANDIDATES)
    for p in cands:
        if not p or not os.path.exists(p):
            continue
        blob = open(p, "rb").read()
        salt, iv = E.salt_iv_of(blob)
        try:
            layer1 = E.decrypt_bytes(blob, E.PASSWORD)
            _, obj = E.parse_bucket(layer1)
            kc = obj.get("_Key", {}).get("value")
            if not isinstance(kc, int):
                kc = 2640
        except Exception:  # noqa: BLE001
            kc = 2640
        return salt, iv, kc, p
    return None


def load_template(path):
    raw = open(path, "rb").read()
    text = raw.decode("utf-8")
    segs = text.split(E.SEP if hasattr(E, "SEP") else "$")
    if len(segs) != NUM_SEGMENTS:
        raise NewSaveError("模板段数 %d != %d，不是合法的 14 段存档"
                           % (len(segs), NUM_SEGMENTS))
    out = []
    for i, s in enumerate(segs):
        try:
            out.append(json.loads(s))
        except json.JSONDecodeError as exc:
            raise NewSaveError("模板第 %d 段不是合法 JSON: %s" % (i, exc))
    return out


def load_reference(explicit=None):
    """找一份「游戏自己写过」的档当字段补全基准，返回 14 段对象或 None。"""
    cands = ([explicit] if explicit else []) + list(SHAPE_REFERENCE_CANDIDATES)
    for p in cands:
        if not p or not os.path.exists(p):
            continue
        plain = E.read_save(p)
        txt = plain.decode("utf-8") if isinstance(plain, bytes) else plain
        parts = txt.split("$")
        if len(parts) != NUM_SEGMENTS:
            continue
        try:
            return [json.loads(s) for s in parts], p
        except json.JSONDecodeError:
            continue
    return None


def merge_reference(segs, ref):
    """把参考档里有、模板里没有的**整段**(整段缺失) 或**字段**补进模板。

    只补不改：模板已有的字段值一律保留（模板是满级档，值是设计好的）；
    缺的字段按参考档的位置插入，以维持与真机档一致的字段顺序。
    """
    added = []
    for i in range(NUM_SEGMENTS):
        have = set(segs[i])
        want = list(ref[i])
        for field in want:
            if field in have:
                continue
            # 按参考档里的相对位置插入：找它后面最近的那个模板里也有的字段
            pos = want.index(field)
            anchor = None
            for nxt in want[pos + 1:]:
                if nxt in have:
                    anchor = nxt
                    break
            if anchor is None:
                # 后面没有可锚定的字段 -> 追加到末尾，保持原顺序
                segs[i][field] = ref[i][field]
            else:
                rebuilt = {}
                for k, v in segs[i].items():
                    if k == anchor:
                        rebuilt[field] = ref[i][field]
                    rebuilt[k] = v
                segs[i].clear()
                segs[i].update(rebuilt)
            have.add(field)
            added.append("seg%d.%s" % (i, field))
    return added


def apply_sets(segs, assigns):
    """--set SEG.FIELD=VALUE，VALUE 按 JSON 解析，失败则当字符串。"""
    for item in assigns:
        if "=" not in item:
            raise NewSaveError("--set 需要 SEG.FIELD=VALUE 形式，收到 %r" % item)
        lhs, rhs = item.split("=", 1)
        if "." not in lhs:
            raise NewSaveError("--set 的左边需要 SEG.FIELD，收到 %r" % lhs)
        seg_s, field = lhs.split(".", 1)
        idx = int(seg_s)
        if not 0 <= idx < NUM_SEGMENTS:
            raise NewSaveError("段号 %d 超出 0..%d" % (idx, NUM_SEGMENTS - 1))
        if field not in segs[idx]:
            raise NewSaveError("seg%d 里没有字段 %r（可用：%s）"
                               % (idx, field, ", ".join(segs[idx])))
        try:
            val = json.loads(rhs)
        except json.JSONDecodeError:
            val = rhs
        segs[idx][field] = val


def build(plain_segs, account, salt, iv, key_counter):
    """把 14 段对象封成完整的 .es3 字节串。"""
    text = "$".join(json.dumps(s, ensure_ascii=False,
                               separators=(",", ":")) for s in plain_segs)
    hexstr = E.des_encrypt(text.encode("utf-8"))
    bucket = E.build_bucket(hexstr, key_counter=key_counter,
                            string_key=account)
    return E.encrypt_bytes(bucket, E.PASSWORD, salt=salt, iv=iv)


def verify(path, account, verbose=True):
    """解析回来校验：段数、槽名、能否重新拼出同样的明文。"""
    blob = open(path, "rb").read()
    layer1 = E.decrypt_bytes(blob, E.PASSWORD)
    hexstr, obj = E.parse_bucket(layer1)
    problems = []

    names = [k for k, v in obj.items()
             if isinstance(v, dict) and v.get("__type") == "string"]
    if names != [account]:
        problems.append("string 槽名不是 [%r]，实际 %r" % (account, names))

    if layer1.lstrip().startswith(b"{"):
        problems.append("桶明文以 { 开头，ES3 原档是以 _Key 开头的裸形式")

    plain = E.des_decrypt(hexstr, E.DES_KEY)
    segs = plain.decode("utf-8").split("$")
    if len(segs) != NUM_SEGMENTS:
        problems.append("解出 %d 段，应为 %d" % (len(segs), NUM_SEGMENTS))
    for i, s in enumerate(segs):
        try:
            json.loads(s)
        except json.JSONDecodeError as exc:
            problems.append("seg%d 不是合法 JSON: %s" % (i, exc))

    if verbose:
        print("文件      : %s (%d 字节)" % (path, len(blob)))
        print("盐/IV     : %s / %s" % (E.salt_iv_of(blob)[0].hex(),
                                        E.salt_iv_of(blob)[1].hex()))
        print("槽名      : %r" % (names,))
        print("_Key      : %r" % obj.get("_Key", {}).get("value"))
        print("内层明文  : %d 字节 / %d 段" % (len(plain), len(segs)))
        if problems:
            print("问题:")
            for p in problems:
                print("  - " + p)
        else:
            print("自检      : 通过")
    return not problems


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="从零构造 SaveFile.es3（不需要现存存档）")
    ap.add_argument("--account", required=True,
                    help="账号名，即 PlayerPrefs[UJHJKOikhS] 的值；"
                         "它决定桶里 string 槽的名字")
    ap.add_argument("--out", required=True, help="输出 .es3 路径")
    ap.add_argument("--template", default=DEFAULT_TEMPLATE,
                    help="14 段骨架模板（默认官方满级档 playerDate_03）")
    ap.add_argument("--base", default=None,
                    help="用来取 salt/iv/_Key 的真机原档；不给则自动在 "
                         "work/live 与 evidence/saves 里找")
    ap.add_argument("--set", action="append", default=[],
                    metavar="SEG.FIELD=VALUE",
                    help="改写模板里的值，可重复，例：13.ZuanShi=9999999")
    ap.add_argument("--reference", default=None,
                    help="字段补全用的参考档（游戏自己写过的档）；"
                         "不给则自动在 evidence/saves 里找")
    ap.add_argument("--no-merge", action="store_true",
                    help="不做字段补全，直接用模板原样（形状可能与真机档不一致）")
    ap.add_argument("--allow-random-outer", action="store_true",
                    help="找不到原档时允许随机 salt/iv（真机表现未验证）")
    ap.add_argument("--verify", action="store_true", help="写完自检")
    a = ap.parse_args(argv)

    if not os.path.exists(a.template):
        raise SystemExit("模板不存在: %s" % a.template)

    segs = load_template(a.template)

    if not a.no_merge:
        ref = load_reference(a.reference)
        if ref is None:
            print("[warn] 找不到参考档，模板形状可能缺字段（docs/22）",
                  file=sys.stderr)
        else:
            ref_segs, ref_path = ref
            added = merge_reference(segs, ref_segs)
            if added:
                print("[merge] 从 %s 补齐 %d 个字段: %s"
                      % (os.path.basename(ref_path), len(added),
                         ", ".join(added)))
            else:
                print("[merge] 模板字段已是参考档的超集，无需补全")

    apply_sets(segs, a.set)

    base = load_baseline(a.base)
    if base is None:
        if not a.allow_random_outer:
            raise SystemExit(
                "找不到可用的真机原档来取 salt/iv。\n"
                "  docs/19：换新的 salt/iv 会导致游戏黑屏。\n"
                "  请用 --base 指定一份原档，或显式加 --allow-random-outer。")
        salt, iv = os.urandom(16), os.urandom(16)
        kc = 2640
        base_path = None
        print("[warn] 使用随机 salt/iv，真机行为未验证", file=sys.stderr)
    else:
        salt, iv, kc, base_path = base
        print("[base] salt/iv/_Key 取自 %s" % base_path)

    blob = build(segs, a.account, salt, iv, kc)
    outdir = os.path.dirname(os.path.abspath(a.out))
    if outdir and not os.path.isdir(outdir):
        os.makedirs(outdir, exist_ok=True)
    with open(a.out, "wb") as f:
        f.write(blob)
    print("[out ] %s (%d 字节)" % (a.out, len(blob)))

    if a.verify:
        ok = verify(a.out, a.account)
        return 0 if ok else 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
