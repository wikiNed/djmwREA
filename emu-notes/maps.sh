#!/system/bin/sh
echo "=== 2808 maps 中的 il2cpp/unity 行 ==="
grep -iE "il2cpp|libunity|libmain|global-metadata" /proc/2808/maps 2>/dev/null | head -20
echo ""
echo "=== 哪个 .so 名称 ==="
awk '{print $6}' /proc/2808/maps 2>/dev/null | grep -i '\.so$' | sort -u | grep -iE "il2cpp|unity|main|moe" 
echo ""
echo "=== frida-server 是否还在 ==="
ps -A 2>/dev/null | grep -c " /data/local/tmp/fs"
