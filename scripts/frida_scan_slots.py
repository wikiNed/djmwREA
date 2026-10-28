"""扫静态字段区，找出所有能读成合法 C# 字符串（含可打印 ASCII）的槽。

SaveManager..ctor 用了 [0x35e7000+0x408]，但读出来是指针数组。
先把 0x35e6000..0x35e8000 整片按 8 字节扫，试解 Il2CppString。
"""

import sys
import time

import frida

JS = r"""
(function () {
    var BASE = ptr("%BASE%");
    var START = BASE.add(0x35e6000);
    var N = 0x2000 / 8;
    var found = [];
    for (var i = 0; i < N; i++) {
        var slot = START.add(i * 8);
        var v;
        try { v = slot.readPointer(); } catch (e) { continue; }
        if (v.isNull()) continue;
        try {
            var len = v.add(0x10).readS32();
            if (len <= 0 || len > 128) continue;
            var s = v.add(0x14).readUtf16String(len);
            // 至少要有一半是可打印 ASCII
            var good = 0;
            for (var k = 0; k < s.length; k++) {
                var c = s.charCodeAt(k);
                if (c >= 0x20 && c < 0x7f) good++;
            }
            if (good >= Math.max(3, Math.floor(s.length * 0.6))) {
                found.push({off: (0x35e6000 + i * 8).toString(16), ptr: v.toString(), len: len, s: s});
            }
        } catch (e) { }
    }
    send({tag: 'scan_done', n: found.length});
    found.slice(0, 200).forEach(function (x) { send({tag: 'cand', off: x.off, ptr: x.ptr, len: x.len, s: x.s}); });
})();
"""


def main():
    gp = int(sys.argv[1])
    base = sys.argv[2]
    js = JS.replace("%BASE%", "0x" + base.lstrip("0x"))
    dm = frida.get_device_manager()
    try:
        dev = dm.add_remote_device("127.0.0.1:27042")
    except Exception:
        dev = dm.get_device_by_id("127.0.0.1:27042", 5000)
    sess = dev.attach(gp)
    script = sess.create_script(js)
    script.on("message", lambda m, d: print(m, flush=True))
    script.load()
    time.sleep(6)


if __name__ == "__main__":
    main()
