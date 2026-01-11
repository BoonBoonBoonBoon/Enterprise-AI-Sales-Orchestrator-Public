-- Create test client record for 'agentic-dev' tenant
-- This UUID is deterministically generated from tenant_id using UUID5
-- Run this in Supabase SQL Editor once

INSERT INTO clients (id, name)
VALUES (
    '93d28de3-2835-52f3-b2ef-c2eb8a2ac09b',
    'Agentic Dev Test Client'
)
ON CONFLICT (id) DO NOTHING;

-- Verify it was created
SELECT * FROM clients WHERE id = '93d28de3-2835-52f3-b2ef-c2eb8a2ac09b';
