#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""探测 v5.5.7 封号相关接口的服务器行为。

v557 metadata 里出现的全部 .asp 端点（0x036d46 = heiMingDan.asp）。

★ 核心结论（docs/25）：
    /heiMingDan.asp 是按 playerID 去重的「加入黑名单」接口，返回码：
        2 = 该 playerID 首次出现，插入成功
        1 = 已存在（已加黑）
       -1 = 缺参数
    qingQiuID 的取值完全不参与判断。

用法：
    python probe_ban_v557.py endpoints   # 全部端点存活探测（默认）
    python probe_ban_v557.py state       # 黑名单状态机验证（会写入！）
    python probe_ban_v557.py query <id>  # 查单个账号是否在名单里
"""
import random
import string
import sys
import urllib.parse
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = "http://www.hqgames2013.com"
UA = "UnityPlayer/2020.3.4f1 (UnityWebRequest/1.0, libcurl/7.64.0-DEV)"


def post(path, fields, timeout=15):
    body = urllib.parse.urlencode(fields).encode()
    req = urllib.request.Request(
        BASE + path, data=body,
        headers={"User-Agent": UA,
                 "Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()[:400]
    except Exception as e:
        return None, ("%s: %s" % (type(e).__name__, e)).encode()


def get(path, timeout=15):
    req = urllib.request.Request(BASE + path, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()[:400]
    except Exception as e:
        return None, ("%s: %s" % (type(e).__name__, e)).encode()


def rand_id():
    return "".join(random.choice(string.ascii_lowercase) for _ in range(10)) + "@probe.com"


def cmd_endpoints():
    print("=" * 70)
    print("端点存活探测")
    print("=" * 70)
    for p in ["/heiMingDan.asp", "/beiFen.asp", "/dateXinXi.asp", "/time.asp",
              "/postTest.asp", "/liBao_LQ.asp", "/xiaZai.asp", "/yanZhengMa.asp",
              "/PaiHangBang/ZhanDouLi/SetPaiHang_ZL.asp",
              "/PaiHangBang/ZuanShi/SetPaiHang.asp",
              "/XiTong/XT_GetGuangBoXinXi.asp"]:
        st, body = get(p)
        print("  %-46s -> %s %r" % (p, st, body[:60]))
    return 0


def cmd_state():
    print("=" * 70)
    print("黑名单状态机验证（★会写入 4 个随机账号）")
    print("=" * 70)
    for _ in range(4):
        p = rand_id()
        a = post("/heiMingDan.asp", {"qingQiuID": "1", "playerID": p})
        b = post("/heiMingDan.asp", {"qingQiuID": "1", "playerID": p})
        print("  %-30s 首次=%r 再次=%r" % (p, a[1], b[1]))
    print()
    print("预期：首次 '2'、再次 '1'。若两者相同说明接口语义变了。")
    return 0


def cmd_query(account):
    st, body = post("/heiMingDan.asp",
                    {"qingQiuID": "1", "playerID": account})
    code = body.decode("ascii", "replace").strip()
    meaning = {"1": "已在黑名单（已存在）",
               "2": "刚刚被加入黑名单（首次，★副作用！）",
               "-1": "参数不全"}.get(code, "未知")
    print("%s -> %s  (%s)" % (account, code, meaning))
    if code == "2":
        print("警告：这个查询把账号写进了黑名单。")
    return 0


def main(argv):
    cmd = argv[0] if argv else "endpoints"
    if cmd == "endpoints":
        return cmd_endpoints()
    if cmd == "state":
        return cmd_state()
    if cmd == "query":
        if len(argv) < 2:
            print("用法: probe_ban_v557.py query <账号>")
            return 1
        return cmd_query(argv[1])
    print("未知命令: %s" % cmd)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
