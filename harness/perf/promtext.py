"""Parser of the Prometheus text exposition format (/actuator/prometheus)."""
from __future__ import annotations

import re
from dataclasses import dataclass

LINE = re.compile(r"^([a-zA-Z_:][a-zA-Z0-9_:]*)(\{(.*)\})?\s+(\S+)(\s+\S+)?$")
LABEL = re.compile(r'([a-zA-Z_][a-zA-Z0-9_]*)="((?:[^"\\]|\\.)*)"')

# Families the campaign keeps; everything else on the endpoint is dropped at parse time.
KEEP_PREFIXES = (
    "http_server_requests_seconds",
    "external_service_requests_seconds",
    "megara_query_duration_seconds",
    "hikaricp_connections",
    "portfolio_listvalued_cache_requests_total",
    "process_cpu_usage",
    "system_cpu_usage",
    "jvm_memory_used_bytes",
    "jvm_threads_live_threads",
    "executor_",
    "orders_",
)


@dataclass(frozen=True)
class Sample:
    name: str
    labels: tuple[tuple[str, str], ...]
    value: float

    def label(self, key: str, default: str = "") -> str:
        for k, v in self.labels:
            if k == key:
                return v
        return default

    def labels_text(self) -> str:
        return ",".join(f"{k}={v}" for k, v in self.labels)


def parse(text: str, keep_prefixes: tuple[str, ...] = KEEP_PREFIXES) -> list[Sample]:
    samples: list[Sample] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = LINE.match(line)
        if not match:
            continue
        name = match.group(1)
        if keep_prefixes and not name.startswith(keep_prefixes):
            continue
        labels = tuple(sorted((k, v.replace('\\"', '"')) for k, v in LABEL.findall(match.group(3) or "")))
        try:
            value = float(match.group(4))
        except ValueError:
            continue
        samples.append(Sample(name, labels, value))
    return samples


def parse_labels_text(text: str) -> dict[str, str]:
    """Inverse of Sample.labels_text for the CSV reader."""
    labels: dict[str, str] = {}
    if not text:
        return labels
    for part in text.split(","):
        if "=" in part:
            k, v = part.split("=", 1)
            labels[k] = v
    return labels
