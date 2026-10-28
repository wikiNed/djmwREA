#!/system/bin/sh
F=/data/local/tmp/memdump.bin
echo "=== ES3 类名/命名空间 (ES3File, ES3Settings...) ==="
grep -aoE "ES3[A-Za-z]{2,20}" $F 2>/dev/null | sort -u | head -40
echo ""
echo "=== SaveManager / setting 附近 ==="
grep -aoE "SaveManager[A-Za-z]{0,20}" $F 2>/dev/null | sort -u | head -20
echo ""
echo "=== .es3 路径 ==="
grep -aoE ".{0,40}SaveFile\.es3.{0,40}" $F 2>/dev/null | sort -u | head -20
