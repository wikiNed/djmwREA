#!/system/bin/sh
echo "=== frida-server 进程 ==="
ps -A 2>/dev/null | grep frida
ps -A 2>/dev/null | grep " /data/local/tmp/fs"
echo ""
echo "=== 端口监听 ==="
netstat -tlnp 2>/dev/null | grep 27042
echo ""
echo "=== 日志 ==="
cat /data/local/tmp/fs.log 2>/dev/null | head -20
echo ""
echo "=== 文件 ==="
ls -la /data/local/tmp/fs
