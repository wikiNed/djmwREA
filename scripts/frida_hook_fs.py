"""全量 hook 文件 IO（libc fopen/fopen64/fwrite/write/open/openat/open64 + Java 层）

Frida 17 API: Module.getGlobalExportByName
"""

import sys
import time

import frida

JS = r"""
(function () {
    function cstr(p) {
        try { return p.isNull() ? null : p.readCString(); } catch (e) { return null; }
    }
    function bt(ctx, n) {
        return Thread.backtrace(ctx, Backtracer.ACCURATE).map(function (a) {
            return a.toString();
        }).slice(0, 10);
    }
    function interesting(p) {
        if (!p) return false;
        var s = p.toLowerCase();
        return s.indexOf('savefile') >= 0 || s.indexOf('.es3') >= 0 ||
               s.indexOf('android/data/game.taptap') >= 0;
    }
    function hook(name, argIdx, tag) {
        var addr = null;
        try { addr = Module.getGlobalExportByName(name); } catch (e) { return; }
        if (!addr) return;
        try {
            Interceptor.attach(addr, {
                onEnter: function (args) {
                    var p = cstr(args[argIdx]);
                    if (interesting(p)) {
                        send({ tag: tag, path: p, bt: bt(this.context, 10) });
                    }
                }
            });
            send({ tag: 'hooked', what: name });
        } catch (e) {
            send({ tag: 'hookfail', what: name, err: e.message });
        }
    }

    hook('open', 0, 'open');
    hook('open64', 0, 'open64');
    hook('openat', 1, 'openat');
    hook('fopen', 0, 'fopen');
    hook('fopen64', 0, 'fopen64');
    hook('access', 0, 'access');
    hook('stat', 0, 'stat');
    hook('stat64', 0, 'stat64');
    hook('unlink', 0, 'unlink');
    hook('rename', 0, 'rename');

    // fwrite 只知道 FILE*，不好查路径；改为 hook write 只看大块
    var wr = null;
    try { wr = Module.getGlobalExportByName('write'); } catch (e) { wr = null; }
    if (wr) {
        Interceptor.attach(wr, {
            onEnter: function (args) {
                var len = args[2].toInt32();
                if (len > 50000) {
                    send({ tag: 'bigwrite', fd: args[0].toInt32(), len: len, bt: bt(this.context, 8) });
                }
            }
        });
        send({ tag: 'hooked', what: 'write(big)' });
    }

    send({ tag: 'ready' });
})();
"""


def main():
    gp = int(sys.argv[1])
    wait = int(sys.argv[2]) if len(sys.argv) > 2 else 240
    dm = frida.get_device_manager()
    dev = dm.add_remote_device("127.0.0.1:27042")
    sess = dev.attach(gp)
    script = sess.create_script(JS)
    script.on("message", lambda m, d: print(m, flush=True))
    script.load()
    print(f"full IO hook 已装，等待 {wait} 秒...", flush=True)
    time.sleep(wait)


if __name__ == "__main__":
    main()
