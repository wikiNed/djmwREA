"""在 frida 侧验证"内存里的 ARM 指令 == 文件里的 ARM 指令"，并与 maps 里的 base 对照。

前几轮所有 hook 都零命中，而 Script.load() 又都成功，说明 attach 到了正确进程但
地址可能落在错误视图。这里不猜，直接做三件事：
  1. 打印 Process.enumerateRanges('r-x') 里所有含 libil2cpp 的段
  2. 在 maps 给的 base + RVA 处读 4 字节，比对文件里的期望字节
  3. 用 Memory.scan 在整个 r-x 里找该 4 字节序列（若是唯一即给出真实 base）
"""
import sys
import time

import frida

SO = r"E:\DSH\game\.rea-study\lib\libil2cpp.so"

# 目标：(方法名, RVA)
TARGETS = [
    ("AESEncryptionAlgorithm.Encrypt(Stream,Stream,string,int)", 0x1782D44),
    ("Rfc2898DeriveBytes..ctor(string,byte[],int)", 0x27A87E0),
    ("ShuJuDate.Init()", 0x18A7674),
    ("ShuJuDate.LoadGame()", 0x18A9374),
    ("ShuJuDate.BaoCunDate()", 0x18A71B4),
    ("ES3Settings.get_location()", 0x174460C),
    ("SaveManager..ctor()", 0x17A64D8),
]


def expected_bytes(rva, n=16):
    with open(SO, "rb") as f:
        f.seek(rva)
        return f.read(n)


def main():
    gp = int(sys.argv[1])
    wait = int(sys.argv[2]) if len(sys.argv) > 2 else 60
    dev = frida.get_device_manager().add_remote_device("127.0.0.1:27042")
    sess = dev.attach(gp)

    items = [{"name": n, "rva": r, "hex": expected_bytes(r).hex()} for n, r in TARGETS]

    js = r"""
    (function () {
        var items = ITEMS;
        var out = [];

        // 1) 列出所有 r-x 段（翻译层下可能是匿名段）
        var ranges = Process.enumerateRanges('r-x');
        send({ tag: 'ranges', n: ranges.length });
        var big = ranges.filter(function (r) { return r.size > 8 * 1024 * 1024; });
        send({ tag: 'big_ranges', list: big.slice(0, 20).map(function (r) {
            return { base: r.base.toString(), size: r.size };
        }) });

        // 2) 每个候选 base 上验证目标字节
        var candidates = big.map(function (r) { return r.base; });
        items.forEach(function (it) {
            var hits = [];
            candidates.forEach(function (b) {
                try {
                    var p = b.add(it.rva);
                    var pat = it.hex;
                    var arr = [];
                    for (var i = 0; i < pat.length; i += 2) arr.push(parseInt(pat.substr(i, 2), 16));
                    var got = '';
                    var bytes = p.readByteArray(arr.length);
                    var u8 = new Uint8Array(bytes);
                    for (var i = 0; i < u8.length; i++) got += (u8[i] < 16 ? '0' : '') + u8[i].toString(16);
                    if (got === pat) hits.push(b.toString());
                } catch (e) { }
            });
            out.push({ name: it.name, rva: it.rva, hits: hits });
        });
        send({ tag: 'verify', out: out });

        // 3) 用文件前 32 字节做全局 scan，确认代码确实存在
        var hdr = items[0].hex;
        try {
            var arr = [];
            for (var i = 0; i < hdr.length; i += 2) arr.push(parseInt(hdr.substr(i, 2), 16));
            var matches = Memory.scanSync(big[0].base, Math.min(big[0].size, 0x40000000),
                arr.map(function (x) { return ('0' + x.toString(16)).slice(-2); }).join(' '));
            send({ tag: 'scan_first_range', n: matches.length, first: matches.slice(0, 5).map(function (m) { return m.address.toString(); }) });
        } catch (e) { send({ tag: 'scan_err', err: e.message }); }
    })();
    """.replace("ITEMS", str(items).replace("'", '"'))

    sc = sess.create_script(js)
    sc.on("message", lambda m, d: print(m, flush=True))
    sc.load()
    time.sleep(5)


if __name__ == "__main__":
    main()
