#!/system/bin/sh
D=/data/local/tmp/memd
echo "=== ASCII SaveFile ==="
for f in $D/seg_*.bin; do
  if [ -s "$f" ]; then
    if grep -qaF 'SaveFile' "$f"; then
      echo "HIT-ascii $f"
    fi
  fi
done
echo "=== ASCII es3 ==="
for f in $D/seg_*.bin; do
  if [ -s "$f" ]; then
    if grep -qaF '.es3' "$f"; then
      echo "HIT-es3 $f"
    fi
  fi
done
echo "=== ASCII ES3 ==="
for f in $D/seg_*.bin; do
  if [ -s "$f" ]; then
    if grep -qaF 'ES3' "$f"; then
      echo "HIT-ES3 $f"
    fi
  fi
done
echo "done"
