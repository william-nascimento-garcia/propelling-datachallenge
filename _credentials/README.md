# _credentials

Local, **git-ignored** folder with the encrypted Snowflake credentials used by
`_modules/snowflake_client.py` (same layout as the IMC data platform).

| File | Content |
|---|---|
| `snowflake.json` | account, user and private key (PEM), each value encrypted with `cryptocode` (AES-GCM) |
| `snowflake.key` | password used to encrypt / decrypt `snowflake.json` |

Create or refresh both by running `generate_credentials.py` (in this folder) step by step, or from the project root:

```powershell
python _credentials\generate_credentials.py
```

Only this README and `generate_credentials.py` are committed. Never commit the `.json` or the `.key`: together they give full access to Snowflake.
