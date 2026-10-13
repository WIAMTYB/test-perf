"""CUSTPPRD access for the analysis and the cleanup (python-oracledb thin, no client)."""
from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from .config import Config


def connect(config: Config):
    import oracledb  # imported lazily so the harness runs without the driver for oc-only commands

    return oracledb.connect(user=config.db_user, password=config.db_password, dsn=config.db_dsn)


def load_sql(config: Config, name: str) -> str:
    path = config.sql_dir / f"{name}.sql"
    if not path.exists():
        raise SystemExit(f"SQL file not found: {path}")
    # Strip comment lines so a trailing comment never ends up after the last clause.
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if not line.strip().startswith("--")]
    return "\n".join(lines).strip().rstrip(";")


def query(connection, sql: str, params: dict | None = None) -> tuple[list[str], list[tuple]]:
    cursor = connection.cursor()
    cursor.execute(sql, params or {})
    columns = [d[0].lower() for d in cursor.description]
    rows = cursor.fetchall()
    cursor.close()
    return columns, rows


def write_csv(path: Path, columns: list[str], rows: list[tuple]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(columns)
        for row in rows:
            writer.writerow([_cell(v) for v in row])
    return len(rows)


def _cell(value):
    if isinstance(value, datetime):
        return value.isoformat(timespec="milliseconds")
    if hasattr(value, "read"):  # LOB
        return value.read()
    return value


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))
