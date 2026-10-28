"""在运行时 hook AESEncryptionAlgorithm.Encrypt(Stream,Stream,string,int)，
截获 password 参数。

RVA 0x1782D44，load base = 0x070e4000（由 maps 第一段得出）。
ARM64 调用约定：x0=this, x1=input, x2=output, x3=password(string*), w4=bufferSize
Il2CppString 布局：+0x10 = length(int32), +0x14 = chars(utf16)
"""

import sys
import time

import frida

JS = r"""
(function () {
    var BASE = ptr("%BASE%");
    var fn = BASE.add(0x1782D44);
    send({tag: 'hook_target', addr: fn.toString()});

    try {
        Interceptor.attach(fn, {
            onEnter: function (args) {
                var s = args[3];
                var out = {tag: 'hit', password_ptr: s.toString()};
                try {
                    if (!s.isNull()) {
                        var len = s.add(0x10).readS32();
                        out.len = len;
                        if (len > 0 && len < 1024) {
                            out.value = s.add(0x14).readUtf16String(len);
                        }
                        var raw = s.add(0x10).readByteArray(0x40);
                        var u8 = new Uint8Array(raw);
                        var hex = '';
                        for (var i = 0; i < u8.length; i++) hex += ('0' + u8[i].toString(16)).slice(-2);
                        out.raw_hex = hex;
                    }
                } catch (e) { out.err = e.message; }
                send(out);
            }
        });
        send({tag: 'attached', ok: true});
    } catch (e) {
        send({tag: 'hook_err', err: e.message});
    }
})();
"""


def main():
    gp = int(sys.argv[1])
    base = sys.argv[2]
    wait = int(sys.argv[3]) if len(sys.argv) > 3 else 120
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
    print(f"钩子已安装，等待 {wait} 秒...", flush=True)
    time.sleep(wait)


if __name__ == "__main__":
    main()
