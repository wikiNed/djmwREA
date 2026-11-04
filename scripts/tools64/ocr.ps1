param([Parameter(Mandatory=$true)][string]$Path)

Add-Type -AssemblyName System.Runtime.WindowsRuntime | Out-Null

$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and
    $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
})[0]

function Await($op, $type) {
    $asTask = $asTaskGeneric.MakeGenericMethod($type)
    $netTask = $asTask.Invoke($null, @($op))
    $netTask.Wait(-1) | Out-Null
    $netTask.Result
}

[Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType = WindowsRuntime] | Out-Null
[Windows.Globalization.Language, Windows.Foundation, ContentType = WindowsRuntime] | Out-Null
[Windows.Storage.StorageFile, Windows.Foundation, ContentType = WindowsRuntime] | Out-Null
[Windows.Graphics.Imaging.BitmapDecoder, Windows.Foundation, ContentType = WindowsRuntime] | Out-Null

$lang = New-Object Windows.Globalization.Language "zh-Hans"
$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($lang)
if (-not $engine) {
    $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
}
if (-not $engine) { Write-Output "NO_OCR_ENGINE"; exit 1 }

$file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($Path)) ([Windows.Storage.StorageFile])
$stream = Await ($file.OpenAsync(0)) ([Windows.Storage.Streams.IRandomAccessStream])
$decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
$bitmap = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
$result = Await ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])

foreach ($line in $result.Lines) {
    $xs = @(); $ys = @(); $xe = @(); $ye = @()
    foreach ($wd in $line.Words) {
        $rc = $wd.BoundingRect
        $xs += [double]$rc.X; $ys += [double]$rc.Y
        $xe += ([double]$rc.X + [double]$rc.Width); $ye += ([double]$rc.Y + [double]$rc.Height)
    }
    $x0 = ($xs | Measure-Object -Minimum).Minimum
    $y0 = ($ys | Measure-Object -Minimum).Minimum
    $x1 = ($xe | Measure-Object -Maximum).Maximum
    $y1 = ($ye | Measure-Object -Maximum).Maximum
    $t = ($line.Words | ForEach-Object { $_.Text }) -join ""
    $cx = [int](($x0 + $x1) / 2); $cy = [int](($y0 + $y1) / 2)
    Write-Output ("{0},{1}  [{2},{3}-{4},{5}]  {6}" -f $cx, $cy, [int]$x0, [int]$y0, [int]$x1, [int]$y1, $t)
}
