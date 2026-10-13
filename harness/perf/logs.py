"""Pod logs of the campaign window: WARN and ERROR lines of the ECS JSON output, summarised."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from .config import Config
from .oc import Oc, OcError

KEEP_LEVELS = {"WARN", "ERROR", "FATAL"}
KEEP_MARKERS = ("Cannot acquire lock", "Rejecting XCAS order", "BrokerUnavailable", "audit queue full",
                "deferring", "giving up", "failed to claim")


def capture(config: Config, out_dir: Path, since_time: str) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    oc = Oc(config.oc_context)
    summary: dict = {"sinceTime": since_time, "pods": {}, "byMessage": {}}
    counter: Counter = Counter()
    for selector, role in ((config.selector_api, "api"), (config.selector_worker, "worker")):
        try:
            pods = oc.pods(config.ns_services, selector)
        except OcError as error:
            summary["pods"][selector] = f"error: {error}"
            continue
        for pod in pods:
            try:
                text = oc.logs(config.ns_services, pod["name"], since_time=since_time)
            except OcError as error:
                summary["pods"][pod["name"]] = f"error: {error}"
                continue
            kept, levels = _filter(text)
            (out_dir / f"{pod['name']}.jsonl").write_text("\n".join(kept) + ("\n" if kept else ""), encoding="utf-8")
            summary["pods"][pod["name"]] = {"role": role, "lines": len(text.splitlines()), "kept": len(kept), "levels": levels}
            for line in kept:
                counter[_key(line)] += 1
    summary["byMessage"] = [{"count": n, "message": k} for k, n in counter.most_common(50)]
    summary["errors"] = sum(v.get("levels", {}).get("ERROR", 0) for v in summary["pods"].values() if isinstance(v, dict))
    summary["warnings"] = sum(v.get("levels", {}).get("WARN", 0) for v in summary["pods"].values() if isinstance(v, dict))
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return summary


def _filter(text: str) -> tuple[list[str], dict[str, int]]:
    kept: list[str] = []
    levels: Counter = Counter()
    for line in text.splitlines():
        level = None
        if line.startswith("{"):
            try:
                record = json.loads(line)
                level = (record.get("log", {}) or {}).get("level") or record.get("level")
            except json.JSONDecodeError:
                record = None
        else:
            record = None
        if (level and level.upper() in KEEP_LEVELS) or any(marker in line for marker in KEEP_MARKERS):
            kept.append(line)
            levels[(level or "TEXT").upper()] += 1
    return kept, dict(levels)


def _key(line: str) -> str:
    try:
        record = json.loads(line)
        logger = (record.get("log", {}) or {}).get("logger", "")
        message = str(record.get("message", ""))
    except (json.JSONDecodeError, AttributeError):
        logger, message = "", line
    # Collapse identifiers so the same message template counts once.
    import re
    template = re.sub(r"BO-\d{8}-\d{6}", "BO-…", message)
    template = re.sub(r"\d+(\.\d+)?", "N", template)
    return f"{logger.split('.')[-1]}: {template[:120]}"
