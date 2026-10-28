import frida, sys, json, time
from pathlib import Path

# 通过 adb forward 暴露的 frida-server 端口连接
dev = frida.get_device_manager().add_remote_device("127.0.0.1:27042")

procs = dev.enumerate_processes()
print(f"进程数: {len(procs)}")
target = None
for p in procs:
    if "TapDemons" in p.name:
        target = p
        break
if target is None:
    print("未找到游戏进程")
    sys.exit(1)
print(f"游戏进程 pid={target.pid} name={target.name}")

sess = dev.attach(target.pid)
print("attached")

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
        with open(str(Path(__file__).resolve().parent.parent / 'emu' / 'modules2.json'),"w",encoding="utf-8") as f:
            json.dump(d,f,ensure_ascii=False,indent=1)

script = sess.create_script(JS)
script.on("message", on_msg)
script.load()
time.sleep(5)
try:
    sess.detach()
except Exception:
    pass
