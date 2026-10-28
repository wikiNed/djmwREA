"""在游戏进程内存里搜索明文存档特征（分片扫描，避免超时）。

只扫匿名 rw- 堆区，按 32MB 分块 yield，记录命中地址。
"""

import sys
import time

import frida

JS = r"""
(function () {
    var NEEDLES_ASCII = ['DateID', 'HerosDates', 'SuoYouBaoShiTongJi', 'BaoShiSuiPian', 'LiBaoIDs'];
    var NEEDLES_U16   = NEEDLES_ASCII.map(function (s) {
        var h = '';
        for (var i = 0; i < s.length; i++) {
            var c = s.charCodeAt(i);
            h += ('0' + (c & 0xff).toString(16)).slice(-2) + ('0' + ((c >> 8) & 0xff).toString(16)).slice(-2);
        }
        return h;
    });
    var NEEDLES_HEX = NEEDLES_ASCII.map(function (s) {
        var h = '';
        for (var i = 0; i < s.length; i++) h += ('0' + s.charCodeAt(i).toString(16)).slice(-2);
        return h;
    });

    var hits = [];
    var scanned = 0;

    Process.enumerateRanges('rw-').forEach(function (r) {
        if (r.file) return;                   // 只看匿名堆
        if (r.size > 512 * 1024 * 1024) return;
        var CHUNK = 16 * 1024 * 1024;
        for (var off = 0; off < r.size; off += CHUNK) {
            var sz = Math.min(CHUNK, r.size - off);
            var base = r.base.add(off);
            for (var k = 0; k < NEEDLES_HEX.length; k++) {
                try {
                    var res = Memory.scanSync(base, sz, NEEDLES_HEX[k]);
                    res.forEach(function (x) {
                        if (hits.length < 40) {
                            hits.push({ addr: x.address.toString(), pat: NEEDLES_ASCII[k], enc: 'ascii' });
                        }
                    });
                } catch (e) {}
                try {
                    var res2 = Memory.scanSync(base, sz, NEEDLES_U16[k]);
                    res2.forEach(function (x) {
                        if (hits.length < 40) {
                            hits.push({ addr: x.address.toString(), pat: NEEDLES_ASCII[k], enc: 'u16' });
                        }
                    });
                } catch (e) {}
            }
            scanned += sz;
        }
    });

    send({ tag: 'done', scanned: scanned, hits: hits });
})();
"""


def main():
    gp = int(sys.argv[1])
    dm = frida.get_device_manager()
    dev = dm.add_remote_device("127.0.0.1:27042")
    sess = dev.attach(gp)
    script = sess.create_script(JS)
    done = []
    script.on("message", lambda m, d: (print(m, flush=True), done.append(1)))
    script.load()
    for _ in range(180):
        if done:
            break
        time.sleep(1)


if __name__ == "__main__":
    main()
