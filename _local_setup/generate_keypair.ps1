# Generates the RSA key pair used by dbt to authenticate to Snowflake.
# Uses the openssl.exe that ships with Git for Windows.
# The keys are stored OUTSIDE the project/OneDrive folder, in %USERPROFILE%\.snowflake

$ErrorActionPreference = "Stop"

$openssl = "C:\Program Files\Git\usr\bin\openssl.exe"
if (-not (Test-Path $openssl)) {
    $openssl = (Get-Command openssl -ErrorAction SilentlyContinue).Source
}
if (-not $openssl) { throw "openssl not found. Install Git for Windows first." }

$keyDir = Join-Path $env:USERPROFILE ".snowflake"
New-Item -ItemType Directory -Force -Path $keyDir | Out-Null
$private = Join-Path $keyDir "dbt_rsa_key.p8"
$public  = Join-Path $keyDir "dbt_rsa_key.pub"

if (Test-Path $private) { throw "$private already exists. Delete it first if you really want a new key." }

$tmp = Join-Path $keyDir "tmp_rsa.pem"
& $openssl genrsa -out $tmp 2048
& $openssl pkcs8 -topk8 -inform PEM -in $tmp -out $private -nocrypt
Remove-Item $tmp
& $openssl rsa -in $private -pubout -out $public

# Single-line public key, ready to paste into _snowflake_setup/01_snowflake_setup.sql
$pubOneLine = (Get-Content $public | Where-Object { $_ -notmatch "-----" }) -join ""

Write-Host ""
Write-Host "Private key : $private   (never commit / share this file)"
Write-Host "Public key  : $public"
Write-Host ""
Write-Host "Paste this value into RSA_PUBLIC_KEY in _snowflake_setup/01_snowflake_setup.sql:" -ForegroundColor Cyan
Write-Host $pubOneLine
Set-Clipboard -Value $pubOneLine
Write-Host "(copied to clipboard)" -ForegroundColor DarkGray
