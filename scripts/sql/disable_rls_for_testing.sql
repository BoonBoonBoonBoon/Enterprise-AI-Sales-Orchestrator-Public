-- Temporarily disable RLS to test basic connectivity
-- WARNING: This removes security! Only for testing.

ALTER TABLE clients DISABLE ROW LEVEL SECURITY;
ALTER TABLE staging_leads DISABLE ROW LEVEL SECURITY;
ALTER TABLE lead_outreach DISABLE ROW LEVEL SECURITY;
ALTER TABLE conversations DISABLE ROW LEVEL SECURITY;

-- Verify RLS is disabled
SELECT schemaname, tablename, rowsecurity
FROM pg_tables
WHERE tablename IN ('clients', 'staging_leads', 'lead_outreach', 'conversations');
