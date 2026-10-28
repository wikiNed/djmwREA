"""hook ShuJuDate.Encrypt(string SourceText, string key) @ RVA 0x18A8A68

ARM64 参数：x0=this, x1=SourceText(明文), x2=key
同时 hook DesDecrypt(string, string sKey) @ 0x18A95B4 看读取路径。
"""

import sys
import time

import frida

JS = r"""
(function () {
    var BASE = ptr("%BASE%");

    function rd(p) {
        try {
            if (p.isNull()) return null;
            var len = p.add(0x10).readS32();
            if (len < 0 || len > 200000) return '<bad len ' + len + '>';
            return p.add(0x14).readUtf16String(len);
        } catch (e) { return '<err ' + e.message + '>'; }
    }

    var enc = BASE.add(0x18A8A68);
    send({tag: 'target', encrypt: enc.toString()});

    Interceptor.attach(enc, {
        onEnter: function (args) {
            var src = rd(args[1]);
            var key = rd(args[2]);
            send({
                tag: 'Encrypt',
                key: key,
                srcLen: src ? src.length : -1,
                srcHead: src ? src.substring(0, 300) : null,
                srcTail: src ? src.substring(Math.max(0, src.length - 120)) : null
            });
        }
    });
    send({tag: 'attached_encrypt'});

    var dec = BASE.add(0x18A95B4);
    Interceptor.attach(dec, {
        onEnter: function (args) {
            var src = rd(args[1]);
            var key = rd(args[2]);
            send({
                tag: 'DesDecrypt',
                key: key,
                srcLen: src ? src.length : -1,
                srcHead: src ? src.substring(0, 120) : null
            });
        }
    });
    send({tag: 'attached_desdecrypt'});
})();
"""


def main():
    gp = int(sys.argv[1])
    base = sys.argv[2]
    wait = int(sys.argv[3]) if len(sys.argv) > 3 else 300
    js = JS.replace("%BASE%", "0x" + base.lstrip("0x"))
    dm = frida.get_device_manager()
    dev = dm.add_remote_device("127.0.0.1:27042")
    sess = dev.attach(gp)
    script = sess.create_script(js)
    script.on("message", lambda m, d: print(m, flush=True))
    script.load()
    print(f"Encrypt hook 已装，等待 {wait} 秒...", flush=True)
    time.sleep(wait)


if __name__ == "__main__":
    main()
