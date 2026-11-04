#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""hqgames2013.com 的本地 HTTP 桩服务。

用途：在宿主机上跑，配合模拟器 /system/etc/hosts 劫持，
让旧版 v5.5.7 (com.HQGAMES.TopDemons) 的联网点全部返回可控值。

关键端点与真实服务器返回值对照（2026-11-02 实测）：
    GET /TapDemonsWeb/PanDuan/ChongXinDengLu.txt  -> ""        (len 0)
    GET /TapDemonsWeb/PanDuan/NiCheng.txt         -> "0"
    GET /TapDemonsWeb/PanDuan/IsNeiGou.txt        -> "1"
    GET /TapDemonsWeb/PanDuan/IsADS.txt           -> "1"

用法:
    python work/stub_server.py                     # 默认账号 nw2026c@qq.com
    python work/stub_server.py --account X@qq.com  # 指定 PanDuan 回显的账号
    python work/stub_server.py --port 80

设计原则：
1. PanDuan/ChongXinDengLu.txt 必须原样返回 PlayerPrefs["UJHJKOikhS"] 的值，
   因为 PanDuanChongXinDengLu 的判据是
   String.op_Equality(服务器返回, ShuJuDate.get_PlayerZhangHao())。
2. heiMingDan.asp 返回 "-1"（协议里 -1 = 参数不全），避免被加入黑名单。
   实测 heiMingDan.asp 状态机：2=插入成功, 1=已存在, -1=参数不全。
3. 其余端点一律返回空串或 "0"，保证游戏不会因解析失败卡住。
"""
import argparse
import datetime
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

LOG = []

#: 请求日志同时写到这个文件（相对 cwd）。每次 main() 启动时清空。
LOGFILE = "work/stub_hits.log"

#: heiMingDan.asp 的保命返回值。任何与客户端封号常量相等的值都会
#: 触发 FengHaoUI 红屏 + QingDang 清档，所以用一个不可能出现的串。
KILL_SWITCH = "__REA_NO_BAN__"


def _now():
    return datetime.datetime.now().strftime("%H:%M:%S")


class Handler(BaseHTTPRequestHandler):
    #: 由 main() 设置
    account = ""
    enc_account = ""
    verbose = True

    def log_message(self, fmt, *args):  # noqa: N802 - 覆盖基类
        pass  # 自己打日志，格式更清楚

    def _send(self, body, code=200, ctype="text/plain; charset=utf-8"):
        if isinstance(body, str):
            body = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _handle(self, method):
        path = self.path.split("?", 1)[0]
        length = int(self.headers.get("Content-Length") or 0)
        post = self.rfile.read(length) if length else b""

        body, note = self.route(path, post)

        LOG.append((_now(), method, path, body, note))
        if self.verbose:
            disp = body if isinstance(body, str) else body.decode("utf-8", "replace")
            line = "[%s] %s %-52s -> %r  %s" % (_now(), method, path, disp, note)
            print(line, flush=True)
            # ★ 同时落盘，避免终端缓冲丢日志
            if LOGFILE:
                try:
                    with open(LOGFILE, "a", encoding="utf-8") as f:
                        f.write(line + "\n")
                except OSError:
                    pass
        self._send(body)

    def route(self, path, post):
        """返回 (响应体, 备注)。所有判定集中在这里。"""
        p = path.lower()

        # ---- PanDuan 三件套（决定能不能读存档）----
        # ★ 回显时要做与 PlayerPrefs 一致的 URL 编码：游戏登录成功后调用
        #   SetZhangHao 写 PlayerPrefs，里面 '@' 被存成 '%40'（实测
        #   `UJHJKOikhS = nw2026c%40qq.com`）。这里若原样返回 '@'，
        #   String.op_Equality 必然 false，游戏会走 OpenYongHuUI（创建角色）。
        if p.endswith("/panduan/chongxindenglu.txt"):
            return self.enc_account, "回显账号名（URL 编码）→ 让 op_Equality 通过"

        if p.endswith("/panduan/nicheng.txt"):
            return "0", "实测真值"

        if p.endswith("/panduan/isneigou.txt"):
            return "1", "实测真值"

        if p.endswith("/panduan/isads.txt"):
            return "1", "实测真值"

        # ---- 封号上报：返回 -1 表示参数不全 ----
        # ★★ 血泪教训（2026-11-02）：返回 "-1" 会导致封号！
        #   XianShiNiCheng.<HeiMingDan>d__16.MoveNext 的判据是
        #       String.op_Equality(dh.text, 常量)
        #   相等 → FengHaoUI.SetActive(true) + ShuJuDate.QingDang()
        #   "-1" 极可能就是那个「命中」常量，所以桩服务必须返回
        #   一个绝不匹配的哨兵值。真实服务器的 -1 是「参数不全」，
        #   但客户端把 -1 当成命中处理 —— 这是客户端逻辑与协议语义脱节。
        if p.endswith("/heimingdan.asp"):
            return KILL_SWITCH, "★ 保命值：绝不匹配封号常量"

        # ---- 云存档备份：失败即可，不影响本地读档 ----
        if p.endswith("/beifen.asp"):
            return "-1", "云备份失败（不影响本地）"

        if p.endswith("/beifen_mian.asp"):
            return "-1", "云备份失败"

        if p.endswith("/beifenhero.asp"):
            return "-1", "云备份失败"

        # ---- 排行榜：只写不读，成功即可 ----
        if "/paihangbang/" in p:
            return "1", "排行榜上报成功（服务端不会真的记）"

        # ---- 时间/杂项 ----
        # ★ time.asp 必须返回 Unix 秒（10 位）。实测真值 b'1793603448'。
        #   返回 13 位毫秒会让 TimeGetter.ZhuanHuanTime 里的
        #   DateTime.AddMilliseconds 抛 ArgumentOutOfRangeException 并卡死加载页。
        if p.endswith("/time.asp"):
            return str(int(datetime.datetime.now().timestamp())), "Unix 秒（10 位）"

        if p.endswith("/xt_getguangboxinxi.asp"):
            return "-1#", "空广播（末尾 # 保证 Split('#') ≥2 段）"

        if p.endswith("/datexinxi.asp"):
            return "-1#", "空公告（末尾 # 保证 Split('#') ≥2 段）"

        if p.endswith("/posttest.asp"):
            return "#and", "实测真值"

        if p.endswith("/xiaziao.asp") or p.endswith("/xiazai.asp"):
            return "-1#", "无下载"

        if p.endswith("/qingqiu.asp") or p.endswith("/qingqiu_tap.asp"):
            return "111", "★ 登录成功（实测 qingQiuID=100 时服务器返回此值）"

        if p.endswith("/yanzhengma.asp"):
            return "000000", "图形验证码（固定值）"

        if p.endswith("/libao_lq.asp"):
            return "-1#", "礼包领取失败"

        if path == "/" or p in ("/index.htm", "/index.html"):
            return "ok", "根路径"

        # ★ 未知路径不能回空串：ChuangJianPlayer.GetGengXin 会
        #   String.Split(text,'#') 后无条件取 [0] 和 [1]，1 段就
        #   IndexOutOfRangeException。回 "#" 让结果变成 ["",""]，恒安全。
        return "#", "未知路径 → 两段空值（防 Split 越界）"

    def do_GET(self):  # noqa: N802
        self._handle("GET")

    def do_POST(self):  # noqa: N802
        self._handle("POST")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--account", default="nw2026c@qq.com",
                    help="ChongXinDengLu.txt 要回显的账号名"
                         "（必须与 PlayerPrefs[UJHJKOikhS] 一致）")
    ap.add_argument("--port", type=int, default=80)
    ap.add_argument("--raw-account", action="store_true",
                    help="回显时不做 URL 编码（@ 保持 @），用于测 GetString 是否解码")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()

    Handler.account = a.account
    # 默认做 URL 编码（@ → %40），与 PlayerPrefs XML 里的字面量一致；
    # 加 --raw-account 则原样返回，用于测「Unity GetString 是否自动解码」。
    Handler.enc_account = a.account if a.raw_account else urllib.parse.quote(
        a.account, safe="")
    Handler.verbose = not a.quiet

    srv = ThreadingHTTPServer((a.host, a.port), Handler)
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print("=" * 68)
    print("hqgames2013 桩服务已启动")
    print("  监听    : %s:%d" % (a.host, a.port))
    print("  PanDuan : ChongXinDengLu.txt -> %r  (编码前 %r)"
          % (Handler.enc_account, a.account))
    print("  封号    : heiMingDan.asp     -> '-1' （不写入）")
    print()
    print("模拟器侧需要（su 0）：")
    print("  echo '10.0.2.2 game.hqgames2013.com' >> /system/etc/hosts")
    print("  echo '10.0.2.2 www.hqgames2013.com'  >> /system/etc/hosts")
    print("=" * 68)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。共处理 %d 个请求。" % len(LOG))


if __name__ == "__main__":
    main()
