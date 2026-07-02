param(
    [Parameter(Mandatory = $true)][string]$Catalog,
    [Parameter(Mandatory = $true)][string]$PdfDirectory,
    [Parameter(Mandatory = $true)][string]$Output,
    [string[]]$SourceId,
    [int]$FirstPdfPage = 1,
    [int]$LastPdfPage = 0,
    [string]$PopplerBin = ""
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Runtime.WindowsRuntime

$runtimeTypes = @(
    "Windows.Media.Ocr.OcrEngine,Windows.Foundation",
    "Windows.Globalization.Language,Windows.Globalization",
    "Windows.Storage.StorageFile,Windows.Storage",
    "Windows.Storage.Streams.IRandomAccessStreamWithContentType,Windows.Storage.Streams",
    "Windows.Graphics.Imaging.BitmapDecoder,Windows.Graphics.Imaging",
    "Windows.Graphics.Imaging.SoftwareBitmap,Windows.Graphics.Imaging",
    "Windows.Media.Ocr.OcrResult,Windows.Foundation"
)
foreach ($type in $runtimeTypes) {
    Invoke-Expression "[$type,ContentType=WindowsRuntime] | Out-Null"
}

function Await-WinRt($Operation, [Type]$ResultType) {
    $method = [System.WindowsRuntimeSystemExtensions].GetMethods() |
        Where-Object {
            $_.Name -eq "AsTask" -and
            $_.IsGenericMethod -and
            $_.GetParameters().Count -eq 1 -and
            $_.GetParameters()[0].ParameterType.Name -eq "IAsyncOperation``1"
        } |
        Select-Object -First 1
    $task = $method.MakeGenericMethod($ResultType).Invoke($null, @($Operation))
    $task.Wait()
    return $task.Result
}

function Read-OcrText([string]$ImagePath, $Engine) {
    $file = Await-WinRt ([Windows.Storage.StorageFile]::GetFileFromPathAsync($ImagePath)) ([Windows.Storage.StorageFile])
    $stream = Await-WinRt ($file.OpenReadAsync()) ([Windows.Storage.Streams.IRandomAccessStreamWithContentType])
    try {
        $decoder = Await-WinRt ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
        $bitmap = Await-WinRt ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
        try {
            $result = Await-WinRt ($Engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
            return ($result.Text -replace "\s+", " ").Trim()
        }
        finally {
            $bitmap.Dispose()
        }
    }
    finally {
        $stream.Dispose()
    }
}

function Normalize-OcrText([string]$Text) {
    $normalized = ($Text -replace "\s+", " ").Trim()
    $normalized = $normalized -replace "(?<=[\u4E00-\u9FFF])\s+(?=[\u4E00-\u9FFF\u3000-\u303F\uFF00-\uFFEF])", ""
    $normalized = $normalized -replace "(?<=[\u3000-\u303F\uFF00-\uFFEF])\s+(?=[\u4E00-\u9FFF])", ""
    return $normalized
}

$catalogPath = (Resolve-Path -LiteralPath $Catalog).Path
$pdfRoot = [System.IO.Path]::GetFullPath($PdfDirectory)
[System.IO.Directory]::CreateDirectory($pdfRoot) | Out-Null
$renderRoot = Join-Path $pdfRoot ".ocr-render"
[System.IO.Directory]::CreateDirectory($renderRoot) | Out-Null
$outputPath = [System.IO.Path]::GetFullPath($Output)
[System.IO.Directory]::CreateDirectory([System.IO.Path]::GetDirectoryName($outputPath)) | Out-Null
$checkpointPath = "$outputPath.pages.jsonl"

if ($PopplerBin) {
    $env:PATH = "$PopplerBin;$env:PATH"
}
$pdftoppm = (Get-Command pdftoppm.exe -ErrorAction Stop).Source
$catalogData = Get-Content -Raw -Encoding UTF8 $catalogPath | ConvertFrom-Json
$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage(
    [Windows.Globalization.Language]::new("zh-Hans-CN")
)
if ($null -eq $engine) {
    throw "Windows OCR language zh-Hans-CN is not installed"
}

$pages = [System.Collections.Generic.List[object]]::new()
$completedPages = @{}
if (Test-Path -LiteralPath $checkpointPath) {
    Get-Content -LiteralPath $checkpointPath -Encoding UTF8 | ForEach-Object {
        if ($_.Trim()) {
            $page = $_ | ConvertFrom-Json
            $key = "$($page.source_id):$($page.pdf_page)"
            if (-not $completedPages.ContainsKey($key)) {
                $pages.Add($page)
                $completedPages[$key] = $true
            }
        }
    }
    Write-Output "Resuming from $($pages.Count) completed OCR pages"
}
elseif (Test-Path -LiteralPath $outputPath) {
    $existing = Get-Content -Raw -LiteralPath $outputPath -Encoding UTF8 | ConvertFrom-Json
    foreach ($page in $existing.pages) {
        $key = "$($page.source_id):$($page.pdf_page)"
        if (-not $completedPages.ContainsKey($key)) {
            $pages.Add($page)
            $completedPages[$key] = $true
            $page | ConvertTo-Json -Compress | Add-Content -LiteralPath $checkpointPath -Encoding UTF8
        }
    }
    Write-Output "Resuming from $($pages.Count) pages in the existing evidence pack"
}
foreach ($source in $catalogData.sources) {
    if ($SourceId -and $source.id -notin $SourceId) {
        continue
    }
    $pdfPath = Join-Path $pdfRoot "$($source.subject).pdf"
    if (-not (Test-Path -LiteralPath $pdfPath)) {
        Invoke-WebRequest -UseBasicParsing -Uri $source.official_url -OutFile $pdfPath
    }
    $actualHash = (Get-FileHash -LiteralPath $pdfPath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actualHash -ne $source.sha256) {
        throw "SHA-256 mismatch for $($source.id): expected $($source.sha256), got $actualHash"
    }
    $last = if ($LastPdfPage -gt 0) {
        [Math]::Min($LastPdfPage, [int]$source.page_count)
    } else {
        [int]$source.page_count
    }
    for ($pdfPage = $FirstPdfPage; $pdfPage -le $last; $pdfPage++) {
        $pageKey = "$($source.id):$pdfPage"
        if ($completedPages.ContainsKey($pageKey)) {
            continue
        }
        $prefix = Join-Path $renderRoot "$($source.id)-$pdfPage"
        & $pdftoppm -f $pdfPage -l $pdfPage -singlefile -png -r 160 $pdfPath $prefix
        if ($LASTEXITCODE -ne 0) {
            throw "pdftoppm failed for $($source.id) page $pdfPage"
        }
        $imagePath = "$prefix.png"
        try {
            $text = Normalize-OcrText (Read-OcrText $imagePath $engine)
            if (-not $text) {
                $text = "[OCR_EMPTY_PAGE]"
            }
            $logicalPage = if ($pdfPage -gt [int]$source.logical_page_offset) {
                $pdfPage - [int]$source.logical_page_offset
            } else {
                $null
            }
            $pageRecord = [ordered]@{
                source_id = $source.id
                pdf_page = $pdfPage
                logical_page = $logicalPage
                text = $text
                image_sha256 = (Get-FileHash -LiteralPath $imagePath -Algorithm SHA256).Hash.ToLowerInvariant()
            }
            $pages.Add($pageRecord)
            $completedPages[$pageKey] = $true
            $pageRecord | ConvertTo-Json -Compress | Add-Content -LiteralPath $checkpointPath -Encoding UTF8
            if ($pdfPage -eq $FirstPdfPage -or $pdfPage % 10 -eq 0 -or $pdfPage -eq $last) {
                Write-Output "OCR $($source.id): page $pdfPage/$last (total completed: $($pages.Count))"
            }
        }
        finally {
            Remove-Item -LiteralPath $imagePath -Force -ErrorAction SilentlyContinue
        }
    }
}

$normalizedPages = @(
    $pages |
        Sort-Object source_id, pdf_page |
        ForEach-Object {
            [ordered]@{
                source_id = $_.source_id
                pdf_page = $_.pdf_page
                logical_page = $_.logical_page
                text = Normalize-OcrText $_.text
                image_sha256 = $_.image_sha256
            }
        }
)
$payload = [ordered]@{
    schema_version = "1.0"
    ocr_engine = "Windows.Media.Ocr/zh-Hans-CN"
    pages = $normalizedPages
}
$payload | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $outputPath -Encoding UTF8
Write-Output $outputPath
