#!/usr/bin/env python3
"""Campaign harness of titres-trading-performance-tests.

    python harness/campaign.py run      --env recette --scenario Smoke --campaign SMOKE-20261015A [--cancel-all]
    python harness/campaign.py snapshot --env recette --out campaigns/recette/manual
    python harness/campaign.py analyze  --run-dir campaigns/recette/20261015-1030-Smoke
    python harness/campaign.py dossier  --run-dir campaigns/recette/20261015-1030-Smoke
    python harness/campaign.py logs     --run-dir ... --since 2026-10-15T10:30:00Z
    python harness/campaign.py cancel-all --run-dir ...
    python harness/campaign.py cleanup  --campaign SMOKE-20261015A [--yes]

`run` does everything in order: preflight, snapshot, sampler, Gatling, snapshot, logs,
analysis, dossier, optional cancel-all. Secrets come from the environment or .env only.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from perf import analysis, cancel, cleanup, dossier, logs, snapshot  # noqa: E402
from perf.config import PROJECT_DIR, check_campaign_id, load  # noqa: E402
from perf.sampler import Sampler  # noqa: E402

SIMULATIONS = ["Smoke", "OrderFlow", "PortfolioRead", "MobileMix", "CapacityRamp", "Soak", "Spike"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="run a full campaign")
    run.add_argument("--env", default=None)
    run.add_argument("--scenario", required=True, choices=SIMULATIONS)
    run.add_argument("--campaign", required=True, help="campaign id, [A-Z0-9-]{4,24}, single use")
    run.add_argument("--duration", default=None, help="ISO-8601, e.g. PT10M")
    run.add_argument("--target-rate", default=None, help="arrivals per second (open models) or ramp step")
    run.add_argument("--users", default=None, help="concurrent clients (closed models, capped by the pool)")
    run.add_argument("--profile", default=None, choices=["nominal", "peak"])
    run.add_argument("--side", default=None, choices=["BUY", "SELL"])
    run.add_argument("--cancel", action="store_true", help="cancel each order once at the market")
    run.add_argument("--max-orders", default=None, help="raise the campaign order cap (capacity ramp)")
    run.add_argument("--pace", default=None, help="seconds between two orders of a client (closed models)")
    run.add_argument("--levels", default=None, help="capacity ramp levels")
    run.add_argument("--seed", default=None)
    run.add_argument("--cancel-all", action="store_true", help="cancel the campaign's open orders at the end")
    run.add_argument("--no-fail", action="store_true", help="exit 0 even when Gatling assertions fail")
    run.add_argument("--skip-preflight", action="store_true")
    run.add_argument("--operator", default=os.environ.get("USERNAME") or os.environ.get("USER") or "")

    snap = sub.add_parser("snapshot", help="environment snapshot only")
    snap.add_argument("--env", default=None)
    snap.add_argument("--out", required=True)

    for name in ("analyze", "dossier", "logs", "cancel-all"):
        p = sub.add_parser(name)
        p.add_argument("--env", default=None)
        p.add_argument("--run-dir", required=True)
        if name == "logs":
            p.add_argument("--since", required=True, help="RFC 3339 instant")
        if name == "analyze":
            p.add_argument("--start", default=None)
            p.add_argument("--end", default=None)

    clean = sub.add_parser("cleanup", help="delete a campaign's rows (dry run unless --yes)")
    clean.add_argument("--env", default=None)
    clean.add_argument("--campaign", required=True)
    clean.add_argument("--yes", action="store_true")

    args = parser.parse_args(argv)
    return {
        "run": cmd_run, "snapshot": cmd_snapshot, "analyze": cmd_analyze, "dossier": cmd_dossier,
        "logs": cmd_logs, "cancel-all": cmd_cancel_all, "cleanup": cmd_cleanup,
    }[args.command](args)


# --- commands -------------------------------------------------------------------------

def cmd_run(args) -> int:
    config = load(args.env)
    campaign_id = check_campaign_id(args.campaign)
    prefix = f"PERF-{campaign_id}-%"
    run_dir = config.new_run_dir(args.scenario)
    run_dir.mkdir(parents=True, exist_ok=False)
    print(f"[harness] campaign {campaign_id} ({args.scenario}) on {config.env} -> {run_dir}")

    db = _db(config)
    if not args.skip_preflight:
        _preflight(config, db, prefix)

    start = datetime.now(timezone.utc)
    (run_dir / "run.json").write_text(json.dumps({
        "campaignId": campaign_id, "scenario": args.scenario, "env": config.env, "startedAt": start.isoformat(),
        "operator": args.operator, "gitSha": _git_sha(), "arguments": {k: v for k, v in vars(args).items() if k != "command"},
    }, indent=2), encoding="utf-8")

    print("[harness] snapshot before")
    snapshot.take(config, run_dir / "env-snapshot" / "before", db)

    stop = threading.Event()
    sampler = None
    if config.has_metrics_key():
        sampler = Sampler(config, run_dir, prefix, stop, db)
        sampler.start()
        print(f"[harness] sampler started ({config.sample_seconds}s)")
    else:
        print("[harness] PERF_METRICS_API_KEY not set: no metrics sampling")

    gatling_exit = _run_gatling(config, args, campaign_id, run_dir)

    stop.set()
    if sampler:
        sampler.join(timeout=60)
        summary = sampler.finish()
        print(f"[harness] sampler stopped: {summary['ticks']} ticks, {summary['errorCount']} errors")
    end = datetime.now(timezone.utc)

    print("[harness] snapshot after")
    snapshot.take(config, run_dir / "env-snapshot" / "after", db)
    print("[harness] logs")
    logs.capture(config, run_dir / "logs", (start - timedelta(seconds=30)).isoformat(timespec="seconds").replace("+00:00", "Z"))
    print("[harness] analysis")
    analysis.analyze(config, run_dir, prefix, start, end + timedelta(seconds=30))
    print("[harness] dossier")
    out = dossier.build(run_dir)
    print(f"[harness] dossier: {out}")
    if args.cancel_all:
        print("[harness] cancel-all")
        print(json.dumps(cancel.cancel_all(config, run_dir, prefix)))
    if db:
        db.close()
    if gatling_exit != 0 and not args.no_fail:
        print(f"[harness] Gatling exit {gatling_exit}: a threshold was breached or the run failed")
        return gatling_exit
    return 0


def cmd_snapshot(args) -> int:
    config = load(args.env)
    db = _db(config)
    summary = snapshot.take(config, Path(args.out), db)
    print(json.dumps({ns: {"deployments": [d.get("name") for d in v.get("deployments", [])]} for ns, v in summary["namespaces"].items()}, indent=2))
    return 0


def cmd_analyze(args) -> int:
    config = load(args.env)
    run_dir = Path(args.run_dir)
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    campaign_end = run_dir / "campaign-end.json"
    start = datetime.fromisoformat(args.start) if args.start else datetime.fromisoformat(run["startedAt"])
    end = datetime.fromisoformat(args.end) if args.end else (
        datetime.fromisoformat(json.loads(campaign_end.read_text(encoding="utf-8"))["endedAt"].replace("Z", "+00:00"))
        if campaign_end.exists() else datetime.now(timezone.utc))
    result = analysis.analyze(config, run_dir, f"PERF-{run['campaignId']}-%", start, end + timedelta(seconds=30))
    print(json.dumps({k: v for k, v in result.items() if k in ("db", "orders", "ledger")}, indent=2, default=str))
    return 0


def cmd_dossier(args) -> int:
    print(dossier.build(Path(args.run_dir)))
    return 0


def cmd_logs(args) -> int:
    config = load(args.env)
    summary = logs.capture(config, Path(args.run_dir) / "logs", args.since)
    print(json.dumps({"errors": summary["errors"], "warnings": summary["warnings"]}, indent=2))
    return 0


def cmd_cancel_all(args) -> int:
    config = load(args.env)
    run_dir = Path(args.run_dir)
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    print(json.dumps(cancel.cancel_all(config, run_dir, f"PERF-{run['campaignId']}-%"), indent=2))
    return 0


def cmd_cleanup(args) -> int:
    config = load(args.env)
    prefix = f"PERF-{check_campaign_id(args.campaign)}-%"
    counts = cleanup.dry_run(config, prefix)
    print(json.dumps(counts, indent=2))
    blocked = cleanup.blockers(counts)
    if blocked:
        print("cleanup would be refused: " + ", ".join(blocked))
        return 2
    if not args.yes:
        print("dry run only; add --yes to delete")
        return 0
    print(json.dumps(cleanup.cleanup(config, prefix), indent=2))
    return 0


# --- helpers --------------------------------------------------------------------------

def _db(config):
    if not config.has_db():
        print("[harness] PERF_DB_USER / PERF_DB_PASSWORD not set: database steps skipped")
        return None
    from perf.db import connect
    return connect(config)


def _preflight(config, db, prefix: str) -> None:
    if not config.has_api_key():
        raise SystemExit("PERF_API_KEY is not set")
    if db is None:
        print("[harness] preflight: no database, campaign id uniqueness and pause not checked")
        return
    cursor = db.cursor()
    cursor.execute("SELECT COUNT(*) FROM orders WHERE source = 'PERF' AND client_reference LIKE :prefix", {"prefix": prefix})
    (existing,) = cursor.fetchone()
    if existing:
        raise SystemExit(f"Campaign id already used: {existing} orders carry the prefix {prefix}")
    cursor.execute("SELECT setting_value FROM app_runtime_setting WHERE setting_key = 'orders.submission.paused'")
    row = cursor.fetchone()
    if row and str(row[0]).strip() not in ("0", "", "false"):
        raise SystemExit("orders.submission.paused is on: the saga would not submit anything")
    cursor.execute("""
        SELECT lifecycle_state, COUNT(*) FROM orders
         WHERE lifecycle_state IN ('RECEIVED', 'VALIDATED', 'CASH_HELD', 'SECURITY_HELD', 'SUBMITTING')
           AND submitted_at > SYSTIMESTAMP - INTERVAL '1' HOUR
         GROUP BY lifecycle_state""")
    pending = cursor.fetchall()
    cursor.close()
    if pending:
        print(f"[harness] preflight: orders already in flight on {config.env}: {pending} (ambient traffic, noted)")


def _run_gatling(config, args, campaign_id: str, run_dir: Path) -> int:
    mvn = _mvn(config.mvn)
    cmd = [mvn, "-q", "gatling:test",
           f"-Dgatling.simulationClass=com.attijariwafa.titres.perf.simulations.{args.scenario}Simulation",
           f"-Dperf.env={config.env}", f"-Dperf.campaignId={campaign_id}", f"-Dperf.runDir={run_dir.resolve()}"]
    for key, value in (("perf.duration", args.duration), ("perf.targetRate", args.target_rate), ("perf.users", args.users),
                       ("perf.profile", args.profile), ("perf.side", args.side), ("perf.maxOrders", args.max_orders),
                       ("perf.paceSeconds", args.pace), ("perf.levels", args.levels), ("perf.seed", args.seed)):
        if value:
            cmd.append(f"-D{key}={value}")
    if args.cancel:
        cmd.append("-Dperf.cancel=true")
    print("[harness] " + " ".join(cmd))
    env = dict(os.environ)
    env.setdefault("MAVEN_OPTS", "")
    before = {p.name for p in (PROJECT_DIR / "target" / "gatling").glob("*")} if (PROJECT_DIR / "target" / "gatling").exists() else set()
    result = subprocess.run(cmd, cwd=PROJECT_DIR, env=env)
    gatling_root = PROJECT_DIR / "target" / "gatling"
    new_runs = sorted((p for p in gatling_root.glob("*") if p.is_dir() and p.name not in before), key=lambda p: p.stat().st_mtime) if gatling_root.exists() else []
    if new_runs:
        target = run_dir / "gatling"
        shutil.copytree(new_runs[-1], target, dirs_exist_ok=True)
        print(f"[harness] gatling report copied to {target}")
    else:
        print("[harness] no Gatling report produced")
    return result.returncode


def _mvn(binary: str) -> str:
    found = shutil.which(binary)
    if found:
        return found
    if os.name == "nt" and not binary.lower().endswith(".cmd"):
        found = shutil.which(binary + ".cmd") or (binary + ".cmd" if Path(binary + ".cmd").exists() else None)
        if found:
            return found
    return binary


def _git_sha() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=PROJECT_DIR, capture_output=True, text=True).stdout.strip()
    except OSError:
        return ""


if __name__ == "__main__":
    sys.exit(main())
