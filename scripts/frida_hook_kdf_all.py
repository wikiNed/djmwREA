"""hook ES3 AES 全链路 —— 补齐所有 Rfc2898 重载与 Aes.Create。

dump.cs 中 Rfc2898DeriveBytes 的 4 个 ctor：
  0x27A8374  .ctor()  (无参)
  0x27A837C  .ctor(byte[] password, byte[] salt, int iterations, HashAlgorithmName)
  0x27A87E0  .ctor(string password, byte[] salt, int iterations)
  0x27A8874  .ctor(string password, byte[] salt, int iterations, HashAlgorithmName)
  slot 5     GetBytes(int cb)  @ 0x27A89D8
  slot 6     Reset()           @ 0x27A88D8

同时 hook Aes.Create() @ 0x27AE80C 与 set_Key/set_IV（SymmetricAlgorithm slot 12/10）。

ARM64 参数：
  ctor(byte[],byte[],int,HashAlgorithmName): x0=this x1=pwBytes x2=salt x3=iters x4=hashAlg
  ctor(string,byte[],int):                  x0=this x1=pwStr   x2=salt x3=iters
  ctor(string,byte[],int,HashAlgorithmName):x0=this x1=pwStr   x2=salt x3=iters x4=hashAlg
"""

import sys
import time

import frida

JS = r"""
(function () {
    var BASE = ptr("%BASE%");

    function arrhex(p, n) {
        try {
            if (p.isNull()) return null;
            var raw = p.readByteArray(n);
            var u8 = new Uint8Array(raw);
            var h = '';
            for (var i = 0; i < u8.length; i++) h += ('0' + u8[i].toString(16)).slice(-2);
            return h;
        } catch (e) { return '<err>'; }
    }
    function arr(p, max) {
        try {
            if (p.isNull()) return { n: -1, hex: null };
            var n = p.add(0x18).readS32();
            return { n: n, hex: arrhex(p.add(0x20), Math.min(n, max || 48)) };
        } catch (e) { return { n: -1, hex: '<err>' }; }
    }
    function rd(p) {
        try {
            if (p.isNull()) return null;
            var len = p.add(0x10).readS32();
            if (len < 0 || len > 1000000) return '<bad ' + len + '>';
            return p.add(0x14).readUtf16String(len);
        } catch (e) { return '<err>'; }
    }

    // 1) byte[] 密码版
    try {
        Interceptor.attach(BASE.add(0x27A837C), {
            onEnter: function (args) {
                var pw = arr(args[1], 48), salt = arr(args[2], 32);
                send({ tag: 'KDF_ctor_byte', pwLen: pw.n, pwHex: pw.hex,
                       iters: args[3].toInt32(), saltLen: salt.n, saltHex: salt.hex });
            }
        });
        send({ tag: 'ok', what: 'KDF_byte' });
    } catch (e) { send({ tag: 'fail', what: 'KDF_byte', err: e.message }); }

    // 2) string 密码版（无 hashAlg）
    try {
        Interceptor.attach(BASE.add(0x27A87E0), {
            onEnter: function (args) {
                var salt = arr(args[2], 32);
                send({ tag: 'KDF_ctor_str', password: rd(args[1]),
                       iters: args[3].toInt32(), saltLen: salt.n, saltHex: salt.hex });
            }
        });
        send({ tag: 'ok', what: 'KDF_str' });
    } catch (e) { send({ tag: 'fail', what: 'KDF_str', err: e.message }); }

    // 3) string 密码 + hashAlg
    try {
        Interceptor.attach(BASE.add(0x27A8874), {
            onEnter: function (args) {
                var salt = arr(args[2], 32);
                send({ tag: 'KDF_ctor_str_alg', password: rd(args[1]),
                       iters: args[3].toInt32(), saltLen: salt.n, saltHex: salt.hex });
            }
        });
        send({ tag: 'ok', what: 'KDF_str_alg' });
    } catch (e) { send({ tag: 'fail', what: 'KDF_str_alg', err: e.message }); }

    // 4) GetBytes
    try {
        Interceptor.attach(BASE.add(0x27A89D8), {
            onEnter: function (args) { this.cb = args[1].toInt32(); },
            onLeave: function (ret) {
                var o = arr(ret, 32);
                send({ tag: 'KDF_GetBytes', cb: this.cb, outLen: o.n, outHex: o.hex });
            }
        });
        send({ tag: 'ok', what: 'KDF_GetBytes' });
    } catch (e) { send({ tag: 'fail', what: 'KDF_GetBytes', err: e.message }); }

    // 5) Aes.Create
    try {
        Interceptor.attach(BASE.add(0x27AE80C), {
            onEnter: function () { send({ tag: 'Aes_Create' }); }
        });
        send({ tag: 'ok', what: 'Aes_Create' });
    } catch (e) { send({ tag: 'fail', what: 'Aes_Create', err: e.message }); }

    send({ tag: 'ready' });
})();
"""


def main():
    gp = int(sys.argv[1])
    base = sys.argv[2]
    wait = int(sys.argv[3]) if len(sys.argv) > 3 else 240
    js = JS.replace("%BASE%", "0x" + base.lstrip("0x"))
    dm = frida.get_device_manager()
    dev = dm.add_remote_device("127.0.0.1:27042")
    sess = dev.attach(gp)
    script = sess.create_script(js)
    script.on("message", lambda m, d: print(m, flush=True))
    script.load()
    print(f"KDF 全重载 hook 已装，等待 {wait} 秒...", flush=True)
    time.sleep(wait)


if __name__ == "__main__":
    main()
