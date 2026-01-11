"""Apply RLS policies for messages table directly using Supabase client"""
import os
from dotenv import load_dotenv
from services.persistence.adapters.supabase_adapter import SupabaseAdapter

load_dotenv()

# Initialize adapter with service role key (bypasses RLS)
adapter = SupabaseAdapter()

# SQL to apply messages policies
messages_policies_sql = """
-- Ensure RLS is enabled
ALTER TABLE messages ENABLE ROW LEVEL SECURITY;

-- Grant permissions
GRANT ALL ON messages TO authenticated, anon;

-- Drop existing policies
DROP POLICY IF EXISTS "messages_agent_select" ON messages;
DROP POLICY IF EXISTS "messages_agent_write" ON messages;

-- Create SELECT policy
CREATE POLICY "messages_agent_select" ON messages
  FOR SELECT
  TO anon
  USING (
    public.get_user_role() IN ('agent_reader', 'agent_writer')
  );

-- Create write policy
CREATE POLICY "messages_agent_write" ON messages
  FOR ALL
  TO anon
  USING (
    public.get_user_role() = 'agent_writer'
  )
  WITH CHECK (
    public.get_user_role() = 'agent_writer'
  );
"""

print("Applying messages RLS policies...")
try:
    # Execute using RPC or direct SQL
    result = adapter.client.rpc('exec_sql', {'sql': messages_policies_sql}).execute()
    print("✅ Messages policies applied successfully")
    print(f"Result: {result}")
except Exception as e:
    print(f"Note: Direct SQL execution may not be available via RPC")
    print(f"Error: {e}")
    print("\n⚠️ Please run the following SQL in Supabase dashboard:")
    print(messages_policies_sql)
