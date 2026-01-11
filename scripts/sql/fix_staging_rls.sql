-- Fix RLS policies for staging tables
-- Run this in Supabase SQL editor

-- 1) Make sure RLS is enabled
ALTER TABLE staging_leads ENABLE ROW LEVEL SECURITY;
ALTER TABLE staging_conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE staging_messages ENABLE ROW LEVEL SECURITY;

-- 2) Drop existing policies if any
DROP POLICY IF EXISTS "service_role_staging_leads_all" ON staging_leads;
DROP POLICY IF EXISTS "service_role_staging_conversations_all" ON staging_conversations;
DROP POLICY IF EXISTS "service_role_staging_messages_all" ON staging_messages;

DROP POLICY IF EXISTS "anon_staging_leads_all" ON staging_leads;
DROP POLICY IF EXISTS "anon_staging_conversations_all" ON staging_conversations;
DROP POLICY IF EXISTS "anon_staging_messages_all" ON staging_messages;

-- 3) Create permissive policies for service_role (bypasses RLS)
CREATE POLICY "service_role_staging_leads_all" ON staging_leads
  FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "service_role_staging_conversations_all" ON staging_conversations
  FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY "service_role_staging_messages_all" ON staging_messages
  FOR ALL TO service_role USING (true) WITH CHECK (true);

-- 4) Create permissive policies for anon role (used by persistence agent with service_role key)
CREATE POLICY "anon_staging_leads_all" ON staging_leads
  FOR ALL TO anon USING (true) WITH CHECK (true);

CREATE POLICY "anon_staging_conversations_all" ON staging_conversations
  FOR ALL TO anon USING (true) WITH CHECK (true);

CREATE POLICY "anon_staging_messages_all" ON staging_messages
  FOR ALL TO anon USING (true) WITH CHECK (true);

-- 5) Verify policies
SELECT tablename, policyname, permissive, roles, cmd 
FROM pg_policies 
WHERE schemaname = 'public' 
AND tablename IN ('staging_leads', 'staging_conversations', 'staging_messages')
ORDER BY tablename, policyname;
