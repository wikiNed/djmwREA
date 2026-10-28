"""hook BaoCunDate 与 SaveGame，读 this+0x40 (gameDateStr = DES hex)

ShuJuDate 字段布局（dump.cs:262692）：
  private GameDate gameDate;      // 0x38
  private string   gameDateStr;   // 0x40   ← DES 加密后的 hex 字符串
  private bool     IsZuDang;      // 0x20
  private string   playerZhangHao;// 0x28
  private string   playerMiMa;    // 0x30
  private const float ziDongSaveTime = 180;

RVA:
  SaveGame()   0x18A7034   末尾调用 BaoCunDate
  BaoCunDate() 0x18A71B4   内部 0x18A75D4 调 Encrypt, 结果存 [x19+0x40]
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
            if (len < 0 || len > 5000000) return '<bad len ' + len + '>';
            return p.add(0x14).readUtf16String(len);
        } catch (e) { return '<err ' + e.message + '>'; }
    }

    // BaoCunDate 返回后读 this+0x40
    var bac = BASE.add(0x18A71B4);
    Interceptor.attach(bac, {
        onEnter: function (args) { this.self = args[0]; },
        onLeave: function (ret) {
            var s = null;
            try {
                var p = this.self.add(0x40).readPointer();
                s = rd(p);
            } catch (e) { s = '<err ' + e.message + '>'; }
            send({
                tag: 'BaoCunDate_done',
                self: this.self.toString(),
                strLen: (s && typeof s === 'string') ? s.length : -1,
                head: (s && typeof s === 'string') ? s.substring(0, 300) : null,
                tail: (s && typeof s === 'string') ? s.substring(Math.max(0, s.length - 120)) : null
            });
        }
    });
    send({ tag: 'hooked', what: 'BaoCunDate' });

    // 同时抓 Encrypt 返回（ret 在 0x18A8CE8）
    var encRet = BASE.add(0x18A8CE4);
    Interceptor.attach(encRet, {
        onEnter: function () {
            var s = rd(this.context.x0);
            if (s && typeof s === 'string' && s.length > 4) {
                send({ tag: 'Encrypt_ret', len: s.length, head: s.substring(0, 200) });
            }
        }
    });
    send({ tag: 'hooked', what: 'Encrypt_ret' });

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
    print(f"BaoCunDate hook 已装，等待 {wait} 秒...", flush=True)
    time.sleep(wait)


if __name__ == "__main__":
    main()
