#!/system/bin/sh
# 逐段 dump 并即时 grep。grep 对 /proc/PID/mem 这种非规则文件不可靠，
# 必须先落成普通文件再搜。
# 覆盖**所有** rw 段（含小的），命中就保留文件并记录来源段。
PID=$1
OUT=$2
MINSZ=${3:-262144}
mkdir -p $OUT
rm -f $OUT/hits.txt

grep ' rw' /proc/$PID/maps | awk '{print $1}' > $OUT/segs.txt
echo "segments: $(wc -l < $OUT/segs.txt)"

while read -r rng; do
  start=${rng%-*}
  end=${rng#*-}
  s=$(printf '%d' "0x$start" 2>/dev/null) || continue
  e=$(printf '%d' "0x$end" 2>/dev/null) || continue
  sz=$((e - s))
  if [ "$sz" -lt "$MINSZ" ]; then continue; fi

  f="$OUT/s_$start.bin"
  dd if=/proc/$PID/mem of="$f" bs=1M skip=$((s / 1048576)) count=$((sz / 1048576 + 2)) 2>/dev/null

  hitA=$(grep -a -c -E 'DateID|BaoShiSuiPian|HeroBaoShis|LiBaoIDs|SuoYouBaoShiTongJi' "$f" 2>/dev/null)
  hitB=$(grep -a -c 'SaveFile' "$f" 2>/dev/null)
  [ -z "$hitA" ] && hitA=0
  [ -z "$hitB" ] && hitB=0

  if [ "$hitA" != "0" ] || [ "$hitB" != "0" ]; then
    echo "HIT $start size=$sz A=$hitA B=$hitB"
    echo "$start $sz $hitA $hitB" >> "$OUT/hits.txt"
  else
    rm -f "$f"
  fi
done < $OUT/segs.txt

echo "=== done, hits: ==="
cat "$OUT/hits.txt" 2>/dev/null
echo "(end)"
