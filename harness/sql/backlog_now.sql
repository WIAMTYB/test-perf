-- Campaign orders per lifecycle state right now, with the oldest entry (the saga backlog).
-- Sampled every tick during the run. Binds: :prefix
SELECT o.lifecycle_state AS state,
       COUNT(*) AS in_state_now,
       MIN(NVL(h.state_since, o.updated_at)) AS oldest_since
  FROM orders o
  LEFT JOIN (SELECT order_id, MAX(entered_at) AS state_since
               FROM order_state_history
              GROUP BY order_id) h ON h.order_id = o.order_id
 WHERE o.source = 'PERF'
   AND o.client_reference LIKE :prefix
 GROUP BY o.lifecycle_state
 ORDER BY 1
