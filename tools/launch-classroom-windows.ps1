$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $root

function Test-ClassroomPython([string]$Python) {
    if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) { return $false }
    try {
        & $Python -E -B -c 'import sys; assert sys.version_info >= (3, 9); import png, classroom.server' *> $null
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
    }
}

function Get-ComponentHash([string]$Path) {
    $sha256 = [Security.Cryptography.SHA256]::Create()
    $stream = [IO.File]::OpenRead($Path)
    try {
        return [BitConverter]::ToString($sha256.ComputeHash($stream)).Replace('-', '').ToLowerInvariant()
    } finally {
        $stream.Dispose()
        $sha256.Dispose()
    }
}

function Request-DownloadRetry([string]$Name) {
    Add-Type -AssemblyName System.Windows.Forms
    $choice = [System.Windows.Forms.MessageBox]::Show(
        "The $Name download did not finish or could not be verified. Check your internet connection, then choose Retry.",
        'SiMetropolis Edu setup', 'RetryCancel', 'Warning')
    return $choice -eq 'Retry'
}

function Save-Component($Component, [string]$Destination) {
    $curl = Join-Path $env:SystemRoot 'System32\curl.exe'
    do {
        Write-Host "Downloading $($Component.name)..."
        & $curl --disable --fail --location --proto '=https' --proto-redir '=https' `
            --progress-bar --connect-timeout 15 --speed-limit 1 --speed-time 30 `
            --output $Destination $Component.url
        if ($LASTEXITCODE -eq 0 -and (Get-ComponentHash $Destination) -eq $Component.sha256) {
            return $true
        }

        Remove-Item -LiteralPath $Destination -Force -ErrorAction SilentlyContinue
    } while (Request-DownloadRetry $Component.name)
    return $false
}

function Install-ClassroomPython {
    $manifest = Join-Path $PSScriptRoot 'windows-classroom-components.json'
    $components = Get-Content -LiteralPath $manifest -Raw | ConvertFrom-Json
    $version = $components.pythonVersion
    $architecture = $env:PROCESSOR_ARCHITECTURE
    if ($env:PROCESSOR_ARCHITEW6432) { $architecture = $env:PROCESSOR_ARCHITEW6432 }
    $arch = switch ($architecture) {
        'AMD64' { 'amd64' }
        'ARM64' { 'arm64' }
        'X86' { 'win32' }
        default { throw "Unsupported Windows processor architecture: $architecture" }
    }
    $manifestHash = (Get-ComponentHash $manifest).Substring(0, 12)
    $cache = Join-Path $root 'runtime\windows'
    $runtime = Join-Path $cache "python-$version-$arch-$manifestHash"
    $python = Join-Path $runtime 'python.exe'
    if (Test-ClassroomPython $python) { return $python }

    [IO.Directory]::CreateDirectory($cache) | Out-Null
    $lockPath = "$runtime.lock"
    $lock = $null
    $waiting = $false
    while (-not $lock) {
        try {
            $lock = [IO.File]::Open($lockPath, 'OpenOrCreate', 'ReadWrite', 'None')
        } catch [IO.IOException] {
            if (($_.Exception.HResult -band 0xffff) -ne 32) { throw }
            if (-not $waiting) { Write-Host 'Waiting for SiMetropolis Edu setup in the other window...' }
            $waiting = $true
            Start-Sleep -Seconds 1
        }
    }

    $staging = Join-Path $cache ('.setup-' + [guid]::NewGuid().ToString('N'))
    try {
        if (Test-ClassroomPython $python) { return $python }
        Write-Host 'Setting up SiMetropolis Edu for this computer.'
        [IO.Directory]::CreateDirectory($staging) | Out-Null
        $archive = Join-Path $staging 'python.zip'
        $pythonComponent = [pscustomobject]@{
            name = 'Python'
            url = "https://www.python.org/ftp/python/$version/python-$version-embed-$arch.zip"
            sha256 = $components.pythonSha256.$arch
        }
        if (-not (Save-Component $pythonComponent $archive)) { return }

        Add-Type -AssemblyName System.IO.Compression.FileSystem
        [IO.Compression.ZipFile]::ExtractToDirectory($archive, $staging)
        Remove-Item -LiteralPath $archive

        # The embeddable interpreter imports these pure Python wheels directly.
        $paths = @('..\..\..')
        foreach ($wheel in $components.wheels) {
            $filename = [IO.Path]::GetFileName(([uri]$wheel.url).AbsolutePath)
            if (-not (Save-Component $wheel (Join-Path $staging $filename))) { return }
            $paths += $filename
        }
        $pathFile = Get-ChildItem -LiteralPath $staging -Filter 'python*._pth' | Select-Object -First 1
        Add-Content -LiteralPath $pathFile.FullName -Value $paths -Encoding ascii
        if (-not (Test-ClassroomPython (Join-Path $staging 'python.exe'))) {
            throw 'The downloaded classroom components could not start.'
        }

        # The lock protects replacement of an unusable runtime. Publish only a complete setup.
        if (Test-Path -LiteralPath $runtime) { Remove-Item -LiteralPath $runtime -Recurse -Force }
        [IO.Directory]::Move($staging, $runtime)
        return $python
    } finally {
        $lock.Dispose()
        if (Test-Path -LiteralPath $staging) { Remove-Item -LiteralPath $staging -Recurse -Force }
    }
}

try {
    $python = Join-Path $root '.venv\Scripts\python.exe'
    if (-not (Test-ClassroomPython $python)) { $python = Install-ClassroomPython }
    if (-not $python) { exit 0 }

    & $python -E -B -m classroom launch
    exit $LASTEXITCODE
} catch {
    Write-Host "SiMetropolis Edu could not open. $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
