-- Holds the campaign left on the partners: live cash reservations at PositionMinute and
-- pending security movements at MegaTrade. The pool loses this until the broker closes
-- the orders. Binds: :prefix
SELECT 'cash' AS kind, m.state, COUNT(*) AS movements, SUM(m.amount) AS total_amount_centimes,
       MIN(m.created_at) AS oldest, MAX(m.created_at) AS newest
  FROM cash_movement m
  JOIN cash_operation c ON c.cash_operation_id = m.cash_operation_id
  JOIN orders o ON o.bank_order_id = c.operation_code
 WHERE o.source = 'PERF'
   AND o.client_reference LIKE :prefix
   AND m.purpose = 'HOLD'
 GROUP BY m.state
UNION ALL
SELECT 'security' AS kind, m.state, COUNT(*), SUM(m.quantity), MIN(m.created_at), MAX(m.created_at)
  FROM security_movement m
  JOIN security_operation s ON s.security_operation_id = m.security_operation_id
  JOIN orders o ON o.bank_order_id = s.operation_code
 WHERE o.source = 'PERF'
   AND o.client_reference LIKE :prefix
   AND m.purpose = 'HOLD'
 GROUP BY m.state
 ORDER BY 1, 2
