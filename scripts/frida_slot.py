import frida
import sys

JS = r"""
(function () {
    try {
        // 1) 用 /proc/self/maps 找到游戏进程里 libil2cpp.so 的映射
        var maps = '';
        try {
            var f = new File('/proc/self/maps', 'r');
            maps = f.read(); f.close();
        } catch (e) {
            send({tag: 'maps_err', err: e.message});
        }
        send({tag: 'maps_len', len: maps.length, has_il2cpp: maps.indexOf('libil2cpp') >= 0});

        var lines = maps.split('\n');
        var il2cpp = [];
        for (var i = 0; i < lines.length; i++) {
            if (lines[i].indexOf('libil2cpp') >= 0) il2cpp.push(lines[i]);
        }
        send({tag: 'il2cpp_lines', n: il2cpp.length, lines: il2cpp});

        // 2) 读静态字段槽 0x35e7408 对应的 .so 虚拟地址
        //    il2cpp 加载基址 = 第一个映射的 start - 文件偏移(vaddr 通常是 0)
        if (il2cpp.length > 0) {
            var first = il2cpp[0].split(/\s+/);
            var rng = first[0].split('-');
            var base = ptr(rng[0]);
            send({tag: 'base', base: base.toString()});
            var addr = base.add(0x35e7408);
            try {
                var v = addr.readPointer();
                send({tag: 'slot', addr: addr.toString(), ptr: v.toString()});
                // 3) 当作 Il2CppString 读：+0x10 = length(int32), +0x14 = chars(utf16)
                if (!v.isNull()) {
                    var len = v.add(0x10).readS32();
                    send({tag: 'strlen', len: len});
                    if (len > 0 && len < 512) {
                        var s = v.add(0x14).readUtf16String(len);
                        send({tag: 'password', value: s});
                    }
                    // 也试 +0x10 是 char 数时的原始字节
                    var raw = v.add(0x10).readByteArray(Math.min(64, len * 2 + 16));
                    send({tag: 'raw', hex: Array.from(new Uint8Array(raw)).map(function(b){return b.toString(16).padStart(2,'0')}).join('')});
                }
            } catch (e) {
                send({tag: 'slot_err', err: e.message});
            }
        }
    } catch (e) {
        send({tag: 'fatal', err: e.message, stack: e.stack});
    }
})();
"""


def on_message(msg, data):
    print(msg)


if __name__ == "__main__":
    pid = int(sys.argv[1])
    dev = frida.get_device_manager().add_remote_device("127.0.0.1:27042")
    sess = dev.attach(pid)
    script = sess.create_script(JS)
    script.on("message", on_message)
    script.load()
    import time

    time.sleep(3)
