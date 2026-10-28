import sys
import json
from pathlib import Path
sys.path.append(r'C:\Users\William Ordiales\OneDrive\Documentos\propelling_datachellenge\_modules')
from cripto import Encryptor

# Credentials Path
credentials_dir = Path(r'C:\Users\William Ordiales\OneDrive\Documentos\propelling_datachellenge\_credentials')
key_file = credentials_dir / 'snowflake.key'
json_file = credentials_dir / 'snowflake.json'
private_key_file = Path.home() / '.snowflake' / 'dbt_rsa_key.p8'

account = 'NZCQYDN-IC18949'
user = 'DBT_USER'
private_key = private_key_file.read_text(encoding='utf-8')

enc = Encryptor()

#Gen Key
if not key_file.exists():
    enc.create_key_file(key_file, 64)
    print('Chave criada:', key_file)
else:
    print('Chave já existe, reaproveitando:', key_file)

key = enc.read_key(key_file)

#Crypt and load
credentials = {
    'account': enc.encrypt(account, key),
    'user': enc.encrypt(user, key),
    'private_key': enc.encrypt(private_key, key),
}
json_file.write_text(json.dumps(credentials, indent=2), encoding='utf-8')
print('Credenciais criptografadas em:', json_file)

#Check
check = enc.load_credentials(json_file, key_file)
print('account ok:    ', check['account'] == account)
print('user ok:       ', check['user'] == user)
print('private_key ok:', check['private_key'] == private_key)
