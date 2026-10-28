"""hook ES3 AES 全链路（4 个 Encrypt/Decrypt 重载 + KDF + Aes.Create）

dump.cs 里的 RVA：
  AESEncryptionAlgorithm.Encrypt(Stream,Stream,string,int) 0x1782D44  (slot 6)
  AESEncryptionAlgorithm.Decrypt(Stream,Stream,string,int) 0x178329C  (slot 7)
  AESEncryptionAlgorithm.Encrypt(byte[],string,int)        0x17826EC
  AESEncryptionAlgorithm.Decrypt(byte[],string,int)        0x1782A18
  CopyStream(Stream,Stream,int)                            0x1782604
  Rfc2898DeriveBytes..ctor(string,byte[],int)              0x27A87E0
  Rfc2898DeriveBytes.GetBytes(int)                         0x27A89D8
  Aes.Create()                                             0x27AE80C
  CryptoStream..ctor(Stream,ICryptoTransform,CryptoStreamMode) 0x27A9300

参数（ARM64）：
  Encrypt(byte[] input, string password, int bufferSize): x0=this, x1=inputBytes, x2=password, x3=bufferSize
  Encrypt(Stream in, Stream out, string password, int bs): x0=this, x1=in, x2=out, x3=password, x4=bs
  KDF..ctor(password, salt, iterations): x0=this, x1=password, x2=salt, x3=iters
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
            if (len < 0 || len > 1000000) return '<bad len ' + len + '>';
            return p.add(0x14).readUtf16String(len);
        } catch (e) { return '<err ' + e.message + '>'; }
    }
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
    function at(arrp) {
        // Il2CppArray: +0x18 = max_length, +0x20 = data
        try {
            var n = arrp.add(0x18).readS32();
            return { n: n, hex: arrhex(arrp.add(0x20), Math.min(n, 64)) };
        } catch (e) { return { n: -1, hex: '<err>' }; }
    }
    function hook(rva, name, fn) {
        try {
            var a = BASE.add(rva);
            Interceptor.attach(a, fn);
            send({ tag: 'hooked', what: name, at: a.toString() });
        } catch (e) {
            send({ tag: 'hookfail', what: name, err: e.message });
        }
    }

    // byte[] 版本
    hook(0x17826EC, 'Encrypt_bytes', {
        onEnter: function (args) {
            var b = at(args[1]);
            send({ tag: 'Encrypt_bytes', password: rd(args[2]), inLen: b.n, inHead: b.hex,
                   bs: args[3].toInt32() });
        }
    });
    hook(0x1782A18, 'Decrypt_bytes', {
        onEnter: function (args) {
            var b = at(args[1]);
            send({ tag: 'Decrypt_bytes', password: rd(args[2]), inLen: b.n, inHead: b.hex,
                   bs: args[3].toInt32() });
        }
    });

    // Stream 版本
    hook(0x1782D44, 'Encrypt_stream', {
        onEnter: function (args) {
            send({ tag: 'Encrypt_stream', password: rd(args[3]), bs: args[4].toInt32(),
                   inS: args[1].toString(), outS: args[2].toString() });
        }
    });
    hook(0x178329C, 'Decrypt_stream', {
        onEnter: function (args) {
            send({ tag: 'Decrypt_stream', password: rd(args[3]), bs: args[4].toInt32(),
                   inS: args[1].toString(), outS: args[2].toString() });
        }
    });

    // KDF
    hook(0x27A87E0, 'KDF_ctor', {
        onEnter: function (args) {
            var s = at(args[2]);
            send({ tag: 'KDF_ctor', password: rd(args[1]), iters: args[3].toInt32(),
                   saltLen: s.n, saltHex: s.hex });
        }
    });
    hook(0x27A89D8, 'KDF_GetBytes', {
        onEnter: function (args) {
            this.self = args[0];
            this.cb = args[1].toInt32();
        },
        onLeave: function (ret) {
            var r = at(ret);
            send({ tag: 'KDF_GetBytes', cb: this.cb, outLen: r.n, outHex: r.hex });
        }
    });

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
    print(f"AES 全链路 hook 已装，等待 {wait} 秒...", flush=True)
    time.sleep(wait)


if __name__ == "__main__":
    main()
