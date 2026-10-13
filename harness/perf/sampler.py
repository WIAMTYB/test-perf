"""Metrics sampler running next to a simulation.

Every tick it lists the api and worker pods (the HPA may add some during the run), scrapes
/actuator/prometheus inside each pod with `oc exec` (the metrics key is passed on stdin,
never on a command line), records `oc adm top` and the campaign's saga backlog, and raises
the ABORT flag when the 5xx share of the last window exceeds the limit.
"""
from __future__ import annotations

import csv
import json
import threading
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

from . import promtext
from .config import Config
from .db import load_sql
from .oc import Oc, OcError

SCRAPE = ("import sys,urllib.request as u;k=sys.stdin.readline().strip();"
          "r=u.Request('http://localhost:8080/actuator/prometheus',headers={'X-Api-Key':k});"
          "sys.stdout.write(u.urlopen(r,timeout=10).read().decode())")


class Sampler(threading.Thread):

    def __init__(self, config: Config, run_dir: Path, prefix: str, stop: threading.Event, db_connection=None):
        super().__init__(name="perf-sampler", daemon=True)
        self.config = config
        self.run_dir = run_dir
        self.prefix = prefix
        self.stop_event = stop
        self.db = db_connection
        self.oc = Oc(config.oc_context)
        self.errors: list[str] = []
        self.ticks = 0
        self._window: deque[tuple[float, float, float]] = deque()  # (epoch, total count, 5xx count)
        (run_dir / "metrics").mkdir(parents=True, exist_ok=True)
        (run_dir / "db").mkdir(parents=True, exist_ok=True)
        self.samples_file = run_dir / "metrics" / "samples.csv"
        self.top_file = run_dir / "metrics" / "pods-top.csv"
        self.backlog_file = run_dir / "db" / "backlog.csv"
        self._init_csv(self.samples_file, ["ts", "pod", "role", "metric", "labels", "value"])
        self._init_csv(self.top_file, ["ts", "pod", "container", "cpu_m", "memory_mi"])
        self._init_csv(self.backlog_file, ["ts", "state", "in_state_now", "oldest_since"])

    @staticmethod
    def _init_csv(path: Path, header: list[str]) -> None:
        if not path.exists() or path.stat().st_size == 0:
            with path.open("w", newline="", encoding="utf-8") as handle:
                csv.writer(handle).writerow(header)

    def run(self) -> None:
        interval = self.config.sample_seconds
        while not self.stop_event.is_set():
            started = time.monotonic()
            try:
                self.tick()
            except Exception as error:  # the sampler must outlive any single failure
                self.errors.append(f"{datetime.now(timezone.utc).isoformat(timespec='seconds')} {error}")
            self.stop_event.wait(max(0.5, interval - (time.monotonic() - started)))

    def tick(self) -> None:
        now = datetime.now(timezone.utc)
        ts = now.isoformat(timespec="seconds")
        pods = []
        for selector, role in ((self.config.selector_api, "api"), (self.config.selector_worker, "worker")):
            try:
                pods += [(p["name"], role) for p in self.oc.pods(self.config.ns_services, selector)]
            except OcError as error:
                self.errors.append(f"{ts} pods {selector}: {error}")
        total, errors5xx = 0.0, 0.0
        with self.samples_file.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            for pod, role in pods:
                try:
                    text = self.oc.exec(self.config.ns_services, pod, ["python3", "-c", SCRAPE],
                                        stdin=self.config.metrics_api_key + "\n", timeout=30)
                except OcError as error:
                    self.errors.append(f"{ts} scrape {pod}: {error}")
                    continue
                for sample in promtext.parse(text):
                    writer.writerow([ts, pod, role, sample.name, sample.labels_text(), repr(sample.value)])
                    if role == "api" and sample.name == "http_server_requests_seconds_count":
                        total += sample.value
                        if sample.label("status").startswith("5"):
                            errors5xx += sample.value
        self._record_top(ts)
        self._record_backlog(ts)
        self._check_abort(now.timestamp(), total, errors5xx)
        self.ticks += 1

    def _record_top(self, ts: str) -> None:
        try:
            rows = self.oc.top_pods(self.config.ns_services)
        except OcError as error:
            self.errors.append(f"{ts} top: {error}")
            return
        with self.top_file.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            for row in rows:
                writer.writerow([ts, row["pod"], row["container"], row["cpu_m"], row["memory_mi"]])

    def _record_backlog(self, ts: str) -> None:
        if self.db is None:
            return
        try:
            cursor = self.db.cursor()
            cursor.execute(load_sql(self.config, "backlog_now"), {"prefix": self.prefix})
            rows = cursor.fetchall()
            cursor.close()
        except Exception as error:
            self.errors.append(f"{ts} backlog: {error}")
            return
        with self.backlog_file.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            for state, count, oldest in rows:
                writer.writerow([ts, state, count, oldest.isoformat(timespec="seconds") if oldest else ""])

    def _check_abort(self, epoch: float, total: float, errors5xx: float) -> None:
        self._window.append((epoch, total, errors5xx))
        horizon = epoch - self.config.abort_window_seconds
        while len(self._window) > 1 and self._window[0][0] < horizon:
            self._window.popleft()
        if len(self._window) < 2:
            return
        first, last = self._window[0], self._window[-1]
        delta_total = last[1] - first[1]
        delta_5xx = last[2] - first[2]
        if delta_total >= 20 and delta_5xx / delta_total * 100 > self.config.abort_5xx_percent:
            flag = self.run_dir / "ABORT"
            if not flag.exists():
                reason = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                          "reason": f"{delta_5xx:.0f} réponses 5xx sur {delta_total:.0f} en {self.config.abort_window_seconds}s "
                                    f"({delta_5xx / delta_total * 100:.1f} % > {self.config.abort_5xx_percent} %)"}
                flag.write_text(json.dumps(reason), encoding="utf-8")
                (self.run_dir / "abort.json").write_text(json.dumps(reason, indent=2, ensure_ascii=False), encoding="utf-8")
                print(f"[harness] ABORT: {reason['reason']}")

    def finish(self) -> dict:
        summary = {"ticks": self.ticks, "errors": self.errors[-50:], "errorCount": len(self.errors)}
        (self.run_dir / "metrics" / "sampler.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
        return summary
