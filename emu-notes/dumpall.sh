#!/system/bin/sh
# dump 指定 PID 的可读可写内存段到 /sdcard/mem/
# 用 su 0 执行，避免 SELinux 与 /proc 权限问题。
# 用法: sh dumpall.sh <pid> <outdir> [max_segs] [min_size]
PID=$1
OUT=$2
MAXN=${3:-20}
MINSZ=${4:-1048576}

mkdir -p "$OUT"
rm -f "$OUT"/*.bin "$OUT"/list.txt

# 解析 maps：只要 rw- 或 r-- 且大小 >= MINSZ 的匿名/堆段
: > "$OUT/list.txt"
while read -r range perms rest; do
    case "$perms" in
        rw-p|r--p|rw-s) ;;
        *) continue ;;
    esac
    start=${range%-*}
    end=${range#*-}
    s=$(printf "%d" "0x$start" 2>/dev/null) || continue
    e=$(printf "%d" "0x$end" 2>/dev/null) || continue
    sz=$((e - s))
    if [ "$sz" -ge "$MINSZ" ]; then
        echo "$start $s $sz $perms" >> "$OUT/list.txt"
    fi
done < /proc/$PID/maps

n=0
while read -r hexstart soff sz perms; do
    n=$((n + 1))
    [ "$n" -gt "$MAXN" ] && break
    outf="$OUT/m_${hexstart}.bin"
    # 用 dd 的 skip_bytes / count_bytes（toybox 支持）比 bs=1 快得多
    dd if=/proc/$PID/mem of="$outf" bs=4096 skip=$((soff / 4096)) count=$((sz / 4096 + 1)) 2>/dev/null
    # 上面按页对齐会多读，用 head -c 截断到精确大小
    head -c "$sz" "$outf" > "$outf.tmp" 2>/dev/null && mv "$outf.tmp" "$outf"
    echo "[$n] $hexstart off=$soff size=$sz $perms -> $(wc -c < "$outf")"
done < "$OUT/list.txt"
echo "done"
