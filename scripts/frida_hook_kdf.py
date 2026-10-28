"""hook Rfc2898DeriveBytes..ctor(string, byte[], int) 与 GetBytes(int)。

RVA 0x27a87e0 —— ES3 加密/解密都走这里，参数即明文口令与 salt。
ARM64: x0=this, x1=password(string*), x2=salt(byte[]), w3=iterations
然后 hook 同一个类的 GetBytes(int): x0=this, w1=count
"""

import sys
import time

import frida

JS = r"""
(function () {
    var BASE = ptr("%BASE%");

    function ilstr(p) {
        try {
            if (p.isNull()) return null;
            var len = p.add(0x10).readS32();
            if (len < 0 || len > 512) return null;
            return p.add(0x14).readUtf16String(len);
        } catch (e) { return '<err ' + e.message + '>'; }
    }
    function hexOf(p, n) {
        try {
            var raw = p.readByteArray(n);
            var u8 = new Uint8Array(raw);
            var h = '';
            for (var i = 0; i < u8.length; i++) h += ('0' + u8[i].toString(16)).slice(-2);
            return h;
        } catch (e) { return '<err ' + e.message + '>'; }
    }
    function arrLen(p) {
        try { return p.add(0x18).readS32(); } catch (e) { return -1; }
    }

    var kdfCtor = BASE.add(0x27a87e0);
    send({tag: 'target', ctor: kdfCtor.toString()});

    // 用原函数地址做 Memory 读取：Il2CppArray 布局 +0x18 = max_length, +0x20 = data
    Interceptor.attach(kdfCtor, {
        onEnter: function (args) {
            var msg = {tag: 'kdf_ctor', this_: args[0].toString()};
            msg.password = ilstr(args[1]);
            msg.iterations = args[3].toInt32();
            var salt = args[2];
            msg.salt_ptr = salt.toString();
            if (!salt.isNull()) {
                msg.salt_len = arrLen(salt);
                msg.salt_hex = hexOf(salt.add(0x20), Math.min(32, Math.max(0, arrLen(salt))));
            }
            send(msg);
        }
    });
    send({tag: 'attached_kdf'});

    // ES3 的 Aes.Create 之后会 set_Key，直接 hook 加密函数再读 key 更稳，
    // 但 key 是派生结果，这里改为 hook GetBytes：ES3 里它在 Rfc2898 实例上被调用
    // 通过扫 its vtable 的方式太麻烦，改 hook AES.set_Key? 先只抓 ctor 的 password。
})();
"""


def main():
    gp = int(sys.argv[1])
    base = sys.argv[2]
    wait = int(sys.argv[3]) if len(sys.argv) > 3 else 300
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
    print(f"KDF hook 已装，等待 {wait} 秒...", flush=True)
    time.sleep(wait)


if __name__ == "__main__":
    main()
