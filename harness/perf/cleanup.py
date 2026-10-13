"""Removes a campaign's rows from CUSTPPRD, after a dry run that shows nothing is live.

Default policy: recette is not purged (the audit rows are the evidence). A purge is for a
formal baseline that needs clean tables, and only once every order is terminal and no hold
is still ACTIVE or PENDING at a partner.
"""
from __future__ import annotations

from .config import Config
from .db import connect, load_sql, query

BLOCKERS = ("orders_not_terminal", "cash_movement_live", "security_movement_live")


def dry_run(config: Config, prefix: str) -> dict[str, int]:
    connection = connect(config)
    try:
        _, rows = query(connection, load_sql(config, "cleanup_dry_run"), {"prefix": prefix})
    finally:
        connection.close()
    return {what: int(count) for what, count in rows}


def blockers(counts: dict[str, int]) -> list[str]:
    return [f"{key} = {counts[key]}" for key in BLOCKERS if counts.get(key, 0) > 0]


def cleanup(config: Config, prefix: str) -> dict[str, int]:
    counts = dry_run(config, prefix)
    blocked = blockers(counts)
    if blocked:
        raise SystemExit("Cleanup refused: " + ", ".join(blocked))
    if counts.get("orders", 0) == 0:
        return counts
    statements = [s.strip() for s in load_sql(config, "cleanup").split(";") if s.strip()]
    connection = connect(config)
    try:
        cursor = connection.cursor()
        deleted: dict[str, int] = {}
        for statement in statements:
            cursor.execute(statement, {"prefix": prefix})
            table = statement.split()[2]
            deleted[table] = deleted.get(table, 0) + cursor.rowcount
        connection.commit()
        cursor.close()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
    return deleted
