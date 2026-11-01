#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Houdini 下 ARM 内存的 frida 能力验证器 —— 把「能做什么、不能做什么」变成可复现命令。

背景
----
32 位 ARM 游戏跑在 libnb.so (Houdini) 翻译层上，frida 看到的是 x86 侧模块表，
`Process.enumerateModules()` 里**根本没有 libil2cpp.so**。但 ARM 映射仍然存在于
`/proc/<pid>/maps`，可以直接按地址读写。

本脚本把这条通路的边界逐项验证，结论要能被人独立复核，而不是一句「能用/不能用」。

★ 四条决定性结论（实测于雷电模拟器-2，v5.5.7）
------------------------------------------------
| 能力                                   | 结果 | 说明 |
|----------------------------------------|------|------|
| 读 ARM 段内存                          | ✅   | 用 **`ptr.readByteArray(n)`**；`Memory.readByteArray` 在 frida 17 **已移除** |
| `Memory.protect(...,'rwx')`            | ✅   | 改权限成功，游戏存活 |
| 写 ARM 代码并读回                      | ✅   | 用 **`ptr.writeByteArray(buf)`**；写 `mov r0,r0`×3 + `bx lr` 读回逐字节正确 |
| `Interceptor.attach` ARM 地址          | ❌   | attached=true 但**机器码一个字节都没被改写**，hits 恒 0 |
| 通过 libhoudini 做 x86→ARM 调用        | ❌   | 62 个导出全是 NativeBridgeItf / android_*，无调用桥 |

一句话：**能看数据，不能动代码。**

⚠ 陷阱清单
-----------
- `Process.findModuleByName('libil2cpp.so')` 返回 null —— 不是加载失败，是不在这张表里。
- `enumerate_processes()` 看不到游戏进程时，先 `ps -A` 拿**最新** pid 再 attach；
  旧 pid 已死会让 `attach` 抛 ProcessNotFoundError，容易误判成「frida 用不了」。
- `hex()` 在 frida 17 的脚本里**不是全局函数**（`ReferenceError`），用 `ptr.toString()`。
- `Memory.scanSync` 返回的 `match.address` **已经是绝对地址**，再 `.add(base)` 就越界了。
- 哨兵判据 `(v >>> 20) === 0xa00`，JS 里必须用 `>>>`；用 `>>` 或直接比 `0xA0000000`
  会因超过 0x7FFFFFFF 做有符号转换而永假。

用法
----
    python frida_arm.py base                  # 从 /proc 找 ARM 映射（base / 可写段 / 大小）
    python frida_arm.py probe                 # 一次性跑完下面全部检查
    python frida_arm.py read <addr> <size>    # 读并 hexdump
    python frida_arm.py protect <addr>        # 试改 rwx 并复查
    python frida_arm.py write <addr>          # 写几条 ARM 指令再还原
    python frida_arm.py hook <addr>           # 验证 Interceptor 是否真改写机器码
    python frida_arm.py sentinel <addr> <size># 统计哨兵形状

前置
----
    adb -s <dev> shell 'su 0 /data/local/tmp/frida-server -D &'
    adb -s <dev> forward tcp:27042 tcp:27042
    客户端：pip install frida（本仓库环境装在 .pylibs）

地址一律**动态获取**：不让任何硬编码的 0x05014000 出现在代码里，因为模拟器每次
重启基址都会变。
"""
from __future__ import annotations

import re
import subprocess
import sys
import time

ADB = r"D:\leidian\LDPlayer9\adb.exe"
DEVICE = "emulator-5558"
PKG = "com.HQGAMES.TopDemons"
FRIDA_PORT = "27042"


# ---------------------------------------------------------------- adb 辅助
def adb(*args, timeout=30):
    return subprocess.run([ADB, "-s", DEVICE, *args],
                          capture_output=True, timeout=timeout)


def shell(cmd, timeout=30):
    r = adb("shell", cmd, timeout=timeout)
    return r.stdout.decode("utf-8", "replace") + r.stderr.decode("utf-8", "replace")


def find_pid() -> int:
    """`ps -A | grep` 取最新 pid。注意设备上没有 pidof。"""
    out = shell("ps -A | grep %s" % PKG)
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[-1].endswith(PKG.split(".")[-1]):
            try:
                return int(parts[1])
            except ValueError:
                continue
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[1].isdigit():
            return int(parts[1])
    raise RuntimeError("找不到 %s 进程，先启动游戏" % PKG)


MAPS_RE = re.compile(
    r"^([0-9a-f]+)-([0-9a-f]+)\s+(\S{4})\s+([0-9a-f]+)\s+\S+\s+\d+\s*(.*)$")


def arm_maps(pid: int, needle: str | None = None):
    """解析 /proc/<pid>/maps，返回 ARM 库的映射项。

    返回 [dict(start, end, perm, offset, path)]。
    路径含 `/arm/` 或 `arm64` 视为 ARM 侧映射（Houdini 翻译层的特征）。
    `needle` 再按子串过滤，例如 `libil2cpp.so`。

    ⚠ 注意：这里的 perm 是**当前**状态。如果之前有脚本跑过 `Memory.protect`，
    这里会看到被改过的 `rwxp`，而不是进程刚启动时的样子。
    """
    txt = shell("su 0 cat /proc/%d/maps" % pid, timeout=60)
    out = []
    for line in txt.splitlines():
        m = MAPS_RE.match(line.strip())
        if not m:
            continue
        s, e, perm, off, path = m.groups()
        p = path.strip()
        if "/arm/" not in p and "arm64" not in p:
            continue
        if needle and needle not in p:
            continue
        out.append(dict(start=int(s, 16), end=int(e, 16), perm=perm,
                        offset=int(off, 16), path=p))
    return out


def report_base(pid: int, needle: str = "libil2cpp.so"):
    maps = arm_maps(pid, needle)
    if not maps:
        print("没有找到路径含 %r 的 ARM 映射" % needle)
        allarm = arm_maps(pid)
        print("该进程共有 %d 个 ARM 映射" % len(allarm))
        return None
    total = sum(m["end"] - m["start"] for m in maps)
    print("pid = %d，%s 有 %d 段映射，合计 0x%x 字节：" % (pid, needle, len(maps), total))
    for m in maps:
        print("  %08x-%08x %s off=0x%-8x"
              % (m["start"], m["end"], m["perm"], m["offset"]))
    base = maps[0]["start"]
    print("\nbase（首段起点） = 0x%08x" % base)
    print("说明：ELF 里的 VA 加到 base 上就是运行时地址。")
    rw = [m for m in maps if "w" in m["perm"]]
    if rw:
        w = rw[-1]
        print("可写段            = 0x%08x size=0x%x" % (w["start"], w["end"] - w["start"]))
    nonx = [m for m in maps if "x" not in m["perm"] and (m["end"] - m["start"]) > 0x100000]
    if nonx:
        print("不可执行的大段    = 0x%08x size=0x%x  ← 代码主体（Houdini 下常见）"
              % (nonx[-1]["start"], nonx[-1]["end"] - nonx[-1]["start"]))
    return base


# ---------------------------------------------------------------- frida 辅助
def connect(pid: int):
    import frida
    adb("forward", "tcp:%s" % FRIDA_PORT, "tcp:%s" % FRIDA_PORT, timeout=15)
    dev = frida.get_device_manager().add_remote_device("127.0.0.1:%s" % FRIDA_PORT)
    return dev.attach(pid)


def run_script(session, source: str, wait: float = 3.0):
    got = []
    script = session.create_script(source)
    script.on("message", lambda m, d: got.append(m))
    script.load()
    time.sleep(wait)
    return got


JS_HELPERS = r"""
// ★ frida 17 的 Memory 对象只剩 {alloc, dup, patchCode, scan}，
//   Memory.readByteArray / writeByteArray **已被移除**（typeof 是 undefined，
//   调用即 'not a function'）。用 ptr 自身的 readByteArray / writeByteArray。
//   网上很多写法是反的 —— 实测 ptr.readByteArray(n) 正常返回 ArrayBuffer。
function rb(p, n) { return new Uint8Array(p.readByteArray(n)); }
function hx(p, n) {
  var b = rb(p, n), s = [];
  for (var i = 0; i < b.length; i++) s.push(('0' + b[i].toString(16)).slice(-2));
  return s.join(' ');
}
"""


def cmd_read(pid, addr, size):
    session = connect(pid)
    src = JS_HELPERS + """
    (function () {
      try { send({ok: true, hex: hx(ptr('%s'), %d)}); }
      catch (e) { send({ok: false, err: e.message}); }
    })();
    """ % (addr, size)
    for m in run_script(session, src, 2.0):
        print(m.get("payload", m))
    session.detach()


def cmd_protect(pid, addr):
    session = connect(pid)
    src = JS_HELPERS + """
    (function () {
      var p = ptr('%s'), res = {};
      try { var r = Process.findRangeByAddress(p);
            res.before = r ? [r.base.toString(), r.size, r.protection] : null; } catch (e) { res.e1 = e.message; }
      try { res.protect = Memory.protect(p, 0x1000, 'rwx'); } catch (e) { res.e2 = e.message; }
      try { var r2 = Process.findRangeByAddress(p);
            res.after = r2 ? [r2.base.toString(), r2.size, r2.protection] : null; } catch (e) { res.e3 = e.message; }
      send(res);
    })();
    """ % addr
    for m in run_script(session, src, 2.0):
        print(m.get("payload", m))
    session.detach()


def cmd_write(pid, addr):
    """在指定地址写 4 条 ARM 指令（mov r0,r0 ×3 + bx lr），读回后立刻还原。"""
    session = connect(pid)
    src = JS_HELPERS + r"""
    (function () {
      var p = ptr('%s'), res = {};
      var bak = null;
      try { res.before = hx(p, 16); }
      catch (e) { res.e1 = e.message; send(res); return; }
      try {
        bak = rb(p, 16);
        Memory.protect(p, 0x1000, 'rwx');
        var ab = new ArrayBuffer(16), dv = new DataView(ab);
        [0xe1a00000, 0xe1a00000, 0xe1a00000, 0xe12fff1e].forEach(function (w, i) {
          dv.setUint32(i * 4, w >>> 0, true);
        });
        p.writeByteArray(ab);
        res.after = hx(p, 16);
        p.writeByteArray(bak.buffer);
        res.restored = hx(p, 16);
      } catch (e) { res.e2 = e.message; }
      send(res);
    })();
    """ % addr
    for m in run_script(session, src, 2.0):
        print(m.get("payload", m))
    session.detach()


def cmd_hook(pid, addr):
    """验证 Interceptor 是否真的改写了 ARM 机器码。"""
    session = connect(pid)
    src = JS_HELPERS + r"""
    (function () {
      var t = ptr('%s'), res = {target: t.toString()}, hits = 0;
      try { res.before = hx(t, 16); } catch (e) { res.e1 = e.message; send(res); return; }
      try {
        var l = Interceptor.attach(t, {
          onEnter: function () { hits++; },
          onLeave: function () {}
        });
        res.attached = true;
        try { res.after = hx(t, 16); } catch (e) { res.e2 = e.message; }
        setTimeout(function () {
          res.hits = hits;
          res.changed = res.before !== res.after;
          try { l.detach(); } catch (e) {}
          send(res);
        }, 5000);
      } catch (e) { res.e3 = e.message; send(res); }
    })();
    """ % addr
    for m in run_script(session, src, 8.0):
        print(m.get("payload", m))
    session.detach()


def cmd_sentinel(pid, addr, size):
    session = connect(pid)
    src = JS_HELPERS + r"""
    (function () {
      var p = ptr('%s'), n = %d, res = {};
      try {
        var raw = p.readByteArray(n);
        var u32 = new Uint32Array(raw);
        var cnt = 0, samples = [];
        for (var i = 0; i < u32.length; i++) {
          // ★ 必须用 >>>，用 >> 会因有符号转换永假
          if ((u32[i] >>> 20) === 0xa00 && (u32[i] & 1) === 1) {
            cnt++;
            if (samples.length < 6) samples.push(p.add(i * 4).toString());
          }
        }
        res.u32_len = u32.length; res.count = cnt; res.samples = samples;
      } catch (e) { res.err = e.message; }
      send(res);
    })();
    """ % (addr, size)
    for m in run_script(session, src, 3.0):
        print(m.get("payload", m))
    session.detach()


def main(argv):
    cmd = argv[0] if argv else "probe"
    if cmd in ("-h", "--help", "help"):
        print(__doc__)
        return 0
    pid = find_pid()

    if cmd == "base":
        print("pid =", pid)
        report_base(pid, argv[1] if len(argv) > 1 else "libil2cpp.so")
        return 0

    print("pid =", pid)

    if cmd == "read":
        cmd_read(pid, argv[1], int(argv[2], 0) if len(argv) > 2 else 64)
        return 0

    if cmd == "protect":
        cmd_protect(pid, argv[1])
        return 0

    if cmd == "write":
        cmd_write(pid, argv[1])
        return 0

    if cmd == "hook":
        cmd_hook(pid, argv[1])
        return 0

    if cmd == "sentinel":
        cmd_sentinel(pid, argv[1], int(argv[2], 0) if len(argv) > 2 else 0x1000)
        return 0

    if cmd == "probe":
        base = report_base(pid)
        if base is None:
            return 1
        maps = arm_maps(pid, "libil2cpp.so")
        w = [m for m in maps if "w" in m["perm"]]
        print("\n--- 1) 读文件头 16 字节（应该是 7f 45 4c 46 01 01 01 00） ---")
        cmd_read(pid, "0x%x" % base, 16)
        print("\n--- 2) 挑一段不可执行的代码主体，试改 rwx ---")
        big = [m for m in maps if "x" not in m["perm"] and (m["end"] - m["start"]) > 0x100000]
        target = big[-1]["start"] if big else base
        print("目标 = 0x%08x" % target)
        cmd_protect(pid, "0x%x" % target)
        if w:
            print("\n--- 3) 可写段哨兵统计（前 32KB） ---")
            cmd_sentinel(pid, "0x%x" % w[-1]["start"], min(0x8000, w[-1]["end"] - w[-1]["start"]))
        print("\n--- 4) Interceptor 是否真的改写机器码（il2cpp 段首函数） ---")
        cmd_hook(pid, "0x%x" % (base + 0x002b8b50))
        print("\n--- 5) 游戏是否存活 ---")
        try:
            print("存活: pid =", find_pid())
        except RuntimeError:
            print("存活: 否（已崩溃）")
        return 0

    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
