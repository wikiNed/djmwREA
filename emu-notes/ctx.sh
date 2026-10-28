#!/system/bin/sh
F=/data/local/tmp/memdump.bin
echo "=== ES3KEY 附近 200 字节上下文 ==="
grep -aboE "ES3KEY|ES3KeyFactory|ES3Oji" $F 2>/dev/null | head -5 | while IFS=: read off rest; do
  s=$((off-100)) ; [ $s -lt 0 ] && s=0
  echo "--- offset $off ($rest) ---"
  dd if=$F bs=1 skip=$s count=300 2>/dev/null | tr -c '[:print:]\n' '.'
  echo ""
done
