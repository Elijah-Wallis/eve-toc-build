
-- WORK CENTERS
CREATE TABLE work_centers (name TEXT, type TEXT, capacity INT, util FLOAT);
-- BUFFER STATES (The Line)
CREATE TABLE buffer_states (name TEXT, current_wip INT, limit_wip INT);
-- CASH FLOW LEDGER
CREATE TABLE throughput_ledger (treatment TEXT, revenue FLOAT, minutes INT);
