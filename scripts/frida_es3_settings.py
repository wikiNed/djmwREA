"""极轻量 hook：在 ES3Writer.Create / ES3Reader.Create 处只记录 settings 指针与密码字段。

设计要点（针对之前 hook 导致游戏卡死的问题）：
  - onEnter 只做一次 args[0] 取值，绝不做循环 / 字符串解码
  - 把指针存到 this，在 onLeave 里再读（此时主线程已不在热路径）
  - 所有 send() 都做 try/catch，异常绝不影响游戏
  - 每个 hook 只挂一次，不加递归

RVA：
    ES3Writer.Create(ES3Settings) @ 0x174B720
    ES3Reader.Create(ES3Settings) @ 0x174BAFC  (字节边界可能偏 2，用 slot 方式兜底)

ES3Settings 字段（dump.cs:563867）：
    0x18 path                  0x20 encryptionType
    0x24 compressionType       0x28 encryptionPassword  <<< 目标
    0x30 directory             0x34 format
    0x38 prettyPrint           0x3C bufferSize
"""
import sys
import time

import frida

JS = r"""
(function () {
    var BASE = ptr("%BASE%");
    var out = [];

    function u16(p) {
        try {
            var len = p.add(0x10).readS32();
            if (len < 0 || len > 4096) return 'len=' + len;
            // 只取前 128 字符，避免大字符串拖慢
            var n = len < 128 ? len : 128;
            return p.add(0x14).readUtf16String(n);
        } catch (e) { return '<e>'; }
    }

    function snap(sp, tag) {
        try {
            var pw = sp.add(0x28).readPointer();
            var r = {
                tag: tag,
                sp: sp.toString(),
                enc: sp.add(0x20).readS32(),
                cmp: sp.add(0x24).readS32(),
                fmt: sp.add(0x34).readS32(),
                buf: sp.add(0x3C).readS32(),
                pwPtr: pw.toString(),
                pw: pw.isNull() ? null : u16(pw)
            };
            send(r);
        } catch (e) {
            send({ tag: tag, err: String(e) });
        }
    }

    var hooked = [];
    function hookAt(rva, name, off) {
        var addr = BASE.add(rva);
        if (off) addr = addr.add(off);
        try {
            Interceptor.attach(addr, {
                onEnter: function (args) { this.sp = args[0]; },
                onLeave: function (ret) {
                    if (this.sp && !this.sp.isNull()) snap(this.sp, name);
                }
            });
            hooked.push(name + '@' + addr);
        } catch (e) {
            hooked.push('FAIL ' + name + ': ' + e.message);
        }
    }

    hookAt(%W_RVA%, 'W');
    hookAt(%R_RVA%, 'R');

    send({ tag: 'install', hooked: hooked });
})();
"""


def main():
    gp = int(sys.argv[1])
    base = sys.argv[2]
    wrva = int(sys.argv[3], 16) if len(sys.argv) > 3 else 0x174B720
    rrva = int(sys.argv[4], 16) if len(sys.argv) > 4 else 0x174BAFC
    wait = int(sys.argv[5]) if len(sys.argv) > 5 else 300

    js = (JS.replace("%BASE%", "0x" + base.lstrip("0x"))
            .replace("%W_RVA%", hex(wrva))
            .replace("%R_RVA%", hex(rrva)))

    dev = frida.get_device_manager().add_remote_device("127.0.0.1:27042")
    sess = dev.attach(gp)
    sc = sess.create_script(js)
    sc.on("message", lambda m, d: print(m, flush=True))
    sc.load()
    print(f"[install] writer=0x{wrva:X} reader=0x{rrva:X}", flush=True)
    time.sleep(wait)


if __name__ == "__main__":
    main()
