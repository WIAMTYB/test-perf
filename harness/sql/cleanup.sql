-- Deletes the campaign's rows in foreign-key order. Executed statement by statement inside one
-- transaction by harness/perf/cleanup.py, only after the dry run shows no live hold and no
-- non-terminal order. Binds: :prefix
DELETE FROM broker_event_trace t WHERE t.bank_order_id IN (SELECT o.bank_order_id FROM orders o WHERE o.source = 'PERF' AND o.client_reference LIKE :prefix);
DELETE FROM broker_event_inbox i WHERE i.bank_order_id IN (SELECT o.bank_order_id FROM orders o WHERE o.source = 'PERF' AND o.client_reference LIKE :prefix);
DELETE FROM broker_call_audit a WHERE a.bank_order_id IN (SELECT o.bank_order_id FROM orders o WHERE o.source = 'PERF' AND o.client_reference LIKE :prefix);
DELETE FROM order_request r WHERE r.bank_order_id IN (SELECT o.bank_order_id FROM orders o WHERE o.source = 'PERF' AND o.client_reference LIKE :prefix);
DELETE FROM custody_instruction_audit ca WHERE ca.caller_reference IN (SELECT e.exec_id FROM order_execution e JOIN orders o ON o.order_id = e.order_id WHERE o.source = 'PERF' AND o.client_reference LIKE :prefix);
DELETE FROM order_execution_history eh WHERE eh.execution_id IN (SELECT e.execution_id FROM order_execution e JOIN orders o ON o.order_id = e.order_id WHERE o.source = 'PERF' AND o.client_reference LIKE :prefix);
DELETE FROM order_execution e WHERE e.order_id IN (SELECT o.order_id FROM orders o WHERE o.source = 'PERF' AND o.client_reference LIKE :prefix);
DELETE FROM order_state_history h WHERE h.order_id IN (SELECT o.order_id FROM orders o WHERE o.source = 'PERF' AND o.client_reference LIKE :prefix);
DELETE FROM position_minute_audit a WHERE a.cash_operation_id IN (SELECT c.cash_operation_id FROM cash_operation c JOIN orders o ON o.bank_order_id = c.operation_code WHERE o.source = 'PERF' AND o.client_reference LIKE :prefix);
DELETE FROM cash_movement m WHERE m.cash_operation_id IN (SELECT c.cash_operation_id FROM cash_operation c JOIN orders o ON o.bank_order_id = c.operation_code WHERE o.source = 'PERF' AND o.client_reference LIKE :prefix);
DELETE FROM cash_operation c WHERE c.operation_code IN (SELECT o.bank_order_id FROM orders o WHERE o.source = 'PERF' AND o.client_reference LIKE :prefix);
DELETE FROM security_movement_audit a WHERE a.security_operation_id IN (SELECT s.security_operation_id FROM security_operation s JOIN orders o ON o.bank_order_id = s.operation_code WHERE o.source = 'PERF' AND o.client_reference LIKE :prefix);
DELETE FROM security_movement m WHERE m.security_operation_id IN (SELECT s.security_operation_id FROM security_operation s JOIN orders o ON o.bank_order_id = s.operation_code WHERE o.source = 'PERF' AND o.client_reference LIKE :prefix);
DELETE FROM security_operation s WHERE s.operation_code IN (SELECT o.bank_order_id FROM orders o WHERE o.source = 'PERF' AND o.client_reference LIKE :prefix);
DELETE FROM orders o WHERE o.source = 'PERF' AND o.client_reference LIKE :prefix;
