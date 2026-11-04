-- A user/assistant pair is inserted in one transaction; now() would tie their timestamps.
ALTER TABLE app.messages ALTER COLUMN created_at SET DEFAULT clock_timestamp();
