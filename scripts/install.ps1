# Pure installation-plan helper. It never executes dsh or changes a profile.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][ValidatePattern('^[A-Za-z0-9][A-Za-z0-9_-]*$')][string]$Profile,
    [Parameter(Mandatory=$true)][string]$PackagePath,
    [string]$DshCommand = 'dsh'
)
$ErrorActionPreference = 'Stop'
$packageFile = (Resolve-Path -LiteralPath $PackagePath).ProviderPath
if (-not [IO.File]::Exists($packageFile) -or [IO.Path]::GetExtension($packageFile) -ne '.tgz') {
    throw 'PackagePath must identify an existing npm .tgz bundle.'
}
function Quote-PowerShellLiteral([string]$Value) { return "'" + $Value.Replace("'", "''") + "'" }
$command = '& ' + (Quote-PowerShellLiteral $DshCommand) + ' plugin --profile ' + (Quote-PowerShellLiteral $Profile) + ' add ' + (Quote-PowerShellLiteral $packageFile)
[pscustomobject]@{
    Profile = $Profile
    PackagePath = $packageFile
    Sha256 = (Get-FileHash -LiteralPath $packageFile -Algorithm SHA256).Hash.ToLowerInvariant()
    InstallCommand = $command
    Executed = $false
    Note = 'Review and run InstallCommand manually. Native DSH add selects a new bundle for activation; this helper does not run it.'
} | ConvertTo-Json -Depth 3
