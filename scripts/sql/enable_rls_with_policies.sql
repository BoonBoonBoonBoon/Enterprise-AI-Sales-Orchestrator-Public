-- Re-enable RLS and create proper policies for agent access
-- Run this after confirming basic connectivity works

-- 1. Re-enable RLS
ALTER TABLE clients ENABLE ROW LEVEL SECURITY;
ALTER TABLE staging_leads ENABLE ROW LEVEL SECURITY;
ALTER TABLE leads ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;

-- 2. Drop any existing policies
DROP POLICY IF EXISTS "clients_service_role_all" ON clients;
DROP POLICY IF EXISTS "clients_agent_select" ON clients;
DROP POLICY IF EXISTS "clients_agent_write" ON clients;
DROP POLICY IF EXISTS "staging_leads_service_role_all" ON staging_leads;
DROP POLICY IF EXISTS "staging_leads_agent_select" ON staging_leads;
DROP POLICY IF EXISTS "staging_leads_agent_write" ON staging_leads;
DROP POLICY IF EXISTS "leads_service_role_all" ON leads;
DROP POLICY IF EXISTS "leads_agent_select" ON leads;
DROP POLICY IF EXISTS "leads_agent_write" ON leads;
DROP POLICY IF EXISTS "conversations_service_role_all" ON conversations;
DROP POLICY IF EXISTS "conversations_agent_select" ON conversations;
DROP POLICY IF EXISTS "conversations_agent_write" ON conversations;
DROP POLICY IF EXISTS "messages_service_role_all" ON messages;
DROP POLICY IF EXISTS "messages_agent_select" ON messages;
DROP POLICY IF EXISTS "messages_agent_write" ON messages;

-- 3. Recreate get_user_role function (if needed)
CREATE OR REPLACE FUNCTION public.get_user_role()
RETURNS TEXT AS $$
  SELECT COALESCE(
    (current_setting('request.jwt.claims', true)::jsonb->>'user_role')::text,
    ''
  );
$$ LANGUAGE SQL STABLE SECURITY DEFINER;

-- 4. Create policies for clients table
CREATE POLICY "clients_agent_select" ON clients
  FOR SELECT
  TO anon
  USING (
    public.get_user_role() IN ('agent_reader', 'agent_writer')
  );

CREATE POLICY "clients_agent_write" ON clients
  FOR ALL
  TO anon
  USING (
    public.get_user_role() = 'agent_writer'
  )
  WITH CHECK (
    public.get_user_role() = 'agent_writer'
  );

-- 5. Create policies for staging_leads table
CREATE POLICY "staging_leads_agent_select" ON staging_leads
  FOR SELECT
  TO anon
  USING (
    public.get_user_role() IN ('agent_reader', 'agent_writer')
  );

CREATE POLICY "staging_leads_agent_write" ON staging_leads
  FOR ALL
  TO anon
  USING (
    public.get_user_role() = 'agent_writer'
  )
  WITH CHECK (
    public.get_user_role() = 'agent_writer'
  );

-- 6. Create policies for leads table
CREATE POLICY "leads_agent_select" ON leads
  FOR SELECT
  TO anon
  USING (
    public.get_user_role() IN ('agent_reader', 'agent_writer')
  );

CREATE POLICY "leads_agent_write" ON leads
  FOR ALL
  TO anon
  USING (
    public.get_user_role() = 'agent_writer'
  )
  WITH CHECK (
    public.get_user_role() = 'agent_writer'
  );

-- 7. Create policies for conversations table
CREATE POLICY "conversations_agent_select" ON conversations
  FOR SELECT
  TO anon
  USING (
    public.get_user_role() IN ('agent_reader', 'agent_writer')
  );

CREATE POLICY "conversations_agent_write" ON conversations
  FOR ALL
  TO anon
  USING (
    public.get_user_role() = 'agent_writer'
  )
  WITH CHECK (
    public.get_user_role() = 'agent_writer'
  );

-- 7. Messages table policies
DROP POLICY IF EXISTS "messages_agent_select" ON messages;
DROP POLICY IF EXISTS "messages_agent_write" ON messages;

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

-- 8. Verify policies
SELECT 
  schemaname, 
  tablename, 
  policyname, 
  roles,
  cmd
FROM pg_policies
WHERE tablename IN ('clients', 'staging_leads', 'leads', 'conversations', 'messages')
ORDER BY tablename, policyname;
