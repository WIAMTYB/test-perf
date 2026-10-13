-- PositionMinute calls (cash holds, releases, balances) for the campaign's orders and for the run window.
-- Binds: :prefix, :start_ts, :end_ts
SELECT 'campaign' AS scope, a.endpoint, a.rule_code, a.http_status, a.return_code, a.transport_error,
       COUNT(*) AS calls,
       ROUND(PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY a.duration_ms)) AS p50_ms,
       ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY a.duration_ms)) AS p95_ms,
       ROUND(PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY a.duration_ms)) AS p99_ms,
       MAX(a.duration_ms) AS max_ms,
       ROUND(AVG(a.duration_ms)) AS avg_ms
  FROM position_minute_audit a
  JOIN cash_operation c ON c.cash_operation_id = a.cash_operation_id
  JOIN orders o ON o.bank_order_id = c.operation_code
 WHERE o.source = 'PERF'
   AND o.client_reference LIKE :prefix
 GROUP BY a.endpoint, a.rule_code, a.http_status, a.return_code, a.transport_error
UNION ALL
SELECT 'window' AS scope, a.endpoint, a.rule_code, a.http_status, a.return_code, a.transport_error,
       COUNT(*),
       ROUND(PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY a.duration_ms)),
       ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY a.duration_ms)),
       ROUND(PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY a.duration_ms)),
       MAX(a.duration_ms),
       ROUND(AVG(a.duration_ms))
  FROM position_minute_audit a
 WHERE a.created_at BETWEEN :start_ts AND :end_ts
 GROUP BY a.endpoint, a.rule_code, a.http_status, a.return_code, a.transport_error
 ORDER BY 1, 2, 3, 4
