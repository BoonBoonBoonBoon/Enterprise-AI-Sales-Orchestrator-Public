-- Fix RLS Policies for Agentic System
-- This script recreates RLS policies with proper service_role bypass

-- First, drop all existing policies
DROP POLICY IF EXISTS "clients_agent_select" ON clients;
DROP POLICY IF EXISTS "clients_agent_write" ON clients;
DROP POLICY IF EXISTS "staging_leads_agent_select" ON staging_leads;
DROP POLICY IF EXISTS "staging_leads_agent_write" ON staging_leads;
DROP POLICY IF EXISTS "lead_outreach_agent_select" ON lead_outreach;
DROP POLICY IF EXISTS "lead_outreach_agent_write" ON lead_outreach;
DROP POLICY IF EXISTS "conversations_agent_select" ON conversations;
DROP POLICY IF EXISTS "conversations_agent_write" ON conversations;

-- Ensure get_user_role function exists
CREATE OR REPLACE FUNCTION public.get_user_role()
RETURNS TEXT AS $$
  SELECT COALESCE(
    (current_setting('request.jwt.claims', true)::jsonb->>'user_role')::text,
    ''
  );
$$ LANGUAGE SQL STABLE SECURITY DEFINER;

-- Create service_role bypass policies (permissive = allow everything for service_role)
CREATE POLICY "clients_service_role_all" ON clients
  FOR ALL
  TO authenticated
  USING (
    (current_setting('request.jwt.claims', true)::jsonb->>'role')::text = 'service_role'
  );

CREATE POLICY "staging_leads_service_role_all" ON staging_leads
  FOR ALL
  TO authenticated
  USING (
    (current_setting('request.jwt.claims', true)::jsonb->>'role')::text = 'service_role'
  );

CREATE POLICY "lead_outreach_service_role_all" ON lead_outreach
  FOR ALL
  TO authenticated
  USING (
    (current_setting('request.jwt.claims', true)::jsonb->>'role')::text = 'service_role'
  );

CREATE POLICY "conversations_service_role_all" ON conversations
  FOR ALL
  TO authenticated
  USING (
    (current_setting('request.jwt.claims', true)::jsonb->>'role')::text = 'service_role'
  );

-- Create anon role policies for agent access

-- Clients table
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

-- Staging Leads table
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

-- Lead Outreach table
CREATE POLICY "lead_outreach_agent_select" ON lead_outreach
  FOR SELECT
  TO anon
  USING (
    public.get_user_role() IN ('agent_reader', 'agent_writer')
  );

CREATE POLICY "lead_outreach_agent_write" ON lead_outreach
  FOR ALL
  TO anon
  USING (
    public.get_user_role() = 'agent_writer'
  )
  WITH CHECK (
    public.get_user_role() = 'agent_writer'
  );

-- Conversations table
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

-- Verify policies were created
SELECT 
  schemaname, 
  tablename, 
  policyname, 
  roles,
  cmd
FROM pg_policies
WHERE tablename IN ('clients', 'staging_leads', 'lead_outreach', 'conversations')
ORDER BY tablename, policyname;
