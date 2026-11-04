-- Write policies must not grant a second, more permissive path to SELECT.
DROP POLICY bots_write ON app.bots;
DROP POLICY sources_write ON app.sources;
DROP POLICY revisions_write ON app.source_revisions;
DROP POLICY chunks_write ON app.chunks;
DROP POLICY datasets_write ON app.datasets;
DO $$ DECLARE item text; operation text; BEGIN
  FOREACH item IN ARRAY ARRAY['bots','sources','source_revisions','chunks','datasets'] LOOP
    EXECUTE format('CREATE POLICY owner_insert ON app.%I FOR INSERT WITH CHECK (owner_id::text=current_setting(''app.principal_id'',true) OR current_setting(''app.is_admin'',true)=''true'')',item);
    EXECUTE format('CREATE POLICY owner_update ON app.%I FOR UPDATE USING (owner_id::text=current_setting(''app.principal_id'',true) OR current_setting(''app.is_admin'',true)=''true'') WITH CHECK (owner_id::text=current_setting(''app.principal_id'',true) OR current_setting(''app.is_admin'',true)=''true'')',item);
    EXECUTE format('CREATE POLICY owner_delete ON app.%I FOR DELETE USING (owner_id::text=current_setting(''app.principal_id'',true) OR current_setting(''app.is_admin'',true)=''true'')',item);
  END LOOP;
END $$;
CREATE INDEX principals_expiry_idx ON app.principals(expires_at) WHERE kind='GUEST';
