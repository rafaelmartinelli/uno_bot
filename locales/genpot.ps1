Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$currentVer = '1.0'
$projectRoot = Split-Path -Parent $PSScriptRoot
$outputPot = Join-Path $projectRoot 'locales\unobot.pot'
$sourceRoot = Join-Path $projectRoot 'unobot'

$normalizedProjectRoot = (Resolve-Path -LiteralPath $projectRoot).Path.TrimEnd([char[]]@('\', '/'))
$pythonFiles = Get-ChildItem -Path $sourceRoot -Recurse -File -Filter '*.py' |
    ForEach-Object {
        $fullPath = $_.FullName
        if (-not $fullPath.StartsWith($normalizedProjectRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "File '$fullPath' is outside project root '$normalizedProjectRoot'."
        }

        # Keep xgettext source references portable and repo-relative.
        $fullPath.Substring($normalizedProjectRoot.Length).TrimStart([char[]]@('\', '/')) -replace '\\', '/'
    }

if (-not $pythonFiles) {
    throw "No Python files found under '$sourceRoot'."
}

$xgettextArgs = @(
    '--output', $outputPot,
    '--foreign-user',
    '--directory', $projectRoot,
    '--package-name', 'uno_bot',
    '--package-version', $currentVer,
    '--msgid-bugs-address', 'uno@jhoeke.de',
    '--keyword=__',
    '--keyword=_',
    '--keyword=_:1,2',
    '--keyword=__:1,2'
) + $pythonFiles

& xgettext @xgettextArgs

if ($LASTEXITCODE -ne 0) {
    throw "xgettext failed with exit code $LASTEXITCODE"
}
