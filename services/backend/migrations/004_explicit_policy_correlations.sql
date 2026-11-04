-- Explicit outer references prevent same-named columns from binding to inner relations.
ALTER POLICY source_insert ON app.sources WITH CHECK (
 current_setting('app.is_admin',true)='true' OR (sources.owner_id::text=current_setting('app.principal_id',true) AND (
 (sources.conversation_id IS NULL AND EXISTS(SELECT 1 FROM app.bots b WHERE b.id=sources.bot_id AND b.owner_id=sources.owner_id)) OR
 (sources.conversation_id IS NOT NULL AND EXISTS(SELECT 1 FROM app.conversations c WHERE c.id=sources.conversation_id AND c.owner_id=sources.owner_id))
 ))
);
ALTER POLICY source_update ON app.sources WITH CHECK (
 current_setting('app.is_admin',true)='true' OR (sources.owner_id::text=current_setting('app.principal_id',true) AND (
 (sources.conversation_id IS NULL AND EXISTS(SELECT 1 FROM app.bots b WHERE b.id=sources.bot_id AND b.owner_id=sources.owner_id)) OR
 (sources.conversation_id IS NOT NULL AND EXISTS(SELECT 1 FROM app.conversations c WHERE c.id=sources.conversation_id AND c.owner_id=sources.owner_id))
 ))
);
ALTER POLICY dataset_insert ON app.datasets WITH CHECK (
 current_setting('app.is_admin',true)='true' OR (datasets.owner_id::text=current_setting('app.principal_id',true) AND
 EXISTS(SELECT 1 FROM app.sources s JOIN app.source_revisions r ON r.source_id=s.id
 WHERE s.id=datasets.source_id AND r.id=datasets.revision_id AND s.bot_id=datasets.bot_id
 AND s.owner_id::text=current_setting('app.principal_id',true)))
);
ALTER POLICY dataset_update ON app.datasets WITH CHECK (
 current_setting('app.is_admin',true)='true' OR (datasets.owner_id::text=current_setting('app.principal_id',true) AND
 EXISTS(SELECT 1 FROM app.sources s JOIN app.source_revisions r ON r.source_id=s.id
 WHERE s.id=datasets.source_id AND r.id=datasets.revision_id AND s.bot_id=datasets.bot_id
 AND s.owner_id::text=current_setting('app.principal_id',true)))
);
