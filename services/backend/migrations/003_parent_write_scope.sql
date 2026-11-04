-- Parent ownership is part of child write authorization, not just an API convention.
DROP POLICY conversations_scope ON app.conversations;
CREATE POLICY conversations_scope ON app.conversations FOR ALL USING (
  current_setting('app.is_admin',true)='true' OR
  (deleted_at IS NULL AND owner_id::text=current_setting('app.principal_id',true)
   AND EXISTS(SELECT 1 FROM app.bots b WHERE b.id=bot_id))
) WITH CHECK (
  current_setting('app.is_admin',true)='true' OR
  (owner_id::text=current_setting('app.principal_id',true) AND EXISTS(SELECT 1 FROM app.bots b WHERE b.id=bot_id))
);

DROP POLICY owner_insert ON app.sources;
DROP POLICY owner_update ON app.sources;
CREATE POLICY source_insert ON app.sources FOR INSERT WITH CHECK (
  current_setting('app.is_admin',true)='true' OR
  (owner_id::text=current_setting('app.principal_id',true) AND
   ((conversation_id IS NULL AND EXISTS(SELECT 1 FROM app.bots b WHERE b.id=bot_id AND b.owner_id=owner_id)) OR
    (conversation_id IS NOT NULL AND EXISTS(SELECT 1 FROM app.conversations c WHERE c.id=conversation_id AND c.owner_id=owner_id))))
);
CREATE POLICY source_update ON app.sources FOR UPDATE USING (
  current_setting('app.is_admin',true)='true' OR owner_id::text=current_setting('app.principal_id',true)
) WITH CHECK (
  current_setting('app.is_admin',true)='true' OR
  (owner_id::text=current_setting('app.principal_id',true) AND
   ((conversation_id IS NULL AND EXISTS(SELECT 1 FROM app.bots b WHERE b.id=bot_id AND b.owner_id=owner_id)) OR
    (conversation_id IS NOT NULL AND EXISTS(SELECT 1 FROM app.conversations c WHERE c.id=conversation_id AND c.owner_id=owner_id))))
);

DROP POLICY owner_insert ON app.source_revisions;
DROP POLICY owner_update ON app.source_revisions;
CREATE POLICY revision_insert ON app.source_revisions FOR INSERT WITH CHECK (
  current_setting('app.is_admin',true)='true' OR (owner_id::text=current_setting('app.principal_id',true) AND
  EXISTS(SELECT 1 FROM app.sources s WHERE s.id=source_id AND s.owner_id::text=current_setting('app.principal_id',true)))
);
CREATE POLICY revision_update ON app.source_revisions FOR UPDATE USING (
  current_setting('app.is_admin',true)='true' OR owner_id::text=current_setting('app.principal_id',true)
) WITH CHECK (
  current_setting('app.is_admin',true)='true' OR (owner_id::text=current_setting('app.principal_id',true) AND
  EXISTS(SELECT 1 FROM app.sources s WHERE s.id=source_id AND s.owner_id::text=current_setting('app.principal_id',true)))
);

DROP POLICY owner_insert ON app.chunks;
DROP POLICY owner_update ON app.chunks;
CREATE POLICY chunk_insert ON app.chunks FOR INSERT WITH CHECK (
  current_setting('app.is_admin',true)='true' OR (owner_id::text=current_setting('app.principal_id',true) AND
  EXISTS(SELECT 1 FROM app.source_revisions r WHERE r.id=revision_id AND r.owner_id::text=current_setting('app.principal_id',true)))
);
CREATE POLICY chunk_update ON app.chunks FOR UPDATE USING (
  current_setting('app.is_admin',true)='true' OR owner_id::text=current_setting('app.principal_id',true)
) WITH CHECK (
  current_setting('app.is_admin',true)='true' OR (owner_id::text=current_setting('app.principal_id',true) AND
  EXISTS(SELECT 1 FROM app.source_revisions r WHERE r.id=revision_id AND r.owner_id::text=current_setting('app.principal_id',true)))
);

DROP POLICY owner_insert ON app.datasets;
DROP POLICY owner_update ON app.datasets;
CREATE POLICY dataset_insert ON app.datasets FOR INSERT WITH CHECK (
  current_setting('app.is_admin',true)='true' OR (owner_id::text=current_setting('app.principal_id',true) AND
  EXISTS(SELECT 1 FROM app.sources s JOIN app.source_revisions r ON r.source_id=s.id
         WHERE s.id=source_id AND r.id=revision_id AND s.bot_id=bot_id AND s.owner_id::text=current_setting('app.principal_id',true)))
);
CREATE POLICY dataset_update ON app.datasets FOR UPDATE USING (
  current_setting('app.is_admin',true)='true' OR owner_id::text=current_setting('app.principal_id',true)
) WITH CHECK (
  current_setting('app.is_admin',true)='true' OR (owner_id::text=current_setting('app.principal_id',true) AND
  EXISTS(SELECT 1 FROM app.sources s JOIN app.source_revisions r ON r.source_id=s.id
         WHERE s.id=source_id AND r.id=revision_id AND s.bot_id=bot_id AND s.owner_id::text=current_setting('app.principal_id',true)))
);
