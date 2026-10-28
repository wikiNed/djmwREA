"""用内存扫描现场求 libil2cpp 真实 base，然后 hook 三处：读档 / 存档 / ES3 入口。

base 求法：拿 get_location 中部的 16 字节指纹，scanSync 到命中后减去锚点 RVA。
（maps 不可信、Process.getModuleByName 找不到模块，见 base_finder_note.py）

hook 目标（RVA）：
    ES3Settings.get_location  0x174460C  -> 拿 settings，读 +0x28 密码
    ES3.Save<int>             0x1A71D64
    ShuJuDate.LoadGame        0x18A9374
    ShuJuDate.BaoCunDate      0x18A71B4
"""
import sys
import time

import frida

SO = r"E:\DSH\game\.rea-study\lib\libil2cpp.so"
ANCHOR_RVA = 0x174460C + 0x18


def anchor_pat(n=16):
    with open(SO, "rb") as f:
        f.seek(ANCHOR_RVA)
        return " ".join("%02x" % c for c in f.read(n))


JS = r"""
(function () {
    var PAT = "%PAT%";
    var ANCHOR = %ANCHOR%;
    var base = null;

    var ranges = Process.enumerateRanges('r--');
    for (var i = 0; i < ranges.length; i++) {
        var r = ranges[i];
        if (r.size < 8 * 1024 * 1024) continue;
        try {
            var ms = Memory.scanSync(r.base, r.size, PAT);
            if (ms.length) {
                base = ms[0].address.sub(ANCHOR);
                break;
            }
        } catch (e) { }
    }
    if (base === null) { send({ tag: 'err', msg: 'base not found' }); return; }
    send({ tag: 'base', base: base.toString() });

    function u16(p, maxLen) {
        try {
            var len = p.add(0x10).readS32();
            if (len < 0 || len > 65536) return '<len=' + len + '>';
            return p.add(0x14).readUtf16String(Math.min(len, maxLen || 120));
        } catch (e) { return '<e>'; }
    }

    function attach(name, rva, hooks) {
        try {
            Interceptor.attach(base.add(rva), hooks);
            send({ tag: 'ok', name: name, at: base.add(rva).toString() });
        } catch (e) { send({ tag: 'fail', name: name, err: e.message }); }
    }

    var seen = {};

    attach('get_location', 0x174460C, {
        onEnter: function (a) { this.sp = a[0]; },
        onLeave: function (r) {
            var sp = this.sp;
            if (!sp || sp.isNull()) return;
            var k = sp.toString();
            if (seen[k]) return;
            seen[k] = 1;
            var pwP = sp.add(0x28).readPointer();
            var paP = sp.add(0x18).readPointer();
            send({
                tag: 'SETTINGS', addr: k, location: r.toInt32(),
                path: paP.isNull() ? null : u16(paP, 200),
                encType: sp.add(0x20).readS32(),
                compType: sp.add(0x24).readS32(),
                fmt: sp.add(0x34).readS32(),
                pwPtr: pwP.toString(),
                password: pwP.isNull() ? null : u16(pwP, 200)
            });
        }
    });

    var nsave = 0;
    attach('ES3.Save_int', 0x1A71D64, {
        onEnter: function (a) {
            nsave++;
            if (nsave <= 40) send({ tag: 'Save_int', key: u16(a[0], 100), value: a[1].toInt32() });
        }
    });

    attach('LoadGame', 0x18A9374, {
        onEnter: function (a) { send({ tag: 'LoadGame', this: a[0].toString() }); },
        onLeave: function (r) { send({ tag: 'LoadGame_ret' }); }
    });

    attach('BaoCunDate', 0x18A71B4, {
        onEnter: function (a) { send({ tag: 'BaoCunDate', this: a[0].toString() }); }
    });

    setInterval(function () { send({ tag: 'tick', saves: nsave, settings: Object.keys(seen).length }); }, 8000);
})();
"""


def main():
    gp = int(sys.argv[1])
    wait = int(sys.argv[2]) if len(sys.argv) > 2 else 90
    js = JS.replace("%PAT%", anchor_pat()).replace("%ANCHOR%", hex(ANCHOR_RVA))
    dev = frida.get_device_manager().add_remote_device("127.0.0.1:27042")
    sess = dev.attach(gp)
    sc = sess.create_script(js)
    sc.on("message", lambda m, d: print(m, flush=True))
    sc.load()
    time.sleep(wait)


if __name__ == "__main__":
    main()
