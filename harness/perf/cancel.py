"""Cancels every campaign order still open, through the client API like the mobile app."""
from __future__ import annotations

import csv
import json
import ssl
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from .config import Config
from .db import connect, read_csv

OPEN_STATES = {"RECEIVED", "VALIDATED", "CASH_HELD", "SECURITY_HELD", "SUBMITTED", "LIVE", "PARTIALLY_FILLED", "SUSPENDED"}


def candidates(config: Config, run_dir: Path, prefix: str) -> list[dict]:
    """(bankOrderId, secAccount) of the orders to cancel: from the database when reachable, else the ledger."""
    if config.has_db():
        connection = connect(config)
        try:
            cursor = connection.cursor()
            cursor.execute("""
                SELECT bank_order_id, client_sec_account, lifecycle_state
                  FROM orders
                 WHERE source = 'PERF' AND client_reference LIKE :prefix
                 ORDER BY order_id""", {"prefix": prefix})
            rows = [{"bankOrderId": b, "secAccount": s, "state": st} for b, s, st in cursor.fetchall()]
            cursor.close()
        finally:
            connection.close()
        return [r for r in rows if r["state"] in OPEN_STATES]
    ledger = read_csv(run_dir / "orders-ledger.csv")
    return [{"bankOrderId": r["bankOrderId"], "secAccount": r["secAccount"], "state": r.get("finalStatus", "")}
            for r in ledger if r.get("bankOrderId") and r.get("finalStatus") in {"104", "105"}]


def cancel_all(config: Config, run_dir: Path, prefix: str, rate_per_second: float = 2.0) -> dict:
    orders = candidates(config, run_dir, prefix)
    out = run_dir / "cancel-all.csv"
    context = ssl._create_unverified_context()  # internal CA on the test routes, host allowlisted by config
    results = {"candidates": len(orders), "accepted": 0, "refused": 0, "errors": 0}
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["at", "bankOrderId", "secAccount", "stateBefore", "httpStatus", "returnCode", "message"])
        for order in orders:
            body = json.dumps({"mainReference": order["bankOrderId"], "clientSecAccount": order["secAccount"]}).encode("utf-8")
            request = urllib.request.Request(config.base_url + "/xcastrade/cancel", data=body, method="POST",
                                             headers={"X-Api-Key": config.api_key, "Content-Type": "application/json",
                                                      "Accept": "application/json"})
            at = datetime.now(timezone.utc).isoformat(timespec="seconds")
            try:
                with urllib.request.urlopen(request, timeout=30, context=context) as response:
                    payload = json.loads(response.read().decode("utf-8") or "{}")
                    code = payload.get("returnCode")
                    status = response.status
                    message = payload.get("errorMessage") or ""
            except urllib.error.HTTPError as error:
                status, code, message = error.code, None, error.read().decode("utf-8", "replace")[:200]
            except Exception as error:  # transport
                status, code, message = 0, None, str(error)[:200]
            if status == 200 and code in (0, 200):
                results["accepted"] += 1
            elif status == 0:
                results["errors"] += 1
            else:
                results["refused"] += 1
            writer.writerow([at, order["bankOrderId"], order["secAccount"], order["state"], status, code, message])
            time.sleep(1.0 / rate_per_second)
    (run_dir / "cancel-all.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    return results
