#!/system/bin/sh
# 抓取当前游戏进程的 rw 匿名段
PID=$(pidof game.taptap.HQGAMES.TapDemons)
echo "PID=$PID"
rm -f /data/local/tmp/mem2.bin
touch /data/local/tmp/mem2.bin
for line in $(cat /proc/$PID/maps | grep rw | grep -v '/lib' | awk '{print $1}' | grep '-'); do
  S=$(echo $line | cut -d- -f1)
  E=$(echo $line | cut -d- -f2)
  SO=$((0x$S))
  EO=$((0x$E))
  SZ=$((EO - SO))
  if [ $SZ -gt 0 ] && [ $SZ -lt 67108864 ]; then
    dd if=/proc/$PID/mem bs=4096 skip=$((SO / 4096)) count=$((SZ / 4096)) 2>/dev/null >> /data/local/tmp/mem2.bin
  fi
done
ls -l /data/local/tmp/mem2.bin
