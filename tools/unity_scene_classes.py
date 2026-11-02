#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""列出某个 Unity bundle / 场景里挂了哪些 C# 类（MonoBehaviour 分布）。

为什么需要
----------
`dump.cs` 只能告诉你类存在，不能告诉你「这个类在哪个场景、有几个实例」。
逆向时经常要回答：「这个界面的脚本在哪个场景？」「这个类实例化了几次？」

实测踩坑（v5.5.7）
------------------
**`MonoScript` 的 `m_Name` 在 raw 偏移 0，不是 8。**

```
+000  0C 00 00 00  "CanvasScaler"          <- m_Name（int32 长度 + 字节）
+010  00 00 00 00 + 16 字节 hash           <- 填充 + m_Assembly
+030  0C 00 00 00  "CanvasScaler"          <- m_ClassName
+040  0E 00 00 00  "UnityEngine.UI"        <- m_Namespace
+04C  12 00 00 00  "UnityEngine.UI.dll"    <- m_AssemblyName
```

按「偏移 8」解会全部读出 `None`（偏移 8 是填充/hash 段）。
`MonoBehaviour` 的 `m_Script.pathID` 在 **raw 偏移 20**
（表头 = `m_GameObject`(8) + `m_Enabled`(1)+pad(3) + `m_Script`(8)）。

用法
----
    python tools/unity_scene_classes.py
        列出 bundle 里所有 asset 文件及其 MonoBehaviour 计数

    python tools/unity_scene_classes.py level7 level11
        列出指定场景的类分布（从多到少）

    python tools/unity_scene_classes.py --find ZuoBi
        反查某个类名出现在哪些场景

默认 bundle：`work/old/data557.unity3d`（v5.5.7，需先从 APK 解出）。
用 `--bundle <path>` 换目标。
"""
import argparse
import struct
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import paths  # noqa: E402

DEFAULT_BUNDLE = paths.WORK / "old" / "data557.unity3d"


def read_str(raw, off):
    """读 Unity 的 length-prefixed string，返回 (字符串, 下一个偏移)。"""
    if off + 4 > len(raw):
        return None, off
    n = struct.unpack_from("<i", raw, off)[0]
    off += 4
    if n < 0 or n > 65536 or off + n > len(raw):
        return None, off
    s = raw[off:off + n].decode("utf-8", "replace")
    off += n
    return s, (off + 3) & ~3


def script_class_map(env):
    """MonoScript path_id -> 类名。"""
    out = {}
    for obj in env.objects:
        if obj.type.name != "MonoScript":
            continue
        raw = obj.get_raw_data()
        _name, off = read_str(raw, 0)          # m_Name 在偏移 0
        cls, _ = read_str(raw, (off + 3) & ~3 + 20)   # 跳过 m_Assembly 的填充+hash
        # 上面的 +20 是「4 字节填充 + 16 字节 assembly hash」的经验值；
        # 解析失败时退回逐 4 字节试探。
        if not cls:
            for probe in range(4, min(len(raw) - 8, 64), 4):
                cand, _ = read_str(raw, probe)
                if cand and cand.isidentifier():
                    cls = cand
                    break
        if cls:
            out[obj.path_id] = cls
    return out


def monobehaviour_class(env, scripts):
    """返回 [(场景名, 类名)]，类名解不出时给 pid=NNN。"""
    rows = []
    for obj in env.objects:
        if obj.type.name != "MonoBehaviour":
            continue
        scene = getattr(obj.assets_file, "name", "?")
        raw = obj.get_raw_data()
        if len(raw) < 24:
            rows.append((scene, "<too-short>"))
            continue
        sid = struct.unpack_from("<i", raw, 20)[0]
        rows.append((scene, scripts.get(sid, "pid=%d" % sid)))
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description="Unity 场景类分布")
    ap.add_argument("scenes", nargs="*", help="场景/asset 文件名（如 level7）")
    ap.add_argument("--bundle", default=str(DEFAULT_BUNDLE))
    ap.add_argument("--find", metavar="CLASS", help="反查类名所在的场景")
    a = ap.parse_args(argv)

    path = Path(a.bundle)
    if not path.exists():
        raise SystemExit(
            "找不到 %s\n先从 APK 提取：\n"
            "  python -c \"import zipfile;open('work/old/data557.unity3d','wb')"
            ".write(zipfile.ZipFile(<apk>).read('assets/bin/Data/data.unity3d'))\""
            % path)

    import UnityPy
    env = UnityPy.load(str(path))
    scripts = script_class_map(env)
    print("MonoScript %d 个（可解类名 %d）"
          % (sum(1 for o in env.objects if o.type.name == "MonoScript"),
             len(scripts)))

    rows = monobehaviour_class(env, scripts)

    if a.find:
        by_scene = defaultdict(int)
        for scene, cls in rows:
            if cls == a.find:
                by_scene[scene] += 1
        if not by_scene:
            print("\n没有任何 MonoBehaviour 使用类 %r" % a.find)
            return 2
        print("\n=== 类 %s 出现在 ===" % a.find)
        for scene, n in sorted(by_scene.items()):
            print("  %-14s %d 个" % (scene, n))
        return 0

    if a.scenes:
        for scene in a.scenes:
            cnt = Counter(c for s, c in rows if s == scene)
            print("\n=== %s : %d 个 MonoBehaviour ===" % (scene, sum(cnt.values())))
            if not cnt:
                print("  （没有找到该 asset，用不带参数的方式先列出全部）")
            for k, v in cnt.most_common():
                print("  %-38s %d" % (k, v))
        return 0

    # 默认：列出所有 asset 文件
    cnt = Counter(s for s, _ in rows)
    print("\n=== 各 asset 文件的 MonoBehaviour 数 ===")
    for scene, n in cnt.most_common():
        print("  %-16s %d" % (scene, n))
    return 0


if __name__ == "__main__":
    sys.exit(main())
