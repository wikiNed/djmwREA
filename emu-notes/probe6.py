import frida, sys, json, time

PID = 2808

dev = frida.get_device_manager().add_remote_device("127.0.0.1:27042")
print("attaching", PID)
sess = dev.attach(PID)
print("attached OK")

JS = r"""
setTimeout(function () {
  var mods = Process.enumerateModules().map(function(m){
     return {n:m.name, b:m.base.toString(), s:m.size};
  });
  send({t:"mods", d:mods});
}, 300);
"""

def on_msg(msg, data):
    p = msg.get("payload") or {}
    if p.get("t") == "mods":
        d = p["d"]
        print(f"模块 {len(d)} 个")
        for m in d:
            if "il2cpp" in m["n"].lower() or "unity" in m["n"].lower():
                print("  ", m["n"], m["b"], m["s"])
        with open(r"E:\DSH\game\.rea-study\emu\modules2.json","w",encoding="utf-8") as f:
            json.dump(d,f,ensure_ascii=False,indent=1)

script = sess.create_script(JS)
script.on("message", on_msg)
script.load()
time.sleep(5)
try:
    sess.detach()
except Exception:
    pass
