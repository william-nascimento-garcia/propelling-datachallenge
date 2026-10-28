# Copy this file to scripts\set_env.ps1 (ignored by git), fill in your values,
# then load it in every new terminal before running dbt:
#
#     . .\scripts\set_env.ps1
#
# SNOWFLAKE_ACCOUNT is the account identifier, format <orgname>-<accountname>.
# Find it in Snowsight: bottom-left menu (your name) > Account > "View account details".

$env:SNOWFLAKE_ACCOUNT          = "ABCDEFG-XY12345"
$env:SNOWFLAKE_USER             = "DBT_USER"
$env:SNOWFLAKE_PRIVATE_KEY_PATH = "$env:USERPROFILE\.snowflake\dbt_rsa_key.p8"
$env:DBT_DEV_NAME               = "WILLIAM"   # dev schemas: DEV_WILLIAM_BRONZE / _SILVER / _GOLD


Write-Host "Snowflake env loaded for $env:SNOWFLAKE_USER @ $env:SNOWFLAKE_ACCOUNT" -ForegroundColor Green
