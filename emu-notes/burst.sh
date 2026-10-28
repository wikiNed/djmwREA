#!/system/bin/sh
# 在存档窗口内高频扫描内存，搜 ES3 明文与路径特征。
# 存档触发：切后台 6 秒后（ShuJuDate.YanShiTime = 6）或 180 秒自动存。
#
# 只 scan 前几个大 rw 段（Unity 托管堆所在），每轮重新读 maps（地址会变）。
PID=$1
ROUNDS=${2:-20}
mkdir -p /data/local/tmp/burst
rm -f /data/local/tmp/burst/*.bin

i=1
while [ $i -le $ROUNDS ]; do
  grep ' rw' /proc/$PID/maps | awk '{print $1}' | head -60 | while read -r rng; do
    start=${rng%-*}; end=${rng#*-}
    s=$(printf '%d' "0x$start" 2>/dev/null) || continue
    e=$(printf '%d' "0x$end" 2>/dev/null) || continue
    sz=$((e - s))
    [ "$sz" -lt 2097152 ] && continue
    [ "$sz" -gt 134217728 ] && sz=134217728
    f=/data/local/tmp/burst/t_${start}.bin
    dd if=/proc/$PID/mem of=$f bs=1M skip=$((s / 1048576)) count=$((sz / 1048576 + 2)) 2>/dev/null
    if grep -a -q -E 'DateID|SaveFile|BaoShiSuiPian' "$f" 2>/dev/null; then
      echo "ROUND$i HIT $start sz=$sz"
      cp "$f" /data/local/tmp/burst/KEEP_${i}_${start}.bin
    fi
    rm -f "$f"
  done
  echo "--- round $i done ---"
  i=$((i+1))
done
