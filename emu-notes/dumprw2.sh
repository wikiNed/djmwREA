#!/system/bin/sh
# 精简版：只 dump 最大的几个 rw 匿名段，用 dd 的 skip/count 按字节对齐。
# 关键：/proc/PID/mem 的 dd 必须用 bs=1 或 bs 与偏移对齐，否则 skip 会算错。
PID=$1
OUT=$2
mkdir -p $OUT

echo "== rw 段清单 =="
grep ' rw' /proc/$PID/maps | awk '{
    split($1, a, "-");
    # awk 里不能直接用 strtonum 的地方用 shell 算
    print a[1], a[2], $6
}' > $OUT/rw.txt
wc -l < $OUT/rw.txt

# 只要匿名大段（没路径 = NF 小）
grep ' rw' /proc/$PID/maps | awk 'NF < 6 { split($1, a, "-"); print a[1], a[2] }' > $OUT/rwanon.txt
echo "匿名 rw 段: $(wc -l < $OUT/rwanon.txt)"

n=0
while read -r s e; do
  ssz=$(printf '%d' 0x$s)
  esz=$(printf '%d' 0x$e)
  sz=$((esz - ssz))
  if [ $sz -lt 8388608 ]; then continue; fi
  n=$((n+1))
  if [ $n -gt 8 ]; then break; fi
  echo "dump $s size=$sz"
  dd if=/proc/$PID/mem of=$OUT/a_${s}.bin bs=1M skip=$((ssz / 1048576)) count=$((sz / 1048576 + 1)) 2>/dev/null
  ls -l $OUT/a_${s}.bin
done < $OUT/rwanon.txt
echo "done"
