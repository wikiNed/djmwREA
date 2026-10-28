"""hook libc open/openat 抓 SaveFile 的真实打开者，并打印返回的调用栈。

前几轮 hook 了 ES3/Encrypt/IO 全零命中，说明写盘者另有其人。这里直接蹲 libc
系统调用层，并且**不按路径过滤，只过滤含 .es3/SaveFile 的**，同时输出 backtrace
以便从 dump.cs 反查 C# 方法名。

frida 17 API 要点：Module.findExportByName 已移除，用 Module.getGlobalExportByName
或 Process.getModuleByName('libc.so').getExportByName(name)。
"""
import sys
import time

import frida

JS = r"""
(function () {
    var base = null;
    function mods() { return Process.enumerateModules(); }

    function find(name) {
        var m = null;
        try { m = Process.getModuleByName(name); } catch (e) { return null; }
        var e2 = null;
        try { e2 = m.getExportByName(name2(name)); } catch (e) { }
        return m;
    }

    function name2(n) { return n; }

    function hook(expName) {
        var addr = null;
        try {
            addr = Module.getGlobalExportByName(expName);
        } catch (e) {
            return null;
        }
        if (!addr) return null;
        var hit = { n: 0 };
        try {
            Interceptor.attach(addr, {
                onEnter: function (args) {
                    try {
                        var p = args[0];
                        if (p.isNull()) return;
                        var s = p.readCString();
                        if (!s) return;
                        if (s.indexOf('.es3') < 0 && s.indexOf('SaveFile') < 0) return;
                        hit.n++;
                        send({
                            tag: 'OPEN', fn: expName, path: s,
                            flags: expName === 'openat' ? args[2].toInt32() : args[1].toInt32(),
                            bt: Thread.backtrace(this.context, Backtracer.ACCURATE).slice(0, 12).map(function (a) { return a.toString(); }),
                            bt_fuzzy: Thread.backtrace(this.context, Backtracer.FUZZY).slice(0, 12).map(function (a) { return a.toString(); })
                        });
                    } catch (e) { }
                }
            });
            return expName;
        } catch (e) { return null; }
    }

    var hooked = [];
    ['open', 'openat', 'fopen', 'fopen64', 'open64'].forEach(function (n) {
        var r = hook(n);
        if (r) hooked.push(r);
    });
    send({ tag: 'install', hooked: hooked });

    // 找 libil2cpp 的 load base 供换算 RVA
    try {
        var il = Process.getModuleByName('libil2cpp.so');
        send({ tag: 'il2cpp', base: il.base.toString(), size: il.size.toString() });
    } catch (e) { send({ tag: 'il2cpp', err: e.message }); }
})();
"""


def main():
    gp = int(sys.argv[1])
    wait = int(sys.argv[2]) if len(sys.argv) > 2 else 120
    dev = frida.get_device_manager().add_remote_device("127.0.0.1:27042")
    sess = dev.attach(gp)
    sc = sess.create_script(JS)
    sc.on("message", lambda m, d: print(m, flush=True))
    sc.load()
    print("[install] open/openat/fopen hooks", flush=True)
    time.sleep(wait)


if __name__ == "__main__":
    main()
