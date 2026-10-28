#!/system/bin/sh
pkg=game.taptap.HQGAMES.TapDemons
echo "=== /data/data/$pkg 近期文件 ==="
find /data/data/$pkg -type f -newermt "-40 minutes" 2>/dev/null | grep -viE "pangle|taptap|qq\.e|turing|bugly|lcdpr|gdt" | head -40
echo ""
echo "=== 全盘 playerDate 搜索 ==="
find /data /sdcard -iname "playerDate*" -o -iname "*.es3" 2>/dev/null | head -20
echo ""
echo "=== 全盘近期修改的 .json / .dat (排除SDK) ==="
find /data/user/0/$pkg /sdcard/Android/data/$pkg -type f 2>/dev/null | grep -viE "pangle|taptap|qq\.e|turing|bugly|lcdpr|gdt|Analytics" | head -40
echo ""
echo "=== 目录树(2层) ==="
ls -la /data/data/$pkg/
