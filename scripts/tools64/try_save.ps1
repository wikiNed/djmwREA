param(
    [Parameter(Mandatory=$true)][string]$Save,
    [string]$Tag = "shot",
    [int]$Wait = 26,
    [int]$AfterTap = 16,
    [switch]$TapLogin
)
$ErrorActionPreference = "Stop"
$adb = "D:\leidian\LDPlayer9\adb.exe"
$dev = "ACPRVB3C30024308"
$dir = "/sdcard/Android/data/com.HQGAMES.TopDemons/files"
$out = "E:\DSH\game\work\shots"
New-Item -ItemType Directory -Force -Path $out | Out-Null

& $adb -s $dev shell am force-stop com.HQGAMES.TopDemons | Out-Null
Start-Sleep -Milliseconds 800
& $adb -s $dev shell "mkdir -p $dir" | Out-Null
& $adb -s $dev push $Save "$dir/djmw@163.com" | Out-Null
& $adb -s $dev shell "ls -l '$dir/djmw@163.com'"

& $adb -s $dev shell am start -W --user 0 -n com.HQGAMES.TopDemons/com.unity3d.player.UnityPlayerActivity | Out-Null
Start-Sleep -Seconds $Wait
if ($TapLogin) {
    & $adb -s $dev shell "input tap 640 1225"
    Start-Sleep -Seconds $AfterTap
}
& $adb -s $dev shell "screencap -p /sdcard/s.png"
& $adb -s $dev pull /sdcard/s.png "$out\$Tag.png" | Out-Null
"shot=$out\$Tag.png md5=" + (Get-FileHash "$out\$Tag.png" -Algorithm MD5).Hash
"proc=" + (& $adb -s $dev shell "ps -A | grep -c HQGAMES").Trim()
