"""
Credential encryption helpers (same approach used in the IMC data platform).

Credentials are stored in a JSON file whose values are encrypted with
cryptocode (AES-GCM, key derived with scrypt). A separate key file holds the
password used to encrypt / decrypt. Both live in the project's _credentials/
folder, which is git-ignored.

    from cripto import Encryptor

    enc = Encryptor()
    enc.create_key_file("_credentials/snowflake.key", 64)
    enc.encrypt_credentials("_credentials/snowflake.json", "_credentials/snowflake.key")
    creds = enc.load_credentials("_credentials/snowflake.json", "_credentials/snowflake.key")
"""

from __future__ import annotations

import json
import secrets
import string
from pathlib import Path
from typing import Any

import cryptocode


class Encryptor:
    """Encrypts / decrypts the values of a credentials JSON (flat or one level nested)."""

    TOKEN_CHARS = string.ascii_letters + string.digits + "!@#$%&*()-_=+"

    # ------------------------------------------------------------------ #
    # Keys
    # ------------------------------------------------------------------ #
    def token_generator(self, length: int) -> str:
        """Random key using `secrets` (cryptographically secure, unlike `random`)."""
        return "".join(secrets.choice(self.TOKEN_CHARS) for _ in range(length))

    def create_key_file(self, file_name: str | Path, token_length: int = 64) -> str:
        """Create the key file. Refuses to overwrite: a new key makes old credentials unreadable."""
        path = Path(file_name)
        if path.exists():
            raise FileExistsError(f"{path} already exists. Delete it only if you will re-encrypt everything.")
        path.parent.mkdir(parents=True, exist_ok=True)
        key = self.token_generator(token_length)
        path.write_text(key, encoding="utf-8")
        return key

    @staticmethod
    def read_key(key_file: str | Path) -> str:
        return Path(key_file).read_text(encoding="utf-8").strip()

    # ------------------------------------------------------------------ #
    # Single values
    # ------------------------------------------------------------------ #
    def encrypt(self, text: str, key: str) -> str:
        return cryptocode.encrypt(text, key)

    def decrypt(self, text: str, key: str) -> str:
        plain = cryptocode.decrypt(text, key)
        if plain is False:
            raise ValueError("Decryption failed: wrong key or corrupted value.")
        return plain

    # ------------------------------------------------------------------ #
    # Whole credentials dict / file
    # ------------------------------------------------------------------ #
    def _apply(self, credentials: dict[str, Any], func, key: str) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for k, v in credentials.items():
            if isinstance(v, str):
                result[k] = func(v, key)
            elif isinstance(v, dict):
                result[k] = {j: func(x, key) for j, x in v.items()}
            else:
                result[k] = v
        return result

    def encrypt_dict(self, credentials: dict[str, Any], key: str) -> dict[str, Any]:
        return self._apply(credentials, self.encrypt, key)

    def decrypt_dict(self, credentials: dict[str, Any], key: str) -> dict[str, Any]:
        return self._apply(credentials, self.decrypt, key)

    def encrypt_credentials(self, json_file: str | Path, key_file: str | Path) -> dict[str, Any]:
        """Encrypt, in place, a JSON file that still holds plain-text values."""
        path = Path(json_file)
        encrypted = self.encrypt_dict(json.loads(path.read_text(encoding="utf-8")), self.read_key(key_file))
        path.write_text(json.dumps(encrypted, indent=2), encoding="utf-8")
        return encrypted

    def save_credentials(self, credentials: dict[str, Any], json_file: str | Path, key_file: str | Path) -> None:
        """Encrypt in memory and write: the plain-text values never touch the disk."""
        path = Path(json_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        encrypted = self.encrypt_dict(credentials, self.read_key(key_file))
        path.write_text(json.dumps(encrypted, indent=2), encoding="utf-8")

    def load_credentials(self, json_file: str | Path, key_file: str | Path) -> dict[str, Any]:
        """Read the encrypted JSON and return the decrypted values."""
        encrypted = json.loads(Path(json_file).read_text(encoding="utf-8"))
        return self.decrypt_dict(encrypted, self.read_key(key_file))
