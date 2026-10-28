#!/system/bin/sh
# 在已 dump 的分块中做 UTF-16 搜索：把搜索串转成 UTF-16LE 十六进制再 grep -aF 不行，
# 改用 python3（模拟器里可能没有）→ 用 od+tr 方案太重，直接 perl 也不一定有。
# 用 toybox 的 grep 配合 $'..' 转义（sh 支持）
D=/data/local/tmp/memd
S16=$(printf 'S\000a\000v\000e\000F\000i\000l\000e\000')
echo "pattern len=${#S16}"
for f in $D/seg_*.bin; do
  if [ -s "$f" ]; then
    if grep -qaF "$S16" "$f"; then
      echo "HIT-utf16 $f"
    fi
  fi
done
echo "--- 也搜 AutoSave ---"
A16=$(printf 'A\000u\000t\000o\000S\000a\000v\000e\000')
for f in $D/seg_*.bin; do
  if [ -s "$f" ]; then
    if grep -qaF "$A16" "$f"; then
      echo "HIT-auto $f"
    fi
  fi
done
echo done
