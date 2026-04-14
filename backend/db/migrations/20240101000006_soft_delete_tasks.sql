-- migrate:up
ALTER TABLE tasks ADD COLUMN deleted_at TIMESTAMPTZ;

CREATE INDEX idx_tasks_live_project
    ON tasks (project_id, created_at DESC)
    WHERE deleted_at IS NULL;

CREATE INDEX idx_tasks_live_assignee
    ON tasks (assignee_id)
    WHERE deleted_at IS NULL;

-- migrate:down
DROP INDEX IF EXISTS idx_tasks_live_project;
DROP INDEX IF EXISTS idx_tasks_live_assignee;
ALTER TABLE tasks DROP COLUMN IF EXISTS deleted_at;
