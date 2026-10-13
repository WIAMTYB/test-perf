-- Campaign orders that did not reach the market, by reason. Binds: :prefix
SELECT o.lifecycle_state,
       o.fail_reason_code,
       o.broker_error_code,
       COUNT(*) AS orders,
       MIN(o.bank_order_id) AS first_order,
       MAX(o.bank_order_id) AS last_order,
       SUBSTR(MIN(o.last_error), 1, 200) AS sample_error
  FROM orders o
 WHERE o.source = 'PERF'
   AND o.client_reference LIKE :prefix
   AND (o.lifecycle_state LIKE 'REJECTED%' OR o.lifecycle_state = 'FAILED')
 GROUP BY o.lifecycle_state, o.fail_reason_code, o.broker_error_code
 ORDER BY 4 DESC
