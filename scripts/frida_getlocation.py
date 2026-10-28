"""hook ES3Settings.get_location —— 一切 ES3 读写的必经点，参数即 settings。

依据（0x1A72274 / 0x1A6FCE4 / 0x1A71DBC 三处均为 `bl #0x174460c`，且 x0 = settings）：
    0x1A72268  cbz  x19, ...           ; x19 = settings
    0x1A7226C  mov  x0, x19
    0x1A72270  mov  x1, xzr
    0x1A72274  bl   #0x174460c         ; ES3.Location get_location()

ES3Settings 字段（dump.cs:563867）：
    0x18 path / 0x20 encryptionType / 0x24 compressionType
    0x28 encryptionPassword  <<< 目标
    0x30 directory / 0x34 format / 0x38 prettyPrint / 0x3C bufferSize

ES3.Location 枚举里 4 = Cache（走 ES3File 缓存，不经 Writer.Create）。
"""
import sys
import time

import frida

JS = r"""
(function () {
    var BASE = ptr("%BASE%");
    var cnt = { loc: 0, save: 0 };
    var seen = {};

    function u16(p, maxLen) {
        try {
            var len = p.add(0x10).readS32();
            if (len < 0 || len > 65536) return 'len=' + len;
            var n = Math.min(len, maxLen || 200);
            return p.add(0x14).readUtf16String(n);
        } catch (e) { return '<e:' + e.message + '>'; }
    }

    // ES3Settings.get_location(ES3Settings* this, MethodInfo*) @ 0x174460c
    try {
        Interceptor.attach(BASE.add(0x174460C), {
            onEnter: function (args) { this.sp = args[0]; },
            onLeave: function (ret) {
                var sp = this.sp;
                if (!sp || sp.isNull()) return;
                var key = sp.toString();
                if (!seen[key]) {
                    seen[key] = 1;
                    var pw = null, pwPtr = sp.add(0x28).readPointer();
                    if (!pwPtr.isNull()) pw = u16(pwPtr, 200);
                    var pathPtr = sp.add(0x18).readPointer();
                    send({
                        tag: 'SETTINGS',
                        addr: key,
                        location: ret.toInt32(),
                        path: pathPtr.isNull() ? null : u16(pathPtr, 200),
                        encryptionType: sp.add(0x20).readS32(),
                        compressionType: sp.add(0x24).readS32(),
                        format: sp.add(0x34).readS32(),
                        bufferSize: sp.add(0x3C).readS32(),
                        pwPtr: pwPtr.toString(),
                        encryptionPassword: pw
                    });
                }
                cnt.loc++;
            }
        });
        send({ tag: 'ok', what: 'get_location' });
    } catch (e) { send({ tag: 'fail', what: 'get_location', err: e.message }); }

    // ES3.Save<int>(string key, int value, ES3Settings settings) @ 0x1A71D64
    try {
        Interceptor.attach(BASE.add(0x1A71D64), {
            onEnter: function (args) {
                cnt.save++;
                if (cnt.save <= 30) {
                    send({ tag: 'Save_int', key: u16(args[0], 120), value: args[1].toInt32() });
                }
            }
        });
        send({ tag: 'ok', what: 'Save_int' });
    } catch (e) { send({ tag: 'fail', what: 'Save_int', err: e.message }); }

    // ES3.Load<int>(string key, ES3Settings settings) @ 0x1A6F750
    try {
        Interceptor.attach(BASE.add(0x1A6F750), {
            onEnter: function (args) {
                this.key = u16(args[0], 120);
            },
            onLeave: function (ret) {
                send({ tag: 'Load_int', key: this.key, value: ret.toInt32() });
            }
        });
        send({ tag: 'ok', what: 'Load_int' });
    } catch (e) { send({ tag: 'fail', what: 'Load_int', err: e.message }); }

    setInterval(function () {
        send({ tag: 'tick', loc: cnt.loc, save: cnt.save, settings: Object.keys(seen).length });
    }, 5000);
})();
"""


def main():
    gp = int(sys.argv[1])
    base = sys.argv[2]
    wait = int(sys.argv[3]) if len(sys.argv) > 3 else 300
    js = JS.replace("%BASE%", "0x" + base.lstrip("0x"))
    dev = frida.get_device_manager().add_remote_device("127.0.0.1:27042")
    sess = dev.attach(gp)
    sc = sess.create_script(js)
    sc.on("message", lambda m, d: print(m, flush=True))
    sc.load()
    print("[install] get_location + Save_int + Load_int", flush=True)
    time.sleep(wait)


if __name__ == "__main__":
    main()
