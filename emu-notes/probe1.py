import frida, sys, json

PKG = "game.taptap.HQGAMES.TapDemons"

dev = frida.get_device_manager().add_remote_device("127.0.0.1:27042")

# 列出所有进程，找游戏的
procs = dev.enumerate_processes()
target = None
for p in procs:
    if "TapDemons" in p.name or "tapdemons" in p.name.lower():
        target = p
        break

if target is None:
    print("未找到游戏进程，前 20 个进程：")
    for p in procs[:20]:
        print("  ", p.pid, p.name)
    sys.exit(1)

print(f"找到进程: {target.pid} {target.name}")
