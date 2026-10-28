#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""探查 ES3 桶的结构：解密 SaveFile.es3 后，看它到底存了什么。

ES3 的 Write(key, value) 会产生 `{"<key>" : { "__type" : "...", "value" : ... }}`
形式的条目；但真实文件的明文**缺最外层 `{`**（ES3 写入器把根花括号吃掉），
所以要先补 `{"` 才能解析。

用法:
    python scripts/es3_probe.py saves/SaveFile.es3
    python scripts/es3_probe.py saves/SaveFile.es3 --dump keys
"""
import json
import sys

from es3save import PASSWORD, decrypt_bytes, _fix_fragment, is_14_segment


def main(argv):
    path = argv[0]
    blob = open(path, "rb").read()
    plain = decrypt_bytes(blob, PASSWORD)
    text = plain.decode("utf-8-sig")
    print("文件 %s" % path)
    print("  密文 %d 字节 / 明文 %d 字节 / 14段=%s"
          % (len(blob), len(plain), is_14_segment(plain)))
    print("  首 60 字符: %r" % text[:60])

    fixed = _fix_fragment(text)
    try:
        obj = json.loads(fixed)
    except Exception as e:  # noqa: BLE001
        print("  补 `{\"` 后仍无法解析: %s" % e)
        print("  末尾 60 字符: %r" % text[-60:])
        return 1

    print("  顶层 key 数: %d" % len(obj))
    for k, v in obj.items():
        if isinstance(v, dict):
            t = v.get("__type")
            inner = v.get("value")
            if isinstance(inner, str):
                s = inner if len(inner) <= 60 else inner[:60] + "..."
                print("    %-40r %-8s %r" % (k, t, s))
            elif isinstance(inner, (int, float, bool)) or inner is None:
                print("    %-40r %-8s %r" % (k, t, inner))
            else:
                print("    %-40r %-8s %s len=%s"
                      % (k, t, type(inner).__name__,
                         len(inner) if hasattr(inner, "__len__") else "?"))
        else:
            print("    %-40r raw %r" % (k, v))
    return 0


if __name__ == "__main__":
    sys.exit(main([a for a in sys.argv[1:] if not a.startswith("--")]))
