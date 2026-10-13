"""Post-run analysis: the campaign's orders in the database, the ledger, the Gatling stats.

Re-runnable at any time from the campaign prefix and the run window: nothing here depends
on the sampler having been alive.
"""
from __future__ import annotations

import json
import statistics
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .config import Config
from .db import connect, load_sql, query, read_csv, write_csv

DB_QUERIES = ["campaign_orders", "step_durations", "broker_calls", "positionminute_calls",
              "security_calls", "custody_calls", "callback_lag", "rejections", "holds"]
WINDOW_QUERIES = {"broker_calls", "positionminute_calls", "security_calls", "custody_calls"}
# Tables whose timestamp column is DEFAULT SYSTIMESTAMP: the database clock, not the
# application's. On recette that clock is hours away from the pods', so their window is
# shifted by the offset measured at analysis time.
DB_CLOCK_QUERIES = {"positionminute_calls", "security_calls", "custody_calls"}


def db_clock_offset(connection) -> timedelta:
    """Database UTC minus workstation UTC, measured now."""
    cursor = connection.cursor()
    cursor.execute("SELECT SYS_EXTRACT_UTC(SYSTIMESTAMP) FROM dual")
    (db_now,) = cursor.fetchone()
    cursor.close()
    local_now = datetime.now(timezone.utc).replace(tzinfo=None)
    return db_now.replace(tzinfo=None) - local_now


def analyze(config: Config, run_dir: Path, prefix: str, start: datetime, end: datetime) -> dict:
    result: dict = {"prefix": prefix, "window": {"start": start.isoformat(), "end": end.isoformat()}, "db": {}}
    db_dir = run_dir / "db"
    db_dir.mkdir(parents=True, exist_ok=True)
    if config.has_db():
        connection = connect(config)
        try:
            start_naive = start.astimezone(timezone.utc).replace(tzinfo=None)
            end_naive = end.astimezone(timezone.utc).replace(tzinfo=None)
            offset = db_clock_offset(connection)
            result["dbClockOffsetSeconds"] = round(offset.total_seconds())
            for name in DB_QUERIES:
                params = {"prefix": prefix}
                if name in WINDOW_QUERIES:
                    shift = offset if name in DB_CLOCK_QUERIES else timedelta(0)
                    params.update({"start_ts": start_naive + shift, "end_ts": end_naive + shift})
                try:
                    columns, rows = query(connection, load_sql(config, name), params)
                    count = write_csv(db_dir / f"{name}.csv", columns, rows)
                    result["db"][name] = {"rows": count}
                except Exception as error:
                    result["db"][name] = {"error": str(error)[:300]}
        finally:
            connection.close()
    else:
        result["db"]["skipped"] = "PERF_DB_USER / PERF_DB_PASSWORD not set"
    result["orders"] = _order_summary(db_dir / "campaign_orders.csv")
    result["ledger"] = ledger_summary(run_dir / "orders-ledger.csv")
    result["gatling"] = gatling_summary(run_dir / "gatling")
    result["levels"] = level_summary(run_dir)
    (run_dir / "analysis.json").write_text(json.dumps(result, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return result


def _order_summary(path: Path) -> dict:
    rows = read_csv(path)
    by_state: dict[str, int] = {}
    for row in rows:
        by_state[row.get("lifecycle_state", "?")] = by_state.get(row.get("lifecycle_state", "?"), 0) + 1
    return {"total": len(rows), "byState": by_state}


def percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = (len(ordered) - 1) * p
    low = int(index)
    high = min(low + 1, len(ordered) - 1)
    return ordered[low] + (ordered[high] - ordered[low]) * (index - low)


def ledger_summary(path: Path) -> dict:
    rows = read_csv(path)
    if not rows:
        return {"orders": 0}
    times = [float(r["timeToSubmittedMs"]) for r in rows if r.get("timeToSubmittedMs")]
    by_status: dict[str, int] = {}
    for row in rows:
        by_status[row.get("finalStatus", "?")] = by_status.get(row.get("finalStatus", "?"), 0) + 1
    conflicts = sum(1 for r in rows if r.get("bookHttpStatus") == "409")
    return {
        "orders": len(rows),
        "submitted": len(times),
        "conflicts409": conflicts,
        "byStatus": by_status,
        "timeToSubmittedMs": {
            "p50": percentile(times, 0.5), "p95": percentile(times, 0.95), "p99": percentile(times, 0.99),
            "max": max(times) if times else None, "mean": statistics.fmean(times) if times else None,
        },
        "polls": {"mean": statistics.fmean(float(r["polls"]) for r in rows if r.get("polls")) if rows else None},
    }


def gatling_summary(gatling_dir: Path) -> dict:
    stats_file = gatling_dir / "js" / "stats.json"
    if not stats_file.exists():
        return {"available": False}
    data = json.loads(stats_file.read_text(encoding="utf-8"))
    rows = []

    def visit(node: dict, depth: int) -> None:
        stats = node.get("stats", {})
        rows.append({
            "name": node.get("name"), "type": node.get("type"), "depth": depth,
            "count": stats.get("numberOfRequests", {}).get("total"),
            "ok": stats.get("numberOfRequests", {}).get("ok"),
            "ko": stats.get("numberOfRequests", {}).get("ko"),
            "min": stats.get("minResponseTime", {}).get("total"),
            "p50": stats.get("percentiles1", {}).get("total"),
            "p75": stats.get("percentiles2", {}).get("total"),
            "p95": stats.get("percentiles3", {}).get("total"),
            "p99": stats.get("percentiles4", {}).get("total"),
            "max": stats.get("maxResponseTime", {}).get("total"),
            "mean": stats.get("meanResponseTime", {}).get("total"),
            "rps": stats.get("meanNumberOfRequestsPerSecond", {}).get("total"),
        })
        for child in (node.get("contents") or {}).values():
            visit(child, depth + 1)

    visit(data, 0)
    assertions_file = gatling_dir / "js" / "assertions.json"
    assertions = json.loads(assertions_file.read_text(encoding="utf-8")) if assertions_file.exists() else {}
    return {"available": True, "requests": rows, "assertions": assertions.get("assertions", assertions)}


def level_summary(run_dir: Path) -> dict | None:
    """Per-level figures of a capacity ramp (two-minute levels, 30 s ramps) and the knee."""
    campaign_file = run_dir / "campaign.json"
    if not campaign_file.exists():
        return None
    campaign = json.loads(campaign_file.read_text(encoding="utf-8"))
    if campaign.get("simulation") != "CapacityRamp":
        return None
    rows = read_csv(run_dir / "orders-ledger.csv")
    if not rows:
        return None
    start = datetime.fromisoformat(campaign["startedAt"].replace("Z", "+00:00"))
    level_seconds, ramp_seconds = 120, 30
    levels: dict[int, list[dict]] = {}
    for row in rows:
        booked = datetime.fromisoformat(row["bookedAt"].replace("Z", "+00:00"))
        elapsed = (booked - start).total_seconds()
        level = int(elapsed // (level_seconds + ramp_seconds)) + 1
        levels.setdefault(level, []).append(row)
    summary = []
    for level in sorted(levels):
        batch = levels[level]
        times = [float(r["timeToSubmittedMs"]) for r in batch if r.get("timeToSubmittedMs")]
        ko = sum(1 for r in batch if not r.get("timeToSubmittedMs"))
        summary.append({"level": level, "orders": len(batch), "submitted": len(times), "ko": ko,
                        "koPercent": round(ko / len(batch) * 100, 1) if batch else 0,
                        "p50": percentile(times, 0.5), "p95": percentile(times, 0.95), "max": max(times) if times else None})
    knee = None
    if summary and summary[0]["p95"]:
        base = summary[0]["p95"]
        for entry in summary[1:]:
            if (entry["p95"] and entry["p95"] > 2 * base) or entry["koPercent"] > 2:
                knee = entry["level"]
                break
    return {"levels": summary, "knee": knee, "baseP95": summary[0]["p95"] if summary else None}
