"""hook SaveFile 写入的实际字节流（libc write）并抓取调用时的缓冲区。

之前发现写文件走 unlink + rename，说明写经历了
  SaveFile.es3.tmp  ->  rename ->  SaveFile.es3
所以只要在 write 前截获缓冲区即可。

但 write 的 fd 无法直接反向映射到路径。更稳的做法：
 1. hook open/openat 记录 fd -> path 映射
 2. hook write 用 fd 查 path
 3. 若 path 含 SaveFile，dump 缓冲区前 64 字节与总长度
"""

import sys
import time

import frida

JS = r"""
(function () {
    function cstr(p) {
        try { return p.isNull() ? null : p.readCString(); } catch (e) { return null; }
    }
    var fdmap = {};

    ['open', 'open64', 'openat'].forEach(function (nm) {
        var a = null;
        try { a = Module.getGlobalExportByName(nm); } catch (e) { return; }
        if (!a) return;
        var idx = (nm === 'openat') ? 1 : 0;
        Interceptor.attach(a, {
            onEnter: function (args) { this.p = cstr(args[idx]); },
            onLeave: function (ret) {
                var fd = ret.toInt32();
                if (fd >= 0 && this.p) fdmap[fd] = this.p;
            }
        });
    });

    var wr = Module.getGlobalExportByName('write');
    Interceptor.attach(wr, {
        onEnter: function (args) {
            var fd = args[0].toInt32();
            var len = args[2].toInt32();
            var p = fdmap[fd];
            if (p && p.indexOf('SaveFile') >= 0) {
                var n = Math.min(len, 64);
                var hex = '';
                try {
                    var raw = args[1].readByteArray(n);
                    var u8 = new Uint8Array(raw);
                    for (var i = 0; i < u8.length; i++) hex += ('0' + u8[i].toString(16)).slice(-2);
                } catch (e) { hex = '<err>'; }
                send({ tag: 'SAVE_WRITE', path: p, fd: fd, len: len, hex: hex });
            }
        }
    });

    // 也 hook pwrite
    var pw = null;
    try { pw = Module.getGlobalExportByName('pwrite'); } catch (e) { pw = null; }
    if (pw) {
        Interceptor.attach(pw, {
            onEnter: function (args) {
                var fd = args[0].toInt32();
                var p = fdmap[fd];
                if (p && p.indexOf('SaveFile') >= 0) {
                    send({ tag: 'SAVE_PWRITE', path: p, fd: fd, len: args[2].toInt32() });
                }
            }
        });
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
    print(f"write-hook 已装，等待 {wait} 秒...", flush=True)
    time.sleep(wait)


if __name__ == "__main__":
    main()
