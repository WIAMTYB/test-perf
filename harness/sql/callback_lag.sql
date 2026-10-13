-- Broker callbacks for the campaign's orders: how long after the broker's event time the
-- callback arrived, and how long the inbox took to apply it. Binds: :prefix
SELECT i.event_type,
       i.processed_state,
       COUNT(*) AS events,
       ROUND(MEDIAN((CAST(i.received_at AS DATE) - CAST(i.event_time AS DATE)) * 86400
                    + (EXTRACT(SECOND FROM i.received_at) - TRUNC(EXTRACT(SECOND FROM i.received_at)))
                    - (EXTRACT(SECOND FROM i.event_time) - TRUNC(EXTRACT(SECOND FROM i.event_time)))), 3) AS arrival_lag_median_s,
       ROUND(MAX((CAST(i.received_at AS DATE) - CAST(i.event_time AS DATE)) * 86400), 1) AS arrival_lag_max_s,
       ROUND(MEDIAN((CAST(i.processed_at AS DATE) - CAST(i.received_at AS DATE)) * 86400
                    + (EXTRACT(SECOND FROM i.processed_at) - TRUNC(EXTRACT(SECOND FROM i.processed_at)))
                    - (EXTRACT(SECOND FROM i.received_at) - TRUNC(EXTRACT(SECOND FROM i.received_at)))), 3) AS apply_lag_median_s,
       ROUND(MAX((CAST(i.processed_at AS DATE) - CAST(i.received_at AS DATE)) * 86400), 1) AS apply_lag_max_s,
       MAX(i.attempt_count) AS max_attempts
  FROM broker_event_inbox i
  JOIN orders o ON o.bank_order_id = i.bank_order_id
 WHERE o.source = 'PERF'
   AND o.client_reference LIKE :prefix
 GROUP BY i.event_type, i.processed_state
 ORDER BY 1, 2
