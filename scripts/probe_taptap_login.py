"""D1: 探测 qingQiu_Tap.asp 与 qingQiu.asp 的行为差异。

docs/18 只测了 qingQiu.asp（自建账号），返回 `?`。
TapDengLuUI 走的是 qingQiu_Tap.asp —— 两者是不同的 URL，从未测过。
"""
import http.client
import socket
import time
import urllib.parse

HOSTS = ["www.hqgames2013.com", "game.hqgames2013.com"]
PATHS = ["/qingQiu_Tap.asp", "/qingQiu.asp", "/yanZhengMa.asp",
         "/yanZhengMa_Tap.asp", "/heiMingDan.asp", "/beiFen.asp"]


def post(host, path, fields, timeout=15, retries=3):
    body = urllib.parse.urlencode(fields)
    for attempt in range(retries):
        try:
            c = http.client.HTTPConnection(host, 80, timeout=timeout)
            c.request("POST", path, body,
                      {"Content-Type": "application/x-www-form-urlencoded",
                       "User-Agent": "UnityPlayer/2020.3.4f1c1"})
            r = c.getresponse()
            data = r.read()
            c.close()
            return r.status, data
        except (socket.timeout, TimeoutError, ConnectionError, OSError) as e:
            if attempt == retries - 1:
                return None, repr(e).encode()
            time.sleep(1.0)
    return None, b""


def main():
    print("=" * 70)
    print("D1: qingQiu_Tap.asp 探测")
    print("=" * 70)

    # 1) 先拿验证码
    print("\n[1] 验证码")
    for host in HOSTS:
        st, body = post(host, "/yanZhengMa.asp", {"a": "1"})
        print("  %-26s %-6s %r" % (host, st, body[:40]))

    st, code_raw = post("www.hqgames2013.com", "/yanZhengMa.asp", {"a": "1"})
    code = code_raw.decode("ascii", "replace").strip()
    print("  使用验证码: %r" % code)

    # 2) 逐个 qingQiuID 测试两个入口
    print("\n[2] qingQiuID 枚举 x 两个入口")
    print("  %-8s %-22s %-22s" % ("id", "qingQiu.asp", "qingQiu_Tap.asp"))
    print("  " + "-" * 54)
    fields_base = {"playerID": "test123@qq.com", "playerMiMa": "abc123456",
                   "yanZhengMa": code}
    for qid in ["0", "1", "2", "100", "111", "222", "333"]:
        row = []
        for path in ["/qingQiu.asp", "/qingQiu_Tap.asp"]:
            f = dict(fields_base)
            f["qingQiuID"] = qid
            st, body = post("www.hqgames2013.com", path, f)
            row.append("%s %r" % (st, body[:20]))
        print("  %-8s %-22s %-22s" % (qid, row[0], row[1]))

    # 3) GET 方式
    print("\n[3] GET 请求")
    for path in ["/qingQiu_Tap.asp", "/qingQiu.asp"]:
        try:
            c = http.client.HTTPConnection("www.hqgames2013.com", 80, timeout=15)
            c.request("GET", path)
            r = c.getresponse()
            d = r.read()
            c.close()
            print("  GET %-22s %-6s %r" % (path, r.status, d[:40]))
        except Exception as e:
            print("  GET %-22s ERR %s" % (path, e))

    # 4) TapTap 特有字段名探测（open_id / tapId 等）
    print("\n[4] TapTap 字段名探测（qingQiu_Tap.asp, qingQiuID=111）")
    for extra in [{}, {"open_id": "test_openid_123"},
                  {"tapId": "12345"}, {"openid": "test_openid_123"},
                  {"playerID": "o2D+pAPsvrXCo74JUkh9jw=="}]:
        f = {"qingQiuID": "111", "playerID": "test", "playerMiMa": "abc",
             "yanZhengMa": code}
        f.update(extra)
        st, body = post("www.hqgames2013.com", "/qingQiu_Tap.asp", f)
        print("  +%-32s %-6s %r" % (list(extra.keys()) or "(无)", st, body[:30]))


if __name__ == "__main__":
    main()
