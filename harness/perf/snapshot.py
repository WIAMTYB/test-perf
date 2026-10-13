"""Environment snapshot: what the platform looked like when the campaign ran.

Everything the regulator dossier needs to reproduce the setup: images with digests,
replicas, resource requests and limits, autoscaling, the mounted application properties
(secrets masked), the quota, and the runtime settings the saga reads from the database.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

from .config import MASK, Config
from .oc import Oc, OcError

OBJECTS_SERVICES = ["deployments", "horizontalpodautoscalers", "configmaps", "services", "routes",
                    "ingresses", "resourcequotas", "limitranges"]
OBJECTS_DATAS = ["deployments", "services", "resourcequotas"]


def take(config: Config, out_dir: Path, db_connection=None) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    oc = Oc(config.oc_context)
    summary: dict = {"takenAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                     "cluster": _cluster(oc), "namespaces": {}}
    for namespace, objects in ((config.ns_services, OBJECTS_SERVICES), (config.ns_datas, OBJECTS_DATAS)):
        ns_dir = out_dir / namespace
        ns_dir.mkdir(exist_ok=True)
        for kind in objects:
            try:
                text = oc.run("get", kind, "-o", "yaml", namespace=namespace, check=True)
            except OcError as error:
                text = f"# not readable: {error}\n"
            (ns_dir / f"{kind}.yaml").write_text(mask(text), encoding="utf-8")
        try:
            pods = oc.json("get", "pods", namespace=namespace)
        except OcError as error:
            pods = {"error": str(error)}
        (ns_dir / "pods.json").write_text(json.dumps(pods, indent=1), encoding="utf-8")
        summary["namespaces"][namespace] = _summarise(oc, namespace, pods)
    if db_connection is not None:
        summary["runtimeSettings"] = _runtime_settings(db_connection)
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    return summary


def mask(text: str) -> str:
    """Masks the value of any key that looks like a credential, in YAML and properties alike."""
    out = []
    for line in text.splitlines():
        if MASK.search(line.split(":")[0] if ":" in line else line.split("=")[0]):
            sep = ":" if ":" in line and (("=" not in line) or line.index(":") < line.index("=")) else "="
            key = line.split(sep, 1)[0]
            out.append(f"{key}{sep} ***")
        else:
            out.append(line)
    return "\n".join(out) + "\n"


def _cluster(oc: Oc) -> dict:
    info: dict = {}
    try:
        info["user"] = oc.whoami()
    except OcError as error:
        info["user"] = f"unknown ({error})"
    try:
        info["server"] = oc.run("whoami", "--show-server").strip()
    except OcError:
        info["server"] = "unknown"
    try:
        version = oc.run("version", "-o", "json", check=False)
        parsed = json.loads(version) if version.strip().startswith("{") else {}
        info["openshiftVersion"] = parsed.get("openshiftVersion") or parsed.get("serverVersion", {}).get("gitVersion")
    except (OcError, json.JSONDecodeError):
        info["openshiftVersion"] = "unknown"
    return info


def _summarise(oc: Oc, namespace: str, pods: dict) -> dict:
    deployments = []
    pod_items = pods.get("items", []) if isinstance(pods, dict) else []
    try:
        for item in oc.json("get", "deployments", namespace=namespace).get("items", []):
            spec = item["spec"]
            containers = spec["template"]["spec"]["containers"]
            name = item["metadata"]["name"]
            # The status block is not always served to a namespace user: count the ready pods instead.
            ready = item.get("status", {}).get("readyReplicas")
            if ready is None:
                selector = spec.get("selector", {}).get("matchLabels", {}) or {}
                ready = sum(1 for p in pod_items
                            if all(p["metadata"].get("labels", {}).get(k) == v for k, v in selector.items())
                            and p.get("status", {}).get("phase") == "Running"
                            and all(c.get("ready") for c in p.get("status", {}).get("containerStatuses", []) or []))
            deployments.append({
                "name": name,
                "replicasWanted": spec.get("replicas"),
                "replicasReady": ready,
                "images": [c["image"] for c in containers],
                "resources": [c.get("resources", {}) for c in containers],
                "env": {e["name"]: ("***" if MASK.search(e["name"]) else e.get("value", "<ref>"))
                        for c in containers for e in c.get("env", [])},
            })
    except OcError as error:
        deployments.append({"error": str(error)})
    hpa = []
    try:
        for item in oc.json("get", "horizontalpodautoscalers", namespace=namespace).get("items", []):
            hpa.append({"name": item["metadata"]["name"], "min": item["spec"].get("minReplicas"),
                        "max": item["spec"].get("maxReplicas"),
                        "current": item.get("status", {}).get("currentReplicas"),
                        "metrics": item["spec"].get("metrics")})
    except OcError:
        pass
    running = []
    for item in pods.get("items", []) if isinstance(pods, dict) else []:
        statuses = item.get("status", {}).get("containerStatuses", []) or []
        running.append({"name": item["metadata"]["name"], "node": item.get("spec", {}).get("nodeName"),
                        "phase": item.get("status", {}).get("phase"),
                        "imageIds": [s.get("imageID") for s in statuses],
                        "restarts": sum(int(s.get("restartCount", 0)) for s in statuses),
                        "startedAt": item.get("status", {}).get("startTime")})
    quota = None
    try:
        items = oc.json("get", "resourcequotas", namespace=namespace).get("items", [])
        if items:
            quota = {"hard": items[0].get("status", {}).get("hard"), "used": items[0].get("status", {}).get("used")}
    except OcError:
        pass
    return {"deployments": deployments, "hpa": hpa, "pods": running, "quota": quota}


def _runtime_settings(connection) -> dict:
    cursor = connection.cursor()
    cursor.execute("SELECT setting_key, setting_value FROM app_runtime_setting WHERE setting_key LIKE 'orders.%' ORDER BY 1")
    rows = {k: v for k, v in cursor.fetchall()}
    cursor.close()
    return rows


def diff(before: dict, after: dict) -> list[str]:
    """Human-readable differences that matter: images, replicas, resources, settings."""
    changes: list[str] = []
    for namespace, b in before.get("namespaces", {}).items():
        a = after.get("namespaces", {}).get(namespace, {})
        b_dep = {d.get("name"): d for d in b.get("deployments", [])}
        a_dep = {d.get("name"): d for d in a.get("deployments", [])}
        for name, bd in b_dep.items():
            ad = a_dep.get(name)
            if not ad:
                changes.append(f"{namespace}/{name}: deployment disparu")
                continue
            for key in ("images", "resources", "replicasWanted"):
                if bd.get(key) != ad.get(key):
                    changes.append(f"{namespace}/{name}: {key} {bd.get(key)} -> {ad.get(key)}")
            if bd.get("replicasReady") != ad.get("replicasReady"):
                changes.append(f"{namespace}/{name}: réplicas prêts {bd.get('replicasReady')} -> {ad.get('replicasReady')}")
        b_pods = {p["name"]: p for p in b.get("pods", [])}
        a_pods = {p["name"]: p for p in a.get("pods", [])}
        for name in sorted(set(b_pods) ^ set(a_pods)):
            changes.append(f"{namespace}: pod {'apparu' if name in a_pods else 'disparu'} {name}")
        for name in set(b_pods) & set(a_pods):
            if b_pods[name].get("restarts") != a_pods[name].get("restarts"):
                changes.append(f"{namespace}: pod {name} redémarré ({b_pods[name].get('restarts')} -> {a_pods[name].get('restarts')})")
    if before.get("runtimeSettings") != after.get("runtimeSettings"):
        changes.append(f"APP_RUNTIME_SETTING: {before.get('runtimeSettings')} -> {after.get('runtimeSettings')}")
    return changes


def load_summary(path: Path) -> dict:
    file = path / "summary.json"
    return json.loads(file.read_text(encoding="utf-8")) if file.exists() else {}


_ = re  # keep the import explicit for readers of MASK
