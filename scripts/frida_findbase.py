"""全局扫描内存，定位 libil2cpp.so 的真实加载基址。

前几轮失败的根因怀疑是 base 算错：maps 里 0x7354000 是 file-off 0 的段，
但读到的字节与文件不符（文件 MD5 与设备一致，排除"文件被改"）。
这里不猜 base，而是拿文件里两段唯一字节直接在进程内存里 scan。

选锚点原则：取函数中部、字节熵高的 16 字节，降低偶然命中概率。
"""
import sys
import time

import frida

SO = r"E:\DSH\game\.rea-study\lib\libil2cpp.so"

# (标签, RVA, 取样偏移) —— 取样偏移避开函数序言（序言在多个函数间高度相似）
ANCHORS = [
    ("AESEncrypt_mid", 0x1782D44, 0x60),
    ("KDF_ctor_mid", 0x27A87E0, 0x40),
    ("ShuJuDate_Init_mid", 0x18A7674, 0x180),
    ("LoadGame_mid", 0x18A9374, 0x30),
    ("BaoCunDate_mid", 0x18A71B4, 0x28),
    ("get_location_mid", 0x174460C, 0x18),
]


def sample(rva, off, n=16):
    with open(SO, "rb") as f:
        f.seek(rva + off)
        return f.read(n)


def main():
    gp = int(sys.argv[1])
    anchors = []
    for tag, rva, off in ANCHORS:
        b = sample(rva, off)
        anchors.append({"tag": tag, "rva": rva, "off": off, "hex": b.hex(),
                        "pat": " ".join("%02x" % c for c in b)})

    js = r"""
    (function () {
        var anchors = ANCHORS;
        var ranges = Process.enumerateRanges('r--').concat(Process.enumerateRanges('rw-'));
        var big = ranges.filter(function (r) { return r.size >= 8 * 1024 * 1024; });
        send({ tag: 'scan_ranges', n: big.length, list: big.map(function (r) {
            return { base: r.base.toString(), size: r.size };
        }) });

        anchors.forEach(function (a) {
            var found = [];
            for (var i = 0; i < big.length; i++) {
                var r = big[i];
                try {
                    var ms = Memory.scanSync(r.base, r.size, a.pat);
                    ms.slice(0, 3).forEach(function (m) {
                        found.push({ where: r.base.toString(), at: m.address.toString() });
                    });
                } catch (e) { }
                if (found.length) break;
            }
            send({ tag: 'anchor', name: a.tag, rva: a.rva, off: a.off, found: found });
        });
    })();
    """
    js = js.replace("ANCHORS", str(anchors).replace("'", '"'))

    dev = frida.get_device_manager().add_remote_device("127.0.0.1:27042")
    sess = dev.attach(gp)
    sc = sess.create_script(js)
    sc.on("message", lambda m, d: print(m, flush=True))
    sc.load()
    time.sleep(60)


if __name__ == "__main__":
    main()
