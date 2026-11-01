#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""在 Houdini（libnb.so）下的 ARM IL2CPP 进程里定位任意类的 Il2CppClass / 静态字段 / 实例。

背景
----
雷电模拟器把 32 位 ARM 游戏跑在 Intel Houdini 翻译层上，于是：

  * `libil2cpp.so` 是 **ARM 库**，不出现在 frida 的 `Process.enumerateModules()` 里
  * 静态反查 `Il2CppCodeRegistration.methodPointers` 在 Stripping 构建下不可行
  * 按字段偏移做字节特征搜方法体，命中率等于噪声
  * `Interceptor.attach` 对 Houdini 翻译的 ARM 代码 **无效**（字节不会被改写，hits 恒 0）
  * 没有 x86→ARM 的调用桥，`NativeFunction` 也调不动 ARM 函数

但有一件事是可以做的：**直接读写 ARM 段的内存**。于是定位链走「数据」而不是「代码」：

  1. 类名字符串在 `global-metadata.dat` 的映射里，扫 `"<ClassName>\\0"`
  2. 全内存搜「值等于该字符串地址」的 4 字节指针 —— 命中处 -8 就是 `Il2CppClass`
  3. 验证 `Il2CppClass`：`+0x00` image 有效、`+0x04` gc_desc、`+0x08` name 能读回类名、
     `+0x5c` static_fields（这个偏移由 `il2cpp_class_get_static_field_data` 的实现
     `ldr r0,[r0,#0x5c]; bx lr` 直接给出）
  4. 静态字段 `static_fields[i]` 里的非零值，读 `+0x00` 若等于该类的 `Il2CppClass` 地址，
     就是该类的实例

用法
----
    python il2cpp_class_locator.py GameGUI
    python il2cpp_class_locator.py GameGUI ChongWuUI ChongWuUIManager_New
    python il2cpp_class_locator.py GameGUI --fields 32
    python il2cpp_class_locator.py GameGUI --pid 12663

输出每个类的 `Il2CppClass` 地址、`static_fields` 地址、以及每个静态字段的
「值 / klass / 是否为本类实例」三元组。

注意
----
地址是**每次进程启动都会变**的（ASLR + GC 堆分配），不要硬编码进脚本；
本工具每次运行都重新扫。上一轮跑出来的地址只能用于同一进程存活期内。
"""
import argparse
import subprocess
import sys
import time

ADB = r"D:\leidian\LDPlayer9\adb.exe"
DEV = "emulator-5558"
FRIDA_HOST = "127.0.0.1:27042"

SCRIPT = r"""
function main() {
  var NAMES = %(names)s;
  var NFIELDS = %(nfields)d;

  var res = {names: NAMES, classes: {}};

  // ---- 1. 收集 metadata 映射 ----
  var all = Process.enumerateRanges('r--').concat(Process.enumerateRanges('rw-'));
  var meta = [];
  for (var i = 0; i < all.length; i++) {
    var r = all[i];
    if (r.file && r.file.path.indexOf('global-metadata') >= 0) meta.push(r);
  }
  res.meta = meta.map(function(r){ return r.base + '+' + r.size; });

  function toHex(s) {
    var h = '';
    for (var i = 0; i < s.length; i++) {
      h += ('0' + s.charCodeAt(i).toString(16)).slice(-2) + ' ';
    }
    return h + '00';
  }

  function readKlassName(k) {
    try {
      var p = ptr(k);
      var n = p.add(8).readU32();
      if (n === 0) return null;
      var s = ptr(n).readCString(64);
      return s ? s.split('\u0000')[0] : null;
    } catch (e) { return null; }
  }

  for (var c = 0; c < NAMES.length; c++) {
    var nm = NAMES[c];
    var out = {name: nm};

    // ---- 2. 找类名字符串 ----
    var pat = toHex(nm);
    var nameAddr = null;
    for (var i = 0; i < meta.length && !nameAddr; i++) {
      var f;
      try { f = Memory.scanSync(meta[i].base, meta[i].size, pat); } catch (e) { continue; }
      if (f.length) nameAddr = f[0].address;
    }
    if (!nameAddr) { out.error = 'class name string not found in metadata'; res.classes[nm] = out; continue; }
    out.name_addr = nameAddr.toString();

    // ---- 3. 全内存找指向该字符串的指针，反推 Il2CppClass ----
    var p2 = nameAddr.toMatchPattern();
    var cands = [];
    for (var i = 0; i < all.length; i++) {
      var r = all[i];
      if (r.size > 96 * 1024 * 1024) continue;
      var f;
      try { f = Memory.scanSync(r.base, r.size, p2); } catch (e) { continue; }
      for (var k = 0; k < f.length && cands.length < 12; k++) {
        var a = f[k].address;
        // 去重（相邻地址只留一个）—— 注意 frida 17 的 NativePointer 没有 abs()
        var dup = false;
        for (var d = 0; d < cands.length; d++) {
          var diff = a.compare(cands[d]) >= 0
            ? a.sub(cands[d]).toUInt32()
            : cands[d].sub(a).toUInt32();
          if (diff < 16) { dup = true; break; }
        }
        if (dup) continue;
        cands.push(a);
      }
    }

    out.candidates = [];
    for (var k = 0; k < cands.length; k++) {
      var at = cands[k];
      var cls = at.sub(8);
      var rec = {at: at.toString(), cls: cls.toString()};
      try {
        rec.image = cls.readU32().toString(16);
        rec.gc_desc = cls.add(4).readU32().toString(16);
        rec.namesp = cls.add(0xc).readU32().toString(16);
        rec.sf = cls.add(0x5c).readU32().toString(16);
        // 反查：cls+0x08 处的 name 必须指回类名字符串
        rec.name_ptr = cls.add(8).readU32().toString(16);
        rec.name_ok = (rec.name_ptr === nameAddr.toString(16));
        rec.is_real = (rec.image !== '0' && rec.name_ok);
      } catch (e) { rec.err = e.message; }

      // ---- 4. 读 static_fields ----
      if (rec.is_real && rec.sf !== '0') {
        var SF = ptr('0x' + rec.sf);
        rec.fields = [];
        for (var fi = 0; fi < NFIELDS; fi++) {
          var v;
          try { v = SF.add(fi * 4).readU32(); } catch (e) { break; }
          var w = {i: fi, v: v.toString(16)};
          if (v !== 0) {
            try {
              var op = ptr(v);
              w.obj_klass = op.readU32().toString(16);
              w.obj_klass_name = readKlassName(w.obj_klass);
              w.is_self_instance = (w.obj_klass === rec.cls.replace(/^0x/, ""));
              w.m_CachedPtr = op.add(8).readU32().toString(16);
            } catch (e) { w.err = e.message; }
          }
          rec.fields.push(w);
        }
      }
      out.candidates.push(rec);
    }
    res.classes[nm] = out;
  }
  send(res);
}
main();
"""


def latest_pid(adb, dev):
    out = subprocess.check_output([adb, "-s", dev, "shell",
                                   "ps -A | grep TopDemons"]).decode()
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[1].isdigit():
            return int(parts[1])
    raise SystemExit("找不到游戏进程，先确认实例已启动且游戏在前台")


def main():
    ap = argparse.ArgumentParser(description="Houdini/ARM IL2CPP 类定位器")
    ap.add_argument("names", nargs="+", help="类名（可多个）")
    ap.add_argument("--fields", type=int, default=16, help="读多少个静态字段（默认 16）")
    ap.add_argument("--pid", type=int, default=0, help="进程 pid（默认自动查最新）")
    ap.add_argument("--adb", default=ADB)
    ap.add_argument("--device", default=DEV)
    ap.add_argument("--frida", default=FRIDA_HOST,
                    help="frida-server 地址，需先 adb forward tcp:27042 tcp:27042")
    a = ap.parse_args()

    import frida

    pid = a.pid or latest_pid(a.adb, a.device)
    print(f"pid = {pid}")

    dev = frida.get_device_manager().add_remote_device(a.frida)
    session = dev.attach(pid)
    script = session.create_script(
        SCRIPT % {"names": str(a.names).replace("'", '"'), "nfields": a.fields})
    deck = []
    got = []

    def on_msg(message, data):
        if message.get("type") == "error":
            print("frida 脚本错误:\n" + (message.get("stack") or message.get("description") or ""),
                  file=sys.stderr)
            deck.append("err")
        got.append(message)

    script.on("message", on_msg)
    script.load()

    # /proc 里所有 rw- 段全扫一遍很慢（几百 MB），给它足够时间。
    deadline = time.time() + 300
    while time.time() < deadline and not got and not deck:
        time.sleep(1)
    if not got:
        print("⚠ 脚本 300 秒内没有回报结果（扫描范围过大或已崩溃）", file=sys.stderr)

    for m in got:
        p = m.get("payload") or {}
        if "meta" in p:
            print("metadata 映射:", p["meta"])
        for nm, rec in (p.get("classes") or {}).items():
            print(f"\n{'='*70}\n类 {nm}")
            if rec.get("error"):
                print("  ", rec["error"])
                continue
            print("  类名字符串 @", rec.get("name_addr"))
            real = [c for c in rec.get("candidates", []) if c.get("is_real")]
            for c in rec.get("candidates", []):
                tag = "  ★真 Il2CppClass" if c.get("is_real") else "  (干扰命中)"
                print(f"{tag}  cls={c['cls']}  image={c.get('image')}  sf={c.get('sf')}")
                if not c.get("is_real"):
                    continue
                for w in c.get("fields", []):
                    if w.get("v") == "0":
                        continue
                    mark = " ← 本类实例" if w.get("is_self_instance") else ""
                    print("     sf[%-2d] = %-10s klass=%-10s %-28s cached=%-10s%s" % (
                        w["i"], w["v"], w.get("obj_klass", "-"),
                        w.get("obj_klass_name") or "-", w.get("m_CachedPtr", "-"), mark))
            if not real:
                print("  ⚠ 没有找到有效的 Il2CppClass（可能类名不在 metadata 或未被加载）")
    session.detach()


if __name__ == "__main__":
    sys.exit(main())
