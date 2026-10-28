import frida, sys

dev = frida.get_device_manager().add_remote_device("127.0.0.1:27042")
procs = dev.enumerate_processes()
print(f"共 {len(procs)} 个进程")
print("--- 含 game/unity/tap 的 ---")
for p in procs:
    n = p.name.lower()
    if "game" in n or "unity" in n or "tap" in n or "hqg" in n:
        print("  ", p.pid, repr(p.name))
print("--- 最后 25 个 ---")
for p in procs[-25:]:
    print("  ", p.pid, repr(p.name))
