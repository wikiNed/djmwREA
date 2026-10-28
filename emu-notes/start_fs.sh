#!/system/bin/sh
# 干净地重启 arm64 frida-server
pkill -f /data/local/tmp/fs 2>/dev/null
pkill -f /data/local/tmp/fsa 2>/dev/null
sleep 1
rm -f /data/local/tmp/fsa.log
setsid /data/local/tmp/fsa -l 0.0.0.0:27042 >/data/local/tmp/fsa.log 2>&1 &
sleep 4
echo "=== 进程 ==="
ps -A 2>/dev/null | grep fsa
echo "=== 端口 ==="
netstat -tln 2>/dev/null | grep 27042
echo "=== 日志 ==="
cat /data/local/tmp/fsa.log 2>/dev/null
