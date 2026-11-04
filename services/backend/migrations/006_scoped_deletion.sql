-- Soft deletion immediately removes a row from its SELECT policy. A narrow,
-- ownership-checked function performs that transition without widening read access.
CREATE FUNCTION app.soft_delete_owned(resource_kind text,target uuid) RETURNS boolean
LANGUAGE plpgsql SECURITY DEFINER SET search_path = '' AS $$
DECLARE caller text := current_setting('app.principal_id',true);
BEGIN
  IF resource_kind='source' THEN
    IF NOT EXISTS(SELECT 1 FROM app.sources s WHERE s.id=target AND s.owner_id::text=caller AND s.deleted_at IS NULL) THEN
      RETURN false;
    END IF;
    UPDATE app.sources SET deleted_at=now(),enabled=false WHERE id=target;
  ELSIF resource_kind='bot' THEN
    IF NOT EXISTS(SELECT 1 FROM app.bots b WHERE b.id=target AND b.owner_id::text=caller AND NOT b.is_seed AND b.deleted_at IS NULL) THEN
      RETURN false;
    END IF;
    UPDATE app.runs SET cancel_requested=true WHERE bot_id=target AND status IN ('QUEUED','RUNNING');
    UPDATE app.bots SET deleted_at=now() WHERE id=target;
  ELSIF resource_kind='conversation' THEN
    IF NOT EXISTS(SELECT 1 FROM app.conversations c WHERE c.id=target AND c.owner_id::text=caller AND c.deleted_at IS NULL) THEN
      RETURN false;
    END IF;
    UPDATE app.runs SET cancel_requested=true WHERE conversation_id=target AND status IN ('QUEUED','RUNNING');
    UPDATE app.conversations SET deleted_at=now() WHERE id=target;
  ELSE
    RETURN false;
  END IF;
  RETURN true;
END $$;
REVOKE ALL ON FUNCTION app.soft_delete_owned(text,uuid) FROM PUBLIC;
