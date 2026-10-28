"""hook ES3Writer.Create / ES3Reader.Create —— 直接读 ES3Settings.encryptionPassword (偏移 0x28)

依据（dump.cs:563867 ES3Settings 字段布局）：
    private ES3.Location _location;         // 0x10
    public string path;                     // 0x18
    public ES3.EncryptionType encryptionType; // 0x20
    public ES3.CompressionType compressionType; // 0x24
    public string encryptionPassword;       // 0x28   <<< 目标
    public ES3.Directory directory;         // 0x30
    public ES3.Format format;               // 0x34
    public bool prettyPrint;                // 0x38
    public int bufferSize;                  // 0x3C

方法 RVA（dump.cs 中 ES3Writer / ES3Reader 的 Create）：
    ES3Writer.Create(ES3Settings)  由 ES3.Save<object> @0x1A722D0 的 bl 目标给出 = 0x174B720
    ES3Reader.Create(ES3Settings)  需在运行时确认：先反汇编 0x1746A84 (ES3.Load(string, ES3Settings))
"""
import sys
import time
from pathlib import Path

import frida

JS_TMPL = r"""
(function () {
    var BASE = ptr("%BASE%");

    function rd(p) {
        try {
            if (p.isNull()) return null;
            var len = p.add(0x10).readS32();
            if (len < 0 || len > 100000) return '<bad ' + len + '>';
            return p.add(0x14).readUtf16String(len);
        } catch (e) { return '<err ' + e.message + '>'; }
    }

    function dumpSettings(p, tag) {
        if (p.isNull()) { send({tag: tag, err: 'null settings'}); return; }
        var st = p.add(0x28).readPointer();
        var info = {
            tag: tag,
            settings: p.toString(),
            encryptionType: p.add(0x20).readS32(),
            compressionType: p.add(0x24).readS32(),
            format: p.add(0x34).readS32(),
            bufferSize: p.add(0x3C).readS32(),
            pathPtr: p.add(0x18).readPointer().toString(),
            password: rd(st),
            passwordRaw: null
        };
        try {
            if (!st.isNull()) {
                var raw = st.readByteArray(24);
                var u8 = new Uint8Array(raw);
                var h = '';
                for (var i = 0; i < u8.length; i++) h += ('0'+u8[i].toString(16)).slice(-2);
                info.passwordRaw = h;
            }
        } catch (e) {}
        send(info);
    }

    // ES3Writer.Create(ES3Settings settings)  -> 参数 x0 = settings
    try {
        Interceptor.attach(BASE.add(%WRITER_RVA%), {
            onEnter: function (args) { dumpSettings(args[0], 'Writer_Create'); },
            onLeave: function (ret) { send({tag:'Writer_ret', ptr: ret.toString()}); }
        });
        send({tag:'ok', what:'Writer_Create'});
    } catch (e) { send({tag:'fail', what:'Writer_Create', err: e.message}); }

    // ES3Reader.Create(ES3Settings settings)
    var readerRva = %READER_RVA%;
    if (readerRva > 0) {
        try {
            Interceptor.attach(BASE.add(readerRva), {
                onEnter: function (args) { dumpSettings(args[0], 'Reader_Create'); }
            });
            send({tag:'ok', what:'Reader_Create'});
        } catch (e) { send({tag:'fail', what:'Reader_Create', err: e.message}); }
    }

    send({tag:'ready'});
})();
"""


def main():
    gp = int(sys.argv[1])
    base = sys.argv[2]
    writer = int(sys.argv[3], 16) if len(sys.argv) > 3 else 0x174B720
    reader = int(sys.argv[4], 16) if len(sys.argv) > 4 else 0
    wait = int(sys.argv[5]) if len(sys.argv) > 5 else 240

    js = (JS_TMPL
          .replace("%BASE%", "0x" + base.lstrip("0x"))
          .replace("%WRITER_RVA%", hex(writer))
          .replace("%READER_RVA%", hex(reader)))

    dm = frida.get_device_manager()
    dev = dm.add_remote_device("127.0.0.1:27042")
    sess = dev.attach(gp)
    script = sess.create_script(js)
    script.on("message", lambda m, d: print(m, flush=True))
    script.load()
    print(f"[hook] writer=0x{writer:X} reader=0x{reader:X} wait={wait}s", flush=True)
    time.sleep(wait)


if __name__ == "__main__":
    main()
