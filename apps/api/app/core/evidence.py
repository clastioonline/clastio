"""Append-only protection for evidence tables (audit_logs, consents).

The migration that introduced these tables installs the same trigger; the test suite builds its schema with
create_all() and installs it from here so tests exercise the real database rule.
"""

EVIDENCE_TABLES = ("audit_logs", "consents")

TRIGGER_FUNCTION_SQL = """
CREATE OR REPLACE FUNCTION forbid_evidence_change() RETURNS trigger AS $$
BEGIN
  IF current_setting('app.allow_evidence_purge', true) = 'on' THEN
    RETURN COALESCE(NEW, OLD);
  END IF;
  -- ON DELETE SET NULL of the acting user is the only update allowed.
  IF TG_OP = 'UPDATE' AND TG_TABLE_NAME = 'audit_logs' THEN
    IF ROW(NEW.id, NEW.action, NEW.target, NEW.target_type, NEW.target_id, NEW.details, NEW.before, NEW.after,
           NEW.reason, NEW.ip, NEW.request_id, NEW.created_at)
       IS NOT DISTINCT FROM
       ROW(OLD.id, OLD.action, OLD.target, OLD.target_type, OLD.target_id, OLD.details, OLD.before, OLD.after,
           OLD.reason, OLD.ip, OLD.request_id, OLD.created_at)
       AND NEW.actor_id IS NULL THEN
      RETURN NEW;
    END IF;
  END IF;
  RAISE EXCEPTION '% is append-only', TG_TABLE_NAME;
END $$ LANGUAGE plpgsql;
"""


def trigger_sql(table: str) -> str:
    return (f"CREATE TRIGGER {table}_append_only BEFORE UPDATE OR DELETE ON {table} "
            f"FOR EACH ROW EXECUTE FUNCTION forbid_evidence_change()")
