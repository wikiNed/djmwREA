"""更全面的 ES3 hook：在 ES3Settings 构造时截获 encryptionPassword。

RVA：
  0x175226C  ES3Settings..ctor(string path?, EncryptionType, string password, ...) 之一
  0x17522A4  另一个重载
  0x1748DA8  ES3Settings.get_defaultSettings()

这里同时 hook：
  - AESEncryptionAlgorithm.Encrypt_stream 0x1782D44
  - AESEncryptionAlgorithm.Decrypt_stream 0x178329C
并在读到的 string 上尝试多种布局。
"""

import sys
import time

import frida

JS = r"""
(function () {
    var BASE = ptr("%BASE%");
    var TARGETS = [
        {name: 'Encrypt_stream', rva: 0x1782D44, passIdx: 3},
        {name: 'Decrypt_stream', rva: 0x178329C, passIdx: 3},
        {name: 'Encrypt_bytes',  rva: 0x17826EC, passIdx: 1},
        {name: 'Decrypt_bytes',  rva: 0x1782A18, passIdx: 1}
    ];

    function readIl2CppString(p) {
        var out = {ptr: p.toString()};
        try {
            if (p.isNull()) { out.nullptr = true; return out; }
            var len = p.add(0x10).readS32();
            out.len = len;
            if (len > 0 && len < 2048) {
                out.value = p.add(0x14).readUtf16String(len);
            }
            var raw = p.add(0x10).readByteArray(0x40);
            var u8 = new Uint8Array(raw);
            var hex = '';
            for (var i = 0; i < u8.length; i++) hex += ('0' + u8[i].toString(16)).slice(-2);
            out.raw_hex = hex;
        } catch (e) { out.err = e.message; }
        return out;
    }

    TARGETS.forEach(function (t) {
        var addr = BASE.add(t.rva);
        try {
            Interceptor.attach(addr, {
                onEnter: function (args) {
                    var msg = {tag: 'hit', fn: t.name, arg0: args[0].toString()};
                    msg.pass = readIl2CppString(args[t.passIdx]);
                    send(msg);
                }
            });
            send({tag: 'attached', fn: t.name, addr: addr.toString()});
        } catch (e) {
            send({tag: 'attach_err', fn: t.name, err: e.message});
        }
    });
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
    print(f"钩子已安装（4 个），等待 {wait} 秒...", flush=True)
    time.sleep(wait)


if __name__ == "__main__":
    main()
