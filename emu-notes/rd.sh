#!/system/bin/sh
# 读 .data 里 ES3 password 槽的运行时值。
# 0x35e7408(vaddr) -> maps 段 0a778000(file off 0x341c000, 页内起点 vaddr 0x3424000)
#   runtime = 0a778000 + (0x35e7408 - 0x3424000) = 0x0a93b408
PID=$1
A=$2      # 待读地址（16 进制，不带 0x）
N=${3:-16}
OFF=$(printf '%d' 0x$A)
# /proc/PID/mem 需要 bs=1 才能按字节 seek
dd if=/proc/$PID/mem bs=1 skip=$OFF count=$N 2>/dev/null | od -A x -t x8
