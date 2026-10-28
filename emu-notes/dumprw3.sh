#!/system/bin/sh
# 精确 dump：/proc/PID/mem 必须用 bs=1 才能按任意字节偏移 seek。
# 段多且大，所以只挑 >= 4MB 的，且限制总数以免超时。
PID=$1
OUT=$2
MAXN=${3:-12}
MINSZ=${4:-4194304}
mkdir -p $OUT

grep ' rw' /proc/$PID/maps | awk -v ms=$MINSZ '{
    split($1, a, "-");
    cmd = "printf %d 0x" a[1];
    s = cmd; s | getline sv; close(s);
    s2 = "printf %d 0x" a[2]; s2 | getline ev; close(s2);
    sz = ev - sv;
    if (sz >= ms) print a[1], sv, sz, (NF>=6 ? $6 : "anon");
}' > $OUT/list.txt

echo "候选段: $(wc -l < $OUT/list.txt)"
n=0
while read -r hexoff off sz name; do
  n=$((n+1))
  if [ $n -gt $MAXN ]; then break; fi
  outf=$OUT/m_${hexoff}.bin
  echo "[$n] $hexoff off=$off size=$sz $name"
  dd if=/proc/$PID/mem of=$outf bs=1 skip=$off count=$sz 2>/dev/null
  echo "    -> $(ls -l $outf | awk '{print $5}')"
done < $OUT/list.txt
echo done
