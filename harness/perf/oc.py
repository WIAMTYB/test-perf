"""Thin wrapper around the `oc` CLI.

The workstation session may carry HTTP(S)_PROXY variables that 407-block the cluster API;
they are cleared for every call. Everything returned by `oc` is data, never a command.
"""
from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass


def _env() -> dict[str, str]:
    env = dict(os.environ)
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
        env.pop(key, None)
    return env


class OcError(RuntimeError):
    pass


@dataclass
class Oc:
    context: str | None = None
    binary: str = "oc"

    def run(self, *args: str, namespace: str | None = None, stdin: str | None = None,
            check: bool = True, timeout: int = 120) -> str:
        cmd = [self.binary]
        if self.context:
            cmd += ["--context", self.context]
        if namespace:
            cmd += ["-n", namespace]
        cmd += list(args)
        result = subprocess.run(cmd, input=stdin, capture_output=True, text=True, env=_env(),
                                timeout=timeout, encoding="utf-8", errors="replace")
        if check and result.returncode != 0:
            raise OcError(f"{' '.join(cmd[:6])}... failed ({result.returncode}): {result.stderr.strip()[:500]}")
        return result.stdout

    def json(self, *args: str, namespace: str | None = None):
        return json.loads(self.run(*args, "-o", "json", namespace=namespace))

    def whoami(self) -> str:
        return self.run("whoami").strip()

    def pods(self, namespace: str, selector: str) -> list[dict]:
        """Running pods of a selector: name, node, phase, images with digests, start time."""
        items = self.json("get", "pods", "-l", selector, namespace=namespace).get("items", [])
        pods = []
        for item in items:
            status = item.get("status", {})
            if status.get("phase") != "Running":
                continue
            containers = status.get("containerStatuses", []) or []
            pods.append({
                "name": item["metadata"]["name"],
                "node": item.get("spec", {}).get("nodeName"),
                "phase": status.get("phase"),
                "startedAt": status.get("startTime"),
                "images": [c.get("image") for c in containers],
                "imageIds": [c.get("imageID") for c in containers],
                "ready": all(c.get("ready") for c in containers) if containers else False,
                "restarts": sum(int(c.get("restartCount", 0)) for c in containers),
            })
        return pods

    def exec(self, namespace: str, pod: str, command: list[str], stdin: str | None = None, timeout: int = 30) -> str:
        args = ["exec", "-i", pod, "--", *command] if stdin is not None else ["exec", pod, "--", *command]
        return self.run(*args, namespace=namespace, stdin=stdin, timeout=timeout)

    def logs(self, namespace: str, pod: str, since_time: str | None = None, tail: int | None = None) -> str:
        args = ["logs", pod]
        if since_time:
            args += ["--since-time", since_time]
        if tail:
            args += ["--tail", str(tail)]
        return self.run(*args, namespace=namespace, timeout=300)

    def top_pods(self, namespace: str) -> list[dict]:
        """`oc adm top pods --containers` rows: pod, container, cpu (millicores), memory (MiB)."""
        out = self.run("adm", "top", "pods", "--containers", "--no-headers", namespace=namespace, check=False)
        rows = []
        for line in out.splitlines():
            parts = line.split()
            if len(parts) < 4:
                continue
            rows.append({"pod": parts[0], "container": parts[1],
                         "cpu_m": _millicores(parts[2]), "memory_mi": _mebibytes(parts[3])})
        return rows


def _millicores(value: str) -> float:
    value = value.strip()
    if value.endswith("m"):
        return float(value[:-1])
    try:
        return float(value) * 1000
    except ValueError:
        return float("nan")


def _mebibytes(value: str) -> float:
    value = value.strip()
    units = {"Ki": 1 / 1024, "Mi": 1, "Gi": 1024, "M": 1, "G": 1024}
    for unit, factor in units.items():
        if value.endswith(unit):
            return float(value[: -len(unit)]) * factor
    try:
        return float(value) / (1024 * 1024)
    except ValueError:
        return float("nan")
