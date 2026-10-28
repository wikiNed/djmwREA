#!/system/bin/sh
# 用 gdb/memtool 硬扫不现实；改为读取游戏进程内存里的字符串
# 先看进程内存中是否有 ES3 相关字符串
PID=2808
echo "=== 扫描 maps 的可读匿名段 ==="
grep -E "rw-p" /proc/$PID/maps 2>/dev/null | head -5
echo ""
echo "=== Unity 加载的资源/脚本路径 ==="
grep -iE "il2cpp|global-metadata|resources" /proc/$PID/maps 2>/dev/null | awk '{print $6}' | sort -u
echo ""
echo "=== 该进程打开的 fd 里是否有 es3 ==="
ls -la /proc/$PID/fd 2>/dev/null | grep -iE "es3|save" 
