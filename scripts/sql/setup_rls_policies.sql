-- ==============================================================================
-- AGENTIC SYSTEM - ROW LEVEL SECURITY (RLS) POLICIES
-- ==============================================================================
-- Fixed: Allows service_role to bypass RLS (standard Supabase behavior)
-- Custom JWTs with user_role claims also supported for future use
-- ==============================================================================

-- Enable Row Level Security on all tables
ALTER TABLE clients ENABLE ROW LEVEL SECURITY;
ALTER TABLE staging_leads ENABLE ROW LEVEL SECURITY;
ALTER TABLE staging_conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE staging_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE lead_outreach ENABLE ROW LEVEL SECURITY;
ALTER TABLE leads ENABLE ROW LEVEL SECURITY;
ALTER TABLE conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;

-- ==============================================================================
-- HELPER FUNCTION: Extract user_role from JWT (in public schema)
-- ==============================================================================
CREATE OR REPLACE FUNCTION public.get_user_role()
RETURNS TEXT AS $$
  SELECT (current_setting('request.jwt.claims', true)::jsonb->>'user_role')::text;
$$ LANGUAGE SQL STABLE;

-- ==============================================================================
-- CLIENTS TABLE - RLS Policies
-- ==============================================================================

DROP POLICY IF EXISTS "service_role_clients_all" ON clients;
DROP POLICY IF EXISTS "agent_reader_clients_select" ON clients;
DROP POLICY IF EXISTS "agent_writer_clients_all" ON clients;

-- Service role bypasses RLS (Supabase default)
CREATE POLICY "service_role_clients_all"
  ON clients
  FOR ALL
  TO service_role
  USING (true)
  WITH CHECK (true);

-- RAG Agent: READ ONLY (for future custom JWT use)
CREATE POLICY "agent_reader_clients_select"
  ON clients
  FOR SELECT
  TO authenticated
  USING (public.get_user_role() = 'agent_reader' OR public.get_user_role() = 'agent_writer');

-- Persistence Agent: FULL CRUD (for future custom JWT use)
CREATE POLICY "agent_writer_clients_all"
  ON clients
  FOR ALL
  TO authenticated
  USING (public.get_user_role() = 'agent_writer')
  WITH CHECK (public.get_user_role() = 'agent_writer');

-- ==============================================================================
-- STAGING_LEADS TABLE - RLS Policies
-- ==============================================================================

DROP POLICY IF EXISTS "service_role_staging_leads_all" ON staging_leads;
DROP POLICY IF EXISTS "agent_reader_staging_leads_select" ON staging_leads;
DROP POLICY IF EXISTS "agent_writer_staging_leads_all" ON staging_leads;

-- ==============================================================================
-- STAGING_CONVERSATIONS TABLE - RLS Policies
-- ==============================================================================

DROP POLICY IF EXISTS "service_role_staging_conversations_all" ON staging_conversations;
DROP POLICY IF EXISTS "agent_reader_staging_conversations_select" ON staging_conversations;
DROP POLICY IF EXISTS "agent_writer_staging_conversations_all" ON staging_conversations;

-- Service role bypasses RLS
CREATE POLICY "service_role_staging_conversations_all"
  ON staging_conversations
  FOR ALL
  TO service_role
  USING (true)
  WITH CHECK (true);

-- RAG Agent: READ ONLY
CREATE POLICY "agent_reader_staging_conversations_select"
  ON staging_conversations
  FOR SELECT
  TO authenticated
  USING (public.get_user_role() = 'agent_reader' OR public.get_user_role() = 'agent_writer');

-- Persistence Agent: FULL CRUD
CREATE POLICY "agent_writer_staging_conversations_all"
  ON staging_conversations
  FOR ALL
  TO authenticated
  USING (public.get_user_role() = 'agent_writer')
  WITH CHECK (public.get_user_role() = 'agent_writer');

-- ==============================================================================
-- STAGING_MESSAGES TABLE - RLS Policies
-- ==============================================================================

DROP POLICY IF EXISTS "service_role_staging_messages_all" ON staging_messages;
DROP POLICY IF EXISTS "agent_reader_staging_messages_select" ON staging_messages;
DROP POLICY IF EXISTS "agent_writer_staging_messages_all" ON staging_messages;

-- Service role bypasses RLS
CREATE POLICY "service_role_staging_messages_all"
  ON staging_messages
  FOR ALL
  TO service_role
  USING (true)
  WITH CHECK (true);

-- RAG Agent: READ ONLY
CREATE POLICY "agent_reader_staging_messages_select"
  ON staging_messages
  FOR SELECT
  TO authenticated
  USING (public.get_user_role() = 'agent_reader' OR public.get_user_role() = 'agent_writer');

-- Persistence Agent: FULL CRUD
CREATE POLICY "agent_writer_staging_messages_all"
  ON staging_messages
  FOR ALL
  TO authenticated
  USING (public.get_user_role() = 'agent_writer')
  WITH CHECK (public.get_user_role() = 'agent_writer');

-- Service role bypasses RLS
CREATE POLICY "service_role_staging_leads_all"
  ON staging_leads
  FOR ALL
  TO service_role
  USING (true)
  WITH CHECK (true);

-- RAG Agent: READ ONLY
CREATE POLICY "agent_reader_staging_leads_select"
  ON staging_leads
  FOR SELECT
  TO authenticated
  USING (public.get_user_role() = 'agent_reader' OR public.get_user_role() = 'agent_writer');

-- Persistence Agent: FULL CRUD
CREATE POLICY "agent_writer_staging_leads_all"
  ON staging_leads
  FOR ALL
  TO authenticated
  USING (public.get_user_role() = 'agent_writer')
  WITH CHECK (public.get_user_role() = 'agent_writer');

-- ==============================================================================
-- LEAD_OUTREACH TABLE - RLS Policies
-- ==============================================================================

DROP POLICY IF EXISTS "service_role_lead_outreach_all" ON lead_outreach;
DROP POLICY IF EXISTS "agent_reader_lead_outreach_select" ON lead_outreach;
DROP POLICY IF EXISTS "agent_writer_lead_outreach_all" ON lead_outreach;

-- ============================================================================== 
-- LEADS TABLE - RLS Policies
-- ============================================================================== 

DROP POLICY IF EXISTS "service_role_leads_all" ON leads;
DROP POLICY IF EXISTS "agent_reader_leads_select" ON leads;
DROP POLICY IF EXISTS "agent_writer_leads_all" ON leads;

-- Service role bypasses RLS
CREATE POLICY "service_role_leads_all"
  ON leads
  FOR ALL
  TO service_role
  USING (true)
  WITH CHECK (true);

-- RAG Agent: READ ONLY
CREATE POLICY "agent_reader_leads_select"
  ON leads
  FOR SELECT
  TO authenticated
  USING (public.get_user_role() = 'agent_reader' OR public.get_user_role() = 'agent_writer');

-- Persistence Agent: FULL CRUD
CREATE POLICY "agent_writer_leads_all"
  ON leads
  FOR ALL
  TO authenticated
  USING (public.get_user_role() = 'agent_writer')
  WITH CHECK (public.get_user_role() = 'agent_writer');

-- Service role bypasses RLS
CREATE POLICY "service_role_lead_outreach_all"
  ON lead_outreach
  FOR ALL
  TO service_role
  USING (true)
  WITH CHECK (true);

-- RAG Agent: READ ONLY
CREATE POLICY "agent_reader_lead_outreach_select"
  ON lead_outreach
  FOR SELECT
  TO authenticated
  USING (public.get_user_role() = 'agent_reader' OR public.get_user_role() = 'agent_writer');

-- Persistence Agent: FULL CRUD
CREATE POLICY "agent_writer_lead_outreach_all"
  ON lead_outreach
  FOR ALL
  TO authenticated
  USING (public.get_user_role() = 'agent_writer')
  WITH CHECK (public.get_user_role() = 'agent_writer');

-- ==============================================================================
-- CONVERSATIONS TABLE - RLS Policies
-- ==============================================================================

DROP POLICY IF EXISTS "service_role_conversations_all" ON conversations;
DROP POLICY IF EXISTS "agent_reader_conversations_select" ON conversations;
DROP POLICY IF EXISTS "agent_writer_conversations_all" ON conversations;

-- ============================================================================== 
-- MESSAGES TABLE - RLS Policies
-- ============================================================================== 

DROP POLICY IF EXISTS "service_role_messages_all" ON messages;
DROP POLICY IF EXISTS "agent_reader_messages_select" ON messages;
DROP POLICY IF EXISTS "agent_writer_messages_all" ON messages;

-- Service role bypasses RLS
CREATE POLICY "service_role_messages_all"
  ON messages
  FOR ALL
  TO service_role
  USING (true)
  WITH CHECK (true);

-- RAG Agent: READ ONLY
CREATE POLICY "agent_reader_messages_select"
  ON messages
  FOR SELECT
  TO authenticated
  USING (public.get_user_role() = 'agent_reader' OR public.get_user_role() = 'agent_writer');

-- Persistence Agent: FULL CRUD
CREATE POLICY "agent_writer_messages_all"
  ON messages
  FOR ALL
  TO authenticated
  USING (public.get_user_role() = 'agent_writer')
  WITH CHECK (public.get_user_role() = 'agent_writer');

-- Service role bypasses RLS
CREATE POLICY "service_role_conversations_all"
  ON conversations
  FOR ALL
  TO service_role
  USING (true)
  WITH CHECK (true);

-- RAG Agent: READ ONLY
CREATE POLICY "agent_reader_conversations_select"
  ON conversations
  FOR SELECT
  TO authenticated
  USING (public.get_user_role() = 'agent_reader' OR public.get_user_role() = 'agent_writer');

-- Persistence Agent: FULL CRUD
CREATE POLICY "agent_writer_conversations_all"
  ON conversations
  FOR ALL
  TO authenticated
  USING (public.get_user_role() = 'agent_writer')
  WITH CHECK (public.get_user_role() = 'agent_writer');

-- ==============================================================================
-- VERIFICATION QUERIES (run these to confirm policies are active)
-- ==============================================================================

-- Check RLS is enabled
SELECT schemaname, tablename, rowsecurity 
FROM pg_tables 
WHERE tablename IN (
  'clients',
  'staging_leads',
  'staging_conversations',
  'staging_messages',
  'lead_outreach',
  'leads',
  'conversations',
  'messages'
)
ORDER BY tablename;
-- Expected: rowsecurity = TRUE for all tables

-- Check policies exist
SELECT schemaname, tablename, policyname, cmd
FROM pg_policies
WHERE tablename IN (
  'clients',
  'staging_leads',
  'staging_conversations',
  'staging_messages',
  'lead_outreach',
  'leads',
  'conversations',
  'messages'
)
ORDER BY tablename, policyname;
-- Expected: policies exist for each table

-- Check helper function exists
SELECT routine_name, routine_type
FROM information_schema.routines
WHERE routine_name = 'get_user_role';
-- Expected: get_user_role | FUNCTION
