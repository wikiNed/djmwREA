import frida, sys, json, time

PID = 2808

JS = r"""
setTimeout(function () {
    var mods = Process.enumerateModules();
    var out = mods.map(function (m) { return { n: m.name, b: m.base.toString(), s: m.size }; });
    send({ type: "mods", data: out });
}, 500);
"""

def on_message(msg, data):
    d = msg.get("payload")
    if d and d.get("type") == "mods":
        mods = d["data"]
        print(f"共 {len(mods)} 个模块")
        for m in mods:
            nm = m["n"]
            if any(k in nm.lower() for k in ("il2cpp", "unity", "main", "meta")):
                print(f"  {nm}  base={m['b']}  size={m['s']}")
        print("--- 全部 ---" if len(mods) < 40 else "--- 前 40 ---")
        for m in mods[:40]:
            print("  ", m["n"])
        with open(r"E:\DSH\game\.rea-study\emu\modules.json", "w", encoding="utf-8") as f:
            json.dump(mods, f, ensure_ascii=False, indent=1)

dev = frida.get_device_manager().add_remote_device("127.0.0.1:27042")
sess = dev.attach(PID)
script = sess.create_script(JS)
script.on("message", on_message)
script.load()
time.sleep(6)
sess.detach()
