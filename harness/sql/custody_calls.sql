-- MegaCustody MT54x notifications: executions of the campaign's orders (none expected with
-- resting prices) and every call of the run window. Binds: :prefix, :start_ts, :end_ts
SELECT 'campaign' AS scope, a.endpoint, a.http_status, a.return_code, a.transport_error,
       COUNT(*) AS calls,
       ROUND(PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY a.duration_ms)) AS p50_ms,
       ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY a.duration_ms)) AS p95_ms,
       ROUND(PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY a.duration_ms)) AS p99_ms,
       MAX(a.duration_ms) AS max_ms,
       ROUND(AVG(a.duration_ms)) AS avg_ms
  FROM custody_instruction_audit a
  JOIN order_execution e ON e.exec_id = a.caller_reference
  JOIN orders o ON o.order_id = e.order_id
 WHERE o.source = 'PERF'
   AND o.client_reference LIKE :prefix
 GROUP BY a.endpoint, a.http_status, a.return_code, a.transport_error
UNION ALL
SELECT 'window' AS scope, a.endpoint, a.http_status, a.return_code, a.transport_error,
       COUNT(*),
       ROUND(PERCENTILE_CONT(0.50) WITHIN GROUP (ORDER BY a.duration_ms)),
       ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY a.duration_ms)),
       ROUND(PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY a.duration_ms)),
       MAX(a.duration_ms),
       ROUND(AVG(a.duration_ms))
  FROM custody_instruction_audit a
 WHERE a.created_at BETWEEN :start_ts AND :end_ts
 GROUP BY a.endpoint, a.http_status, a.return_code, a.transport_error
 ORDER BY 1, 2, 3
