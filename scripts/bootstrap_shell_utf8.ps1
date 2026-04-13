param(
    [switch]$Quiet
)

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)

[void](cmd /c chcp 65001 > $null)
[Console]::InputEncoding = $utf8NoBom
[Console]::OutputEncoding = $utf8NoBom
$OutputEncoding = $utf8NoBom

$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"

if (-not $Quiet) {
    $sample = -join @(
        [char]0x0451, [char]0x0436, [char]0x0438, [char]0x043A,
        ", ",
        [char]0x043C, [char]0x043E, [char]0x0434, [char]0x0443, [char]0x043B, [char]0x044C,
        ", handshake"
    )
    Write-Output "PowerShell UTF-8 bootstrap applied."
    Write-Output "OutputEncoding=$($OutputEncoding.WebName)"
    Write-Output "ConsoleOutputEncoding=$([Console]::OutputEncoding.WebName)"
    Write-Output "PYTHONUTF8=$env:PYTHONUTF8"
    Write-Output "PYTHONIOENCODING=$env:PYTHONIOENCODING"
    Write-Output "UTF-8 sample: $sample"
}
