import csv
import json
import tempfile
import unittest
from pathlib import Path

from perf import analysis, dossier, svg


def _write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


class DossierTests(unittest.TestCase):

    def _run_dir(self, tmp: str) -> Path:
        run_dir = Path(tmp)
        (run_dir / "campaign.json").write_text(json.dumps({
            "campaignId": "TEST-1", "simulation": "Smoke", "env": "recette", "baseUrl": "https://x.apps.ocpdev.attijariwafa.net",
            "startedAt": "2026-10-15T10:30:00Z", "seed": 1, "duration": "PT2M", "profile": "nominal", "side": "BUY",
            "instruments": [{"isin": "MA0000011884", "symbol": "BCP", "referencePrice": 335.5}], "parameters": {"a": "b"}}), encoding="utf-8")
        (run_dir / "campaign-end.json").write_text(json.dumps({"endedAt": "2026-10-15T10:32:00Z", "ordersBooked": 2, "aborted": False}), encoding="utf-8")
        _write_csv(run_dir / "orders-ledger.csv", [
            {"clientReference": "PERF-TEST-1-1-1", "bankOrderId": "BO-20261015-000001", "secAccount": "0000101841", "cashAccount": "000375N000300615",
             "isin": "MA0000011884", "side": "Buy", "price": "234.85", "quantity": "1", "bookHttpStatus": "200", "bookReturnCode": "200",
             "bookedAt": "2026-10-15T10:30:01.000Z", "submittedAt": "2026-10-15T10:30:02.100Z", "timeToSubmittedMs": "1100", "polls": "3", "finalStatus": "105", "failReason": ""},
            {"clientReference": "PERF-TEST-1-1-2", "bankOrderId": "BO-20261015-000002", "secAccount": "0000101841", "cashAccount": "000375N000300615",
             "isin": "MA0000011884", "side": "Buy", "price": "234.85", "quantity": "1", "bookHttpStatus": "200", "bookReturnCode": "200",
             "bookedAt": "2026-10-15T10:30:05.000Z", "submittedAt": "", "timeToSubmittedMs": "", "polls": "40", "finalStatus": "TIMEOUT", "failReason": ""}])
        _write_csv(run_dir / "db" / "step_durations.csv", [{"state": "RECEIVED", "completed": 2, "median_seconds": 0.3, "p95_seconds": 0.4, "max_seconds": 0.4}])
        _write_csv(run_dir / "db" / "rejections.csv", [{"lifecycle_state": "REJECTED_NO_CASH", "fail_reason_code": "208", "broker_error_code": "", "orders": 1}])
        _write_csv(run_dir / "metrics" / "samples.csv", [
            {"ts": "2026-10-15T10:30:00+00:00", "pod": "api-1", "role": "api", "metric": "http_server_requests_seconds_count", "labels": "status=200,uri=/xcastrade/book", "value": "10.0"},
            {"ts": "2026-10-15T10:30:15+00:00", "pod": "api-1", "role": "api", "metric": "http_server_requests_seconds_count", "labels": "status=200,uri=/xcastrade/book", "value": "25.0"},
            {"ts": "2026-10-15T10:30:15+00:00", "pod": "api-1", "role": "api", "metric": "http_server_requests_seconds", "labels": "quantile=0.95,uri=/xcastrade/book", "value": "0.2"},
            {"ts": "2026-10-15T10:30:15+00:00", "pod": "worker-1", "role": "worker", "metric": "orders_broker_events_pending", "labels": "module=orders", "value": "0.0"}])
        _write_csv(run_dir / "metrics" / "pods-top.csv", [{"ts": "2026-10-15T10:30:15+00:00", "pod": "api-1", "container": "api", "cpu_m": "120", "memory_mi": "130"}])
        (run_dir / "gatling" / "js").mkdir(parents=True)
        (run_dir / "gatling" / "js" / "stats.json").write_text(json.dumps({
            "type": "GROUP", "name": "All Requests", "stats": {"numberOfRequests": {"total": 5, "ok": 4, "ko": 1}, "percentiles1": {"total": 100},
                                                               "percentiles3": {"total": 300}, "percentiles4": {"total": 400}, "maxResponseTime": {"total": 500},
                                                               "minResponseTime": {"total": 50}, "meanResponseTime": {"total": 150}, "meanNumberOfRequestsPerSecond": {"total": 1.2}},
            "contents": {"req1": {"type": "REQUEST", "name": "book", "stats": {"numberOfRequests": {"total": 2, "ok": 2, "ko": 0}}}}}), encoding="utf-8")
        return run_dir

    def test_ledger_and_gatling_summaries(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = self._run_dir(tmp)
            ledger = analysis.ledger_summary(run_dir / "orders-ledger.csv")
            self.assertEqual(ledger["orders"], 2)
            self.assertEqual(ledger["submitted"], 1)
            self.assertEqual(ledger["byStatus"]["TIMEOUT"], 1)
            self.assertEqual(ledger["timeToSubmittedMs"]["p95"], 1100)
            gatling = analysis.gatling_summary(run_dir / "gatling")
            self.assertTrue(gatling["available"])
            self.assertEqual(gatling["requests"][1]["name"], "book")

    def test_dossier_renders_every_section(self):
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = self._run_dir(tmp)
            ledger = analysis.ledger_summary(run_dir / "orders-ledger.csv")
            (run_dir / "analysis.json").write_text(json.dumps({"ledger": ledger, "gatling": analysis.gatling_summary(run_dir / "gatling"),
                                                               "orders": {"total": 2, "byState": {"SUBMITTED": 1, "REJECTED_NO_CASH": 1}}}), encoding="utf-8")
            out = dossier.build(run_dir)
            html = out.read_text(encoding="utf-8")
        for needle in ("Campagne de performance TEST-1", "Environnement", "time-to-submitted", "REJECTED_NO_CASH",
                       "Débit par pod api", "<svg", "Limites observées", "Paramètres de la campagne"):
            self.assertIn(needle, html)

    def test_percentile_interpolates(self):
        self.assertEqual(analysis.percentile([1, 2, 3, 4], 0.5), 2.5)
        self.assertIsNone(analysis.percentile([], 0.5))

    def test_chart_without_data_is_an_empty_block(self):
        self.assertIn("aucune donnée", svg.line_chart("x", {}))


if __name__ == "__main__":
    unittest.main()
