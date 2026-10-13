import unittest

from perf import promtext

TEXT = """
# HELP http_server_requests_seconds Duration of HTTP server request handling
# TYPE http_server_requests_seconds summary
http_server_requests_seconds{application="api-titres-selfcare",exception="none",method="POST",module="orders",outcome="SUCCESS",status="200",uri="/xcastrade/book",quantile="0.95",} 0.21
http_server_requests_seconds_count{application="api-titres-selfcare",exception="none",method="POST",module="orders",outcome="SUCCESS",status="200",uri="/xcastrade/book",} 42.0
http_server_requests_seconds_sum{application="api-titres-selfcare",method="POST",status="200",uri="/xcastrade/book",} 7.5
jvm_memory_used_bytes{area="heap",id="eden space",} 1.2E7
jvm_gc_pause_seconds_count{action="end of minor GC",cause="G1 Evacuation Pause",} 3.0
external_service_requests_seconds{external_service="broker",operation="ordercreate",status="202",quantile="0.95",} 0.148
orders_broker_events_pending{module="orders",} 0.0
"""


class PromTextTests(unittest.TestCase):

    def test_keeps_only_the_families_of_interest(self):
        samples = promtext.parse(TEXT)
        names = {s.name for s in samples}
        self.assertIn("http_server_requests_seconds_count", names)
        self.assertIn("external_service_requests_seconds", names)
        self.assertIn("orders_broker_events_pending", names)
        self.assertNotIn("jvm_gc_pause_seconds_count", names)

    def test_labels_and_values(self):
        samples = {(s.name, s.label("quantile")): s for s in promtext.parse(TEXT)}
        count = samples[("http_server_requests_seconds_count", "")]
        self.assertEqual(count.value, 42.0)
        self.assertEqual(count.label("uri"), "/xcastrade/book")
        self.assertEqual(count.label("status"), "200")
        p95 = samples[("http_server_requests_seconds", "0.95")]
        self.assertAlmostEqual(p95.value, 0.21)
        self.assertEqual(samples[("jvm_memory_used_bytes", "")].value, 1.2e7)

    def test_labels_round_trip_through_csv_text(self):
        sample = next(s for s in promtext.parse(TEXT) if s.name == "external_service_requests_seconds")
        labels = promtext.parse_labels_text(sample.labels_text())
        self.assertEqual(labels["external_service"], "broker")
        self.assertEqual(labels["operation"], "ordercreate")
        self.assertEqual(labels["quantile"], "0.95")


if __name__ == "__main__":
    unittest.main()
