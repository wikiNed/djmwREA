"""直接在游戏进程里读 ES3Settings.encryptionPassword 的静态字段槽。

基址推导（由 /proc/<pid>/maps 得到）：
  第一段 libil2cpp.so: 070e4000-08517000  offset 00000000
  → load base = 0x070e4000
  静态字段槽 RVA = 0x35e7408（SaveManager..ctor 里 [0x35e7000+0x408]）
  → 运行时地址 = 0x070e4000 + 0x35e7408
"""

import sys
import time

import frida

JS = r"""
(function () {
    var BASE = ptr("%BASE%");
    var SLOT = BASE.add(0x35e7408);
    send({tag: 'addr', slot: SLOT.toString()});
    send({tag: 'maps_hint', base: BASE.toString()});
    try {
        var v = SLOT.readPointer();
        send({tag: 'slot_ptr', value: v.toString()});
        if (!v.isNull()) {
            try {
                var len = v.add(0x10).readS32();
                send({tag: 'len', value: len});
                var raw = v.add(0x10).readByteArray(0x30);
                var hex = '';
                var u8 = new Uint8Array(raw);
                for (var i = 0; i < u8.length; i++) hex += ('0' + u8[i].toString(16)).slice(-2);
                send({tag: 'raw_hex', value: hex});
                if (len > 0 && len < 400) {
                    send({tag: 'utf16', value: v.add(0x14).readUtf16String(len)});
                }
            } catch (e2) { send({tag: 'str_err', err: e2.message}); }
        }
    } catch (e) {
        send({tag: 'read_err', err: e.message});
    }
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
    script.on("message", lambda m, d: print(m))
    script.load()
    time.sleep(3)


if __name__ == "__main__":
    main()
