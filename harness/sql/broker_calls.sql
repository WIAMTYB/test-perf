-- NTS broker calls: the campaign's own orders, and every call of the run window for comparison.
-- Binds: :prefix, :start_ts, :end_ts (UTC timestamps)
SELECT 'campaign' AS scope, a.action, a.outcome, a.http_status,
       COUNT(*) AS calls,
       ROUND(PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY a.duration_ms)) AS p50_ms,
       ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY a.duration_ms)) AS p95_ms,
       ROUND(PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY a.duration_ms)) AS p99_ms,
       MAX(a.duration_ms) AS max_ms,
       ROUND(AVG(a.duration_ms)) AS avg_ms
  FROM broker_call_audit a
  JOIN orders o ON o.bank_order_id = a.bank_order_id
 WHERE o.source = 'PERF'
   AND o.client_reference LIKE :prefix
 GROUP BY a.action, a.outcome, a.http_status
UNION ALL
SELECT 'window' AS scope, a.action, a.outcome, a.http_status,
       COUNT(*),
       ROUND(PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY a.duration_ms)),
       ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY a.duration_ms)),
       ROUND(PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY a.duration_ms)),
       MAX(a.duration_ms),
       ROUND(AVG(a.duration_ms))
  FROM broker_call_audit a
 WHERE a.called_at BETWEEN :start_ts AND :end_ts
 GROUP BY a.action, a.outcome, a.http_status
 ORDER BY 1, 2, 3, 4
