#!/system/bin/sh
# 从游戏进程内存扫描疑似 ES3 密钥
# 思路：ES3Settings 的 encryptionPassword 是 string，会被 ES3 用于 AES
#       AES 需要 16/24/32 字节密钥 -> 原字符串长度常见 16/24/32（或任意长度经 MD5/SHA 派生）
# 这里扫描 rw- 匿名堆段里的可打印 ASCII 串，过滤出长度 8~64 的
PID=2808
OUT=/data/local/tmp/memdump.bin
rm -f $OUT
: > $OUT
for rng in $(awk '$2 ~ /^rw/ {print $1}' /proc/$PID/maps 2>/dev/null); do
  start=${rng%-*}
  end=${rng#*-}
  # 用 dd 读 /proc/pid/mem 需要跳过不可读段，这里用 busybox dd 尽力而为
  dd if=/proc/$PID/mem bs=4096 skip=$(($((0x$start))/4096)) count=$(( ( $((0x$end))-$((0x$start)) )/4096 )) >>$OUT 2>/dev/null
done
echo "dump size: $(stat -c %s $OUT 2>/dev/null)"
grep -aoE '[ -~]{12,40}' $OUT 2>/dev/null | sort -u | grep -iE 'es3|encrypt|passwo|SaveFile|\.es3' | head -40
