"""用 maps 里真实的 ELF 头段（file offset 0）作为 base，验证 ARM 代码字节是否可读。

结论预告（上一轮已推断）：libil2cpp.so 在 MuMu 的 ARM 翻译层下被拆成多段，
真正含 0x1782D44 的段是 `r--p`（只读不可执行），说明翻译层把 ARM 代码当"数据"读。
本脚本只做只读校验，不 hook、不写内存，因此不会崩进程。
"""
import sys
import time

import frida

SO = r"E:\DSH\game\.rea-study\lib\libil2cpp.so"

# maps 实测：libil2cpp.so 首个段（file off 0）在 0x07354000
BASES = [0x07354000, 0x0878a000, 0x08b1c000, 0x07300000]

TARGETS = [
    ("AESEncryptionAlgorithm.Encrypt", 0x1782D44),
    ("Rfc2898DeriveBytes..ctor", 0x27A87E0),
    ("ShuJuDate.Init", 0x18A7674),
    ("ShuJuDate.LoadGame", 0x18A9374),
    ("ShuJuDate.BaoCunDate", 0x18A71B4),
    ("ES3Settings.get_location", 0x174460C),
    ("SaveManager..ctor", 0x17A64D8),
    ("ShuJuDate.Encrypt", 0x18A8A68),
]


def read_file(rva, n=16):
    with open(SO, "rb") as f:
        f.seek(rva)
        return f.read(n)


def main():
    gp = int(sys.argv[1])
    items = [{"name": n, "rva": r, "hex": read_file(r).hex()} for n, r in TARGETS]
    bases = ["0x%x" % b for b in BASES]

    js = r"""
    (function () {
        var items = ITEMS, bases = BASES;
        var res = [];
        items.forEach(function (it) {
            var line = { name: it.name, rva: it.rva, hits: [], reads: [] };
            bases.forEach(function (bs) {
                var b = ptr(bs);
                try {
                    var want = it.hex;
                    var n = want.length / 2;
                    var bytes = new Uint8Array(b.add(it.rva).readByteArray(n));
                    var got = '';
                    for (var i = 0; i < bytes.length; i++) got += ('0' + bytes[i].toString(16)).slice(-2);
                    line.reads.push({ base: bs, got: got, match: got === want });
                    if (got === want) line.hits.push(bs);
                } catch (e) {
                    line.reads.push({ base: bs, err: e.message });
                }
            });
            res.push(line);
        });
        send({ tag: 'verify', res: res });
    })();
    """
    js = js.replace("ITEMS", str(items).replace("'", '"')).replace("BASES", str(bases).replace("'", '"'))

    dev = frida.get_device_manager().add_remote_device("127.0.0.1:27042")
    sess = dev.attach(gp)
    sc = sess.create_script(js)
    sc.on("message", lambda m, d: print(m, flush=True))
    sc.load()
    time.sleep(4)


if __name__ == "__main__":
    main()
