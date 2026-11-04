param(
    [string]$Serial = "127.0.0.1:16384",
    [string]$Adb = "E:\Program Files\Netease\MuMu\nx_main\adb.exe",
    [int]$Scale = 2,
    [string]$Out = "E:\DSH\game\djmwREA\work\live\_ui.png",
    [switch]$Text
)

# 截屏 -> 放大 -> OCR（带坐标）。放大是为了让 Unity 小字也能被识别。
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force

$raw = [System.IO.Path]::ChangeExtension($Out, ".raw.png")
& $Adb -s $Serial shell screencap -p /sdcard/_ui_raw.png 2>$null | Out-Null
& $Adb -s $Serial pull /sdcard/_ui_raw.png $raw 2>$null | Out-Null

$py = "C:\Users\86156\.dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe"
& $py -X utf8 -c "from PIL import Image; im=Image.open(r'$raw').convert('RGB'); im.resize((im.width*$Scale, im.height*$Scale), Image.LANCZOS).save(r'$Out')" 2>$null

if ($Text) {
    & "$PSScriptRoot\ocr.ps1" -Path $Out
} else {
    & "$PSScriptRoot\ocr.ps1" -Path $Out -Boxes -Scale $Scale
}