"""The campaign dossier: one self-contained French HTML page per run.

Everything comes from the run directory (campaign.json, env-snapshot, metrics, db, logs,
gatling, ledger, analysis.json), so the dossier can be regenerated later from the archive.
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from html import escape
from pathlib import Path

from . import snapshot, svg
from .db import read_csv
from .promtext import parse_labels_text

CSS = """
body{font-family:Segoe UI,Arial,sans-serif;margin:24px auto;max-width:1100px;color:#222;line-height:1.4}
h1{border-bottom:3px solid #1f5f8b;padding-bottom:6px} h2{margin-top:36px;color:#1f5f8b;border-bottom:1px solid #ccc}
table{border-collapse:collapse;margin:8px 0 16px;font-size:13px} th,td{border:1px solid #ccc;padding:4px 8px;text-align:right}
th{background:#eef3f7} td:first-child,th:first-child{text-align:left} .ok{color:#2e8b57} .ko{color:#b22222;font-weight:bold}
.banner{background:#fff3cd;border:1px solid #d9822b;padding:10px;margin:12px 0} .muted{color:#666;font-size:12px}
.chart{display:block;margin:12px 0} .chart-title{font-weight:bold;font-size:14px} .grid{stroke:#e5e5e5;stroke-width:1}
.axis{font-size:10px;fill:#555} .legend{font-size:11px;fill:#333} pre{background:#f6f6f6;padding:8px;font-size:12px;overflow:auto}
@media print{h2{page-break-after:avoid} .chart{page-break-inside:avoid}}
"""


def build(run_dir: Path) -> Path:
    campaign = _json(run_dir / "campaign.json")
    end = _json(run_dir / "campaign-end.json")
    analysis = _json(run_dir / "analysis.json")
    run_info = _json(run_dir / "run.json")
    before = snapshot.load_summary(run_dir / "env-snapshot" / "before")
    after = snapshot.load_summary(run_dir / "env-snapshot" / "after")
    logs = _json(run_dir / "logs" / "summary.json")
    abort = _json(run_dir / "abort.json")

    parts = [f"<!doctype html><html lang='fr'><head><meta charset='utf-8'><title>Campagne {escape(str(campaign.get('campaignId', run_dir.name)))}</title><style>{CSS}</style></head><body>"]
    parts.append(f"<h1>Campagne de performance {escape(str(campaign.get('campaignId', '')))} — {escape(str(campaign.get('simulation', '')))}</h1>")
    parts.append(_header(campaign, end, run_info))
    if abort:
        parts.append(f"<div class='banner'><b>Campagne interrompue</b> : {escape(abort.get('reason', ''))} ({escape(abort.get('at', ''))})</div>")
    rejections = read_csv(run_dir / "db" / "rejections.csv")
    if rejections:
        total = sum(int(r["orders"]) for r in rejections)
        parts.append(f"<div class='banner'><b>{total} ordre(s) de la campagne n'ont pas atteint le marché</b> — voir la section Rejets. "
                     "Un rejet pour cash insuffisant signale un pool de comptes à réapprovisionner, pas une limite de la plateforme.</div>")
    parts.append("<h2>1. Environnement</h2>")
    parts.append(_environment(before, after))
    parts.append("<h2>2. Résultats côté client (Gatling)</h2>")
    parts.append(_gatling(analysis.get("gatling", {}), run_dir))
    parts.append(_ledger(analysis.get("ledger", {})))
    parts.append("<h2>3. Parcours des ordres dans la plateforme</h2>")
    parts.append(_table("Temps passé par étape (ORDER_STATE_HISTORY, secondes)", read_csv(run_dir / "db" / "step_durations.csv")))
    parts.append(_orders_by_state(analysis.get("orders", {})))
    parts.append("<h2>4. Partenaires : latence par appel</h2>")
    parts.append("<p class='muted'>Périmètre « campaign » : les appels des ordres de la campagne ; « window » : tous les appels de la fenêtre de tir, campagne et trafic ambiant confondus.</p>")
    parts.append(_table("NTS (BROKER_CALL_AUDIT)", read_csv(run_dir / "db" / "broker_calls.csv")))
    parts.append(_table("PositionMinute (POSITION_MINUTE_AUDIT)", read_csv(run_dir / "db" / "positionminute_calls.csv")))
    parts.append(_table("MegaTrade mouvements titres (SECURITY_MOVEMENT_AUDIT)", read_csv(run_dir / "db" / "security_calls.csv")))
    parts.append(_table("MegaCustody MT54x (CUSTODY_INSTRUCTION_AUDIT)", read_csv(run_dir / "db" / "custody_calls.csv")))
    parts.append(_table("Callbacks du broker (BROKER_EVENT_INBOX)", read_csv(run_dir / "db" / "callback_lag.csv")))
    parts.append("<h2>5. Rejets et réservations restantes</h2>")
    parts.append(_table("Rejets", rejections))
    parts.append(_table("Réservations laissées chez les partenaires", read_csv(run_dir / "db" / "holds.csv")))
    parts.append("<h2>6. Métriques de la plateforme pendant le tir</h2>")
    parts.extend(_charts(run_dir, campaign))
    parts.append("<h2>7. Limites observées</h2>")
    parts.append(_limits(analysis))
    parts.append("<h2>8. Journaux</h2>")
    parts.append(_logs(logs))
    parts.append("<h2>9. Paramètres de la campagne</h2>")
    parts.append(f"<pre>{escape(json.dumps(campaign.get('parameters', {}), indent=1, ensure_ascii=False))}</pre>")
    parts.append(f"<p class='muted'>Généré le {datetime.now():%d/%m/%Y %H:%M} par titres-trading-performance-tests.</p></body></html>")
    out = run_dir / "dossier.html"
    out.write_text("\n".join(parts), encoding="utf-8")
    return out


# --- sections -------------------------------------------------------------------------

def _header(campaign: dict, end: dict, run_info: dict) -> str:
    rows = [("Environnement", campaign.get("env")), ("URL", campaign.get("baseUrl")),
            ("Début", campaign.get("startedAt")), ("Fin", end.get("endedAt")),
            ("Ordres passés", end.get("ordersBooked")), ("Interrompue", "oui" if end.get("aborted") else "non"),
            ("Durée demandée", campaign.get("duration")), ("Débit cible", campaign.get("targetRate")),
            ("Profil", campaign.get("profile")), ("Sens", campaign.get("side")), ("Graine", campaign.get("seed")),
            ("Instruments", ", ".join(f"{i.get('symbol') or i.get('isin')} @ {i.get('referencePrice')}" for i in campaign.get("instruments", []))),
            ("Gatling", campaign.get("gatlingVersion")), ("Java", campaign.get("javaVersion")),
            ("Opérateur", run_info.get("operator")), ("Commit", run_info.get("gitSha"))]
    return "<table>" + "".join(f"<tr><th>{escape(str(k))}</th><td>{escape(str(v if v is not None else ''))}</td></tr>" for k, v in rows) + "</table>"


def _environment(before: dict, after: dict) -> str:
    if not before:
        return "<p class='muted'>Pas de snapshot d'environnement.</p>"
    out = [f"<p>Cluster : {escape(str(before.get('cluster', {}).get('server', '')))} (OpenShift {escape(str(before.get('cluster', {}).get('openshiftVersion', '')))}), "
           f"relevé le {escape(str(before.get('takenAt', '')))}.</p>"]
    for namespace, data in before.get("namespaces", {}).items():
        out.append(f"<h3>{escape(namespace)}</h3><table><tr><th>Déploiement</th><th>Image</th><th>Réplicas</th><th>Requests</th><th>Limits</th></tr>")
        for dep in data.get("deployments", []):
            res = (dep.get("resources") or [{}])[0]
            out.append(f"<tr><td>{escape(str(dep.get('name')))}</td><td>{escape(', '.join(dep.get('images', [])))}</td>"
                       f"<td>{escape(str(dep.get('replicasReady')))} / {escape(str(dep.get('replicasWanted')))}</td>"
                       f"<td>{escape(_res(res.get('requests')))}</td><td>{escape(_res(res.get('limits')))}</td></tr>")
        out.append("</table>")
        if data.get("hpa"):
            out.append("<p>HPA : " + "; ".join(f"{h['name']} min {h['min']} / max {h['max']} (actuel {h.get('current')})" for h in data["hpa"]) + "</p>")
        if data.get("quota"):
            out.append(f"<p class='muted'>Quota : {escape(json.dumps(data['quota'].get('hard', {})))} — utilisé {escape(json.dumps(data['quota'].get('used', {})))}</p>")
        pods = data.get("pods", [])
        if pods:
            out.append("<table><tr><th>Pod</th><th>Nœud</th><th>Image (digest)</th><th>Redémarrages</th></tr>")
            for pod in pods:
                out.append(f"<tr><td>{escape(pod['name'])}</td><td>{escape(str(pod.get('node')))}</td>"
                           f"<td class='muted'>{escape(', '.join(str(i).split('@')[-1][:19] for i in pod.get('imageIds', [])))}</td><td>{pod.get('restarts')}</td></tr>")
            out.append("</table>")
    settings = before.get("runtimeSettings")
    if settings:
        out.append("<p>Paramètres de validation (APP_RUNTIME_SETTING) : " + ", ".join(f"{escape(k)} = {escape(str(v))}" for k, v in settings.items()) + "</p>")
    changes = snapshot.diff(before, after) if after else []
    if changes:
        out.append("<div class='banner'><b>L'environnement a changé pendant le tir :</b><ul>" + "".join(f"<li>{escape(c)}</li>" for c in changes) + "</ul></div>")
    elif after:
        out.append("<p class='ok'>Aucun changement d'environnement entre le début et la fin du tir.</p>")
    return "\n".join(out)


def _res(values) -> str:
    return ", ".join(f"{k} {v}" for k, v in (values or {}).items()) or "-"


def _gatling(gatling: dict, run_dir: Path) -> str:
    if not gatling.get("available"):
        return "<p class='muted'>Rapport Gatling absent.</p>"
    out = ["<p>Rapport détaillé : <a href='gatling/index.html'>gatling/index.html</a></p>",
           "<table><tr><th>Requête</th><th>Total</th><th>OK</th><th>KO</th><th>min</th><th>p50</th><th>p75</th><th>p95</th><th>p99</th><th>max</th><th>moy.</th><th>req/s</th></tr>"]
    for row in gatling.get("requests", []):
        indent = "&nbsp;" * 4 * row.get("depth", 0)
        ko_class = " class='ko'" if (row.get("ko") or 0) > 0 else ""
        out.append(f"<tr><td>{indent}{escape(str(row['name']))}</td><td>{row.get('count')}</td><td>{row.get('ok')}</td><td{ko_class}>{row.get('ko')}</td>"
                   f"<td>{row.get('min')}</td><td>{row.get('p50')}</td><td>{row.get('p75')}</td><td>{row.get('p95')}</td><td>{row.get('p99')}</td>"
                   f"<td>{row.get('max')}</td><td>{row.get('mean')}</td><td>{row.get('rps')}</td></tr>")
    out.append("</table><p class='muted'>Temps en millisecondes. Le groupe « time-to-submitted » mesure, côté client, le délai entre l'envoi de l'ordre et sa visibilité au marché (statut 105), temps d'attente entre deux interrogations compris.</p>")
    assertions = gatling.get("assertions") or []
    if assertions:
        out.append("<table><tr><th>Seuil</th><th>Résultat</th><th>Valeur</th></tr>")
        for a in assertions:
            ok = a.get("result")
            out.append(f"<tr><td>{escape(str(a.get('message') or a.get('path')))}</td><td class='{'ok' if ok else 'ko'}'>{'respecté' if ok else 'dépassé'}</td><td>{escape(str(a.get('actualValue', '')))}</td></tr>")
        out.append("</table>")
    return "\n".join(out)


def _ledger(ledger: dict) -> str:
    if not ledger or not ledger.get("orders"):
        return ""
    t = ledger.get("timeToSubmittedMs", {})
    return ("<table><tr><th>Ordres passés</th><th>Arrivés au marché</th><th>Conflits 409</th><th>p50</th><th>p95</th><th>p99</th><th>max</th><th>moy.</th><th>Interrogations moy.</th></tr>"
            f"<tr><td>{ledger.get('orders')}</td><td>{ledger.get('submitted')}</td><td>{ledger.get('conflicts409')}</td>"
            f"<td>{_ms(t.get('p50'))}</td><td>{_ms(t.get('p95'))}</td><td>{_ms(t.get('p99'))}</td><td>{_ms(t.get('max'))}</td><td>{_ms(t.get('mean'))}</td>"
            f"<td>{_num(ledger.get('polls', {}).get('mean'))}</td></tr></table>"
            "<p class='muted'>Délai réception → marché mesuré exactement par le générateur (ledger), par ordre.</p>")


def _orders_by_state(orders: dict) -> str:
    if not orders or not orders.get("total"):
        return ""
    rows = "".join(f"<tr><td>{escape(k)}</td><td>{v}</td></tr>" for k, v in sorted(orders.get("byState", {}).items()))
    return f"<table><tr><th>État final (ORDERS)</th><th>Ordres</th></tr>{rows}<tr><th>Total</th><td>{orders.get('total')}</td></tr></table>"


def _table(title: str, rows: list[dict]) -> str:
    if not rows:
        return f"<h4>{escape(title)}</h4><p class='muted'>aucune ligne</p>"
    columns = list(rows[0].keys())
    out = [f"<h4>{escape(title)}</h4><table><tr>" + "".join(f"<th>{escape(c)}</th>" for c in columns) + "</tr>"]
    for row in rows:
        out.append("<tr>" + "".join(f"<td>{escape(str(row.get(c, '') if row.get(c) is not None else ''))}</td>" for c in columns) + "</tr>")
    out.append("</table>")
    return "\n".join(out)


def _charts(run_dir: Path, campaign: dict) -> list[str]:
    samples = read_csv(run_dir / "metrics" / "samples.csv")
    top = read_csv(run_dir / "metrics" / "pods-top.csv")
    backlog = read_csv(run_dir / "db" / "backlog.csv")
    if not samples and not top:
        return ["<p class='muted'>Pas d'échantillons de métriques (clé PERF_METRICS_API_KEY absente ou exec refusé).</p>"]
    out = []
    counters = _series(samples, "http_server_requests_seconds_count", by="pod", filter_role="api")
    out.append(svg.line_chart("Débit par pod api (req/s, toutes routes)", _rates(counters), unit=""))
    quantiles = _series([s for s in samples if parse_labels_text(s["labels"]).get("quantile") == "0.95"],
                        "http_server_requests_seconds", by="uri", scale=1000, aggregate="max")
    out.append(svg.line_chart("p95 par route (ms, percentile glissant Micrometer, max des pods)", quantiles, unit=""))
    errors = _series([s for s in samples if parse_labels_text(s["labels"]).get("status", "").startswith("5")],
                     "http_server_requests_seconds_count", by="pod", filter_role="api")
    out.append(svg.line_chart("Réponses 5xx par pod (par seconde)", _rates(errors), unit=""))
    ext = _series([s for s in samples if parse_labels_text(s["labels"]).get("quantile") == "0.95"],
                  "external_service_requests_seconds", by="external_service", scale=1000, aggregate="max")
    out.append(svg.line_chart("p95 des appels partenaires (ms, percentile glissant, max des pods)", ext, unit=""))
    active = _series(samples, "hikaricp_connections_active", by="pod")
    pending = _series(samples, "hikaricp_connections_pending", by="pod")
    out.append(svg.line_chart("Connexions Oracle actives par pod (HikariCP)", active))
    out.append(svg.line_chart("Threads en attente d'une connexion Oracle (HikariCP pending)", pending))
    cpu = defaultdict(list)
    mem = defaultdict(list)
    for row in top:
        ts = _ts(row["ts"])
        cpu[row["pod"]].append((ts, float(row["cpu_m"])))
        mem[row["pod"]].append((ts, float(row["memory_mi"])))
    out.append(svg.line_chart("CPU par pod (millicœurs, oc adm top)", dict(cpu)))
    out.append(svg.line_chart("Mémoire par pod (MiB, oc adm top)", dict(mem)))
    gauges = {}
    for name in ("orders_submitting_oldest_age_seconds", "orders_broker_events_pending", "orders_failed_with_hold", "orders_broker_events_failed"):
        for key, values in _series(samples, name, by="pod", filter_role="worker").items():
            gauges[name.replace("orders_", "")] = values
    out.append(svg.line_chart("Jauges de la saga (pod orders-worker)", gauges))
    states = defaultdict(list)
    for row in backlog:
        states[row["state"]].append((_ts(row["ts"]), float(row["in_state_now"])))
    out.append(svg.line_chart("Ordres de la campagne par état (file de la saga)", dict(states)))
    hits = _series([s for s in samples if parse_labels_text(s["labels"]).get("result") == "hit"], "portfolio_listvalued_cache_requests_total", by="pod")
    misses = _series([s for s in samples if parse_labels_text(s["labels"]).get("result") == "miss"], "portfolio_listvalued_cache_requests_total", by="pod")
    out.append(svg.line_chart("Cache listvalued : hits et miss par pod (par seconde)",
                              {**{f"hit {k}": v for k, v in _rates(hits).items()}, **{f"miss {k}": v for k, v in _rates(misses).items()}}))
    return out


def _series(samples: list[dict], metric: str, by: str, filter_role: str | None = None, scale: float = 1.0,
            aggregate: str = "sum") -> dict[str, list[tuple[datetime, float]]]:
    """Sums (or maxes) the samples of a metric per tick, keyed by a label or the pod."""
    buckets: dict[str, dict[str, float]] = defaultdict(dict)
    for row in samples:
        if row["metric"] != metric or (filter_role and row["role"] != filter_role):
            continue
        labels = parse_labels_text(row["labels"])
        key = row["pod"] if by == "pod" else labels.get(by, "?")
        value = float(row["value"]) * scale
        current = buckets[key].get(row["ts"])
        if current is None:
            buckets[key][row["ts"]] = value
        elif aggregate == "max":
            buckets[key][row["ts"]] = max(current, value)
        else:
            buckets[key][row["ts"]] = current + value
    return {key: sorted((_ts(ts), v) for ts, v in values.items()) for key, values in buckets.items()}


def _rates(series: dict[str, list[tuple[datetime, float]]]) -> dict[str, list[tuple[datetime, float]]]:
    rates = {}
    for key, values in series.items():
        points = []
        for (t0, v0), (t1, v1) in zip(values, values[1:]):
            seconds = (t1 - t0).total_seconds()
            if seconds > 0:
                points.append((t1, max(0.0, (v1 - v0) / seconds)))
        rates[key] = points
    return rates


def _limits(analysis: dict) -> str:
    levels = analysis.get("levels")
    ledger = analysis.get("ledger", {})
    out = []
    if levels and levels.get("levels"):
        out.append("<table><tr><th>Palier</th><th>Ordres</th><th>Au marché</th><th>KO %</th><th>p50</th><th>p95</th><th>max</th></tr>")
        for entry in levels["levels"]:
            cls = " class='ko'" if levels.get("knee") == entry["level"] else ""
            out.append(f"<tr{cls}><td>{entry['level']}</td><td>{entry['orders']}</td><td>{entry['submitted']}</td><td>{entry['koPercent']}</td>"
                       f"<td>{_ms(entry['p50'])}</td><td>{_ms(entry['p95'])}</td><td>{_ms(entry['max'])}</td></tr>")
        out.append("</table>")
        if levels.get("knee"):
            out.append(f"<p><b>Coude observé au palier {levels['knee']}</b> : le p95 réception → marché dépasse le double du palier 1 ({_ms(levels.get('baseP95'))}) ou les échecs dépassent 2 %. "
                       "Rapprocher ce palier des graphiques (CPU du pod orders-worker, HikariCP, p95 partenaires) pour nommer le composant saturé.</p>")
        else:
            out.append("<p>Aucun coude dans les paliers tirés : la limite est au-delà du dernier palier.</p>")
    elif ledger.get("orders"):
        out.append("<p>Tir à charge constante : pas de recherche de limite. Les p95/p99 ci-dessus sont les valeurs de référence à ce niveau de charge.</p>")
    else:
        out.append("<p class='muted'>Pas d'ordre dans ce tir.</p>")
    return "\n".join(out)


def _logs(logs: dict) -> str:
    if not logs:
        return "<p class='muted'>Journaux non capturés.</p>"
    out = [f"<p>{logs.get('errors', 0)} erreur(s), {logs.get('warnings', 0)} avertissement(s) dans les pods pendant le tir (depuis {escape(str(logs.get('sinceTime', '')))}).</p>"]
    if logs.get("byMessage"):
        out.append("<table><tr><th>Message</th><th>Occurrences</th></tr>")
        for entry in logs["byMessage"][:30]:
            out.append(f"<tr><td>{escape(entry['message'])}</td><td>{entry['count']}</td></tr>")
        out.append("</table>")
    return "\n".join(out)


# --- helpers -------------------------------------------------------------------------

def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _ts(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _ms(value) -> str:
    return "-" if value is None else f"{float(value):.0f} ms"


def _num(value) -> str:
    return "-" if value is None else f"{float(value):.1f}"
