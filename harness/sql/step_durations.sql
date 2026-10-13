-- Time the campaign's orders spent in each lifecycle state (same window query as the back
-- office order book, OrderLifecycleMetricsRepository.STEP_DURATIONS). Binds: :prefix
SELECT state,
       COUNT(*) AS completed,
       ROUND(AVG(seconds), 3) AS average_seconds,
       ROUND(MEDIAN(seconds), 3) AS median_seconds,
       ROUND(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY seconds), 3) AS p95_seconds,
       ROUND(PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY seconds), 3) AS p99_seconds,
       ROUND(MAX(seconds), 3) AS max_seconds
  FROM (
        SELECT state,
               EXTRACT(DAY FROM spent) * 86400 + EXTRACT(HOUR FROM spent) * 3600
                   + EXTRACT(MINUTE FROM spent) * 60 + EXTRACT(SECOND FROM spent) AS seconds
          FROM (
                SELECT h.to_state AS state,
                       h.entered_at,
                       h.worker_id,
                       LEAD(h.worker_id) OVER (PARTITION BY h.order_id ORDER BY h.entered_at, h.history_id) AS next_worker_id,
                       LEAD(h.entered_at) OVER (PARTITION BY h.order_id ORDER BY h.entered_at, h.history_id) - h.entered_at AS spent
                  FROM order_state_history h
                  JOIN orders o ON o.order_id = h.order_id
                 WHERE o.source = 'PERF'
                   AND o.client_reference LIKE :prefix
               )
         WHERE spent IS NOT NULL
           AND NVL(worker_id, '-') <> 'backfill'
           AND NVL(next_worker_id, '-') <> 'backfill'
       )
 GROUP BY state
 ORDER BY CASE state
            WHEN 'RECEIVED' THEN 1 WHEN 'VALIDATED' THEN 2 WHEN 'CASH_HELD' THEN 3 WHEN 'SECURITY_HELD' THEN 4
            WHEN 'SUBMITTING' THEN 5 WHEN 'SUBMITTED' THEN 6 ELSE 9 END, state
