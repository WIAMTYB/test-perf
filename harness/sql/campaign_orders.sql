-- Every order of the campaign, as ORDERS holds it. Binds: :prefix (client reference LIKE pattern)
SELECT o.bank_order_id,
       o.client_reference,
       o.client_sec_account,
       o.client_cash_account,
       o.isin,
       CASE o.side WHEN '1' THEN 'BUY' WHEN '2' THEN 'SELL' ELSE o.side END AS side,
       o.ord_type,
       o.price,
       o.order_qty,
       o.net_client,
       o.lifecycle_state,
       o.exchange_status,
       o.fail_reason_code,
       o.broker_error_code,
       o.broker_order_id,
       o.attempt_count,
       o.last_error,
       o.submitted_at AS received_at,
       o.updated_at,
       o.cash_hold_reference,
       o.security_hold_reference
  FROM orders o
 WHERE o.source = 'PERF'
   AND o.client_reference LIKE :prefix
 ORDER BY o.order_id
