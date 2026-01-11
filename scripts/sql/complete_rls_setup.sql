-- Complete RLS Setup for All Tables
-- Ensures GRANT permissions + RLS policies for messages table

-- 1. Grant permissions to messages table (if missing)
GRANT ALL ON messages TO authenticated, anon;

-- 2. Enable RLS on messages (if not already enabled)
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;

-- 3. Drop existing message policies
DROP POLICY IF EXISTS "messages_agent_select" ON messages;
DROP POLICY IF EXISTS "messages_agent_write" ON messages;

-- 4. Create policies for messages table
CREATE POLICY "messages_agent_select" ON messages
  FOR SELECT
  TO anon
  USING (
    public.get_user_role() IN ('agent_reader', 'agent_writer')
  );

CREATE POLICY "messages_agent_write" ON messages
  FOR ALL
  TO anon
  USING (
    public.get_user_role() = 'agent_writer'
  )
  WITH CHECK (
    public.get_user_role() = 'agent_writer'
  );

-- 5. Verify all table permissions
SELECT 
    table_name,
    grantee,
    privilege_type
FROM information_schema.table_privileges
WHERE table_name IN ('clients', 'staging_leads', 'leads', 'conversations', 'messages')
  AND grantee IN ('anon', 'authenticated')
ORDER BY table_name, grantee, privilege_type;

-- 6. Verify all RLS policies
SELECT 
  tablename, 
  policyname, 
  roles,
  cmd,
  qual IS NOT NULL as has_using,
  with_check IS NOT NULL as has_check
FROM pg_policies
WHERE tablename IN ('clients', 'staging_leads', 'leads', 'conversations', 'messages')
ORDER BY tablename, policyname;

-- 7. Verify RLS is enabled on all tables
SELECT 
  schemaname,
  tablename, 
  rowsecurity as rls_enabled
FROM pg_tables
WHERE tablename IN ('clients', 'staging_leads', 'leads', 'conversations', 'messages')
ORDER BY tablename;
