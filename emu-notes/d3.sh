#!/system/bin/sh
# 分块抓取游戏进程全部 rw 段，每段单独存文件避免超大
PID=$(pidof game.taptap.HQGAMES.TapDemons)
echo "PID=$PID"
OUT=/data/local/tmp/memd
rm -rf $OUT
mkdir -p $OUT
i=0
cat /proc/$PID/maps | grep ' rw' | while read line; do
  RANGE=$(echo "$line" | awk '{print $1}')
  S=${RANGE%-*}
  E=${RANGE#*-}
  SO=$((0x$S))
  EO=$((0x$E))
  SZ=$((EO - SO))
  # 只抓 256KB 以上、512MB 以下的段
  if [ $SZ -ge 262144 ] && [ $SZ -le 536870912 ]; then
    i=$((i + 1))
    dd if=/proc/$PID/mem bs=4096 skip=$((SO / 4096)) count=$((SZ / 4096)) 2>/dev/null > $OUT/seg_$i.bin
    echo "$i $RANGE $SZ $(echo "$line" | awk '{print $2, $6}')" >> $OUT/index.txt
  fi
done
ls -l $OUT | head -20
du -sh $OUT
