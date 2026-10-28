#!/system/bin/sh
# 检查 frida 注入进程的实际情况
echo "=== 当前 frida-server 版本(x86/arm) ==="
DATA=$(readlink -f /proc/5831/exe 2>/dev/null)
echo "fs exe: $DATA"
echo ""
echo "=== 游戏进程 2808 的 Zygote 来源 ==="
cat /proc/2808/status 2>/dev/null | grep -E "Name|Uid|TracerPid"
echo ""
echo "=== 是否存在 frida 注入痕迹 ==="
ls -la /data/local/tmp/*.dex 2>/dev/null | tail -3
echo ""
echo "=== 游戏进程的线程架构 ==="
ls /proc/2808/task | wc -l
grep -E "libil2cpp|libunity" /proc/2808/maps 2>/dev/null | head -2
