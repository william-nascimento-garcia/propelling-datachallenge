from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional, Sequence

import pandas as pd
import snowflake.connector
from cryptography.hazmat.primitives import serialization
from snowflake.connector import SnowflakeConnection
try:  # works both as "from _modules import ..." and with _modules on sys.path
    from .cripto import Encryptor
except ImportError:
    from cripto import Encryptor

LAYERS = ("bronze", "silver", "gold")
# Schemas outside the medallion layers: same name in every target.
# AUDIT holds the dbt run log (macros/log_run_results.sql).
SHARED_SCHEMAS = {"audit": "AUDIT"}
TARGETS = ("dev", "prod")

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CREDENTIALS_FILE = PROJECT_ROOT / "_credentials" / "snowflake.json"
DEFAULT_KEY_FILE = PROJECT_ROOT / "_credentials" / "snowflake.key"


def load_encrypted_credentials() -> dict[str, str]:
    """Decrypted credentials from _credentials/ (or the paths in the env vars), {} if absent."""
    json_file = Path(os.getenv("SNOWFLAKE_CREDENTIALS_FILE", DEFAULT_CREDENTIALS_FILE))
    key_file = Path(os.getenv("SNOWFLAKE_CRYPTO_KEY_FILE", DEFAULT_KEY_FILE))
    if not (json_file.is_file() and key_file.is_file()):
        return {}
    return Encryptor().load_credentials(json_file, key_file)


@dataclass
class QueryResult:
    """Raw result of a query: column names + rows, plus execution metadata."""

    sql: str
    columns: list[str]
    rows: list[tuple]
    elapsed_seconds: float
    query_id: Optional[str] = None
    schema: Optional[str] = None
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def rowcount(self) -> int:
        return len(self.rows)

    def __repr__(self) -> str:
        return (
            f"QueryResult(rows={self.rowcount}, columns={len(self.columns)}, "
            f"elapsed={self.elapsed_seconds:.2f}s, schema={self.schema}, query_id={self.query_id})"
        )


class SnowflakeClient:
    """
    Thin wrapper around snowflake-connector-python for the TPC-H Medallion project.

    Credentials resolution, in order:
      1. arguments passed explicitly to the constructor;
      2. encrypted credentials in _credentials/snowflake.json, decrypted with
         _credentials/snowflake.key (via _modules/cripto.py);
      3. plain environment variables used by dbt (SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER,
         SNOWFLAKE_PRIVATE_KEY_PATH) as a fallback.
    Schema naming follows macros/generate_schema_name.sql:
        prod -> BRONZE / SILVER / GOLD
        dev  -> DEV_<NAME>_BRONZE / DEV_<NAME>_SILVER / DEV_<NAME>_GOLD
    """

    def __init__(
        self,
        account: Optional[str] = None,
        user: Optional[str] = None,
        private_key_path: Optional[str] = None,
        role: str = "TRANSFORMER",
        warehouse: str = "WH_TRANSFORM",
        database: str = "TPCH_ANALYTICS",
        target: str = "dev",
        layer: str = "gold",
        dev_name: Optional[str] = None,
    ) -> None:
        embedded = load_encrypted_credentials()
        self.credentials_source = "encrypted" if embedded else "environment"

        self.account = account or embedded.get("account") or os.getenv("SNOWFLAKE_ACCOUNT")
        self.user = user or embedded.get("user") or os.getenv("SNOWFLAKE_USER")
        # PEM text of the private key (only when it comes from the encrypted file)
        self._private_key_pem: Optional[str] = None if private_key_path else embedded.get("private_key")
        self.private_key_path = private_key_path or os.getenv("SNOWFLAKE_PRIVATE_KEY_PATH")

        if not self.account or not self.user or not (self._private_key_pem or self.private_key_path):
            raise ValueError(
                "No Snowflake credentials found. Run scripts/encrypt_credentials.py to create "
                "_credentials/snowflake.json + snowflake.key, or set SNOWFLAKE_ACCOUNT / "
                "SNOWFLAKE_USER / SNOWFLAKE_PRIVATE_KEY_PATH."
            )
        self.role = role
        self.warehouse = warehouse
        self.database = database
        self.dev_name = (dev_name or os.getenv("DBT_DEV_NAME", "WILLIAM")).upper()

        self.target = self._validate_target(target)
        self.layer = self._validate_layer(layer)
        self._conn: Optional[SnowflakeConnection] = None

    # ------------------------------------------------------------------ #
    # Connection
    # ------------------------------------------------------------------ #
    def connect(self) -> "SnowflakeClient":
        """Open the connection (key-pair auth) and point it to the current layer."""
        if self.is_connected:
            return self
        self._conn = snowflake.connector.connect(
            account=self.account,
            user=self.user,
            **self._private_key_args(),
            role=self.role,
            warehouse=self.warehouse,
            database=self.database,
            schema=self.schema(),
            session_parameters={"QUERY_TAG": "jupyter_exploration"},
        )
        return self

    def _private_key_args(self) -> dict[str, Any]:
        """Key-pair auth: decrypted PEM in memory (never written to disk), or a key file."""
        if self._private_key_pem:
            key = serialization.load_pem_private_key(self._private_key_pem.encode(), password=None)
            der = key.private_bytes(
                encoding=serialization.Encoding.DER,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
            return {"private_key": der}
        if not Path(self.private_key_path).is_file():
            raise FileNotFoundError(
                f"Private key not found at {self.private_key_path}. "
                "Run scripts/generate_keypair.ps1 or set SNOWFLAKE_PRIVATE_KEY_PATH."
            )
        return {"private_key_file": self.private_key_path}

    def close(self) -> None:
        """Close the connection (safe to call more than once)."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    @property
    def is_connected(self) -> bool:
        return self._conn is not None and not self._conn.is_closed()

    def __enter__(self) -> "SnowflakeClient":
        return self.connect()

    def __exit__(self, *exc) -> None:
        self.close()

    def __repr__(self) -> str:
        status = "connected" if self.is_connected else "disconnected"
        return (
            f"SnowflakeClient({self.user}@{self.account}, credentials={self.credentials_source}, target={self.target}, "
            f"schema={self.database}.{self.schema()}, {status})"
        )

    # ------------------------------------------------------------------ #
    # Layer / environment selection
    # ------------------------------------------------------------------ #
    def schema(self, layer: Optional[str] = None, target: Optional[str] = None) -> str:
        """Schema name of a layer in a target, without changing the session."""
        layer = self._validate_layer(layer or self.layer)
        target = self._validate_target(target or self.target)
        if layer in SHARED_SCHEMAS:
            return SHARED_SCHEMAS[layer]
        if target == "prod":
            return layer.upper()
        return f"DEV_{self.dev_name}_{layer.upper()}"

    def set_layer(self, layer: str, target: Optional[str] = None) -> str:
        """
        Choose the layer (bronze / silver / gold, or audit for the dbt run log)
        and optionally the environment (dev / prod). Unqualified table names in later queries resolve to it.
        Returns the fully qualified schema.
        """
        self.layer = self._validate_layer(layer)
        if target is not None:
            self.target = self._validate_target(target)
        if self.is_connected:
            self._conn.cursor().execute(f"use schema {self.database}.{self.schema()}")
        return f"{self.database}.{self.schema()}"

    def set_target(self, target: str) -> str:
        """Switch environment (dev / prod), keeping the current layer."""
        return self.set_layer(self.layer, target=target)

    def list_tables(self, layer: Optional[str] = None) -> pd.DataFrame:
        """Tables of a layer in the current target, with row counts and size."""
        sch = self.schema(layer)
        return self.to_pandas(self.query(
            f"""
            select table_name, row_count, round(bytes / 1024 / 1024, 1) as size_mb
            from {self.database}.information_schema.tables
            where table_schema = '{sch}'
            order by table_name
            """
        ))

    # ------------------------------------------------------------------ #
    # Queries
    # ------------------------------------------------------------------ #
    def query(self, sql: str, params: Optional[Sequence[Any] | dict] = None) -> QueryResult:
        """
        Execute a SQL statement and return the raw result.

        - Unqualified tables resolve to the layer chosen with set_layer().
        - {bronze} / {silver} / {gold} are replaced by the schemas of the
          current target; {audit} by the shared AUDIT schema.
        - params are bound by the connector (use %s or %(name)s in the SQL),
          never concatenate user input into the SQL string.
        """
        if not self.is_connected:
            self.connect()
        rendered = self._render(sql)
        start = time.perf_counter()
        with self._conn.cursor() as cur:
            cur.execute(rendered, params)
            columns = [col[0].lower() for col in cur.description] if cur.description else []
            rows = cur.fetchall() if cur.description else []
            query_id = cur.sfqid
        return QueryResult(
            sql=rendered,
            columns=columns,
            rows=rows,
            elapsed_seconds=time.perf_counter() - start,
            query_id=query_id,
            schema=f"{self.database}.{self.schema()}",
        )

    @staticmethod
    def to_pandas(result: QueryResult) -> pd.DataFrame:
        """
        Convert a QueryResult into a pandas DataFrame.
        Snowflake NUMBER columns arrive as Decimal; they are converted to
        int/float so pandas can aggregate and plot them.
        """
        df = pd.DataFrame(result.rows, columns=result.columns)
        for col in df.columns:
            if df[col].dtype == object:
                non_null = df[col].dropna()
                if non_null.empty or not non_null.map(lambda v: isinstance(v, Decimal)).all():
                    continue
                is_integer = all(v == v.to_integral_value() for v in non_null)
                if is_integer and len(non_null) == len(df):
                    df[col] = df[col].astype("int64")
                elif is_integer:
                    df[col] = df[col].astype(float).astype("Int64")   # nullable integer
                else:
                    df[col] = df[col].astype(float)
        return df

    def query_df(self, sql: str, params: Optional[Sequence[Any] | dict] = None) -> pd.DataFrame:
        """Shortcut: query() + to_pandas()."""
        return self.to_pandas(self.query(sql, params))

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #
    def _render(self, sql: str) -> str:
        for layer in (*LAYERS, *SHARED_SCHEMAS):
            sql = sql.replace("{" + layer + "}", f"{self.database}.{self.schema(layer)}")
        return sql

    @staticmethod
    def _validate_layer(layer: str) -> str:
        layer = layer.lower().strip()
        valid = (*LAYERS, *SHARED_SCHEMAS)
        if layer not in valid:
            raise ValueError(f"Invalid layer '{layer}'. Use one of: {', '.join(valid)}")
        return layer

    @staticmethod
    def _validate_target(target: str) -> str:
        target = target.lower().strip()
        if target not in TARGETS:
            raise ValueError(f"Invalid target '{target}'. Use one of: {', '.join(TARGETS)}")
        return target
