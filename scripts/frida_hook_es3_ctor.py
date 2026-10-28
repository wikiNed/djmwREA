"""真机 ARM64 首选脚本：hook ES3Settings..ctor(EncryptionType, string)，直接打印口令。

【为什么选这个点】
    ES3Settings..ctor(EncryptionType, string) @ RVA 0x175226C
      0x175227C  mov  x19, x2
      0x1752284  bl   #0x1751f88          ; .ctor(applyDefaults)
      0x1752288  str  x19, [x21, #0x28]!  ; this.encryptionPassword  ★
      0x175228C  stur w20, [x21, #-8]     ; +0x20 = encryptionType

    参数 x1 = EncryptionType（1 == AES），x2 = password（Il2CppString*）。
    这是口令进入 ES3Settings 的唯一入口，比 hook ES3Writer.Create 再读 +0x28 更直接。

【Il2CppString 内存布局】
    +0x00  klass*
    +0x08  monitor*
    +0x10  int32 length      （字符数，不含结尾 \\0）
    +0x14  utf16le 字符数据

【用法】
    python frida_hook_es3_ctor.py <pid> <base> [wait_sec]

    base 从目标机取：
        adb shell "cat /proc/\\$(pidof game.taptap.HQGAMES.TapDemons)/maps | grep libil2cpp" | head -1
    取第一列 起始地址 减 0 即为 base。

    真机上 libil2cpp.so 是正常 r-xp 映射，base + RVA 直接可 hook。
    MuMu 12 等 x86 翻译层模拟器上本脚本无效（见 docs/08-模拟器翻译层调研.md）。

【成功判据】
    打印出 password= 一串可读字符串，且 encryptionType == 1。
    拿到后：
        from es3decrypt import decrypt
        plain = decrypt('SaveFile.es3', password)
        # plain 应为 b'{"DateID":0,...}${"DateID":1,...}$...'
"""
import sys
import time

import frida

JS_TMPL = r"""
(function () {
    var BASE = ptr("%BASE%");
    var CTOR_RVA = %CTOR_RVA%;   // 0x175226C

    function utf16(p) {
        // p 是 Il2CppString*
        if (p.isNull()) return null;
        try {
            var len = p.add(0x10).readS32();
            if (len < 0 || len > 4096) return '<bad len ' + len + '>';
            return p.add(0x14).readUtf16String(len);
        } catch (e) { return '<err ' + e.message + '>'; }
    }

    function hexdump(p, n) {
        try {
            var raw = p.readByteArray(n);
            var a = new Uint8Array(raw), s = '';
            for (var i = 0; i < a.length; i++) s += ('0' + a[i].toString(16)).slice(-2);
            return s;
        } catch (e) { return null; }
    }

    try {
        Interceptor.attach(BASE.add(CTOR_RVA), {
            onEnter: function (args) {
                var encType = args[1].toInt32();
                var pwPtr   = args[2];
                var out = {
                    tag: 'ES3Settings_ctor',
                    thisPtr: args[0].toString(),
                    encryptionType: encType,
                    passwordPtr: pwPtr.toString(),
                    password: utf16(pwPtr),
                    raw: hexdump(pwPtr, 48)
                };
                if (encType === 1) {
                    out.note = '*** AES，这就是目标口令 ***';
                }
                send(out);
            }
        });
        send({tag: 'ok', what: 'ES3Settings..ctor', addr: BASE.add(CTOR_RVA).toString()});
    } catch (e) {
        send({tag: 'fail', err: e.message});
    }

    // 备选：SaveManager..ctor @ 0x17A64D8，读它也走同一条链
    try {
        Interceptor.attach(BASE.add(0x17A64D8), {
            onEnter: function (args) { send({tag: 'SaveManager_ctor', thisPtr: args[0].toString()}); }
        });
        send({tag: 'ok', what: 'SaveManager..ctor'});
    } catch (e) { send({tag: 'fail', what: 'SaveManager', err: e.message}); }

    send({tag: 'ready'});
})();
"""


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    pid = int(sys.argv[1])
    base = sys.argv[2]
    wait = int(sys.argv[3]) if len(sys.argv) > 3 else 300

    js = (JS_TMPL
          .replace("%BASE%", "0x" + base.lstrip("0x"))
          .replace("%CTOR_RVA%", hex(0x175226C)))

    dm = frida.get_device_manager()
    try:
        dev = dm.get_remote_device("127.0.0.1:27042")
    except Exception:
        try:
            dev = dm.add_remote_device("127.0.0.1:27042")
        except Exception:
            dev = frida.get_usb_device()

    session = dev.attach(pid)
    script = session.create_script(js)

    hits = []

    def on_message(msg, data):
        if msg.get("type") == "send":
            pl = msg["payload"]
            print(pl, flush=True)
            if pl.get("tag") == "ES3Settings_ctor" and pl.get("password"):
                hits.append(pl)
        else:
            print("ERR", msg, flush=True)

    script.on("message", on_message)
    script.load()
    print(f"[*] 已装入，base={base}，等待 {wait}s …", flush=True)

    try:
        time.sleep(wait)
    except KeyboardInterrupt:
        pass

    print("\n===== 汇总 =====", flush=True)
    if hits:
        seen = set()
        for h in hits:
            if h["password"] in seen:
                continue
            seen.add(h["password"])
            print(f"  encryptionType={h['encryptionType']}  password={h['password']!r}", flush=True)
        print(f"\n[*] 共 {len(seen)} 个唯一口令", flush=True)
    else:
        print("  未捕获。检查：\n"
              "   1) base 是否正确（真机上 libil2cpp 应为 r-xp）\n"
              "   2) 是否在 hook 之后才触发存档（等待期内切后台 6 秒触发 YanShiTime 存档）",
              flush=True)


if __name__ == "__main__":
    main()
