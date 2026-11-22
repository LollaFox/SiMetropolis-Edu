param([string]$OutputDirectory)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
if (-not $OutputDirectory) { $OutputDirectory = Join-Path $root 'dist' }
$output = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($OutputDirectory)
[IO.Directory]::CreateDirectory($output) | Out-Null

$files = @(
    'Open SiMetropolis Edu.cmd'
    'LICENSE'
    'tools/launch-classroom-windows.ps1'
    'tools/windows-classroom-components.json'
)
$files += Get-ChildItem -LiteralPath (Join-Path $root 'classroom') -File -Filter '*.py' |
    ForEach-Object { 'classroom/' + $_.Name }
$static = Join-Path $root 'classroom\static'
$files += Get-ChildItem -LiteralPath $static -File -Recurse |
    ForEach-Object { 'classroom/static/' + $_.FullName.Substring($static.Length + 1).Replace('\', '/') }

Add-Type -AssemblyName System.IO.Compression.FileSystem
$zipPath = Join-Path $output 'SiMetropolis-Edu-Windows.zip'
$temporaryZip = Join-Path $output ([guid]::NewGuid().ToString('N') + '.zip')
try {
    $zip = [IO.Compression.ZipFile]::Open($temporaryZip, 'Create')
    try {
        foreach ($file in $files) {
            [IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
                $zip, (Join-Path $root $file), $file, 'Optimal') | Out-Null
        }
    } finally {
        $zip.Dispose()
    }
    Move-Item -LiteralPath $temporaryZip -Destination $zipPath -Force
    Write-Output $zipPath
} finally {
    if (Test-Path -LiteralPath $temporaryZip) { Remove-Item -LiteralPath $temporaryZip }
}
