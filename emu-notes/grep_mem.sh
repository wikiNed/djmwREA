#!/system/bin/sh
F=/data/local/tmp/memdump.bin
echo "=== 文件大小 ==="
ls -la $F
echo ""
echo "=== ES3 关键字 ==="
grep -aoE "[ -~]{6,60}" $F 2>/dev/null | grep -iE "es3|encrypt|password|SaveFile" | sort -u | head -60
echo ""
echo "=== 可能的密钥候选 (16/24/32 字符可打印串) ==="
grep -aoE "[A-Za-z0-9_\-!@#\$%^&*+=]{16,32}" $F 2>/dev/null | sort | uniq -c | sort -rn | head -40
