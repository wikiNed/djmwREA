#!/system/bin/sh
echo "=== 进程树 (PID PPID NAME) ==="
ps -A -o PID,PPID,NAME 2>/dev/null | grep -iE "tapdemons|moe|unity|nemu" 
echo ""
echo "=== 全部含 PID 的 ps ==="
ps -A 2>/dev/null | grep -iE "TapDemons|moe|UnityPlayer"
echo ""
echo "=== maps 中含 il2cpp 的进程 ==="
for p in /proc/[0-9]*; do
  pid=${p#/proc/}
  if grep -ql il2cpp "$p/maps" 2>/dev/null; then
    echo "PID $pid  ==>  $(cat $p/cmdline 2>/dev/null | tr '\0' ' ')"
  fi
done
