-- What a cleanup would delete for the campaign, per table, and what blocks it.
-- Binds: :prefix
SELECT 'orders' AS what, COUNT(*) AS rows_ FROM orders o WHERE o.source = 'PERF' AND o.client_reference LIKE :prefix
UNION ALL SELECT 'orders_not_terminal', COUNT(*) FROM orders o WHERE o.source = 'PERF' AND o.client_reference LIKE :prefix
   AND o.lifecycle_state NOT IN ('REJECTED_VALIDATION', 'REJECTED_NO_CASH', 'REJECTED_NO_SECURITY', 'REJECTED_MARKET', 'FAILED', 'CANCELLED', 'EXPIRED', 'FILLED')
UNION ALL SELECT 'order_state_history', COUNT(*) FROM order_state_history h JOIN orders o ON o.order_id = h.order_id WHERE o.source = 'PERF' AND o.client_reference LIKE :prefix
UNION ALL SELECT 'order_request', COUNT(*) FROM order_request r JOIN orders o ON o.bank_order_id = r.bank_order_id WHERE o.source = 'PERF' AND o.client_reference LIKE :prefix
UNION ALL SELECT 'broker_call_audit', COUNT(*) FROM broker_call_audit a JOIN orders o ON o.bank_order_id = a.bank_order_id WHERE o.source = 'PERF' AND o.client_reference LIKE :prefix
UNION ALL SELECT 'broker_event_inbox', COUNT(*) FROM broker_event_inbox i JOIN orders o ON o.bank_order_id = i.bank_order_id WHERE o.source = 'PERF' AND o.client_reference LIKE :prefix
UNION ALL SELECT 'broker_event_trace', COUNT(*) FROM broker_event_trace t JOIN orders o ON o.bank_order_id = t.bank_order_id WHERE o.source = 'PERF' AND o.client_reference LIKE :prefix
UNION ALL SELECT 'order_execution', COUNT(*) FROM order_execution e JOIN orders o ON o.order_id = e.order_id WHERE o.source = 'PERF' AND o.client_reference LIKE :prefix
UNION ALL SELECT 'order_execution_history', COUNT(*) FROM order_execution_history eh JOIN order_execution e ON e.execution_id = eh.execution_id JOIN orders o ON o.order_id = e.order_id WHERE o.source = 'PERF' AND o.client_reference LIKE :prefix
UNION ALL SELECT 'custody_instruction_audit', COUNT(*) FROM custody_instruction_audit ca JOIN order_execution e ON e.exec_id = ca.caller_reference JOIN orders o ON o.order_id = e.order_id WHERE o.source = 'PERF' AND o.client_reference LIKE :prefix
UNION ALL SELECT 'cash_operation', COUNT(*) FROM cash_operation c JOIN orders o ON o.bank_order_id = c.operation_code WHERE o.source = 'PERF' AND o.client_reference LIKE :prefix
UNION ALL SELECT 'cash_movement', COUNT(*) FROM cash_movement m JOIN cash_operation c ON c.cash_operation_id = m.cash_operation_id JOIN orders o ON o.bank_order_id = c.operation_code WHERE o.source = 'PERF' AND o.client_reference LIKE :prefix
UNION ALL SELECT 'cash_movement_live', COUNT(*) FROM cash_movement m JOIN cash_operation c ON c.cash_operation_id = m.cash_operation_id JOIN orders o ON o.bank_order_id = c.operation_code WHERE o.source = 'PERF' AND o.client_reference LIKE :prefix AND m.state IN ('ACTIVE', 'PENDING')
UNION ALL SELECT 'position_minute_audit', COUNT(*) FROM position_minute_audit a JOIN cash_operation c ON c.cash_operation_id = a.cash_operation_id JOIN orders o ON o.bank_order_id = c.operation_code WHERE o.source = 'PERF' AND o.client_reference LIKE :prefix
UNION ALL SELECT 'security_operation', COUNT(*) FROM security_operation s JOIN orders o ON o.bank_order_id = s.operation_code WHERE o.source = 'PERF' AND o.client_reference LIKE :prefix
UNION ALL SELECT 'security_movement', COUNT(*) FROM security_movement m JOIN security_operation s ON s.security_operation_id = m.security_operation_id JOIN orders o ON o.bank_order_id = s.operation_code WHERE o.source = 'PERF' AND o.client_reference LIKE :prefix
UNION ALL SELECT 'security_movement_live', COUNT(*) FROM security_movement m JOIN security_operation s ON s.security_operation_id = m.security_operation_id JOIN orders o ON o.bank_order_id = s.operation_code WHERE o.source = 'PERF' AND o.client_reference LIKE :prefix AND m.state IN ('ACTIVE', 'PENDING')
UNION ALL SELECT 'security_movement_audit', COUNT(*) FROM security_movement_audit a JOIN security_operation s ON s.security_operation_id = a.security_operation_id JOIN orders o ON o.bank_order_id = s.operation_code WHERE o.source = 'PERF' AND o.client_reference LIKE :prefix
