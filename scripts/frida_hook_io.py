"""hook 文件写入路径（Frida 17 API: Module.getGlobalExportByName）

定位谁在写 SaveFile.es3。只记录大块写（>1000 字节）与含 SaveFile 的 open。
"""

import sys
import time

import frida

JS = r"""
(function () {
    var BASE = ptr("%BASE%");

    function cstr(p) {
        try { return p.isNull() ? null : p.readCString(); } catch (e) { return null; }
    }

    function bt(ctx, n) {
        return Thread.backtrace(ctx, Backtracer.ACCURATE).map(function (a) {
            return a.toString();
        }).slice(0, n);
    }

    function isSave(p) {
        return !!p && (p.indexOf('SaveFile') >= 0 || p.indexOf('.es3') >= 0);
    }

    var targets = [
        { name: 'open',   arg: 0,  tag: 'open'   },
        { name: 'open64', arg: 0,  tag: 'open64' },
        { name: 'openat', arg: 1,  tag: 'openat' }
    ];
    targets.forEach(function (t) {
        var addr = null;
        try { addr = Module.getGlobalExportByName(t.name); } catch (e) { addr = null; }
        if (!addr) return;
        Interceptor.attach(addr, {
            onEnter: function (args) {
                var p = cstr(args[t.arg]);
                if (isSave(p)) {
                    send({ tag: t.tag, path: p, bt: bt(this.context, 14) });
                }
            }
        });
        send({ tag: 'attached', what: t.name });
    });

    var wr = null;
    try { wr = Module.getGlobalExportByName('write'); } catch (e) { wr = null; }
    if (wr) {
        Interceptor.attach(wr, {
            onEnter: function (args) {
                var len = args[2].toInt32();
                if (len > 2000) {
                    send({ tag: 'write', fd: args[0].toInt32(), len: len, bt: bt(this.context, 12) });
                }
            }
        });
        send({ tag: 'attached', what: 'write' });
    }

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
    print(f"IO hook 已装，等待 {wait} 秒...", flush=True)
    time.sleep(wait)


if __name__ == "__main__":
    main()
