#!/system/bin/sh
# 在存档窗口内反复 dump 进程堆的 rw- 大段，然后离线搜明文 JSON 特征。
# 用法：sh /data/local/tmp/dumprw.sh <pid> <outdir> <轮数> <间隔秒>
PID=$1
OUT=$2
N=$3
SLEEP=$4
mkdir -p $OUT

i=1
while [ $i -le $N ]; do
  # 逐个 rw 段 dump（只挑 >=4MB 的，避开零碎）
  grep ' rw' /proc/$PID/maps | awk '$1 ~ /-/ {
      split($1, a, "-");
      start=strtonum("0x" a[1]); end=strtonum("0x" a[2]);
      sz=end-start;
      if (sz >= 4194304) printf "%s %d %s\n", a[1], sz, (NF>=6 ? $6 : "anon");
  }' > $OUT/ranges_$i.txt

  echo "[round $i] ranges: $(wc -l < $OUT/ranges_$i.txt)"
  j=0
  while read -r line; do
    start=$(echo $line | cut -d' ' -f1)
    sz=$(echo $line | cut -d' ' -f2)
    name=$(echo $line | cut -d' ' -f3)
    base=$(basename "$name")
    j=$((j+1))
    if [ $j -gt 6 ]; then break; fi
    dd if=/proc/$PID/mem of=$OUT/r${i}_${j}_${base}.bin bs=1048576 skip=$(( 0x$start / 1048576 )) count=$(( sz / 1048576 + 1 )) 2>/dev/null
    dd if=/proc/$PID/mem bs=1 skip=$((0x$start)) count=0 2>/dev/null
    echo "  dumped ${start} size=${sz} name=${base}"
  done < $OUT/ranges_$i.txt

  i=$((i+1))
  sleep $SLEEP
done
echo "done"
